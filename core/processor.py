"""
Audio processor module for SlowJams application.

This module handles the audio manipulation effects, such as slowing down audio
while preserving pitch, adding reverb, and other effects.
"""

import os
import logging
import tempfile
import subprocess
import json
import numpy as np
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List, Tuple, Union

# Try to import optional libraries
try:
    import librosa
    import librosa.effects
    import soundfile as sf
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

# Import from core package
try:
    from core.converter import AudioConverter, AudioFormat, ConversionOptions
except ImportError:
    # For standalone usage or testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.converter import AudioConverter, AudioFormat, ConversionOptions

# Import the custom utilities
try:
    from utils.env_loader import get_bool_env
except ImportError:
    # For standalone usage or testing
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.env_loader import get_bool_env

logger = logging.getLogger(__name__)


class EffectType(Enum):
    """Types of audio effects supported by the processor."""
    SLOW = auto()       # Slow down audio with pitch preservation
    REVERB = auto()     # Add reverb effect
    PITCH = auto()      # Change pitch without changing speed
    VOLUME = auto()     # Adjust volume
    EQUALIZER = auto()  # Apply equalization
    CHORUS = auto()     # Add chorus effect
    NOISE_REDUCTION = auto()  # Reduce background noise


@dataclass
class ProcessingOptions:
    """Options for audio processing effects."""
    
    # General options
    temp_dir: Optional[str] = None
    output_format: AudioFormat = AudioFormat.MP3
    output_bitrate: str = "320k"
    normalize_output: bool = True
    preserve_metadata: bool = True
    
    # Slow effect options
    slow_factor: float = 0.8  # Speed factor (0.5 = half speed, 2.0 = double speed)
    preserve_pitch: bool = True  # Whether to preserve pitch when changing speed
    
    # Reverb effect options
    reverb_enabled: bool = False
    reverb_room_size: float = 0.5  # 0.0 to 1.0
    reverb_damping: float = 0.5  # 0.0 to 1.0
    reverb_wet_level: float = 0.3  # 0.0 to 1.0
    reverb_dry_level: float = 0.7  # 0.0 to 1.0
    
    # Pitch effect options
    pitch_enabled: bool = False
    pitch_semitones: float = 0.0  # Semitones to shift (-12 to 12)
    
    # Volume effect options
    volume_enabled: bool = False
    volume_gain_db: float = 0.0  # Volume gain in dB (-20 to 20)
    
    # Equalizer options
    equalizer_enabled: bool = False
    equalizer_bands: Dict[str, float] = field(default_factory=dict)  # Frequency bands and gains
    
    # Chorus effect options
    chorus_enabled: bool = False
    chorus_delay: float = 0.05  # Delay in seconds (0.01 to 0.1)
    chorus_depth: float = 0.5  # Depth (0.0 to 1.0)
    chorus_rate: float = 0.5  # Rate in Hz (0.1 to 5.0)
    
    # Noise reduction options
    noise_reduction_enabled: bool = False
    noise_reduction_amount: float = 0.5  # Amount of reduction (0.0 to 1.0)
    
    @classmethod
    def slow_jam_preset(cls) -> 'ProcessingOptions':
        """Preset for the classic "slowed + reverb" effect."""
        return cls(
            slow_factor=0.8,  # 80% of original speed
            preserve_pitch=True,
            reverb_enabled=True,
            reverb_room_size=0.6,
            reverb_wet_level=0.4,
            reverb_dry_level=0.6,
            normalize_output=True
        )
    
    @classmethod
    def chopped_and_screwed_preset(cls) -> 'ProcessingOptions':
        """Preset inspired by the Houston "chopped and screwed" style."""
        return cls(
            slow_factor=0.7,  # 70% of original speed
            preserve_pitch=False,  # Lower pitch
            reverb_enabled=True,
            reverb_room_size=0.5,
            reverb_wet_level=0.3,
            normalize_output=True
        )
    
    @classmethod
    def vaporwave_preset(cls) -> 'ProcessingOptions':
        """Preset for vaporwave-style audio."""
        return cls(
            slow_factor=0.75,  # 75% of original speed
            preserve_pitch=False,
            reverb_enabled=True,
            reverb_room_size=0.7,
            reverb_wet_level=0.5,
            pitch_enabled=True,
            pitch_semitones=-1.0,  # Slight pitch down
            chorus_enabled=True,
            chorus_depth=0.7,
            normalize_output=True
        )


class AudioProcessor:
    """
    Class for processing audio with various effects.
    Can use either FFmpeg or librosa depending on availability and requirements.
    """
    
    def __init__(self, ffmpeg_path: Optional[str] = None, 
                 ffprobe_path: Optional[str] = None,
                 temp_dir: Optional[str] = None):
        """
        Initialize the audio processor.
        
        Args:
            ffmpeg_path: Path to the FFmpeg executable. If None, assumes it's in PATH.
            ffprobe_path: Path to the FFprobe executable. If None, assumes it's in PATH.
            temp_dir: Directory for temporary files. If None, uses system temp dir.
        """
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"
        self.ffprobe_path = ffprobe_path or "ffprobe"
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.simulation_mode = get_bool_env("SIMULATION_MODE", False)
        self.converter = AudioConverter(ffmpeg_path, ffprobe_path, temp_dir)
        
        # Log whether librosa is available
        if LIBROSA_AVAILABLE:
            logger.info("Librosa available for advanced audio processing")
        else:
            logger.info("Librosa not available, falling back to FFmpeg for all processing")
    
    def process_audio(self, input_path: str, output_path: Optional[str] = None,
                     options: Optional[ProcessingOptions] = None,
                     progress_callback: Optional[Callable[[float], None]] = None) -> str:
        """
        Process audio with the specified effects.
        
        Args:
            input_path: Path to the input audio file.
            output_path: Path for the output audio file. If None, generates one.
            options: Processing options. If None, uses defaults.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            Path to the processed audio file.
            
        Raises:
            ValueError: If the input file doesn't exist or processing fails.
            FileNotFoundError: If required executables are not found.
        """
        if not os.path.exists(input_path):
            raise ValueError(f"Input audio file not found: {input_path}")
        
        options = options or ProcessingOptions()
        temp_dir = options.temp_dir or self.temp_dir
        
        # Generate output path if not provided
        if not output_path:
            input_name = os.path.splitext(os.path.basename(input_path))[0]
            output_path = os.path.join(
                temp_dir, 
                f"{input_name}_processed.{options.output_format.extension}"
            )
        
        # Get original metadata if preserving
        original_metadata = None
        if options.preserve_metadata:
            try:
                original_metadata = self.converter.get_metadata(input_path)
            except Exception as e:
                logger.warning(f"Failed to read original metadata: {str(e)}")
        
        # Choose processing method based on options and available libraries
        if options.slow_factor != 1.0 and options.preserve_pitch and LIBROSA_AVAILABLE:
            # Use librosa for high-quality time stretching with pitch preservation
            return self._process_with_librosa(
                input_path, output_path, options, original_metadata, progress_callback
            )
        else:
            # Use FFmpeg for other effects or if librosa is not available
            return self._process_with_ffmpeg(
                input_path, output_path, options, original_metadata, progress_callback
            )
    
    def _process_with_librosa(self, input_path: str, output_path: str,
                            options: ProcessingOptions, 
                            original_metadata: Any,
                            progress_callback: Optional[Callable[[float], None]] = None) -> str:
        """
        Process audio using librosa for high-quality results.
        
        Args:
            input_path: Path to the input audio file.
            output_path: Path for the output audio file.
            options: Processing options.
            original_metadata: Original audio metadata, if available.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            Path to the processed audio file.
        """
        if self.simulation_mode:
            logger.info("Simulation mode: Would process audio with librosa")
            # Create a small dummy audio file in simulation mode
            with open(output_path, "wb") as f:
                f.write(b"\0" * 1024)  # 1KB dummy file
            return output_path
        
        try:
            # Load audio file with progress reporting
            if progress_callback:
                progress_callback(0.0)
                logger.info(f"Loading audio file: {input_path}")
            
            # Load audio with librosa
            y, sr = librosa.load(input_path, sr=None, mono=True)
            
            if progress_callback:
                progress_callback(10.0)
                logger.info("Audio loaded, applying effects")
            
            # Apply slow effect (time stretching)
            if options.slow_factor != 1.0:
                # Time stretching with pitch preservation
                y = librosa.effects.time_stretch(y, rate=options.slow_factor)
                
                if progress_callback:
                    progress_callback(40.0)
                    logger.info(f"Applied time stretching with factor {options.slow_factor}")
            
            # Apply pitch shifting if enabled
            if options.pitch_enabled and options.pitch_semitones != 0.0:
                y = librosa.effects.pitch_shift(y, sr=sr, n_steps=options.pitch_semitones)
                
                if progress_callback:
                    progress_callback(60.0)
                    logger.info(f"Applied pitch shifting of {options.pitch_semitones} semitones")
            
            # Apply volume adjustment if enabled
            if options.volume_enabled and options.volume_gain_db != 0.0:
                gain_factor = 10 ** (options.volume_gain_db / 20.0)
                y = y * gain_factor
                
                if progress_callback:
                    progress_callback(70.0)
                    logger.info(f"Applied volume gain of {options.volume_gain_db} dB")
            
            # Normalize output if requested
            if options.normalize_output:
                max_val = np.max(np.abs(y))
                if max_val > 0:
                    y = y / max_val * 0.95  # 95% of maximum to avoid clipping
                
                if progress_callback:
                    progress_callback(80.0)
                    logger.info("Applied normalization")
            
            # Save processed audio to a temporary WAV file
            temp_wav_path = os.path.join(self.temp_dir, "temp_processed.wav")
            sf.write(temp_wav_path, y, sr)
            
            if progress_callback:
                progress_callback(90.0)
                logger.info("Saved processed audio, applying final conversion")
            
            # Convert to final format with FFmpeg to apply any remaining effects
            # and ensure proper format and metadata
            conv_options = ConversionOptions(
                format=options.output_format,
                bitrate=options.output_bitrate,
                metadata=original_metadata.to_ffmpeg_metadata() if original_metadata else None
            )
            
            # Apply reverb and other effects during the final conversion
            if (options.reverb_enabled or 
                options.chorus_enabled or 
                options.equalizer_enabled or 
                options.noise_reduction_enabled):
                
                # Build FFmpeg filter chain for remaining effects
                filters = []
                
                # Add reverb filter
                if options.reverb_enabled:
                    reverb_filter = (
                        f"aecho=0.8:{options.reverb_room_size * 1000}:"
                        f"{options.reverb_damping * 1000}:{options.reverb_wet_level}"
                    )
                    filters.append(reverb_filter)
                
                # Add chorus filter
                if options.chorus_enabled:
                    chorus_filter = (
                        f"chorus=0.5:{options.chorus_depth}:"
                        f"{options.chorus_rate}:{options.chorus_delay * 1000}:0.5:0.5"
                    )
                    filters.append(chorus_filter)
                
                # Add equalizer filter
                if options.equalizer_enabled and options.equalizer_bands:
                    eq_parts = []
                    for band, gain in options.equalizer_bands.items():
                        eq_parts.append(f"equalizer=f={band}:width_type=h:width=200:g={gain}")
                    filters.extend(eq_parts)
                
                # Add noise reduction filter
                if options.noise_reduction_enabled:
                    # Use FFmpeg's basic noise reduction
                    nr_filter = f"anlmdn=s={options.noise_reduction_amount}"
                    filters.append(nr_filter)
                
                # Apply filters in FFmpeg
                filter_chain = ",".join(filters)
                
                cmd = [
                    self.ffmpeg_path, "-y",
                    "-i", temp_wav_path,
                    "-af", filter_chain
                ]
                
                # Add format-specific options
                if options.output_format == AudioFormat.MP3:
                    cmd.extend(["-c:a", "libmp3lame", "-b:a", options.output_bitrate])
                elif options.output_format == AudioFormat.FLAC:
                    cmd.extend(["-c:a", "flac"])
                elif options.output_format == AudioFormat.WAV:
                    cmd.extend(["-c:a", "pcm_s16le"])
                elif options.output_format == AudioFormat.AAC:
                    cmd.extend(["-c:a", "aac", "-b:a", options.output_bitrate])
                elif options.output_format == AudioFormat.OGG:
                    cmd.extend(["-c:a", "libvorbis", "-b:a", options.output_bitrate])
                
                # Add metadata if available
                if original_metadata:
                    for key, value in original_metadata.to_ffmpeg_metadata().items():
                        cmd.extend(["-metadata", f"{key}={value}"])
                
                cmd.append(output_path)
                
                # Execute FFmpeg for final processing
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            else:
                # No additional effects, just convert to final format
                self.converter.convert_audio(temp_wav_path, output_path, conv_options)
            
            # Clean up temporary file
            try:
                os.remove(temp_wav_path)
            except Exception:
                pass
            
            if progress_callback:
                progress_callback(100.0)
                logger.info("Processing complete")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error processing audio with librosa: {str(e)}")
            # Fall back to FFmpeg processing
            logger.info("Falling back to FFmpeg processing")
            return self._process_with_ffmpeg(
                input_path, output_path, options, original_metadata, progress_callback
            )
    
    def _process_with_ffmpeg(self, input_path: str, output_path: str,
                           options: ProcessingOptions, 
                           original_metadata: Any,
                           progress_callback: Optional[Callable[[float], None]] = None) -> str:
        """
        Process audio using FFmpeg.
        
        Args:
            input_path: Path to the input audio file.
            output_path: Path for the output audio file.
            options: Processing options.
            original_metadata: Original audio metadata, if available.
            progress_callback: Optional callback for progress updates.
            
        Returns:
            Path to the processed audio file.
        """
        # Build FFmpeg filter chain for all effects
        filters = []
        
        # Add speed/tempo effect
        if options.slow_factor != 1.0:
            if options.preserve_pitch:
                # Use ATEMPO filter for speed change with pitch preservation
                # ATEMPO has a limited range (0.5 to 2.0), so chain multiple instances if needed
                atempo_factor = options.slow_factor
                
                # Handle factors outside the valid range
                if atempo_factor < 0.5:
                    # Chain multiple atempo filters (e.g., 0.25 = 0.5 * 0.5)
                    atempo_chain = []
                    while atempo_factor < 0.5:
                        atempo_chain.append("atempo=0.5")
                        atempo_factor /= 0.5
                    atempo_chain.append(f"atempo={atempo_factor:.4f}")
                    filters.append(",".join(atempo_chain))
                elif atempo_factor > 2.0:
                    # Chain multiple atempo filters (e.g., 4.0 = 2.0 * 2.0)
                    atempo_chain = []
                    while atempo_factor > 2.0:
                        atempo_chain.append("atempo=2.0")
                        atempo_factor /= 2.0
                    atempo_chain.append(f"atempo={atempo_factor:.4f}")
                    filters.append(",".join(atempo_chain))
                else:
                    # Within valid range
                    filters.append(f"atempo={atempo_factor:.4f}")
            else:
                # Use ASETRATE to change speed (affects pitch)
                # Get original sample rate
                original_sr = 44100  # default
                try:
                    metadata = self.converter.get_metadata(input_path)
                    if metadata and metadata.sample_rate:
                        original_sr = metadata.sample_rate
                except Exception:
                    pass
                
                # Change rate to slow down/speed up
                new_sr = int(original_sr / options.slow_factor)
                filters.append(f"asetrate={new_sr}")
        
        # Add reverb effect
        if options.reverb_enabled:
            # Use aecho filter as a simple reverb
            reverb_filter = (
                f"aecho=0.8:{options.reverb_room_size * 1000}:"
                f"{options.reverb_damping * 1000}:{options.reverb_wet_level}"
            )
            filters.append(reverb_filter)
        
        # Add pitch shift effect
        if options.pitch_enabled and options.pitch_semitones != 0.0:
            # Use RUBBERBAND (if available) or simple asetrate+atempo combination
            try:
                # Check if RUBBERBAND is available
                result = subprocess.run(
                    [self.ffmpeg_path, "-filters"],
                    capture_output=True, text=True, check=True
                )
                if "rubberband" in result.stdout:
                    # Use RUBBERBAND for better quality pitch shifting
                    filters.append(f"rubberband=pitch={options.pitch_semitones}")
                else:
                    # Fallback method: combine asetrate and atempo
                    # This shifts pitch but tries to preserve duration
                    pitch_factor = 2 ** (options.pitch_semitones / 12.0)
                    filters.append(f"asetrate={44100 * pitch_factor}")
                    filters.append(f"atempo={1.0/pitch_factor}")
            except Exception:
                # Simple fallback method
                pitch_factor = 2 ** (options.pitch_semitones / 12.0)
                filters.append(f"asetrate={44100 * pitch_factor}")
                filters.append(f"atempo={1.0/pitch_factor}")
        
        # Add volume adjustment
        if options.volume_enabled and options.volume_gain_db != 0.0:
            filters.append(f"volume={options.volume_gain_db}dB")
        
        # Add equalizer
        if options.equalizer_enabled and options.equalizer_bands:
            eq_parts = []
            for band, gain in options.equalizer_bands.items():
                eq_parts.append(f"equalizer=f={band}:width_type=h:width=200:g={gain}")
            filters.extend(eq_parts)
        
        # Add chorus effect
        if options.chorus_enabled:
            chorus_filter = (
                f"chorus=0.5:{options.chorus_depth}:"
                f"{options.chorus_rate}:{options.chorus_delay * 1000}:0.5:0.5"
            )
            filters.append(chorus_filter)
        
        # Add noise reduction
        if options.noise_reduction_enabled:
            # Use FFmpeg's basic noise reduction
            filters.append(f"anlmdn=s={options.noise_reduction_amount}")
        
        # Add normalization if requested
        if options.normalize_output:
            filters.append("loudnorm=I=-16:LRA=11:TP=-1.5")
        
        # Build the FFmpeg command
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", input_path
        ]
        
        # Add filter chain if any filters were specified
        if filters:
            filter_chain = ",".join(filters)
            cmd.extend(["-af", filter_chain])
        
        # Add format-specific options
        if options.output_format == AudioFormat.MP3:
            cmd.extend(["-c:a", "libmp3lame", "-b:a", options.output_bitrate])
        elif options.output_format == AudioFormat.FLAC:
            cmd.extend(["-c:a", "flac"])
        elif options.output_format == AudioFormat.WAV:
            cmd.extend(["-c:a", "pcm_s16le"])
        elif options.output_format == AudioFormat.AAC:
            cmd.extend(["-c:a", "aac", "-b:a", options.output_bitrate])
        elif options.output_format == AudioFormat.OGG:
            cmd.extend(["-c:a", "libvorbis", "-b:a", options.output_bitrate])
        
        # Add metadata if available
        if original_metadata:
            for key, value in original_metadata.to_ffmpeg_metadata().items():
                cmd.extend(["-metadata", f"{key}={value}"])
        
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
            logger.error(f"FFmpeg error during audio processing: {error_msg}")
            raise ValueError(f"Failed to process audio: {error_msg}")
        except FileNotFoundError:
            logger.error(f"FFmpeg not found at {self.ffmpeg_path}")
            raise FileNotFoundError(f"FFmpeg not found at {self.ffmpeg_path}")
        except Exception as e:
            logger.error(f"Unexpected error during audio processing: {str(e)}")
            raise
    
    def preview_effect(self, input_path: str, effect_type: EffectType,
                     options: Optional[ProcessingOptions] = None,
                     duration: float = 10.0,
                     offset: float = 30.0) -> str:
        """
        Create a short preview of an effect applied to an audio file.
        
        Args:
            input_path: Path to the input audio file.
            effect_type: Type of effect to preview.
            options: Processing options. If None, uses defaults.
            duration: Duration of the preview in seconds.
            offset: Starting offset into the audio in seconds.
            
        Returns:
            Path to the preview audio file.
            
        Raises:
            ValueError: If the input file doesn't exist or processing fails.
        """
        if not os.path.exists(input_path):
            raise ValueError(f"Input audio file not found: {input_path}")
        
        options = options or ProcessingOptions()
        
        # Create a temporary file for the preview
        preview_output = os.path.join(
            self.temp_dir, 
            f"preview_{effect_type.name.lower()}.{options.output_format.extension}"
        )
        
        # Extract the preview segment from the input file
        total_duration = self._get_duration(input_path)
        
        # Adjust offset if it exceeds the file duration
        if offset >= total_duration:
            offset = max(0, total_duration / 2 - duration / 2)
        
        # Adjust duration if it exceeds the remaining file duration
        if offset + duration > total_duration:
            duration = max(1.0, total_duration - offset)
        
        # Create a temporary options object with time range
        preview_options = ProcessingOptions(**vars(options))
        
        # Process the audio segment
        temp_segment = os.path.join(self.temp_dir, "preview_segment.wav")
        
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", input_path,
            "-ss", str(offset),
            "-t", str(duration),
            "-c:a", "pcm_s16le",
            temp_segment
        ]
        
        if self.simulation_mode:
            logger.info(f"Simulation mode: Would run command: {' '.join(cmd)}")
            # Create a small dummy audio file in simulation mode
            with open(temp_segment, "wb") as f:
                f.write(b"\0" * 1024)  # 1KB dummy file
        else:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # Process the segment with the desired effect
        try:
            result = self.process_audio(temp_segment, preview_output, options)
            
            # Clean up temporary segment
            try:
                os.remove(temp_segment)
            except Exception:
                pass
                
            return result
            
        except Exception as e:
            # Clean up temporary segment
            try:
                os.remove(temp_segment)
            except Exception:
                pass
                
            logger.error(f"Error creating preview: {str(e)}")
            raise ValueError(f"Failed to create preview: {str(e)}")
    
    def _get_duration(self, file_path: str) -> float:
        """
        Get the duration of a media file in seconds.
        
        Args:
            file_path: Path to the media file.
            
        Returns:
            Duration in seconds, or 0 if not available.
        """
        try:
            metadata = self.converter.get_metadata(file_path)
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
        print("Usage: python processor.py <input_file> [output_file]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        processor = AudioProcessor()
        
        # Simple progress callback
        def progress_callback(progress):
            print(f"Progress: {progress:.1f}%", end="\r")
        
        # Use slow jam preset
        options = ProcessingOptions.slow_jam_preset()
        
        print(f"Processing {input_file} with slow jam preset...")
        print(f"  Speed: {options.slow_factor:.2f}x")
        print(f"  Pitch preservation: {options.preserve_pitch}")
        print(f"  Reverb: {options.reverb_enabled}")
        
        # Process the audio
        result = processor.process_audio(
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