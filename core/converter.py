"""
Audio converter module for SlowJams application.

This module handles the extraction of audio from video files and conversion
between different audio formats with configurable quality settings.
"""

import os
import subprocess
import logging
import tempfile
import json
from typing import Optional, Dict, Any, Callable, Tuple, List
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass

# Import the custom utilities
try:
    from utils.env_loader import get_bool_env
except ImportError:
    # For standalone usage or testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.env_loader import get_bool_env

logger = logging.getLogger(__name__)


class AudioFormat(Enum):
    """Supported audio formats."""
    MP3 = auto()
    WAV = auto()
    FLAC = auto()
    AAC = auto()
    OGG = auto()
    
    @classmethod
    def from_string(cls, format_str: str) -> 'AudioFormat':
        """Convert a string to an AudioFormat enum value."""
        format_map = {
            "mp3": cls.MP3,
            "wav": cls.WAV,
            "flac": cls.FLAC,
            "aac": cls.AAC,
            "m4a": cls.AAC,  # Treat m4a as AAC
            "ogg": cls.OGG
        }
        
        format_str = format_str.lower().strip()
        if format_str not in format_map:
            raise ValueError(f"Unsupported audio format: {format_str}")
        
        return format_map[format_str]
    
    @property
    def extension(self) -> str:
        """Get the file extension for the format."""
        extensions = {
            AudioFormat.MP3: "mp3",
            AudioFormat.WAV: "wav",
            AudioFormat.FLAC: "flac",
            AudioFormat.AAC: "m4a",
            AudioFormat.OGG: "ogg"
        }
        return extensions[self]


@dataclass
class ConversionOptions:
    """Options for audio conversion."""
    
    format: AudioFormat = AudioFormat.MP3
    bitrate: str = "192k"  # For lossy formats
    sample_rate: int = 44100  # Hz
    channels: int = 2  # Stereo
    normalize: bool = False  # Whether to normalize audio levels
    start_time: Optional[float] = None  # Start time in seconds
    end_time: Optional[float] = None  # End time in seconds
    metadata: Optional[Dict[str, str]] = None  # Metadata to embed
    
    @classmethod
    def default_options(cls) -> 'ConversionOptions':
        """Get default conversion options."""
        return cls()
    
    @classmethod
    def high_quality(cls) -> 'ConversionOptions':
        """Get high quality conversion options."""
        return cls(
            format=AudioFormat.MP3,
            bitrate="320k",
            sample_rate=48000,
            normalize=True
        )
    
    @classmethod
    def lossless(cls) -> 'ConversionOptions':
        """Get lossless conversion options."""
        return cls(
            format=AudioFormat.FLAC,
            sample_rate=96000,
            normalize=False
        )


@dataclass
class AudioMetadata:
    """Audio file metadata."""
    
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[str] = None
    track: Optional[str] = None
    genre: Optional[str] = None
    comment: Optional[str] = None
    duration: Optional[float] = None  # Duration in seconds
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    bitrate: Optional[int] = None  # Bitrate in kbps
    
    def to_ffmpeg_metadata(self) -> Dict[str, str]:
        """Convert to FFmpeg metadata format."""
        metadata = {}
        
        if self.title:
            metadata["title"] = self.title
        if self.artist:
            metadata["artist"] = self.artist
        if self.album:
            metadata["album"] = self.album
        if self.year:
            metadata["date"] = self.year
        if self.track:
            metadata["track"] = self.track
        if self.genre:
            metadata["genre"] = self.genre
        if self.comment:
            metadata["comment"] = self.comment
            
        return metadata
    
    @classmethod
    def from_ffprobe_data(cls, data: Dict[str, Any]) -> 'AudioMetadata':
        """Create AudioMetadata from ffprobe output."""
        try:
            # Extract duration and technical details from format section
            format_data = data.get("format", {})
            duration = float(format_data.get("duration", 0))
            bitrate = int(int(format_data.get("bit_rate", 0)) / 1000)  # Convert to kbps
            
            # Find the audio stream
            audio_stream = None
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    audio_stream = stream
                    break
            
            if not audio_stream:
                return cls(duration=duration, bitrate=bitrate)
            
            # Extract technical details from audio stream
            sample_rate = int(audio_stream.get("sample_rate", 0))
            channels = int(audio_stream.get("channels", 0))
            
            # Extract metadata
            tags = {}
            # Check format tags
            if "tags" in format_data:
                tags.update(format_data["tags"])
            # Check stream tags (may override format tags)
            if "tags" in audio_stream:
                tags.update(audio_stream["tags"])
            
            # Normalize tag keys to lowercase for case-insensitive matching
            tags = {k.lower(): v for k, v in tags.items()}
            
            # Extract common metadata fields
            title = tags.get("title")
            artist = tags.get("artist") or tags.get("album_artist")
            album = tags.get("album")
            year = tags.get("date") or tags.get("year")
            track = tags.get("track")
            genre = tags.get("genre")
            comment = tags.get("comment")
            
            return cls(
                title=title,
                artist=artist,
                album=album,
                year=year,
                track=track,
                genre=genre,
                comment=comment,
                duration=duration,
                sample_rate=sample_rate,
                channels=channels,
                bitrate=bitrate
            )
            
        except Exception as e:
            logger.error(f"Error extracting metadata from ffprobe data: {str(e)}")
            return cls()


class AudioConverter:
    """
    Class for converting between audio formats and extracting audio from videos.
    Uses FFmpeg for conversion operations.
    """
    
    def __init__(self, ffmpeg_path: Optional[str] = None, 
                 ffprobe_path: Optional[str] = None,
                 temp_dir: Optional[str] = None):
        """
        Initialize the audio converter.
        
        Args:
            ffmpeg_path: Path to the FFmpeg executable. If None, assumes it's in PATH.
            ffprobe_path: Path to the FFprobe executable. If None, assumes it's in PATH.
            temp_dir: Directory for temporary files. If None, uses system temp dir.
        """
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"
        self.ffprobe_path = ffprobe_path or "ffprobe"
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.simulation_mode = get_bool_env("SIMULATION_MODE", False)
        
    def extract_audio(self, video_path: str, output_path: Optional[str] = None,
                     options: Optional[ConversionOptions] = None,
                     progress_callback: Optional[Callable[[float], None]] = None) -> str:
        """
        Extract audio from a video file.
        
        Args:
            video_path: Path to the video file.
            output_path: Path for the output audio file. If None, generates one.
            options: Conversion options. If None, uses defaults.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            Path to the extracted audio file.
            
        Raises:
            ValueError: If the video file doesn't exist or the extraction fails.
            FileNotFoundError: If FFmpeg is not found.
        """
        if not os.path.exists(video_path):
            raise ValueError(f"Video file not found: {video_path}")
        
        options = options or ConversionOptions.default_options()
        
        # Generate output path if not provided
        if not output_path:
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(
                self.temp_dir, 
                f"{video_name}.{options.format.extension}"
            )
        
        # Build FFmpeg command
        cmd = [self.ffmpeg_path, "-y", "-i", video_path]
        
        # Add time range if specified
        if options.start_time is not None:
            cmd.extend(["-ss", str(options.start_time)])
        if options.end_time is not None:
            cmd.extend(["-to", str(options.end_time)])
        
        # Add audio options
        cmd.extend([
            "-vn",  # No video
            "-ar", str(options.sample_rate),
            "-ac", str(options.channels),
        ])
        
        # Format-specific options
        if options.format == AudioFormat.MP3:
            cmd.extend(["-c:a", "libmp3lame", "-b:a", options.bitrate])
        elif options.format == AudioFormat.FLAC:
            cmd.extend(["-c:a", "flac"])
        elif options.format == AudioFormat.WAV:
            cmd.extend(["-c:a", "pcm_s16le"])
        elif options.format == AudioFormat.AAC:
            cmd.extend(["-c:a", "aac", "-b:a", options.bitrate])
        elif options.format == AudioFormat.OGG:
            cmd.extend(["-c:a", "libvorbis", "-b:a", options.bitrate])
        
        # Normalization if requested
        if options.normalize:
            cmd.extend(["-af", "loudnorm=I=-16:LRA=11:TP=-1.5"])
        
        # Add metadata if provided
        if options.metadata:
            for key, value in options.metadata.items():
                cmd.extend(["-metadata", f"{key}={value}"])
        
        # Output file
        cmd.append(output_path)
        
        if self.simulation_mode:
            logger.info(f"Simulation mode: Would run command: {' '.join(cmd)}")
            # Create a small dummy audio file in simulation mode
            with open(output_path, "wb") as f:
                f.write(b"\0" * 1024)  # 1KB dummy file
            return output_path
        
        try:
            if progress_callback:
                # Get video duration for progress calculation
                duration = self._get_duration(video_path)
                
                # Run with progress monitoring
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                for line in iter(process.stdout.readline, ""):
                    # Parse time information from FFmpeg output
                    if "time=" in line:
                        time_str = line.split("time=")[1].split(" ")[0].strip()
                        try:
                            # Convert HH:MM:SS.MS to seconds
                            h, m, s = time_str.split(":")
                            current_time = float(h) * 3600 + float(m) * 60 + float(s)
                            if duration > 0:
                                progress = min(100.0, (current_time / duration) * 100.0)
                                progress_callback(progress)
                        except (ValueError, IndexError):
                            pass
                
                process.wait()
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, cmd)
            else:
                # Run without progress monitoring
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                
            return output_path
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if hasattr(e, 'stderr') and e.stderr else str(e)
            logger.error(f"FFmpeg error during audio extraction: {error_msg}")
            raise ValueError(f"Failed to extract audio: {error_msg}")
        except FileNotFoundError:
            logger.error(f"FFmpeg not found at {self.ffmpeg_path}")
            raise FileNotFoundError(f"FFmpeg not found at {self.ffmpeg_path}")
        except Exception as e:
            logger.error(f"Unexpected error during audio extraction: {str(e)}")
            raise
    
    def convert_audio(self, input_path: str, output_path: Optional[str] = None,
                     options: Optional[ConversionOptions] = None,
                     progress_callback: Optional[Callable[[float], None]] = None) -> str:
        """
        Convert an audio file to a different format or quality.
        
        Args:
            input_path: Path to the input audio file.
            output_path: Path for the output audio file. If None, generates one.
            options: Conversion options. If None, uses defaults.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            Path to the converted audio file.
            
        Raises:
            ValueError: If the input file doesn't exist or the conversion fails.
            FileNotFoundError: If FFmpeg is not found.
        """
        if not os.path.exists(input_path):
            raise ValueError(f"Input audio file not found: {input_path}")
        
        options = options or ConversionOptions.default_options()
        
        # Generate output path if not provided
        if not output_path:
            input_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(
                self.temp_dir, 
                f"{input_name}.{options.format.extension}"
            )
        
        # Read original metadata if available and none provided in options
        original_metadata = None
        if not options.metadata:
            try:
                original_metadata = self.get_metadata(input_path)
                if original_metadata:
                    options.metadata = original_metadata.to_ffmpeg_metadata()
            except Exception as e:
                logger.warning(f"Failed to read original metadata: {str(e)}")
        
        # Build FFmpeg command
        cmd = [self.ffmpeg_path, "-y", "-i", input_path]
        
        # Add time range if specified
        if options.start_time is not None:
            cmd.extend(["-ss", str(options.start_time)])
        if options.end_time is not None:
            cmd.extend(["-to", str(options.end_time)])
        
        # Add audio options
        cmd.extend([
            "-ar", str(options.sample_rate),
            "-ac", str(options.channels),
        ])
        
        # Format-specific options
        if options.format == AudioFormat.MP3:
            cmd.extend(["-c:a", "libmp3lame", "-b:a", options.bitrate])
        elif options.format == AudioFormat.FLAC:
            cmd.extend(["-c:a", "flac"])
        elif options.format == AudioFormat.WAV:
            cmd.extend(["-c:a", "pcm_s16le"])
        elif options.format == AudioFormat.AAC:
            cmd.extend(["-c:a", "aac", "-b:a", options.bitrate])
        elif options.format == AudioFormat.OGG:
            cmd.extend(["-c:a", "libvorbis", "-b:a", options.bitrate])
        
        # Normalization if requested
        if options.normalize:
            cmd.extend(["-af", "loudnorm=I=-16:LRA=11:TP=-1.5"])
        
        # Add metadata if provided
        if options.metadata:
            for key, value in options.metadata.items():
                cmd.extend(["-metadata", f"{key}={value}"])
        
        # Output file
        cmd.append(output_path)
        
        if self.simulation_mode:
            logger.info(f"Simulation mode: Would run command: {' '.join(cmd)}")
            # Create a small dummy audio file in simulation mode
            with open(output_path, "wb") as f:
                f.write(b"\0" * 1024)  # 1KB dummy file
            return output_path
        
        try:
            if progress_callback:
                # Get audio duration for progress calculation
                duration = self._get_duration(input_path)
                
                # Run with progress monitoring
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                for line in iter(process.stdout.readline, ""):
                    # Parse time information from FFmpeg output
                    if "time=" in line:
                        time_str = line.split("time=")[1].split(" ")[0].strip()
                        try:
                            # Convert HH:MM:SS.MS to seconds
                            h, m, s = time_str.split(":")
                            current_time = float(h) * 3600 + float(m) * 60 + float(s)
                            if duration > 0:
                                progress = min(100.0, (current_time / duration) * 100.0)
                                progress_callback(progress)
                        except (ValueError, IndexError):
                            pass
                
                process.wait()
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, cmd)
            else:
                # Run without progress monitoring
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                
            return output_path
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if hasattr(e, 'stderr') and e.stderr else str(e)
            logger.error(f"FFmpeg error during audio conversion: {error_msg}")
            raise ValueError(f"Failed to convert audio: {error_msg}")
        except FileNotFoundError:
            logger.error(f"FFmpeg not found at {self.ffmpeg_path}")
            raise FileNotFoundError(f"FFmpeg not found at {self.ffmpeg_path}")
        except Exception as e:
            logger.error(f"Unexpected error during audio conversion: {str(e)}")
            raise
    
    def get_metadata(self, file_path: str) -> Optional[AudioMetadata]:
        """
        Get metadata from an audio or video file.
        
        Args:
            file_path: Path to the media file.
            
        Returns:
            AudioMetadata object if successful, None otherwise.
            
        Raises:
            ValueError: If the file doesn't exist or is not a valid media file.
            FileNotFoundError: If FFprobe is not found.
        """
        if not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")
        
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        
        if self.simulation_mode:
            logger.info(f"Simulation mode: Would run command: {' '.join(cmd)}")
            # Return dummy metadata in simulation mode
            return AudioMetadata(
                title="Simulation Audio",
                artist="Simulation Artist",
                duration=180.0,
                sample_rate=44100,
                channels=2,
                bitrate=192
            )
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            return AudioMetadata.from_ffprobe_data(data)
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.error(f"FFprobe error: {error_msg}")
            raise ValueError(f"Failed to get metadata: {error_msg}")
        except json.JSONDecodeError:
            logger.error("Failed to parse FFprobe JSON output")
            raise ValueError("Failed to parse media metadata")
        except FileNotFoundError:
            logger.error(f"FFprobe not found at {self.ffprobe_path}")
            raise FileNotFoundError(f"FFprobe not found at {self.ffprobe_path}")
        except Exception as e:
            logger.error(f"Unexpected error getting metadata: {str(e)}")
            raise
    
    def _get_duration(self, file_path: str) -> float:
        """
        Get the duration of a media file in seconds.
        
        Args:
            file_path: Path to the media file.
            
        Returns:
            Duration in seconds, or 0 if not available.
        """
        try:
            metadata = self.get_metadata(file_path)
            return metadata.duration if metadata and metadata.duration else 0
        except Exception:
            logger.warning(f"Couldn't get duration for {file_path}")
            return 0


if __name__ == "__main__":
    # Example usage
    import sys
    
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if len(sys.argv) < 2:
        print("Usage: python converter.py <input_file> [output_file]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        converter = AudioConverter()
        
        # Get metadata
        print(f"Getting metadata for {input_file}...")
        metadata = converter.get_metadata(input_file)
        print(f"Title: {metadata.title}")
        print(f"Artist: {metadata.artist}")
        print(f"Duration: {metadata.duration:.2f} seconds")
        print(f"Sample Rate: {metadata.sample_rate} Hz")
        print(f"Channels: {metadata.channels}")
        print(f"Bitrate: {metadata.bitrate} kbps")
        
        # Extract audio if it's a video, or convert if it's audio
        print(f"\nProcessing {input_file}...")
        
        # Simple progress callback
        def progress_callback(progress):
            print(f"Progress: {progress:.1f}%", end="\r")
        
        # Check if it's a video or audio file
        if os.path.splitext(input_file)[1].lower() in ['.mp4', '.mkv', '.webm', '.avi', '.mov']:
            print("Extracting audio from video...")
            options = ConversionOptions(
                format=AudioFormat.MP3,
                bitrate="320k",
                normalize=True
            )
            result = converter.extract_audio(
                input_file, 
                output_file, 
                options,
                progress_callback
            )
        else:
            print("Converting audio...")
            options = ConversionOptions(
                format=AudioFormat.MP3 if not output_file else 
                       AudioFormat.from_string(os.path.splitext(output_file)[1][1:]),
                bitrate="320k",
                normalize=True
            )
            result = converter.convert_audio(
                input_file, 
                output_file, 
                options,
                progress_callback
            )
            
        print(f"\nProcessing complete. Output saved to: {result}")
        
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {str(e)}")
        print("Make sure FFmpeg and FFprobe are installed and in your PATH.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)