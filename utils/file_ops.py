"""
File operations utility module for SlowJams application.

This module provides utilities for file system operations such as creating directories,
generating file paths, handling duplicates, and cleaning up temporary files.
"""

import os
import re
import shutil
import tempfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Set, Tuple, Dict, Any, Union

logger = logging.getLogger(__name__)


def ensure_directory_exists(directory_path: str) -> bool:
    """
    Ensure that a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory.
        
    Returns:
        True if directory exists or was created, False on failure.
    """
    if not directory_path:
        return False
    
    try:
        os.makedirs(directory_path, exist_ok=True)
        return os.path.isdir(directory_path)
    except Exception as e:
        logger.error(f"Failed to create directory {directory_path}: {str(e)}")
        return False


def generate_output_filename(base_path: str, title: str, author: Optional[str] = None, 
                          extension: str = "mp3", effect: Optional[str] = None,
                          allow_overwrite: bool = False) -> str:
    """
    Generate a unique output filename based on the video title and other parameters.
    
    Args:
        base_path: Base directory for the output file.
        title: Title of the video/audio.
        author: Optional author/channel name.
        extension: File extension (without the dot).
        effect: Optional effect type (e.g., "slowed", "chopped").
        allow_overwrite: Whether to allow overwriting existing files.
        
    Returns:
        The generated file path.
    """
    # Sanitize the title and author for use in filenames
    sanitized_title = sanitize_filename(title)
    
    if author:
        sanitized_author = sanitize_filename(author)
        filename_base = f"{sanitized_title} - {sanitized_author}"
    else:
        filename_base = sanitized_title
    
    # Add effect if specified
    if effect:
        filename_base = f"{filename_base} ({effect})"
    
    # Ensure extension doesn't have a leading dot
    extension = extension.lstrip(".")
    
    # Construct the initial file path
    file_path = os.path.join(base_path, f"{filename_base}.{extension}")
    
    # If overwriting is allowed and this is a new filename, return it
    if allow_overwrite or not os.path.exists(file_path):
        return file_path
    
    # Otherwise, find a unique filename
    counter = 1
    while os.path.exists(file_path):
        file_path = os.path.join(base_path, f"{filename_base} ({counter}).{extension}")
        counter += 1
    
    return file_path


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a string for use as a filename.
    
    Args:
        filename: The string to sanitize.
        
    Returns:
        Sanitized filename.
    """
    if not filename:
        return "unnamed"
    
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", filename)
    
    # Replace multiple spaces with a single space
    sanitized = re.sub(r'\s+', " ", sanitized)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(". ")
    
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:197] + "..."
    
    # Ensure the filename is not empty after sanitization
    if not sanitized:
        return "unnamed"
    
    return sanitized


def get_file_metadata(file_path: str) -> Dict[str, Any]:
    """
    Get metadata about a file (size, creation time, etc.).
    
    Args:
        file_path: Path to the file.
        
    Returns:
        Dictionary of metadata.
    """
    if not os.path.exists(file_path):
        return {}
    
    try:
        stat_info = os.stat(file_path)
        
        return {
            "size": stat_info.st_size,
            "size_readable": format_file_size(stat_info.st_size),
            "created": datetime.fromtimestamp(stat_info.st_ctime),
            "modified": datetime.fromtimestamp(stat_info.st_mtime),
            "extension": os.path.splitext(file_path)[1].lstrip(".").lower(),
            "filename": os.path.basename(file_path),
            "directory": os.path.dirname(file_path),
            "is_file": os.path.isfile(file_path),
            "is_dir": os.path.isdir(file_path),
        }
    except Exception as e:
        logger.error(f"Failed to get metadata for {file_path}: {str(e)}")
        return {}


def format_file_size(size_bytes: int) -> str:
    """
    Format a file size in bytes to a human-readable string.
    
    Args:
        size_bytes: File size in bytes.
        
    Returns:
        Human-readable file size.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    
    size_kb = size_bytes / 1024
    if size_kb < 1024:
        return f"{size_kb:.1f} KB"
    
    size_mb = size_kb / 1024
    if size_mb < 1024:
        return f"{size_mb:.1f} MB"
    
    size_gb = size_mb / 1024
    return f"{size_gb:.2f} GB"


def create_temp_directory() -> str:
    """
    Create a temporary directory for processing files.
    
    Returns:
        Path to the temporary directory.
    """
    try:
        temp_dir = tempfile.mkdtemp(prefix="slowjams_")
        return temp_dir
    except Exception as e:
        logger.error(f"Failed to create temporary directory: {str(e)}")
        return tempfile.gettempdir()


def clean_temp_directory(directory: str, force: bool = False) -> bool:
    """
    Clean up a temporary directory.
    
    Args:
        directory: Path to the directory to clean.
        force: Whether to force deletion even if it's not a temp directory.
        
    Returns:
        True if successful, False otherwise.
    """
    if not directory or not os.path.exists(directory):
        return False
    
    # Safety check to avoid deleting non-temp directories
    if not force and not os.path.basename(directory).startswith("slowjams_"):
        logger.warning(f"Refusing to delete non-temporary directory: {directory}")
        return False
    
    try:
        shutil.rmtree(directory)
        return True
    except Exception as e:
        logger.error(f"Failed to clean temporary directory {directory}: {str(e)}")
        return False


def list_files_by_extension(directory: str, extensions: List[str]) -> List[str]:
    """
    List all files in a directory with specified extensions.
    
    Args:
        directory: Directory to search.
        extensions: List of extensions to match (without the dot).
        
    Returns:
        List of matching file paths.
    """
    if not directory or not os.path.isdir(directory):
        return []
    
    # Normalize extensions
    exts = [ext.lower().lstrip(".") for ext in extensions]
    
    # Find matching files
    matching_files = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            file_ext = os.path.splitext(file)[1].lstrip(".").lower()
            if file_ext in exts:
                matching_files.append(os.path.join(root, file))
    
    return matching_files


def get_recent_files(directory: str, max_count: int = 10, 
                   extensions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Get a list of recently modified files in a directory.
    
    Args:
        directory: Directory to search.
        max_count: Maximum number of files to return.
        extensions: Optional list of extensions to filter by.
        
    Returns:
        List of file metadata dictionaries, sorted by modification time (newest first).
    """
    if not directory or not os.path.isdir(directory):
        return []
    
    # Get all files, optionally filtered by extension
    all_files = []
    if extensions:
        all_files = list_files_by_extension(directory, extensions)
    else:
        for root, _, files in os.walk(directory):
            for file in files:
                all_files.append(os.path.join(root, file))
    
    # Get metadata for files
    file_data = []
    for file_path in all_files:
        metadata = get_file_metadata(file_path)
        if metadata:
            file_data.append(metadata)
    
    # Sort by modification time (newest first)
    file_data.sort(key=lambda x: x.get("modified", datetime.min), reverse=True)
    
    # Return the top N files
    return file_data[:max_count]


def move_file(source: str, destination: str, overwrite: bool = False) -> bool:
    """
    Move a file from source to destination.
    
    Args:
        source: Source file path.
        destination: Destination file path.
        overwrite: Whether to overwrite existing files.
        
    Returns:
        True if successful, False otherwise.
    """
    if not source or not os.path.exists(source):
        logger.error(f"Source file does not exist: {source}")
        return False
    
    if not destination:
        logger.error("Destination path is empty")
        return False
    
    # Check if destination exists
    if os.path.exists(destination) and not overwrite:
        logger.error(f"Destination file already exists: {destination}")
        return False
    
    # Ensure destination directory exists
    dest_dir = os.path.dirname(destination)
    if dest_dir and not ensure_directory_exists(dest_dir):
        logger.error(f"Failed to create destination directory: {dest_dir}")
        return False
    
    try:
        shutil.move(source, destination)
        return True
    except Exception as e:
        logger.error(f"Failed to move file from {source} to {destination}: {str(e)}")
        return False


def copy_file(source: str, destination: str, overwrite: bool = False) -> bool:
    """
    Copy a file from source to destination.
    
    Args:
        source: Source file path.
        destination: Destination file path.
        overwrite: Whether to overwrite existing files.
        
    Returns:
        True if successful, False otherwise.
    """
    if not source or not os.path.exists(source):
        logger.error(f"Source file does not exist: {source}")
        return False
    
    if not destination:
        logger.error("Destination path is empty")
        return False
    
    # Check if destination exists
    if os.path.exists(destination) and not overwrite:
        logger.error(f"Destination file already exists: {destination}")
        return False
    
    # Ensure destination directory exists
    dest_dir = os.path.dirname(destination)
    if dest_dir and not ensure_directory_exists(dest_dir):
        logger.error(f"Failed to create destination directory: {dest_dir}")
        return False
    
    try:
        shutil.copy2(source, destination)
        return True
    except Exception as e:
        logger.error(f"Failed to copy file from {source} to {destination}: {str(e)}")
        return False


def organize_files_by_date(source_dir: str, dest_dir: str, 
                        date_format: str = "%Y-%m-%d") -> Dict[str, List[str]]:
    """
    Organize files into subdirectories based on modification date.
    
    Args:
        source_dir: Source directory containing files.
        dest_dir: Destination directory for organized files.
        date_format: Format string for date subdirectories.
        
    Returns:
        Dictionary mapping date directories to lists of moved files.
    """
    if not source_dir or not os.path.isdir(source_dir):
        logger.error(f"Source directory does not exist: {source_dir}")
        return {}
    
    if not ensure_directory_exists(dest_dir):
        logger.error(f"Failed to create destination directory: {dest_dir}")
        return {}
    
    # Track files moved to each date directory
    result = {}
    
    # Process each file in the source directory
    for file_name in os.listdir(source_dir):
        file_path = os.path.join(source_dir, file_name)
        
        # Skip directories
        if not os.path.isfile(file_path):
            continue
        
        try:
            # Get file modification time
            mod_time = os.path.getmtime(file_path)
            date_str = datetime.fromtimestamp(mod_time).strftime(date_format)
            
            # Create date directory
            date_dir = os.path.join(dest_dir, date_str)
            ensure_directory_exists(date_dir)
            
            # Move file
            dest_path = os.path.join(date_dir, file_name)
            if move_file(file_path, dest_path, overwrite=False):
                if date_str not in result:
                    result[date_str] = []
                result[date_str].append(dest_path)
        
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {str(e)}")
    
    return result


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Create a test directory
    test_dir = os.path.join(tempfile.gettempdir(), "slowjams_test")
    ensure_directory_exists(test_dir)
    
    # Generate a filename
    output_file = generate_output_filename(
        test_dir,
        "Test Video - With Special Characters: ?*|\"<>",
        "Test Channel",
        "mp3",
        "slowed"
    )
    
    print(f"Generated filename: {output_file}")
    
    # Create a temporary file
    with open(output_file, "w") as f:
        f.write("Test content")
    
    # Get metadata
    metadata = get_file_metadata(output_file)
    print(f"File metadata: {metadata}")
    
    # Clean up
    os.remove(output_file)
    os.rmdir(test_dir)