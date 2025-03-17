"""
Settings management module for SlowJams application.

This module provides a high-level interface for managing application settings,
built on top of the database module.
"""

import os
import json
import logging
from typing import Optional, Dict, List, Any, Union, Callable
from pathlib import Path

# Import database module
try:
    from data.database import get_database
except ImportError:
    # For standalone usage or testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from data.database import get_database

logger = logging.getLogger(__name__)


# Define settings categories
class SettingsCategory:
    """Settings category constants."""
    GENERAL = "general"
    DOWNLOAD = "download"
    CONVERSION = "conversion"
    PROCESSING = "processing"
    UI = "ui"
    ADVANCED = "advanced"


# Define default settings
DEFAULT_SETTINGS = {
    SettingsCategory.GENERAL: {
        "first_run": True,
        "download_dir": str(Path.home() / "Downloads" / "SlowJams"),
        "temp_dir": "",  # Empty means use system temp dir
        "check_updates": True,
        "auto_cleanup_temp": True,
        "language": "en"
    },
    SettingsCategory.DOWNLOAD: {
        "max_download_threads": 2,
        "default_format": "best",  # "best", "audio", specific format ID
        "save_thumbnails": True,
        "save_metadata": True,
        "skip_existing": True,
        "max_retries": 3,
        "timeout": 30  # seconds
    },
    SettingsCategory.CONVERSION: {
        "default_format": "mp3",  # mp3, wav, flac, aac, ogg
        "default_bitrate": "320k",  # For lossy formats
        "default_sample_rate": 44100,
        "default_channels": 2,
        "normalize_audio": True,
        "keep_original": False
    },
    SettingsCategory.PROCESSING: {
        "default_effect": "slow_jam",  # slow_jam, chopped, vaporwave, none
        "default_speed": 0.8,
        "preserve_pitch": True,
        "reverb_enabled": True,
        "reverb_room_size": 0.6,
        "reverb_wet_level": 0.4,
        "reverb_dry_level": 0.6,
        "max_processing_threads": 1
    },
    SettingsCategory.UI: {
        "theme": "system",  # light, dark, system
        "show_tooltips": True,
        "remember_window_size": True,
        "window_width": 1000,
        "window_height": 700,
        "show_notifications": True,
        "notification_duration": 5,  # seconds
        "show_progress_in_taskbar": True,
        "show_tray_icon": True,
        "minimize_to_tray": False
    },
    SettingsCategory.ADVANCED: {
        "ffmpeg_path": "",  # Empty means use system PATH
        "ffprobe_path": "",  # Empty means use system PATH
        "yt_dlp_path": "",  # Empty means use system PATH
        "verbose_logging": False,
        "log_dir": "",  # Empty means default log location
        "debug_mode": False,
        "simulation_mode": False
    }
}


class Settings:
    """
    Settings manager for SlowJams application.
    
    This class provides a high-level interface for accessing and modifying
    application settings, with change notifications and data validation.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the settings manager.
        
        Args:
            db_path: Optional path to the SQLite database file.
        """
        self.db = get_database(db_path)
        self.callbacks: Dict[str, List[Callable[[str, Any], None]]] = {}
        
        # Initialize default settings if this is the first run
        self._initialize_defaults()
    
    def _initialize_defaults(self):
        """Initialize default settings for first run."""
        first_run = self.get("first_run", True, SettingsCategory.GENERAL)
        
        if first_run:
            logger.info("First run detected, initializing default settings")
            
            # Initialize each category
            for category, defaults in DEFAULT_SETTINGS.items():
                # Check if category exists
                existing = self.db.get_settings_by_category(category)
                
                if not existing:
                    # Category doesn't exist, add all defaults
                    for key, value in defaults.items():
                        self.db.set_setting(key, value, category)
                    
                    logger.info(f"Initialized default settings for category '{category}'")
                else:
                    # Category exists, only add missing settings
                    for key, value in defaults.items():
                        if key not in existing:
                            self.db.set_setting(key, value, category)
            
            # Mark first run as complete
            self.db.set_setting("first_run", False, SettingsCategory.GENERAL)
    
    def get(self, key: str, default: Any = None, category: str = SettingsCategory.GENERAL) -> Any:
        """
        Get a setting value.
        
        Args:
            key: Setting key.
            default: Default value if setting not found.
            category: Setting category.
            
        Returns:
            The setting value, or the default if not found.
        """
        value = self.db.get_setting(key, None, category)
        
        if value is None:
            # Value not found, check default settings
            category_defaults = DEFAULT_SETTINGS.get(category, {})
            default_value = category_defaults.get(key, default)
            
            # Store default value for future use
            if default_value is not None:
                self.db.set_setting(key, default_value, category)
            
            return default_value
        
        return value
    
    def set(self, key: str, value: Any, category: str = SettingsCategory.GENERAL) -> bool:
        """
        Set a setting value.
        
        Args:
            key: Setting key.
            value: Setting value.
            category: Setting category.
            
        Returns:
            True if successful, False otherwise.
        """
        # Store the old value for change detection
        old_value = self.get(key, None, category)
        
        # Set the new value
        result = self.db.set_setting(key, value, category)
        
        # Notify callbacks if the value changed
        if result and value != old_value:
            self._notify_callbacks(key, value, category)
        
        return result
    
    def delete(self, key: str, category: str = SettingsCategory.GENERAL) -> bool:
        """
        Delete a setting.
        
        Args:
            key: Setting key.
            category: Setting category.
            
        Returns:
            True if successful, False otherwise.
        """
        return self.db.delete_setting(key, category)
    
    def get_category(self, category: str) -> Dict[str, Any]:
        """
        Get all settings in a category.
        
        Args:
            category: Category to get settings for.
            
        Returns:
            Dictionary of key-value pairs.
        """
        settings = self.db.get_settings_by_category(category)
        
        # Add default values for missing settings
        category_defaults = DEFAULT_SETTINGS.get(category, {})
        
        for key, default_value in category_defaults.items():
            if key not in settings:
                settings[key] = default_value
                
                # Store default value for future use
                self.db.set_setting(key, default_value, category)
        
        return settings
    
    def reset_category(self, category: str) -> bool:
        """
        Reset a category to default values.
        
        Args:
            category: Category to reset.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Get default values for category
            category_defaults = DEFAULT_SETTINGS.get(category, {})
            
            if not category_defaults:
                logger.warning(f"No default settings found for category '{category}'")
                return False
            
            # Delete existing settings in the category
            current_settings = self.db.get_settings_by_category(category)
            
            for key in current_settings:
                self.db.delete_setting(key, category)
            
            # Add default values
            for key, value in category_defaults.items():
                self.db.set_setting(key, value, category)
                self._notify_callbacks(key, value, category)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset category '{category}': {str(e)}")
            return False
    
    def reset_all(self) -> bool:
        """
        Reset all settings to default values.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            for category in DEFAULT_SETTINGS:
                self.reset_category(category)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset all settings: {str(e)}")
            return False
    
    def register_callback(self, key: str, callback: Callable[[str, Any], None], 
                        category: str = SettingsCategory.GENERAL):
        """
        Register a callback for setting changes.
        
        Args:
            key: Setting key to watch. Use "*" for all keys in category.
            callback: Function to call when the setting changes.
            category: Setting category.
        """
        callback_key = f"{category}:{key}"
        
        if callback_key not in self.callbacks:
            self.callbacks[callback_key] = []
        
        self.callbacks[callback_key].append(callback)
    
    def unregister_callback(self, key: str, callback: Callable[[str, Any], None],
                          category: str = SettingsCategory.GENERAL) -> bool:
        """
        Unregister a callback for setting changes.
        
        Args:
            key: Setting key.
            callback: Function to remove.
            category: Setting category.
            
        Returns:
            True if callback was removed, False if not found.
        """
        callback_key = f"{category}:{key}"
        
        if callback_key in self.callbacks and callback in self.callbacks[callback_key]:
            self.callbacks[callback_key].remove(callback)
            return True
        
        return False
    
    def _notify_callbacks(self, key: str, value: Any, category: str):
        """
        Notify registered callbacks about a setting change.
        
        Args:
            key: Changed setting key.
            value: New setting value.
            category: Setting category.
        """
        # Notify specific key callbacks
        specific_key = f"{category}:{key}"
        if specific_key in self.callbacks:
            for callback in self.callbacks[specific_key]:
                try:
                    callback(key, value)
                except Exception as e:
                    logger.error(f"Error in settings callback: {str(e)}")
        
        # Notify wildcard callbacks for category
        wildcard_key = f"{category}:*"
        if wildcard_key in self.callbacks:
            for callback in self.callbacks[wildcard_key]:
                try:
                    callback(key, value)
                except Exception as e:
                    logger.error(f"Error in settings callback: {str(e)}")


# Singleton instance for application-wide use
_settings_instance = None

def get_settings(db_path: Optional[str] = None) -> Settings:
    """
    Get the settings manager instance.
    
    Args:
        db_path: Optional database path. Only used when creating the instance.
        
    Returns:
        The settings manager instance.
    """
    global _settings_instance
    
    if _settings_instance is None:
        _settings_instance = Settings(db_path)
    
    return _settings_instance


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Initialize settings
    settings = get_settings()
    
    # Get some settings
    download_dir = settings.get("download_dir", category=SettingsCategory.GENERAL)
    theme = settings.get("theme", category=SettingsCategory.UI)
    
    print(f"Download directory: {download_dir}")
    print(f"Theme: {theme}")
    
    # Update a setting
    settings.set("theme", "dark", SettingsCategory.UI)
    
    # Get all settings in a category
    ui_settings = settings.get_category(SettingsCategory.UI)
    print("\nUI Settings:")
    for key, value in ui_settings.items():
        print(f" - {key}: {value}")
    
    # Callback example
    def theme_changed(key, value):
        print(f"\nTheme changed to: {value}")
    
    settings.register_callback("theme", theme_changed, SettingsCategory.UI)
    
    # Change the theme again to trigger the callback
    settings.set("theme", "light", SettingsCategory.UI)