"""
Database module for SlowJams application.

This module handles the SQLite database connection and schema management for storing
download history, queue items, and application settings.
"""

import os
import json
import sqlite3
import logging
import threading
from typing import Optional, Dict, List, Any, Union, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """
    SQLite database manager for SlowJams application.
    
    This class handles the database connection, schema creation and upgrades,
    and provides methods for common database operations.
    """
    
    # Schema version - increment when making changes to the schema
    SCHEMA_VERSION = 1
    
    # SQL for creating database tables
    CREATE_TABLES_SQL = [
        # Settings table
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            category TEXT,
            updated_at TIMESTAMP
        )
        """,
        
        # History table
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            platform TEXT,
            download_date TIMESTAMP,
            file_path TEXT,
            file_size INTEGER,
            duration REAL,
            status TEXT,
            metadata TEXT
        )
        """,
        
        # Queue table
        """
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE NOT NULL,
            task_type TEXT NOT NULL,
            url TEXT,
            input_file TEXT,
            output_file TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            status TEXT,
            progress REAL,
            error_message TEXT,
            parameters TEXT
        )
        """,
        
        # Schema version table
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP
        )
        """
    ]
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses a default path.
        """
        # Determine database path
        if db_path is None:
            # Default path in user's home directory
            home_dir = str(Path.home())
            app_dir = os.path.join(home_dir, ".slowjams")
            os.makedirs(app_dir, exist_ok=True)
            db_path = os.path.join(app_dir, "slowjams.db")
        
        self.db_path = db_path
        self.connection = None
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        
        # Connect to database and initialize schema
        self._connect()
        self._initialize_schema()
    
    def _connect(self):
        """Connect to the SQLite database."""
        try:
            self.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,  # We'll handle thread safety with locks
                isolation_level=None      # Enable autocommit mode
            )
            
            # Enable foreign keys
            self.connection.execute("PRAGMA foreign_keys = ON")
            
            # Configure connection
            self.connection.row_factory = sqlite3.Row
            
            logger.info(f"Connected to database at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise
    
    def _initialize_schema(self):
        """Initialize the database schema."""
        with self.lock:
            try:
                # Create tables
                for table_sql in self.CREATE_TABLES_SQL:
                    self.connection.execute(table_sql)
                
                # Check schema version
                cursor = self.connection.execute(
                    "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
                )
                row = cursor.fetchone()
                
                current_version = row[0] if row else 0
                
                if current_version < self.SCHEMA_VERSION:
                    # Schema upgrade needed
                    self._upgrade_schema(current_version)
                    
                    # Update schema version
                    self.connection.execute(
                        "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                        (self.SCHEMA_VERSION, datetime.now().isoformat())
                    )
                    
                    logger.info(f"Database schema upgraded to version {self.SCHEMA_VERSION}")
                
            except Exception as e:
                logger.error(f"Failed to initialize database schema: {str(e)}")
                raise
    
    def _upgrade_schema(self, current_version: int):
        """
        Upgrade the database schema to the latest version.
        
        Args:
            current_version: Current schema version.
        """
        logger.info(f"Upgrading database schema from version {current_version} to {self.SCHEMA_VERSION}")
        
        # Apply migrations based on current version
        # Each case should handle the migration from its version to the next
        
        if current_version < 1:
            logger.info("Applying schema migration to version 1")
            # Initial schema - nothing to upgrade, already created by CREATE_TABLES_SQL
    
    def close(self):
        """Close the database connection."""
        with self.lock:
            if self.connection:
                self.connection.close()
                logger.info("Database connection closed")
    
    def execute(self, sql: str, parameters: Optional[Tuple] = None) -> sqlite3.Cursor:
        """
        Execute a SQL statement with parameters.
        
        Args:
            sql: SQL statement to execute.
            parameters: Optional parameters for the SQL statement.
            
        Returns:
            The cursor object.
        """
        with self.lock:
            if parameters:
                return self.connection.execute(sql, parameters)
            else:
                return self.connection.execute(sql)
    
    def execute_many(self, sql: str, parameters_list: List[Tuple]) -> sqlite3.Cursor:
        """
        Execute a SQL statement with multiple sets of parameters.
        
        Args:
            sql: SQL statement to execute.
            parameters_list: List of parameter tuples.
            
        Returns:
            The cursor object.
        """
        with self.lock:
            return self.connection.executemany(sql, parameters_list)
    
    def begin_transaction(self):
        """Begin a transaction."""
        with self.lock:
            self.connection.execute("BEGIN TRANSACTION")
    
    def commit(self):
        """Commit the current transaction."""
        with self.lock:
            self.connection.execute("COMMIT")
    
    def rollback(self):
        """Roll back the current transaction."""
        with self.lock:
            self.connection.execute("ROLLBACK")
    
    def get_setting(self, key: str, default: Any = None, category: Optional[str] = None) -> Any:
        """
        Get a setting value from the database.
        
        Args:
            key: Setting key.
            default: Default value if setting not found.
            category: Optional category for grouping settings.
            
        Returns:
            The setting value, or the default if not found.
        """
        with self.lock:
            try:
                if category:
                    cursor = self.execute(
                        "SELECT value FROM settings WHERE key = ? AND category = ?",
                        (key, category)
                    )
                else:
                    cursor = self.execute(
                        "SELECT value FROM settings WHERE key = ?",
                        (key,)
                    )
                
                row = cursor.fetchone()
                
                if row:
                    # Try to parse as JSON first
                    try:
                        return json.loads(row[0])
                    except (json.JSONDecodeError, TypeError):
                        # Return as string if not JSON
                        return row[0]
                
                return default
                
            except Exception as e:
                logger.error(f"Failed to get setting {key}: {str(e)}")
                return default
    
    def set_setting(self, key: str, value: Any, category: Optional[str] = None) -> bool:
        """
        Set a setting value in the database.
        
        Args:
            key: Setting key.
            value: Setting value (will be converted to JSON if not a string).
            category: Optional category for grouping settings.
            
        Returns:
            True if successful, False otherwise.
        """
        with self.lock:
            try:
                # Convert value to JSON if not a string
                if not isinstance(value, str):
                    value = json.dumps(value)
                
                # Get current timestamp
                timestamp = datetime.now().isoformat()
                
                # Insert or update
                self.execute(
                    """
                    INSERT INTO settings (key, value, category, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        category = excluded.category,
                        updated_at = excluded.updated_at
                    """,
                    (key, value, category, timestamp)
                )
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to set setting {key}: {str(e)}")
                return False
    
    def delete_setting(self, key: str, category: Optional[str] = None) -> bool:
        """
        Delete a setting from the database.
        
        Args:
            key: Setting key.
            category: Optional category for grouping settings.
            
        Returns:
            True if successful, False otherwise.
        """
        with self.lock:
            try:
                if category:
                    self.execute(
                        "DELETE FROM settings WHERE key = ? AND category = ?",
                        (key, category)
                    )
                else:
                    self.execute(
                        "DELETE FROM settings WHERE key = ?",
                        (key,)
                    )
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to delete setting {key}: {str(e)}")
                return False
    
    def get_settings_by_category(self, category: str) -> Dict[str, Any]:
        """
        Get all settings in a category.
        
        Args:
            category: Category to get settings for.
            
        Returns:
            Dictionary of key-value pairs.
        """
        with self.lock:
            try:
                cursor = self.execute(
                    "SELECT key, value FROM settings WHERE category = ?",
                    (category,)
                )
                
                result = {}
                
                for row in cursor:
                    key = row[0]
                    value = row[1]
                    
                    # Try to parse as JSON first
                    try:
                        result[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        # Use string value if not JSON
                        result[key] = value
                
                return result
                
            except Exception as e:
                logger.error(f"Failed to get settings for category {category}: {str(e)}")
                return {}
    
    def add_history_item(self, url: str, title: Optional[str] = None,
                       platform: Optional[str] = None, file_path: Optional[str] = None,
                       file_size: Optional[int] = None, duration: Optional[float] = None,
                       status: str = "completed", metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Add an item to the download history.
        
        Args:
            url: URL of the downloaded video.
            title: Title of the video.
            platform: Platform (youtube, twitter, etc.).
            file_path: Path to the downloaded file.
            file_size: Size of the file in bytes.
            duration: Duration of the video in seconds.
            status: Status of the download (completed, failed, etc.).
            metadata: Additional metadata as a dictionary.
            
        Returns:
            ID of the inserted history item, or -1 on failure.
        """
        with self.lock:
            try:
                # Convert metadata to JSON if provided
                metadata_json = None
                if metadata:
                    metadata_json = json.dumps(metadata)
                
                # Get current timestamp
                timestamp = datetime.now().isoformat()
                
                cursor = self.execute(
                    """
                    INSERT INTO history (
                        url, title, platform, download_date, file_path,
                        file_size, duration, status, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (url, title, platform, timestamp, file_path,
                     file_size, duration, status, metadata_json)
                )
                
                return cursor.lastrowid
                
            except Exception as e:
                logger.error(f"Failed to add history item: {str(e)}")
                return -1
    
    def get_history_items(self, limit: int = 50, offset: int = 0,
                        status: Optional[str] = None,
                        platform: Optional[str] = None,
                        search_term: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get items from the download history.
        
        Args:
            limit: Maximum number of items to return.
            offset: Offset for pagination.
            status: Optional filter by status.
            platform: Optional filter by platform.
            search_term: Optional search term for title or URL.
            
        Returns:
            List of history items as dictionaries.
        """
        with self.lock:
            try:
                query = "SELECT * FROM history"
                params = []
                conditions = []
                
                # Add filters
                if status:
                    conditions.append("status = ?")
                    params.append(status)
                
                if platform:
                    conditions.append("platform = ?")
                    params.append(platform)
                
                if search_term:
                    conditions.append("(title LIKE ? OR url LIKE ?)")
                    search_pattern = f"%{search_term}%"
                    params.extend([search_pattern, search_pattern])
                
                # Build the final query
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                # Add ordering and limit
                query += " ORDER BY download_date DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor = self.execute(query, tuple(params))
                
                result = []
                
                for row in cursor:
                    item = dict(row)
                    
                    # Parse metadata JSON if present
                    if item["metadata"]:
                        try:
                            item["metadata"] = json.loads(item["metadata"])
                        except Exception:
                            item["metadata"] = {}
                    else:
                        item["metadata"] = {}
                    
                    result.append(item)
                
                return result
                
            except Exception as e:
                logger.error(f"Failed to get history items: {str(e)}")
                return []
    
    def delete_history_item(self, item_id: int) -> bool:
        """
        Delete an item from the download history.
        
        Args:
            item_id: ID of the history item to delete.
            
        Returns:
            True if successful, False otherwise.
        """
        with self.lock:
            try:
                self.execute(
                    "DELETE FROM history WHERE id = ?",
                    (item_id,)
                )
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to delete history item {item_id}: {str(e)}")
                return False
    
    def clear_history(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear the download history.
        
        Args:
            older_than_days: Optional, only clear items older than this many days.
            
        Returns:
            Number of deleted items.
        """
        with self.lock:
            try:
                if older_than_days is not None:
                    # Calculate the cutoff date
                    cutoff_date = datetime.now().timestamp() - (older_than_days * 86400)
                    cutoff_iso = datetime.fromtimestamp(cutoff_date).isoformat()
                    
                    cursor = self.execute(
                        "DELETE FROM history WHERE download_date < ?",
                        (cutoff_iso,)
                    )
                else:
                    cursor = self.execute("DELETE FROM history")
                
                return cursor.rowcount
                
            except Exception as e:
                logger.error(f"Failed to clear history: {str(e)}")
                return 0


# Singleton instance for application-wide use
_db_instance = None

def get_database(db_path: Optional[str] = None) -> Database:
    """
    Get the database instance.
    
    Args:
        db_path: Optional database path. Only used when creating the instance.
        
    Returns:
        The database instance.
    """
    global _db_instance
    
    if _db_instance is None:
        _db_instance = Database(db_path)
    
    return _db_instance


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Initialize database
    db = get_database()
    
    # Set a setting
    db.set_setting("test_setting", "test_value", "test_category")
    
    # Get a setting
    value = db.get_setting("test_setting", category="test_category")
    print(f"Setting value: {value}")
    
    # Add a history item
    history_id = db.add_history_item(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Test Video",
        platform="youtube",
        file_path="/path/to/file.mp3",
        file_size=1024 * 1024,
        duration=180.5,
        status="completed",
        metadata={"format": "mp3", "quality": "high"}
    )
    
    print(f"Added history item with ID: {history_id}")
    
    # Get history items
    history_items = db.get_history_items(limit=10)
    print(f"History items: {len(history_items)}")
    
    for item in history_items:
        print(f" - {item['title']} ({item['platform']}) - {item['status']}")
    
    # Clean up
    db.delete_history_item(history_id)
    db.delete_setting("test_setting", "test_category")
    
    # Close the database
    db.close()