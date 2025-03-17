"""
Video downloader module for SlowJams application.

This module handles the downloading of videos from supported platforms (YouTube and Twitter).
It provides classes for different platform downloaders and a factory to create the appropriate
downloader based on the URL.
"""

import os
import re
import logging
import tempfile
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from pathlib import Path
import subprocess
import json
import requests
from urllib.parse import urlparse, parse_qs

# Import the custom utilities
try:
    from utils.env_loader import get_bool_env
except ImportError:
    # For standalone usage or testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.env_loader import get_bool_env

logger = logging.getLogger(__name__)

@dataclass
class VideoMetadata:
    """Data class for storing video metadata."""
    
    video_id: str
    title: str
    author: str
    duration: float  # in seconds
    thumbnail_url: str
    platform: str
    formats: List[Dict[str, Union[str, int]]]
    original_url: str
    description: Optional[str] = None
    upload_date: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    
    @property
    def duration_formatted(self) -> str:
        """Return the duration formatted as HH:MM:SS."""
        minutes, seconds = divmod(self.duration, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"


class BaseDownloader(ABC):
    """Abstract base class for platform-specific downloaders."""
    
    def __init__(self, download_dir: Optional[str] = None):
        """
        Initialize the downloader.
        
        Args:
            download_dir: Directory to save downloaded files. If None, uses temp dir.
        """
        self.download_dir = download_dir or tempfile.gettempdir()
        os.makedirs(self.download_dir, exist_ok=True)
        self.simulation_mode = get_bool_env("SIMULATION_MODE", False)
        
    @abstractmethod
    def extract_id_from_url(self, url: str) -> str:
        """
        Extract the video ID from the URL.
        
        Args:
            url: The URL to extract the ID from.
            
        Returns:
            The extracted video ID.
            
        Raises:
            ValueError: If the URL is invalid or the ID cannot be extracted.
        """
        pass
    
    @abstractmethod
    def get_metadata(self, url: str) -> VideoMetadata:
        """
        Get metadata for the video at the given URL.
        
        Args:
            url: The URL of the video.
            
        Returns:
            A VideoMetadata object containing the video's metadata.
            
        Raises:
            ValueError: If the URL is invalid or the metadata cannot be fetched.
        """
        pass
    
    @abstractmethod
    def download(self, url: str, format_id: Optional[str] = None, 
                 progress_callback=None) -> str:
        """
        Download the video at the given URL.
        
        Args:
            url: The URL of the video to download.
            format_id: Optional format ID to download. If None, uses best quality.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            The path to the downloaded file.
            
        Raises:
            ValueError: If the URL is invalid or the download fails.
        """
        pass


class YouTubeDownloader(BaseDownloader):
    """Downloader for YouTube videos using yt-dlp."""
    
    PLATFORM_NAME = "youtube"
    URL_PATTERNS = [
        r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$'
    ]
    
    def __init__(self, download_dir: Optional[str] = None, 
                 yt_dlp_path: Optional[str] = None):
        """
        Initialize the YouTube downloader.
        
        Args:
            download_dir: Directory to save downloaded files.
            yt_dlp_path: Path to the yt-dlp executable. If None, assumes it's in PATH.
        """
        super().__init__(download_dir)
        self.yt_dlp_path = yt_dlp_path or "yt-dlp"
        
    def extract_id_from_url(self, url: str) -> str:
        """Extract the video ID from a YouTube URL."""
        if "youtu.be" in url:
            # Short URL format
            path = urlparse(url).path
            video_id = path.strip("/")
        else:
            # Regular youtube.com URL
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            if "v" in query_params:
                video_id = query_params["v"][0]
            else:
                # Try to extract from path for shorts or other formats
                match = re.search(r'/([a-zA-Z0-9_-]{11})(?:/|$)', parsed_url.path)
                if match:
                    video_id = match.group(1)
                else:
                    raise ValueError(f"Could not extract video ID from URL: {url}")
        
        # Validate video ID format
        if not re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
            raise ValueError(f"Invalid YouTube video ID format: {video_id}")
            
        return video_id
    
    def get_metadata(self, url: str) -> VideoMetadata:
        """Get metadata for a YouTube video."""
        try:
            video_id = self.extract_id_from_url(url)
            
            # Run yt-dlp to get video info
            cmd = [
                self.yt_dlp_path,
                "--dump-json",
                "--no-playlist",
                url
            ]
            
            if self.simulation_mode:
                logger.info(f"Simulation mode: Would run command: {' '.join(cmd)}")
                # Return dummy metadata in simulation mode
                return VideoMetadata(
                    video_id=video_id,
                    title="Simulation Video",
                    author="Simulation Channel",
                    duration=180.0,
                    thumbnail_url="https://example.com/thumbnail.jpg",
                    platform=self.PLATFORM_NAME,
                    formats=[
                        {"format_id": "22", "ext": "mp4", "resolution": "720p", 
                         "filesize": 1024*1024*10}
                    ],
                    original_url=url
                )
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            video_info = json.loads(result.stdout)
            
            # Extract relevant metadata
            formats = []
            for fmt in video_info.get('formats', []):
                if fmt.get('acodec') != 'none' and fmt.get('vcodec') != 'none':
                    formats.append({
                        'format_id': fmt.get('format_id'),
                        'ext': fmt.get('ext'),
                        'resolution': fmt.get('resolution') or f"{fmt.get('width', 0)}x{fmt.get('height', 0)}",
                        'filesize': fmt.get('filesize') or fmt.get('filesize_approx')
                    })
            
            return VideoMetadata(
                video_id=video_id,
                title=video_info.get('title', 'Unknown Title'),
                author=video_info.get('uploader', 'Unknown Author'),
                duration=float(video_info.get('duration', 0)),
                thumbnail_url=video_info.get('thumbnail', ''),
                platform=self.PLATFORM_NAME,
                formats=formats,
                original_url=url,
                description=video_info.get('description'),
                upload_date=video_info.get('upload_date'),
                view_count=video_info.get('view_count'),
                like_count=video_info.get('like_count')
            )
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"Error fetching YouTube metadata: {error_msg}")
            raise ValueError(f"Failed to get metadata for YouTube video: {error_msg}")
        except json.JSONDecodeError:
            logger.error("Failed to parse yt-dlp JSON output")
            raise ValueError("Failed to parse video metadata")
        except Exception as e:
            logger.error(f"Unexpected error in get_metadata: {str(e)}")
            raise
    
    def download(self, url: str, format_id: Optional[str] = None, 
                 progress_callback=None) -> str:
        """Download a YouTube video."""
        try:
            video_id = self.extract_id_from_url(url)
            output_template = os.path.join(self.download_dir, f"%(title)s-{video_id}.%(ext)s")
            
            cmd = [
                self.yt_dlp_path,
                "--no-playlist",
                "--no-warnings",
                "-o", output_template
            ]
            
            if format_id:
                cmd.extend(["-f", format_id])
            else:
                cmd.extend(["-f", "best"])
            
            cmd.append(url)
            
            if self.simulation_mode:
                logger.info(f"Simulation mode: Would run command: {' '.join(cmd)}")
                # Return a dummy file path in simulation mode
                return os.path.join(self.download_dir, f"simulation-video-{video_id}.mp4")
            
            if progress_callback:
                # Run with progress updates
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                for line in process.stdout:
                    if "download" in line.lower() and "%" in line:
                        try:
                            # Extract progress percentage
                            match = re.search(r'(\d+\.\d+)%', line)
                            if match:
                                progress = float(match.group(1))
                                progress_callback(progress)
                        except Exception:
                            # Continue even if progress parsing fails
                            pass
                
                process.wait()
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, cmd)
            else:
                # Run without progress updates
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Find the downloaded file
            for file in os.listdir(self.download_dir):
                if video_id in file:
                    return os.path.join(self.download_dir, file)
            
            raise ValueError("Downloaded file not found")
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"Error downloading YouTube video: {error_msg}")
            raise ValueError(f"Failed to download YouTube video: {error_msg}")
        except Exception as e:
            logger.error(f"Unexpected error in download: {str(e)}")
            raise


class TwitterDownloader(BaseDownloader):
    """Downloader for Twitter videos."""
    
    PLATFORM_NAME = "twitter"
    URL_PATTERNS = [
        r'^(https?://)?(www\.)?(twitter\.com|x\.com)/.+$'
    ]
    
    def __init__(self, download_dir: Optional[str] = None, 
                 yt_dlp_path: Optional[str] = None):
        """
        Initialize the Twitter downloader.
        
        Args:
            download_dir: Directory to save downloaded files.
            yt_dlp_path: Path to the yt-dlp executable. If None, assumes it's in PATH.
        """
        super().__init__(download_dir)
        self.yt_dlp_path = yt_dlp_path or "yt-dlp"
    
    def extract_id_from_url(self, url: str) -> str:
        """Extract the tweet ID from a Twitter URL."""
        # Support both twitter.com and x.com
        match = re.search(r'/(status|statuses)/(\d+)', url)
        if not match:
            raise ValueError(f"Could not extract tweet ID from URL: {url}")
        
        tweet_id = match.group(2)
        return tweet_id
    
    def get_metadata(self, url: str) -> VideoMetadata:
        """Get metadata for a Twitter video."""
        try:
            tweet_id = self.extract_id_from_url(url)
            
            # Run yt-dlp to get video info
            cmd = [
                self.yt_dlp_path,
                "--dump-json",
                url
            ]
            
            if self.simulation_mode:
                logger.info(f"Simulation mode: Would run command: {' '.join(cmd)}")
                # Return dummy metadata in simulation mode
                return VideoMetadata(
                    video_id=tweet_id,
                    title=f"Twitter Video {tweet_id}",
                    author="Twitter User",
                    duration=60.0,
                    thumbnail_url="https://example.com/twitter_thumbnail.jpg",
                    platform=self.PLATFORM_NAME,
                    formats=[
                        {"format_id": "best", "ext": "mp4", "resolution": "720p", 
                         "filesize": 1024*1024*5}
                    ],
                    original_url=url
                )
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            video_info = json.loads(result.stdout)
            
            # Extract relevant metadata
            formats = []
            for fmt in video_info.get('formats', []):
                if fmt.get('acodec') != 'none' and fmt.get('vcodec') != 'none':
                    formats.append({
                        'format_id': fmt.get('format_id'),
                        'ext': fmt.get('ext'),
                        'resolution': fmt.get('resolution') or f"{fmt.get('width', 0)}x{fmt.get('height', 0)}",
                        'filesize': fmt.get('filesize') or fmt.get('filesize_approx')
                    })
            
            # Twitter videos often don't have proper titles, create one from tweet text
            title = video_info.get('title', '').strip()
            if not title or title == "Twitter":
                # Try to create a title from description or just use tweet ID
                desc = video_info.get('description', '')
                if desc:
                    # Use first 50 chars of description as title
                    title = desc[:50] + ('...' if len(desc) > 50 else '')
                else:
                    title = f"Twitter Video {tweet_id}"
            
            return VideoMetadata(
                video_id=tweet_id,
                title=title,
                author=video_info.get('uploader', 'Unknown User'),
                duration=float(video_info.get('duration', 0)),
                thumbnail_url=video_info.get('thumbnail', ''),
                platform=self.PLATFORM_NAME,
                formats=formats,
                original_url=url,
                description=video_info.get('description'),
                upload_date=video_info.get('upload_date')
            )
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"Error fetching Twitter metadata: {error_msg}")
            raise ValueError(f"Failed to get metadata for Twitter video: {error_msg}")
        except json.JSONDecodeError:
            logger.error("Failed to parse yt-dlp JSON output")
            raise ValueError("Failed to parse video metadata")
        except Exception as e:
            logger.error(f"Unexpected error in get_metadata: {str(e)}")
            raise
    
    def download(self, url: str, format_id: Optional[str] = None, 
                 progress_callback=None) -> str:
        """Download a Twitter video."""
        try:
            tweet_id = self.extract_id_from_url(url)
            output_template = os.path.join(self.download_dir, f"twitter-{tweet_id}.%(ext)s")
            
            cmd = [
                self.yt_dlp_path,
                "--no-warnings",
                "-o", output_template
            ]
            
            if format_id:
                cmd.extend(["-f", format_id])
            else:
                cmd.extend(["-f", "best"])
            
            cmd.append(url)
            
            if self.simulation_mode:
                logger.info(f"Simulation mode: Would run command: {' '.join(cmd)}")
                # Return a dummy file path in simulation mode
                return os.path.join(self.download_dir, f"twitter-{tweet_id}.mp4")
            
            if progress_callback:
                # Run with progress updates
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                for line in process.stdout:
                    if "download" in line.lower() and "%" in line:
                        try:
                            # Extract progress percentage
                            match = re.search(r'(\d+\.\d+)%', line)
                            if match:
                                progress = float(match.group(1))
                                progress_callback(progress)
                        except Exception:
                            # Continue even if progress parsing fails
                            pass
                
                process.wait()
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, cmd)
            else:
                # Run without progress updates
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Find the downloaded file
            for file in os.listdir(self.download_dir):
                if f"twitter-{tweet_id}" in file:
                    return os.path.join(self.download_dir, file)
            
            raise ValueError("Downloaded file not found")
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"Error downloading Twitter video: {error_msg}")
            raise ValueError(f"Failed to download Twitter video: {error_msg}")
        except Exception as e:
            logger.error(f"Unexpected error in download: {str(e)}")
            raise


class DownloaderFactory:
    """Factory for creating platform-specific downloaders."""
    
    _downloaders = {
        "youtube": YouTubeDownloader,
        "twitter": TwitterDownloader,
    }
    
    @classmethod
    def create_downloader(cls, url: str, download_dir: Optional[str] = None) -> BaseDownloader:
        """
        Create a downloader for the given URL.
        
        Args:
            url: The URL to create a downloader for.
            download_dir: Optional directory to save downloaded files.
            
        Returns:
            A downloader instance appropriate for the URL.
            
        Raises:
            ValueError: If no downloader is available for the URL.
        """
        # Try to match URL against known patterns
        for platform, downloader_class in cls._downloaders.items():
            for pattern in downloader_class.URL_PATTERNS:
                if re.match(pattern, url):
                    return downloader_class(download_dir)
        
        # If no pattern matched, try to parse and check domain
        try:
            domain = urlparse(url).netloc.lower()
            
            if "youtube" in domain or "youtu.be" in domain:
                return cls._downloaders["youtube"](download_dir)
            
            if "twitter" in domain or "x.com" in domain:
                return cls._downloaders["twitter"](download_dir)
        except Exception:
            pass
        
        raise ValueError(f"No downloader available for URL: {url}")
    
    @classmethod
    def register_downloader(cls, platform: str, downloader_class: type) -> None:
        """
        Register a new downloader class.
        
        Args:
            platform: The platform identifier.
            downloader_class: The downloader class to register.
        """
        cls._downloaders[platform] = downloader_class


def is_supported_url(url: str) -> bool:
    """
    Check if a URL is supported by any registered downloader.
    
    Args:
        url: The URL to check.
        
    Returns:
        True if the URL is supported, False otherwise.
    """
    try:
        DownloaderFactory.create_downloader(url)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    # Example usage
    import sys
    
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if len(sys.argv) < 2:
        print("Usage: python downloader.py <url> [download_dir]")
        sys.exit(1)
    
    url = sys.argv[1]
    download_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        downloader = DownloaderFactory.create_downloader(url, download_dir)
        print(f"Getting metadata for {url}...")
        metadata = downloader.get_metadata(url)
        print(f"Title: {metadata.title}")
        print(f"Author: {metadata.author}")
        print(f"Duration: {metadata.duration_formatted}")
        print(f"Platform: {metadata.platform}")
        
        print("\nAvailable formats:")
        for i, fmt in enumerate(metadata.formats):
            print(f"{i+1}. Format ID: {fmt.get('format_id')}, "
                  f"Resolution: {fmt.get('resolution')}, "
                  f"Extension: {fmt.get('ext')}, "
                  f"Size: {fmt.get('filesize', 'Unknown')}")
        
        print("\nDownloading video...")
        output_path = downloader.download(url)
        print(f"Video downloaded to: {output_path}")
        
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)