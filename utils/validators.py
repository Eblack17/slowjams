"""
Validator utilities for SlowJams application.

This module provides functions for validating user input such as URLs, file paths,
and various parameter values.
"""

import os
import re
from typing import Union, Tuple, Optional, Dict, Any, List
from urllib.parse import urlparse

# Import core functionality for URL validation
try:
    from core.downloader import is_supported_url
except ImportError:
    # For standalone usage or testing, create a simple placeholder
    def is_supported_url(url: str) -> bool:
        """Check if a URL is supported by any registered downloader."""
        # Simple check for YouTube or Twitter URLs
        parsed = urlparse(url.lower())
        domain = parsed.netloc
        return any(service in domain for service in ["youtube", "youtu.be", "twitter", "x.com"])


def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a URL for video downloading.
    
    Args:
        url: The URL to validate.
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if URL is empty or None
    if not url or not url.strip():
        return False, "URL cannot be empty"
    
    url = url.strip()
    
    # Basic URL format check
    if not re.match(r'^https?://', url):
        return False, "URL must start with http:// or https://"
    
    # Check if the URL is valid
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False, "Invalid URL format"
    except Exception:
        return False, "Invalid URL format"
    
    # Check if the URL is from a supported platform
    if not is_supported_url(url):
        return False, "Unsupported platform. We currently support YouTube and Twitter."
    
    return True, None


def validate_file_path(path: str, must_exist: bool = False, 
                    check_writeable: bool = False,
                    allowed_extensions: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate a file path.
    
    Args:
        path: The file path to validate.
        must_exist: Whether the file must already exist.
        check_writeable: Whether to check if the directory is writeable.
        allowed_extensions: List of allowed file extensions (without the dot).
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if path is empty or None
    if not path or not path.strip():
        return False, "Path cannot be empty"
    
    path = path.strip()
    
    # Check if path is absolute or relative
    is_absolute = os.path.isabs(path)
    
    # Check if file must exist
    if must_exist and not os.path.exists(path):
        return False, f"File does not exist: {path}"
    
    # Check file extension if specified
    if allowed_extensions is not None:
        _, ext = os.path.splitext(path)
        ext = ext.lstrip('.').lower()
        if ext not in [e.lower() for e in allowed_extensions]:
            return False, f"Invalid file extension. Allowed: {', '.join(allowed_extensions)}"
    
    # Check if parent directory exists and is writeable
    if check_writeable:
        parent_dir = os.path.dirname(path) or os.getcwd()
        if not os.path.exists(parent_dir):
            return False, f"Directory does not exist: {parent_dir}"
        if not os.access(parent_dir, os.W_OK):
            return False, f"Directory is not writeable: {parent_dir}"
    
    return True, None


def validate_numeric_range(value: Union[int, float], 
                        min_value: Optional[Union[int, float]] = None,
                        max_value: Optional[Union[int, float]] = None,
                        include_min: bool = True,
                        include_max: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate a numeric value within a range.
    
    Args:
        value: The value to validate.
        min_value: Minimum allowed value, or None for no minimum.
        max_value: Maximum allowed value, or None for no maximum.
        include_min: Whether the minimum value is inclusive.
        include_max: Whether the maximum value is inclusive.
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check minimum
    if min_value is not None:
        if include_min and value < min_value:
            return False, f"Value must be at least {min_value}"
        elif not include_min and value <= min_value:
            return False, f"Value must be greater than {min_value}"
    
    # Check maximum
    if max_value is not None:
        if include_max and value > max_value:
            return False, f"Value must be at most {max_value}"
        elif not include_max and value >= max_value:
            return False, f"Value must be less than {max_value}"
    
    return True, None


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate an email address.
    
    Args:
        email: The email address to validate.
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email or not email.strip():
        return False, "Email cannot be empty"
    
    email = email.strip()
    
    # Basic email format check
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return False, "Invalid email format"
    
    return True, None


def validate_duration(duration_str: str) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Validate a duration string in HH:MM:SS or MM:SS format and convert to seconds.
    
    Args:
        duration_str: Duration string to validate.
        
    Returns:
        Tuple of (is_valid, error_message, seconds)
    """
    if not duration_str or not duration_str.strip():
        return False, "Duration cannot be empty", None
    
    duration_str = duration_str.strip()
    
    # Check format (HH:MM:SS or MM:SS)
    if not re.match(r'^(\d+:)?[0-5]?\d:[0-5]\d(\.\d+)?$', duration_str):
        return False, "Invalid duration format. Use HH:MM:SS or MM:SS", None
    
    # Parse the duration
    try:
        parts = duration_str.split(':')
        seconds = 0
        
        if len(parts) == 3:  # HH:MM:SS
            seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:  # MM:SS
            seconds = int(parts[0]) * 60 + float(parts[1])
        else:
            return False, "Invalid duration format", None
        
        if seconds < 0:
            return False, "Duration cannot be negative", None
        
        return True, None, seconds
    
    except ValueError:
        return False, "Invalid duration format", None


def validate_bitrate(bitrate: str) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Validate a bitrate string (e.g., '192k', '320k') and convert to kbps.
    
    Args:
        bitrate: Bitrate string to validate.
        
    Returns:
        Tuple of (is_valid, error_message, kbps)
    """
    if not bitrate or not bitrate.strip():
        return False, "Bitrate cannot be empty", None
    
    bitrate = bitrate.strip().lower()
    
    # Check format (e.g., 192k, 320k)
    match = re.match(r'^(\d+)(k)?$', bitrate)
    if not match:
        return False, "Invalid bitrate format. Use e.g., 192k or 320", None
    
    kbps = int(match.group(1))
    
    # Validate range
    if kbps < 32 or kbps > 320:
        return False, "Bitrate must be between 32 and 320 kbps", None
    
    return True, None, kbps


if __name__ == "__main__":
    # Example usage
    urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://twitter.com/username/status/1234567890",
        "https://x.com/username/status/1234567890",
        "https://invalid-url",
        "not-a-url",
    ]
    
    print("URL Validation:")
    for url in urls:
        valid, error = validate_url(url)
        status = "✅ Valid" if valid else f"❌ Invalid: {error}"
        print(f"  {url} - {status}")
    
    print("\nFile Path Validation:")
    paths = [
        "example.mp3",
        "invalid.xyz",
        "/non/existent/path/file.mp3",
        os.getcwd(),
    ]
    
    for path in paths:
        valid, error = validate_file_path(path, check_writeable=True, allowed_extensions=["mp3", "wav"])
        status = "✅ Valid" if valid else f"❌ Invalid: {error}"
        print(f"  {path} - {status}")