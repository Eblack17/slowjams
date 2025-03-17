"""
Download history module for SlowJams application.

This module provides a high-level interface for accessing and managing
the download history, built on top of the database module.
"""

import os
import logging
from typing import Optional, Dict, List, Any, Union, Callable
from datetime import datetime
from dataclasses import dataclass, field

# Import database module
try:
    from data.database import get_database
except ImportError:
    # For standalone usage or testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from data.database import get_database

logger = logging.getLogger(__name__)


@dataclass
class HistoryItem:
    """Class representing an item in the download history."""
    
    id: int = -1  # Database ID (-1 means not saved)
    url: str = ""
    title: Optional[str] = None
    platform: Optional[str] = None
    download_date: Optional[datetime] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[float] = None
    status: str = "completed"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HistoryItem':
        """
        Create a HistoryItem from a dictionary.
        
        Args:
            data: Dictionary data, typically from database.
            
        Returns:
            A new HistoryItem instance.
        """
        # Convert string timestamp to datetime if present
        download_date = data.get("download_date")
        if isinstance(download_date, str):
            try:
                download_date = datetime.fromisoformat(download_date)
            except (ValueError, TypeError):
                download_date = None
        
        return cls(
            id=data.get("id", -1),
            url=data.get("url", ""),
            title=data.get("title"),
            platform=data.get("platform"),
            download_date=download_date,
            file_path=data.get("file_path"),
            file_size=data.get("file_size"),
            duration=data.get("duration"),
            status=data.get("status", "completed"),
            metadata=data.get("metadata", {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to a dictionary.
        
        Returns:
            Dictionary representation of the item.
        """
        result = {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "platform": self.platform,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "duration": self.duration,
            "status": self.status,
            "metadata": self.metadata
        }
        
        # Convert datetime to ISO format string
        if self.download_date:
            result["download_date"] = self.download_date.isoformat()
        
        return result
    
    @property
    def is_saved(self) -> bool:
        """Check if the item has been saved to the database."""
        return self.id > 0
    
    @property
    def formatted_size(self) -> str:
        """Get the file size formatted as a human-readable string."""
        if self.file_size is None:
            return "Unknown"
        
        if self.file_size < 1024:
            return f"{self.file_size} B"
        
        size_kb = self.file_size / 1024
        if size_kb < 1024:
            return f"{size_kb:.1f} KB"
        
        size_mb = size_kb / 1024
        if size_mb < 1024:
            return f"{size_mb:.1f} MB"
        
        size_gb = size_mb / 1024
        return f"{size_gb:.2f} GB"
    
    @property
    def formatted_duration(self) -> str:
        """Get the duration formatted as HH:MM:SS."""
        if self.duration is None:
            return "Unknown"
        
        total_seconds = int(self.duration)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    @property
    def formatted_date(self) -> str:
        """Get the download date formatted as a string."""
        if self.download_date is None:
            return "Unknown"
        
        return self.download_date.strftime("%Y-%m-%d %H:%M:%S")
    
    @property
    def file_exists(self) -> bool:
        """Check if the file exists."""
        if not self.file_path:
            return False
        
        return os.path.exists(self.file_path)


class HistoryManager:
    """
    Manager for download history.
    
    This class provides a high-level interface for accessing and managing
    the download history, with methods for adding, retrieving, and deleting items.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the history manager.
        
        Args:
            db_path: Optional path to the SQLite database file.
        """
        self.db = get_database(db_path)
        self.callbacks: List[Callable[[], None]] = []
    
    def add_item(self, item: HistoryItem) -> int:
        """
        Add an item to the download history.
        
        Args:
            item: HistoryItem to add.
            
        Returns:
            ID of the inserted history item, or -1 on failure.
        """
        if not item.url:
            logger.error("Cannot add history item without URL")
            return -1
        
        # Set download date if not provided
        if item.download_date is None:
            item.download_date = datetime.now()
        
        # Add to database
        item_id = self.db.add_history_item(
            url=item.url,
            title=item.title,
            platform=item.platform,
            file_path=item.file_path,
            file_size=item.file_size,
            duration=item.duration,
            status=item.status,
            metadata=item.metadata
        )
        
        # Update item ID if successful
        if item_id > 0:
            item.id = item_id
            self._notify_callbacks()
        
        return item_id
    
    def get_items(self, limit: int = 50, offset: int = 0,
                status: Optional[str] = None,
                platform: Optional[str] = None,
                search_term: Optional[str] = None) -> List[HistoryItem]:
        """
        Get items from the download history.
        
        Args:
            limit: Maximum number of items to return.
            offset: Offset for pagination.
            status: Optional filter by status.
            platform: Optional filter by platform.
            search_term: Optional search term for title or URL.
            
        Returns:
            List of HistoryItem objects.
        """
        # Get items from database
        items_data = self.db.get_history_items(
            limit=limit,
            offset=offset,
            status=status,
            platform=platform,
            search_term=search_term
        )
        
        # Convert to HistoryItem objects
        return [HistoryItem.from_dict(item_data) for item_data in items_data]
    
    def get_item(self, item_id: int) -> Optional[HistoryItem]:
        """
        Get a specific history item by ID.
        
        Args:
            item_id: ID of the history item.
            
        Returns:
            HistoryItem if found, None otherwise.
        """
        items = self.get_items(limit=1, offset=0)
        
        for item in items:
            if item.id == item_id:
                return item
        
        return None
    
    def update_item(self, item: HistoryItem) -> bool:
        """
        Update an existing history item.
        
        Args:
            item: HistoryItem to update.
            
        Returns:
            True if successful, False otherwise.
        """
        if not item.is_saved:
            logger.error("Cannot update unsaved history item")
            return False
        
        # Delete existing item
        if not self.delete_item(item.id):
            logger.error(f"Failed to delete existing history item {item.id}")
            return False
        
        # Add updated item with same ID
        new_id = self.db.add_history_item(
            url=item.url,
            title=item.title,
            platform=item.platform,
            file_path=item.file_path,
            file_size=item.file_size,
            duration=item.duration,
            status=item.status,
            metadata=item.metadata
        )
        
        if new_id > 0:
            self._notify_callbacks()
            return True
        
        return False
    
    def delete_item(self, item_id: int) -> bool:
        """
        Delete a history item.
        
        Args:
            item_id: ID of the history item to delete.
            
        Returns:
            True if successful, False otherwise.
        """
        result = self.db.delete_history_item(item_id)
        
        if result:
            self._notify_callbacks()
        
        return result
    
    def clear_history(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear the download history.
        
        Args:
            older_than_days: Optional, only clear items older than this many days.
            
        Returns:
            Number of deleted items.
        """
        deleted_count = self.db.clear_history(older_than_days)
        
        if deleted_count > 0:
            self._notify_callbacks()
        
        return deleted_count
    
    def register_callback(self, callback: Callable[[], None]):
        """
        Register a callback for history changes.
        
        Args:
            callback: Function to call when the history changes.
        """
        if callback not in self.callbacks:
            self.callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[], None]) -> bool:
        """
        Unregister a callback for history changes.
        
        Args:
            callback: Function to remove.
            
        Returns:
            True if callback was removed, False if not found.
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            return True
        
        return False
    
    def _notify_callbacks(self):
        """Notify registered callbacks about history changes."""
        for callback in self.callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in history callback: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the download history.
        
        Returns:
            Dictionary with statistics.
        """
        stats = {
            "total_items": 0,
            "completed_items": 0,
            "failed_items": 0,
            "total_size": 0,
            "total_duration": 0,
            "platforms": {},
            "recent_downloads": []
        }
        
        # Get all items (up to a reasonable limit)
        items = self.get_items(limit=1000)
        
        stats["total_items"] = len(items)
        
        # Calculate stats
        for item in items:
            # Count by status
            if item.status == "completed":
                stats["completed_items"] += 1
            elif item.status == "failed":
                stats["failed_items"] += 1
            
            # Total size and duration
            if item.file_size:
                stats["total_size"] += item.file_size
            
            if item.duration:
                stats["total_duration"] += item.duration
            
            # Count by platform
            if item.platform:
                if item.platform not in stats["platforms"]:
                    stats["platforms"][item.platform] = 0
                stats["platforms"][item.platform] += 1
        
        # Get recent downloads
        stats["recent_downloads"] = [
            item.to_dict() for item in items[:5]
        ]
        
        # Format total size
        if stats["total_size"] < 1024:
            stats["total_size_formatted"] = f"{stats['total_size']} B"
        elif stats["total_size"] < 1024 * 1024:
            stats["total_size_formatted"] = f"{stats['total_size'] / 1024:.1f} KB"
        elif stats["total_size"] < 1024 * 1024 * 1024:
            stats["total_size_formatted"] = f"{stats['total_size'] / (1024 * 1024):.1f} MB"
        else:
            stats["total_size_formatted"] = f"{stats['total_size'] / (1024 * 1024 * 1024):.2f} GB"
        
        # Format total duration
        total_seconds = int(stats["total_duration"])
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        stats["total_duration_formatted"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        return stats


# Singleton instance for application-wide use
_history_instance = None

def get_history(db_path: Optional[str] = None) -> HistoryManager:
    """
    Get the history manager instance.
    
    Args:
        db_path: Optional database path. Only used when creating the instance.
        
    Returns:
        The history manager instance.
    """
    global _history_instance
    
    if _history_instance is None:
        _history_instance = HistoryManager(db_path)
    
    return _history_instance


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Initialize history manager
    history = get_history()
    
    # Add a history item
    item = HistoryItem(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="Rick Astley - Never Gonna Give You Up",
        platform="youtube",
        file_path="/path/to/file.mp3",
        file_size=1024 * 1024 * 5,  # 5 MB
        duration=213.5,  # 3:33
        status="completed",
        metadata={"format": "mp3", "quality": "high"}
    )
    
    item_id = history.add_item(item)
    print(f"Added history item with ID: {item_id}")
    
    # Get history items
    items = history.get_items(limit=10)
    print(f"\nHistory items: {len(items)}")
    
    for item in items:
        print(f" - {item.title} ({item.platform}) - {item.status}")
        print(f"   Size: {item.formatted_size}, Duration: {item.formatted_duration}")
        print(f"   Downloaded: {item.formatted_date}")
    
    # Get statistics
    stats = history.get_statistics()
    print("\nHistory statistics:")
    print(f" - Total items: {stats['total_items']}")
    print(f" - Completed items: {stats['completed_items']}")
    print(f" - Failed items: {stats['failed_items']}")
    print(f" - Total size: {stats['total_size_formatted']}")
    print(f" - Total duration: {stats['total_duration_formatted']}")
    print(" - Platforms:")
    for platform, count in stats["platforms"].items():
        print(f"   - {platform}: {count}")
    
    # Clean up
    history.delete_item(item_id)