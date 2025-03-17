#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Environment loader utility for the SlowJams application.

This module provides functions for loading environment variables and setting up logging.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union, Dict

from dotenv import load_dotenv

def load_env(env_file: Optional[str] = None) -> Dict[str, str]:
    """
    Load environment variables from .env file.
    
    Args:
        env_file: Optional path to .env file. If not provided, will look for .env in current directory.
    
    Returns:
        Dictionary of environment variables loaded from the .env file.
    """
    if env_file and os.path.exists(env_file):
        # Load from specified file
        load_dotenv(env_file)
    else:
        # Try to load from default locations
        default_locations = ['.env', os.path.join(os.path.dirname(__file__), '..', '.env')]
        for location in default_locations:
            if os.path.exists(location):
                load_dotenv(location)
                break
    
    # Log the environment loaded
    env_type = os.getenv('ENVIRONMENT', 'development')
    logging.info(f"Loaded environment from .env file: {env_type}")
    
    # Return a dictionary of the loaded environment variables
    return {key: value for key, value in os.environ.items()}

def setup_logging(level: int = logging.INFO, 
                  filepath: Optional[str] = None) -> logging.Logger:
    """
    Set up logging for the application.
    
    Args:
        level: Logging level (default: INFO)
        filepath: Optional path to log file. If not provided, will log to console and default log file.
    
    Returns:
        Logger object
    """
    # Get default log directory from environment or use ./logs
    log_dir = os.getenv('LOG_DIR', './logs')
    
    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Default log file
    default_log_file = os.path.join(log_dir, 'slowed_mp3_converter.log')
    
    # Use specified filepath or default
    log_file = filepath or default_log_file
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    # Create and return logger for this module
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Level: {logging.getLevelName(level)}, File: {log_file}")
    
    return logger

def get_int_env(key: str, default: int) -> int:
    """
    Get integer environment variable value.
    
    Args:
        key: Environment variable key
        default: Default value if key is not found or not an integer
    
    Returns:
        Integer value
    """
    value = os.getenv(key)
    if value is None:
        return default
    
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def get_bool_env(key: str, default: bool) -> bool:
    """
    Get boolean environment variable value.
    
    Args:
        key: Environment variable key
        default: Default value if key is not found
    
    Returns:
        Boolean value
    """
    value = os.getenv(key)
    if value is None:
        return default
    
    # Check for common boolean string representations
    return value.lower() in ('true', 'yes', '1', 'y', 't')

def use_simulation_mode() -> bool:
    """
    Check if simulation mode is enabled.
    
    Returns:
        True if simulation mode is enabled, False otherwise
    """
    return get_bool_env('SIMULATION_MODE', False)