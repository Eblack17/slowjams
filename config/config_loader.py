"""
Configuration loader module for SlowJams application.

This module handles loading configuration from the default INI file
and any user-specific configuration overrides.
"""

import os
import sys
import logging
import configparser
from typing import Dict, Any, Optional, Union, List, Tuple
from pathlib import Path

# Import utility functions
try:
    from utils.env_loader import get_int_env, get_bool_env, setup_logging
except ImportError:
    # For standalone usage or testing
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.append(parent_dir)
    from utils.env_loader import get_int_env, get_bool_env, setup_logging

logger = logging.getLogger(__name__)

# Default configuration file path
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'default_config.ini')


class ConfigLoader:
    """
    Configuration loader class for SlowJams application.
    
    This class handles loading configuration from the default INI file
    and any user-specific configuration overrides.
    """
    
    def __init__(self, config_dir: Optional[str] = None, user_config_path: Optional[str] = None):
        """
        Initialize the configuration loader.
        
        Args:
            config_dir: Optional directory for configuration files.
            user_config_path: Optional path to user configuration file.
        """
        self.config = configparser.ConfigParser(interpolation=configparser.BasicInterpolation())
        
        # Set configuration directory
        if config_dir is None:
            if os.environ.get('SLOWJAMS_CONFIG_DIR'):
                self.config_dir = os.environ.get('SLOWJAMS_CONFIG_DIR')
            elif os.environ.get('APPDATA'):  # Windows
                self.config_dir = os.path.join(os.environ.get('APPDATA'), 'SlowJams')
            elif os.environ.get('XDG_CONFIG_HOME'):  # Linux
                self.config_dir = os.path.join(os.environ.get('XDG_CONFIG_HOME'), 'slowjams')
            elif os.path.exists(os.path.expanduser('~/.config')):  # Linux/Mac
                self.config_dir = os.path.expanduser('~/.config/slowjams')
            else:  # Fallback
                self.config_dir = os.path.expanduser('~/.slowjams')
        else:
            self.config_dir = config_dir
        
        # Make sure the config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Set user configuration path
        if user_config_path is None:
            self.user_config_path = os.path.join(self.config_dir, 'config.ini')
        else:
            self.user_config_path = user_config_path
        
        # Load configuration
        self.load_config()
    
    def load_config(self) -> bool:
        """
        Load configuration from default and user config files.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            # First, load the default configuration
            if not os.path.exists(DEFAULT_CONFIG_PATH):
                logger.error(f"Default configuration file not found at {DEFAULT_CONFIG_PATH}")
                return False
            
            self.config.read(DEFAULT_CONFIG_PATH)
            logger.info(f"Loaded default configuration from {DEFAULT_CONFIG_PATH}")
            
            # Then, load user configuration if it exists
            if os.path.exists(self.user_config_path):
                self.config.read(self.user_config_path)
                logger.info(f"Loaded user configuration from {self.user_config_path}")
            else:
                logger.info(f"No user configuration found at {self.user_config_path}")
            
            # Apply any environment variable overrides
            self._apply_environment_overrides()
            
            return True
        
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return False
    
    def _apply_environment_overrides(self):
        """Apply environment variable overrides to configuration."""
        # Loop through all sections and options
        for section in self.config.sections():
            for option in self.config.options(section):
                # Create the environment variable name
                env_var_name = f"SLOWJAMS_{section.upper()}_{option.upper()}"
                
                # Check if the environment variable exists
                if env_var_name in os.environ:
                    # Apply the override
                    self.config.set(section, option, os.environ[env_var_name])
                    logger.debug(f"Applied environment override: {env_var_name}")
    
    def get_string(self, section: str, option: str, fallback: Optional[str] = None) -> Optional[str]:
        """
        Get a string value from the configuration.
        
        Args:
            section: Section name.
            option: Option name.
            fallback: Optional fallback value.
            
        Returns:
            The string value, or fallback if not found.
        """
        try:
            return self.config.get(section, option, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback
    
    def get_int(self, section: str, option: str, fallback: Optional[int] = None) -> Optional[int]:
        """
        Get an integer value from the configuration.
        
        Args:
            section: Section name.
            option: Option name.
            fallback: Optional fallback value.
            
        Returns:
            The integer value, or fallback if not found or not an integer.
        """
        try:
            return self.config.getint(section, option, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_float(self, section: str, option: str, fallback: Optional[float] = None) -> Optional[float]:
        """
        Get a float value from the configuration.
        
        Args:
            section: Section name.
            option: Option name.
            fallback: Optional fallback value.
            
        Returns:
            The float value, or fallback if not found or not a float.
        """
        try:
            return self.config.getfloat(section, option, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_bool(self, section: str, option: str, fallback: Optional[bool] = None) -> Optional[bool]:
        """
        Get a boolean value from the configuration.
        
        Args:
            section: Section name.
            option: Option name.
            fallback: Optional fallback value.
            
        Returns:
            The boolean value, or fallback if not found or not a boolean.
        """
        try:
            return self.config.getboolean(section, option, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def get_list(self, section: str, option: str, delimiter: str = ',', fallback: Optional[List[str]] = None) -> List[str]:
        """
        Get a list value from the configuration.
        
        Args:
            section: Section name.
            option: Option name.
            delimiter: Delimiter for splitting the string.
            fallback: Optional fallback value.
            
        Returns:
            The list value, or fallback if not found.
        """
        try:
            value = self.config.get(section, option)
            if not value:
                return fallback if fallback is not None else []
            
            return [item.strip() for item in value.split(delimiter)]
        
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback if fallback is not None else []
    
    def get_path(self, section: str, option: str, fallback: Optional[str] = None) -> Optional[Path]:
        """
        Get a file path from the configuration.
        
        Args:
            section: Section name.
            option: Option name.
            fallback: Optional fallback value.
            
        Returns:
            The path value as a Path object, or fallback if not found.
        """
        try:
            value = self.config.get(section, option, fallback=fallback)
            if not value:
                return Path(fallback) if fallback is not None else None
            
            # Expand user directory (~/...)
            return Path(os.path.expanduser(value))
        
        except (configparser.NoSectionError, configparser.NoOptionError):
            return Path(fallback) if fallback is not None else None
    
    def get_all_options(self, section: str) -> Dict[str, str]:
        """
        Get all options from a section.
        
        Args:
            section: Section name.
            
        Returns:
            A dictionary of all options in the section.
        """
        try:
            return dict(self.config.items(section))
        except configparser.NoSectionError:
            return {}
    
    def get_all_sections(self) -> List[str]:
        """
        Get all section names.
        
        Returns:
            A list of all section names.
        """
        return self.config.sections()
    
    def save_user_config(self) -> bool:
        """
        Save the current configuration to the user config file.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            os.makedirs(os.path.dirname(self.user_config_path), exist_ok=True)
            
            with open(self.user_config_path, 'w') as f:
                self.config.write(f)
            
            logger.info(f"Saved user configuration to {self.user_config_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving user configuration: {str(e)}")
            return False
    
    def set_value(self, section: str, option: str, value: Any) -> bool:
        """
        Set a configuration value.
        
        Args:
            section: Section name.
            option: Option name.
            value: Value to set.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Ensure the section exists
            if not self.config.has_section(section):
                self.config.add_section(section)
            
            # Convert the value to string
            if value is None:
                str_value = ''
            elif isinstance(value, bool):
                str_value = 'true' if value else 'false'
            elif isinstance(value, (list, tuple)):
                str_value = ', '.join(str(item) for item in value)
            else:
                str_value = str(value)
            
            # Set the value
            self.config.set(section, option, str_value)
            return True
        
        except Exception as e:
            logger.error(f"Error setting configuration value: {str(e)}")
            return False
    
    def get_user_config_path(self) -> str:
        """
        Get the path to the user configuration file.
        
        Returns:
            The path to the user configuration file.
        """
        return self.user_config_path
    
    def reset_to_defaults(self, section: Optional[str] = None) -> bool:
        """
        Reset configuration to defaults.
        
        Args:
            section: Optional section to reset. If None, all sections are reset.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Create a new config parser for default values
            default_config = configparser.ConfigParser()
            default_config.read(DEFAULT_CONFIG_PATH)
            
            if section is not None:
                # Reset a specific section
                if default_config.has_section(section):
                    # Remove the section from the current config
                    if self.config.has_section(section):
                        self.config.remove_section(section)
                    
                    # Add the section from the default config
                    self.config.add_section(section)
                    for option, value in default_config.items(section):
                        self.config.set(section, option, value)
                else:
                    logger.warning(f"Section '{section}' not found in default configuration")
                    return False
            else:
                # Reset all sections
                for default_section in default_config.sections():
                    # Remove the section from the current config
                    if self.config.has_section(default_section):
                        self.config.remove_section(default_section)
                    
                    # Add the section from the default config
                    self.config.add_section(default_section)
                    for option, value in default_config.items(default_section):
                        self.config.set(default_section, option, value)
            
            return True
        
        except Exception as e:
            logger.error(f"Error resetting configuration: {str(e)}")
            return False
    
    def get_download_directory(self) -> Path:
        """
        Get the download directory.
        
        Returns:
            The download directory as a Path object.
        """
        download_dir = self.get_string('General', 'download_directory')
        
        if not download_dir:
            # Use the system's default Downloads directory
            if os.name == 'nt':  # Windows
                download_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            else:  # Linux/Mac
                download_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        
        # Ensure the directory exists
        os.makedirs(download_dir, exist_ok=True)
        
        return Path(download_dir)
    
    def get_temp_directory(self) -> Path:
        """
        Get the temporary directory.
        
        Returns:
            The temporary directory as a Path object.
        """
        temp_dir = self.get_string('General', 'temp_directory')
        
        if not temp_dir:
            # Use the system's default temp directory
            import tempfile
            temp_dir = os.path.join(tempfile.gettempdir(), 'slowjams')
        
        # Ensure the directory exists
        os.makedirs(temp_dir, exist_ok=True)
        
        return Path(temp_dir)
    
    def is_simulation_mode(self) -> bool:
        """
        Check if simulation mode is enabled.
        
        Returns:
            True if simulation mode is enabled, False otherwise.
        """
        return self.get_bool('Advanced', 'simulation_mode', fallback=False)


# Singleton instance
_config_instance = None


def get_config(config_dir: Optional[str] = None, user_config_path: Optional[str] = None) -> ConfigLoader:
    """
    Get the configuration loader instance.
    
    Args:
        config_dir: Optional directory for configuration files.
        user_config_path: Optional path to user configuration file.
        
    Returns:
        The configuration loader instance.
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = ConfigLoader(config_dir, user_config_path)
    
    return _config_instance


if __name__ == "__main__":
    # Example usage
    setup_logging()
    
    # Initialize configuration
    config = get_config()
    
    # Print some configuration values
    print("\nGeneral configuration:")
    print(f"Download directory: {config.get_download_directory()}")
    print(f"Max simultaneous downloads: {config.get_int('General', 'max_simultaneous_downloads')}")
    print(f"Show notifications: {config.get_bool('General', 'show_notifications')}")
    
    print("\nDownload configuration:")
    print(f"Max retries: {config.get_int('Download', 'max_retries')}")
    print(f"Request timeout: {config.get_int('Download', 'request_timeout')}")
    print(f"Use proxy: {config.get_bool('Download', 'use_proxy')}")
    
    print("\nConversion configuration:")
    print(f"Default bitrate: {config.get_int('Conversion', 'default_bitrate')}")
    print(f"Default sample rate: {config.get_int('Conversion', 'default_sample_rate')}")
    print(f"Default channels: {config.get_int('Conversion', 'default_channels')}")
    
    print("\nUI configuration:")
    print(f"Theme: {config.get_string('UI', 'theme')}")
    print(f"Show advanced options: {config.get_bool('UI', 'show_advanced_options')}")
    
    # Demonstrate setting and saving a value
    config.set_value('General', 'max_simultaneous_downloads', 5)
    print("\nAfter modification:")
    print(f"Max simultaneous downloads: {config.get_int('General', 'max_simultaneous_downloads')}")
    
    # Save the configuration
    config.save_user_config()