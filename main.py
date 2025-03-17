#!/usr/bin/env python3
"""
SlowJams - YouTube and Twitter to Slowed MP3 Converter

This application allows users to download videos from YouTube and Twitter,
convert them to audio, and apply "slowed + reverb" effects for a unique sound.

Features:
- Download videos from YouTube and Twitter
- Extract audio and convert to MP3
- Apply various audio effects (slow, reverb, etc.)
- Batch processing
- Customizable settings
- Light/dark theme support
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Any, Union

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import application components
try:
    from utils.env_loader import load_env, setup_logging, get_bool_env
    from core.downloader import DownloaderFactory, is_supported_url
    from core.converter import AudioConverter, AudioFormat, ConversionOptions
    from core.processor import AudioProcessor, ProcessingOptions
    from core.queue_manager import QueueManager, QueueTask, TaskType
    
    # Import UI components - these will be implemented later
    # from ui.main_window import MainWindow
    
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please make sure all dependencies are installed.")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="SlowJams - YouTube and Twitter to Slowed MP3 Converter"
    )
    
    # Basic arguments
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Enable verbose output"
    )
    parser.add_argument(
        "--headless", 
        action="store_true", 
        help="Run in headless mode (no GUI)"
    )
    parser.add_argument(
        "--env", 
        type=str, 
        help="Path to .env file"
    )
    
    # Headless mode arguments
    parser.add_argument(
        "--url", 
        type=str, 
        help="URL to download (for headless mode)"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        help="Output file or directory (for headless mode)"
    )
    parser.add_argument(
        "--effect", 
        type=str, 
        choices=["slow", "chopped", "vaporwave", "none"],
        default="slow",
        help="Effect preset to apply (for headless mode)"
    )
    parser.add_argument(
        "--speed", 
        type=float, 
        help="Speed factor (0.5 to 1.5, for headless mode)"
    )
    parser.add_argument(
        "--format", 
        type=str, 
        choices=["mp3", "wav", "flac", "aac", "ogg"],
        default="mp3",
        help="Output audio format (for headless mode)"
    )
    
    return parser.parse_args()


def setup_environment(args):
    """
    Set up the application environment.
    
    Args:
        args: Command line arguments
        
    Returns:
        Tuple of (log_level, config_dict)
    """
    # Determine log level
    log_level = logging.DEBUG if args.verbose else logging.INFO
    
    # Load environment variables
    env_file = args.env if args.env else None
    config = load_env(env_file)
    
    # Set up logging
    logger = setup_logging(level=log_level)
    
    # Log startup information
    logger.info("Starting SlowJams")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Operating system: {sys.platform}")
    logger.info(f"Log level: {logging.getLevelName(log_level)}")
    
    if env_file:
        logger.info(f"Loaded environment from: {env_file}")
    
    simulation_mode = get_bool_env("SIMULATION_MODE", False)
    if simulation_mode:
        logger.warning("SIMULATION MODE ENABLED - No actual downloads or processing will occur")
    
    return log_level, config


def run_headless(args, config):
    """
    Run the application in headless mode.
    
    Args:
        args: Command line arguments
        config: Configuration dictionary
    """
    logger = logging.getLogger(__name__)
    
    if not args.url:
        logger.error("URL is required in headless mode")
        sys.exit(1)
    
    url = args.url.strip()
    
    if not is_supported_url(url):
        logger.error(f"Unsupported URL: {url}")
        sys.exit(1)
    
    # Configure output
    output_path = args.output
    if not output_path:
        # Use default download directory from config or current directory
        download_dir = config.get("DOWNLOAD_DIR", os.getcwd())
        output_path = os.path.join(download_dir, "output.mp3")
    
    # Configure processing options
    if args.effect == "slow":
        options = ProcessingOptions.slow_jam_preset()
    elif args.effect == "chopped":
        options = ProcessingOptions.chopped_and_screwed_preset()
    elif args.effect == "vaporwave":
        options = ProcessingOptions.vaporwave_preset()
    else:  # "none"
        options = ProcessingOptions()
        options.slow_factor = 1.0
        options.reverb_enabled = False
    
    # Override speed if specified
    if args.speed is not None:
        options.slow_factor = max(0.5, min(1.5, args.speed))
    
    # Set output format
    options.output_format = AudioFormat.from_string(args.format)
    
    # Progress callback for console output
    def progress_callback(task_id, progress):
        percent = progress.percent
        step = progress.current_step
        print(f"\r{step}: {percent:.1f}%", end="")
        if percent >= 100:
            print()  # New line at 100%
    
    # Create queue manager
    manager = QueueManager(num_workers=1)
    manager.set_progress_callback(progress_callback)
    manager.start()
    
    # Add task
    logger.info(f"Processing URL: {url}")
    logger.info(f"Output path: {output_path}")
    logger.info(f"Effect: {args.effect}")
    logger.info(f"Speed factor: {options.slow_factor}")
    logger.info(f"Output format: {options.output_format.name}")
    
    task_id = manager.add_download_task(
        url=url,
        output_file=output_path,
        process_after_download=True,
        processing_options=options
    )
    
    # Wait for task to complete
    try:
        import time
        
        print("Processing... Press Ctrl+C to cancel")
        
        while True:
            task = manager.get_task(task_id)
            if not task:
                logger.error("Task not found in queue")
                break
                
            if task.progress.status.name in ["COMPLETED", "FAILED", "CANCELLED"]:
                break
                
            time.sleep(0.5)
        
        # Show result
        task = manager.get_task(task_id)
        if task.progress.status.name == "COMPLETED":
            logger.info(f"Task completed successfully!")
            logger.info(f"Output file: {task.output_file}")
        elif task.progress.status.name == "FAILED":
            logger.error(f"Task failed: {task.progress.error_message}")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\nCancelling task...")
        manager.cancel_task(task_id)
    finally:
        manager.stop()


def run_gui(args, config, log_level):
    """
    Run the application with the graphical user interface.
    
    Args:
        args: Command line arguments
        config: Configuration dictionary
        log_level: Logging level
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting GUI")
    
    try:
        # This will be implemented when the UI package is created
        from ui.main_window import MainWindow
        from PyQt5.QtWidgets import QApplication
        
        app = QApplication(sys.argv)
        window = MainWindow(config, log_level)
        window.show()
        
        # Start with a URL if provided
        if args.url:
            window.set_url(args.url)
        
        sys.exit(app.exec_())
        
    except ImportError:
        logger.error("GUI components not available")
        logger.error("Please install PyQt5 or run in headless mode with --headless")
        sys.exit(1)


def main():
    """Main entry point for the application."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Set up environment
    log_level, config = setup_environment(args)
    
    # Run in appropriate mode
    if args.headless:
        run_headless(args, config)
    else:
        run_gui(args, config, log_level)


if __name__ == "__main__":
    main()