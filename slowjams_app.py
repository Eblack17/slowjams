#!/usr/bin/env python3
"""
SlowJams - Audio Extraction and Manipulation Tool

This script serves as the entry point for the SlowJams application,
which allows downloading and manipulating audio from online video sources.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

# Fix import paths for both script and module usage
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import application modules
try:
    # Core modules
    from utils.env_loader import load_env, setup_logging, get_bool_env
    from config.config_loader import get_config
    from core.downloader import Downloader
    from core.converter import AudioConverter
    from core.processor import AudioProcessor
    from core.queue_manager import QueueManager, Task, TaskType, TaskStatus
    
    # Data modules
    from data.settings import Settings
    from data.history import get_history
    from data.database import get_database
    
    # GUI module (optional)
    try:
        from gui.main_window import run_gui
        HAS_GUI = True
    except ImportError:
        HAS_GUI = False
        
except ImportError as e:
    print(f"Error importing SlowJams modules: {e}")
    print("Make sure you're running this script from the SlowJams directory")
    print("or that SlowJams is properly installed.")
    sys.exit(1)

logger = logging.getLogger("slowjams")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="SlowJams - Audio Extraction and Manipulation Tool",
        epilog="For more information, visit https://github.com/eblack17/slowjams"
    )
    
    # Basic options
    parser.add_argument('-v', '--version', action='store_true',
                        help='Show version information and exit')
    parser.add_argument('--headless', action='store_true',
                        help='Run in headless mode (no GUI)')
    parser.add_argument('--config', type=str, metavar='FILE',
                        help='Path to configuration file')
    parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Set logging level')
    parser.add_argument('--log-file', type=str, metavar='FILE',
                        help='Log to specified file')
    
    # Headless mode options
    parser.add_argument('--url', type=str, metavar='URL',
                        help='URL to download (for headless mode)')
    parser.add_argument('--output-dir', type=str, metavar='DIR',
                        help='Output directory (for headless mode)')
    parser.add_argument('--format', type=str, choices=['mp3', 'wav', 'ogg', 'm4a'],
                        help='Output format (for headless mode)')
    parser.add_argument('--quality', type=str, choices=['high', 'medium', 'low'],
                        help='Output quality (for headless mode)')
    
    # Advanced options
    parser.add_argument('--simulation', action='store_true',
                        help='Run in simulation mode (no actual downloads)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode')
    
    return parser.parse_args()


def show_version():
    """Display version information and exit."""
    version = "0.1.0"  # Initial version
    print(f"SlowJams version {version}")
    print("A tool for downloading and manipulating audio from online video sources.")
    print("Copyright (c) 2025 SlowJams Contributors")
    print("License: MIT")
    sys.exit(0)


def setup_environment(args):
    """
    Set up the application environment.
    
    Args:
        args: Command line arguments.
        
    Returns:
        Tuple of (config, settings) objects.
    """
    # Load environment variables
    load_env()
    
    # Set up logging
    log_level = args.log_level or os.environ.get('SLOWJAMS_LOG_LEVEL', 'INFO')
    log_file = args.log_file or os.environ.get('SLOWJAMS_LOG_FILE')
    
    setup_logging(
        level=getattr(logging, log_level),
        filepath=log_file
    )
    
    # Enable debug mode if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Load configuration
    config = get_config(
        user_config_path=args.config
    )
    
    # Enable simulation mode if requested
    if args.simulation:
        os.environ['SLOWJAMS_ADVANCED_SIMULATION_MODE'] = 'true'
        logger.info("Simulation mode enabled")
    
    # Initialize settings
    settings = Settings()
    
    # Initialize database
    db = get_database()
    
    # Initialize history
    history = get_history()
    
    # Log startup information
    logger.info(f"SlowJams starting up in {'headless' if args.headless else 'GUI'} mode")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Operating system: {os.name} - {sys.platform}")
    logger.info(f"Config directory: {config.config_dir}")
    
    return config, settings


def run_headless(args, config, settings):
    """
    Run the application in headless mode.
    
    Args:
        args: Command line arguments.
        config: Configuration object.
        settings: Settings object.
        
    Returns:
        Exit code.
    """
    logger.info("Running in headless mode")
    
    # Check if URL is provided
    if not args.url:
        logger.error("URL is required in headless mode")
        print("Error: URL is required in headless mode")
        print("Use --url to specify a URL to download")
        return 1
    
    # Set up the download task
    url = args.url
    output_dir = args.output_dir or config.get_download_directory()
    output_format = args.format or config.get_string('General', 'default_audio_format', fallback='mp3')
    
    # Quality mapping
    quality_mapping = {
        'high': 320,
        'medium': 192,
        'low': 128
    }
    quality = quality_mapping.get(
        args.quality, 
        config.get_int('Conversion', 'default_bitrate', fallback=192)
    )
    
    # Create components
    downloader = Downloader()
    converter = AudioConverter()
    processor = AudioProcessor()
    queue_manager = QueueManager()
    
    # Create a download task
    task_id = queue_manager.add_task(
        TaskType.DOWNLOAD,
        url=url,
        output_dir=str(output_dir),
        format=output_format,
        quality=quality
    )
    
    # Start processing the queue
    queue_manager.start()
    
    # Wait for the task to complete
    logger.info(f"Started download task {task_id} for URL: {url}")
    print(f"Downloading {url}...")
    
    # Check task status periodically
    import time
    while True:
        task = queue_manager.get_task(task_id)
        
        if not task:
            logger.error(f"Task {task_id} not found")
            return 1
        
        if task.status == TaskStatus.COMPLETED:
            logger.info(f"Task {task_id} completed successfully")
            print(f"Download completed: {task.result}")
            return 0
        
        elif task.status == TaskStatus.FAILED:
            logger.error(f"Task {task_id} failed: {task.error}")
            print(f"Download failed: {task.error}")
            return 1
        
        elif task.status == TaskStatus.CANCELLED:
            logger.warning(f"Task {task_id} was cancelled")
            print("Download was cancelled")
            return 1
        
        # Print progress
        if task.progress > 0:
            print(f"Progress: {task.progress:.1f}%", end='\r')
        
        # Wait before checking again
        time.sleep(0.5)


def main():
    """Main entry point."""
    # Parse command line arguments
    args = parse_args()
    
    # Show version and exit if requested
    if args.version:
        show_version()
    
    # Set up the environment
    config, settings = setup_environment(args)
    
    # Run in headless or GUI mode
    if args.headless:
        return run_headless(args, config, settings)
    else:
        # Check if GUI is available
        if not HAS_GUI:
            logger.error("GUI mode requires PyQt5, but it is not installed")
            print("Error: GUI mode requires PyQt5")
            print("Please install PyQt5 or run with --headless option")
            return 1
        
        # Run the GUI
        return run_gui()


if __name__ == "__main__":
    sys.exit(main())