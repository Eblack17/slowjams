"""
Tests for the validators module.

This module contains tests for the validator functions
in the utils.validators module.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Import module to test
from utils.validators import (
    validate_url,
    validate_file_path,
    validate_numeric_range,
    validate_email,
    validate_duration,
    validate_bitrate
)


class TestValidateUrl:
    """Tests for the validate_url function."""
    
    def test_valid_youtube_url(self):
        """Test with a valid YouTube URL."""
        result = validate_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result is True
    
    def test_valid_youtube_short_url(self):
        """Test with a valid YouTube short URL."""
        result = validate_url("https://youtu.be/dQw4w9WgXcQ")
        assert result is True
    
    def test_valid_twitter_url(self):
        """Test with a valid Twitter URL."""
        result = validate_url("https://twitter.com/username/status/1234567890")
        assert result is True
    
    def test_empty_url(self):
        """Test with an empty URL."""
        with pytest.raises(ValueError):
            validate_url("")
    
    def test_non_string_url(self):
        """Test with a non-string URL."""
        with pytest.raises(ValueError):
            validate_url(12345)
    
    def test_invalid_url_no_protocol(self):
        """Test with a URL lacking a protocol."""
        with pytest.raises(ValueError):
            validate_url("youtube.com/watch?v=dQw4w9WgXcQ")
    
    def test_unsupported_platform(self):
        """Test with an unsupported platform URL."""
        with pytest.raises(ValueError):
            validate_url("https://example.com/video")


class TestValidateFilePath:
    """Tests for the validate_file_path function."""
    
    def test_valid_existing_file(self):
        """Test with a valid existing file."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
            result = validate_file_path(temp_file.name, must_exist=True)
            assert result is True
    
    def test_valid_new_file(self):
        """Test with a valid new file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.mp3")
            result = validate_file_path(file_path, must_exist=False)
            assert result is True
    
    def test_empty_path(self):
        """Test with an empty file path."""
        with pytest.raises(ValueError):
            validate_file_path("")
    
    def test_directory_path(self):
        """Test with a directory path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError):
                validate_file_path(temp_dir, must_exist=True)
    
    def test_non_writable_directory(self):
        """Test with a path in a non-writable directory."""
        if os.name != 'nt':  # Skip on Windows where permissions work differently
            with tempfile.TemporaryDirectory() as temp_dir:
                # Make the directory non-writable
                os.chmod(temp_dir, 0o555)
                file_path = os.path.join(temp_dir, "test.mp3")
                
                with pytest.raises(ValueError):
                    validate_file_path(file_path, must_exist=False)
                
                # Restore permissions to allow deletion
                os.chmod(temp_dir, 0o755)
    
    def test_invalid_extension(self):
        """Test with an invalid file extension."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            with pytest.raises(ValueError):
                validate_file_path(temp_file.name, allowed_extensions=[".mp3", ".wav"])


class TestValidateNumericRange:
    """Tests for the validate_numeric_range function."""
    
    def test_valid_integer(self):
        """Test with a valid integer."""
        result = validate_numeric_range(5, 0, 10)
        assert result == 5
    
    def test_valid_float(self):
        """Test with a valid float."""
        result = validate_numeric_range(5.5, 0, 10)
        assert result == 5.5
    
    def test_valid_string_number(self):
        """Test with a valid string number."""
        result = validate_numeric_range("5", 0, 10)
        assert result == 5
    
    def test_below_minimum(self):
        """Test with a value below the minimum."""
        with pytest.raises(ValueError):
            validate_numeric_range(-1, 0, 10)
    
    def test_above_maximum(self):
        """Test with a value above the maximum."""
        with pytest.raises(ValueError):
            validate_numeric_range(11, 0, 10)
    
    def test_non_numeric_string(self):
        """Test with a non-numeric string."""
        with pytest.raises(ValueError):
            validate_numeric_range("abc", 0, 10)


class TestValidateEmail:
    """Tests for the validate_email function."""
    
    def test_valid_email(self):
        """Test with a valid email address."""
        result = validate_email("user@example.com")
        assert result is True
    
    def test_valid_complex_email(self):
        """Test with a valid complex email address."""
        result = validate_email("user.name+tag@example-domain.co.uk")
        assert result is True
    
    def test_empty_email(self):
        """Test with an empty email address."""
        with pytest.raises(ValueError):
            validate_email("")
    
    def test_invalid_email_no_at(self):
        """Test with an email address lacking an @ symbol."""
        with pytest.raises(ValueError):
            validate_email("userexample.com")
    
    def test_invalid_email_no_domain(self):
        """Test with an email address lacking a domain."""
        with pytest.raises(ValueError):
            validate_email("user@")
    
    def test_invalid_email_no_username(self):
        """Test with an email address lacking a username."""
        with pytest.raises(ValueError):
            validate_email("@example.com")


class TestValidateDuration:
    """Tests for the validate_duration function."""
    
    def test_valid_minutes_seconds(self):
        """Test with a valid MM:SS duration."""
        result = validate_duration("3:45")
        assert result == 225  # 3*60 + 45 = 225
    
    def test_valid_hours_minutes_seconds(self):
        """Test with a valid HH:MM:SS duration."""
        result = validate_duration("1:30:45")
        assert result == 5445  # 1*3600 + 30*60 + 45 = 5445
    
    def test_valid_seconds_only(self):
        """Test with valid seconds only."""
        result = validate_duration("90")
        assert result == 90
    
    def test_empty_duration(self):
        """Test with an empty duration."""
        with pytest.raises(ValueError):
            validate_duration("")
    
    def test_invalid_format(self):
        """Test with an invalid duration format."""
        with pytest.raises(ValueError):
            validate_duration("3:45:30:15")
    
    def test_non_numeric_components(self):
        """Test with non-numeric components."""
        with pytest.raises(ValueError):
            validate_duration("3:ab")


class TestValidateBitrate:
    """Tests for the validate_bitrate function."""
    
    def test_valid_numeric_bitrate(self):
        """Test with a valid numeric bitrate."""
        result = validate_bitrate("192")
        assert result == 192
    
    def test_valid_bitrate_with_k(self):
        """Test with a valid bitrate with 'k' suffix."""
        result = validate_bitrate("192k")
        assert result == 192
    
    def test_valid_bitrate_with_kbps(self):
        """Test with a valid bitrate with 'kbps' suffix."""
        result = validate_bitrate("192kbps")
        assert result == 192
    
    def test_empty_bitrate(self):
        """Test with an empty bitrate."""
        with pytest.raises(ValueError):
            validate_bitrate("")
    
    def test_non_numeric_bitrate(self):
        """Test with a non-numeric bitrate."""
        with pytest.raises(ValueError):
            validate_bitrate("high")
    
    def test_negative_bitrate(self):
        """Test with a negative bitrate."""
        with pytest.raises(ValueError):
            validate_bitrate("-192")
    
    def test_zero_bitrate(self):
        """Test with a zero bitrate."""
        with pytest.raises(ValueError):
            validate_bitrate("0")


if __name__ == "__main__":
    pytest.main(["-v", __file__])