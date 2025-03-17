# SlowJams: YouTube and Twitter to Slowed MP3 Converter

## Overview

SlowJams is a desktop application that allows users to download videos from YouTube and Twitter, convert them to MP3 audio files, apply AI-powered effects (including slowing down the audio), and save the processed MP3 files. The application provides a user-friendly interface with batch processing capabilities, theme customization, and advanced audio editing features.

## Features

- **Multi-platform Video Download**: Download videos from YouTube and Twitter with URL detection
- **Video to MP3 Conversion**: Convert downloaded videos to high-quality MP3 files
- **AI-Powered Audio Processing**: Slow down audio while maintaining quality using AI techniques
- **Advanced Audio Editing**: Trim audio, adjust volume, and apply effects
- **Batch Processing**: Process multiple files at once with progress tracking
- **Theme Customization**: Choose between light, dark, or system theme
- **User Preferences**: Save and restore user settings
- **Drag and Drop Support**: Easy file handling with drag and drop functionality
- **Progress Visualization**: Clear visual feedback during processing operations
- **Audio Visualization**: Waveform displays for audio files

## Installation

### Prerequisites

- Python 3.8 or higher
- Required Python packages (see requirements.txt)
- FFmpeg (for audio processing)

### Setup

1. Clone this repository
2. Install the dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and adjust settings as needed
4. Run the application: `python main.py`

## Usage

### Download Videos

1. Enter a YouTube or Twitter video URL in the Download tab
2. Click "Download" to fetch the video
3. The application will automatically detect the platform and download the video

### Convert to MP3

1. After downloading, switch to the Convert tab
2. Select the downloaded video file
3. Configure conversion settings (bitrate, sample rate)
4. Click "Convert" to generate the MP3 file

### Edit Audio

1. Switch to the Edit tab
2. Load the MP3 file
3. Use the trimming controls to select the desired portion
4. Adjust volume as needed
5. Save the edited audio

### Apply AI Processing

1. Navigate to the AI Processing tab
2. Load the MP3 file
3. Configure the slowing factor and other AI settings
4. Click "Apply" to process the audio
5. Save the processed MP3

### Batch Processing

1. Add multiple files to the batch processing queue
2. Configure settings for all files
3. Start batch processing
4. Monitor progress in the batch processing dialog

## Project Structure

- `main.py`: Application entry point
- `core/`: Core processing logic
- `ui/`: User interface components
- `data/`: Data management
- `utils/`: Utility functions
- `resources/`: Application resources
- `project-docs/`: Project documentation

## Configuration

Application settings can be configured through the `.env` file or via the Preferences dialog in the application.

## Development

### Testing

Run the test suite with: `python run_tests.py`

### Adding New Features

See the project documentation in the `project-docs/` directory for development guidelines.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- PyQt5 for the UI framework
- yt-dlp for YouTube downloading
- FFmpeg for audio processing
- Various AI models for audio manipulation