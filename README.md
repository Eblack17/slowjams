# SlowJams

![SlowJams](https://img.shields.io/badge/SlowJams-v0.1.0-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

SlowJams is a powerful desktop application for downloading videos from YouTube and Twitter, converting them to audio, and applying "slowed + reverb" effects for that unique aesthetic sound.

## Features

- **Multi-Platform Support**: Download videos from YouTube and Twitter with ease
- **Audio Extraction**: Extract high-quality audio from videos
- **Audio Effects**:
  - Slow down audio with pitch preservation
  - Add customizable reverb
  - Apply pitch shifting, chorus, and EQ
  - Choose from presets like "Slow Jam", "Chopped & Screwed", and "Vaporwave"
- **Batch Processing**: Process multiple files at once with a queue system
- **Modern UI**: Clean interface with light/dark/system theme support
- **Customization**: Extensive settings for output format, quality, and effects
- **Progress Visualization**: See real-time progress for all operations
- **Audio Visualization**: Preview audio waveforms and effects

## Installation

### Prerequisites

- Python 3.10 or higher
- FFmpeg (for audio processing)
- PyQt5 (for UI)

### Install from Source

1. Clone the repository:
```bash
git clone https://github.com/Eblack17/slowjams.git
cd slowjams
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file from the example:
```bash
cp .env.example .env
```

5. Edit the `.env` file to configure your settings.

6. Run the application:
```bash
python main.py
```

## Usage

### Graphical User Interface

Simply run `python main.py` to start the application in GUI mode.

1. Enter a YouTube or Twitter URL in the input field
2. Select your desired effect and settings
3. Click "Download & Process" to begin
4. Monitor progress and access the file when complete

### Command Line Usage

SlowJams can also be used from the command line:

```bash
# Basic usage
python main.py --headless --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Specify output file
python main.py --headless --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --output "output.mp3"

# Choose effect preset
python main.py --headless --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --effect chopped

# Customize speed and format
python main.py --headless --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --speed 0.7 --format flac
```

For more options, run: `python main.py --help`

## Configuration

SlowJams can be configured through the `.env` file or through the preferences dialog in the application.

Key configuration options:
- `DOWNLOAD_DIR`: Default directory for downloads
- `OUTPUT_FORMAT`: Default audio format (MP3, WAV, FLAC, AAC, OGG)
- `OUTPUT_QUALITY`: Default bitrate for lossy formats
- `DEFAULT_EFFECT`: Default effect preset to apply
- `THEME`: UI theme (light, dark, system)

## Project Structure

```
slowjams/
├── core/                      # Core application functionality
│   ├── downloader.py          # Media downloading functionality
│   ├── converter.py           # Format conversion
│   ├── processor.py           # Audio processing and effects
│   └── queue_manager.py       # Processing queue management
│
├── ui/                        # User interface components
│   ├── main_window.py         # Main application window
│   ├── preferences.py         # Settings dialog
│   ├── batch_dialog.py        # Batch processing interface
│   └── widgets/               # Reusable UI components
│
├── data/                      # Data management
│   ├── database.py            # SQLite database interface
│   ├── history.py             # Download and processing history
│   └── settings.py            # User settings management
│
├── utils/                     # Utility functions
│   ├── env_loader.py          # Environment variable management
│   ├── validators.py          # Input validation
│   └── file_ops.py            # File operations
│
├── tests/                     # Test suite
│
├── project-docs/              # Project documentation
│
├── .env.example               # Example environment variables
├── requirements.txt           # Python dependencies
└── main.py                    # Application entry point
```

## Development

### Environment Setup

1. Install development dependencies:
```bash
pip install -r requirements.txt
```

2. Install pre-commit hooks:
```bash
pip install pre-commit
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=.

# Run specific test file
pytest tests/test_downloader.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for video downloading
- [FFmpeg](https://ffmpeg.org/) for audio processing
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) for the UI
- [librosa](https://librosa.org/) for advanced audio analysis

---

Made with ♥ by [EBdesigns](https://github.com/Eblack17)