#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main entry point for the YouTube and Twitter to Slowed MP3 Converter application.
"""

import sys
import os
import logging
from pathlib import Path
import argparse

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from utils.env_loader import load_env, setup_logging
from ui.main_window import MainWindow

# Set up command line arguments
def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="YouTube and Twitter to Slowed MP3 Converter"
    )
    
    parser.add_argument(
        "-d", "--debug", 
        action="store_true", 
        help="Enable debug mode"
    )
    
    parser.add_argument(
        "-s", "--simulation", 
        action="store_true", 
        help="Run in simulation mode (no actual downloads or conversions)"
    )
    
    parser.add_argument(
        "-l", "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level"
    )
    
    parser.add_argument(
        "--log-file", 
        type=str,
        default=None,
        help="Path to log file (default: slowed_mp3_converter.log)"
    )
    
    parser.add_argument(
        "--theme", 
        choices=["light", "dark", "system"],
        default=None,
        help="Set the application theme (overrides preferences)"
    )
    
    return parser.parse_args()

def main():
    """Main application entry point."""
    # Parse command line arguments
    args = parse_args()
    
    # Load environment variables
    load_env()
    
    # Set up logging
    log_level = getattr(logging, args.log_level)
    setup_logging(level=log_level, filepath=args.log_file)
    
    # Create logger for this module
    logger = logging.getLogger(__name__)
    
    # Log application start
    logger.info("Starting YouTube and Twitter to Slowed MP3 Converter application")
    
    # Enable high DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Slowed MP3 Converter")
    app.setApplicationVersion("1.0.0")
    
    # Create main window
    window = MainWindow()
    
    # Apply theme from command line if specified
    if args.theme:
        from ui.themes import theme_manager, ThemeType
        if args.theme == "light":
            theme_manager.set_theme(ThemeType.LIGHT)
        elif args.theme == "dark":
            theme_manager.set_theme(ThemeType.DARK)
        else:  # system
            theme_manager.set_theme(ThemeType.SYSTEM)
        
        logger.info(f"Applied {args.theme} theme from command line")
    
    # Show the window
    window.show()
    
    # Run the application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()