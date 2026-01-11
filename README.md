# eBook TTS

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![TTS](https://img.shields.io/badge/TTS-Kokoro--82M-orange.svg)

Convert PDF/EPUB ebooks to audiobooks using Kokoro TTS with 22 pre-built voices.

## Table of Contents

- [Quick Start](#quick-start)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
  - [Basic Conversion](#basic-conversion)
  - [Voice Selection](#voice-selection)
  - [Pronunciation Dictionaries](#pronunciation-dictionaries)
  - [Text Extraction](#text-extraction)
  - [Other Commands](#other-commands)
  - [Checkpoint/Resume](#checkpointresume)
- [Voices](#voices)
- [Docker](#docker)
- [REST API](#rest-api)
- [Development](#development)
- [Architecture](#architecture)
- [License](#license)

## Quick Start

```bash
# Install
pip install .

# Convert PDF/EPUB to audiobook
ebook-tts convert --input book.pdf --output book.wav

# Convert EPUB to audiobook
ebook-tts convert --input book.epub --output book.wav

# List available voices
ebook-tts list-voices
```

## Features

- **22 pre-built voices** - American, British, Spanish, French, Japanese, and Chinese accents
- **Chapter detection** - Automatic chapter markers from TOC or patterns (English/Spanish)
- **Multiple formats** - WAV, MP3, M4B with embedded chapter markers
- **GPU acceleration** - 10-15x real-time on NVIDIA GPUs
- **CPU fallback** - Works without GPU at 1-2x real-time
- **Pronunciation dictionaries** - Custom word pronunciations via YAML files
- **Streaming output** - Memory-efficient processing for long books
- **Checkpoint/Resume** - Resume interrupted conversions without losing progress

## Installation

### Requirements

| Requirement | Purpose |
|------------|---------|
| Python 3.10+ | Runtime |
| `espeak-ng` | Phoneme generation (required) |
| `ffmpeg` | MP3/M4B output (optional) |
| NVIDIA GPU | Faster inference (optional) |

EPUB support uses `ebooklib` and `beautifulsoup4` (installed via pip).
Use `numpy<2` to avoid compatibility issues with TTS dependencies.

### Install from source

```bash
git clone https://github.com/v0xg/ebook-tts.git
cd ebook-tts
pip install .
```

### Install from GitHub

```bash
pip install git+https://github.com/v0xg/ebook-tts.git
```

### GPU Setup (Optional)

For NVIDIA GPUs, ensure PyTorch with CUDA is installed:

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Usage

### Basic Conversion

```bash
# Default conversion (GPU, af_heart voice)
ebook-tts convert --input book.pdf --output book.wav

# Use CPU mode
ebook-tts convert --input book.pdf --output book.wav --cpu

# MP3 output with chapter markers
ebook-tts convert --input book.pdf --output book.mp3

# M4B audiobook format
ebook-tts convert --input book.pdf --output book.m4b
```

### Voice Selection

```bash
# Use a specific voice
ebook-tts convert --input book.pdf --output book.wav --voice bf_emma

# Adjust speech speed (0.5-2.0)
ebook-tts convert --input book.pdf --output book.wav --speed 1.2

# List all voices
ebook-tts list-voices

# Filter by language (a=American, b=British, e=Spanish)
ebook-tts list-voices --lang b
```

### Pronunciation Dictionaries

Custom pronunciation dictionaries let you control how specific words are spoken.

```bash
# Use a custom pronunciation dictionary
ebook-tts convert --input book.pdf --output book.wav --dict my_pronunciations.yaml
```

**Dictionary Format (YAML):**

```yaml
version: 1
language: en

# Custom word pronunciations
words:
  Nguyen: "win"
  cache: "cash"

# Abbreviation expansions
abbreviations:
  Dr.: "Doctor"
  etc.: "et cetera"

# Acronym pronunciations
acronyms:
  FBI: "F. B. I."
  NASA: "NASA"
  SQL: "sequel"

# Regex pattern replacements
patterns:
  - pattern: '(\d+)km'
    replacement: '\1 kilometers'
  - pattern: '\$(\d+)'
    replacement: '\1 dollars'
```

See `examples/base_en.yaml` for a complete example.

### Text Extraction

```bash
# Extract raw text
ebook-tts extract --input book.pdf --output book.txt

# Extract with preprocessing
ebook-tts extract --input book.pdf --output book.txt --processed

# Include metadata
ebook-tts extract --input book.pdf --output book.txt --processed --include-meta

# With custom dictionary
ebook-tts extract --input book.pdf --output book.txt --processed --dict my_dict.yaml
```

### Other Commands

```bash
# List detected chapters
ebook-tts chapters --input book.pdf

# Preview processed text
ebook-tts preview --input book.pdf --chars 2000

# Convert specific chapters only
ebook-tts convert --input book.pdf --output ch1-3.wav --chapters 1,2,3

# Test mode (no GPU required)
ebook-tts convert --input book.pdf --output test.wav --mock
```

### Checkpoint/Resume

For long books, enable checkpointing to resume interrupted conversions:

```bash
# Enable checkpoint (creates .book.wav.checkpoint/ directory)
ebook-tts convert --input book.pdf --output book.wav --checkpoint

# Resume an interrupted conversion (automatically detects existing checkpoint)
ebook-tts convert --input book.pdf --output book.wav --checkpoint

# Discard existing checkpoint and start fresh
ebook-tts convert --input book.pdf --output book.wav --checkpoint --force
```

The checkpoint system:
- Saves progress after each synthesized chunk
- Caches audio chunks to avoid re-synthesis
- Validates input file hash and settings to ensure consistency
- Automatically cleans up checkpoint directory on successful completion

### Direct Text-to-Audio

```bash
# Convert text file to audio
ebook-tts text-to-wav --input text.txt --output audio.wav

# With preprocessing and custom dictionary
ebook-tts text-to-wav --input text.txt --output audio.wav --preprocess --dict my_dict.yaml
```

## Voices

| Voice | Language | Quality | Description |
|-------|----------|---------|-------------|
| `af_heart` | American English | A | Best quality female |
| `af_bella` | American English | A- | Warm female |
| `af_nicole` | American English | - | Clear female |
| `af_sarah` | American English | - | Natural female |
| `af_sky` | American English | - | Sky |
| `am_adam` | American English | - | Neutral male |
| `am_michael` | American English | - | Michael |
| `am_fenrir` | American English | - | Fenrir |
| `am_puck` | American English | - | Puck |
| `bf_emma` | British English | B- | British female |
| `bf_isabella` | British English | - | Elegant female |
| `bf_alice` | British English | - | Alice |
| `bm_george` | British English | - | British male |
| `bm_lewis` | British English | - | Clear male |
| `bm_daniel` | British English | - | Daniel |
| `ef_dora` | Spanish | - | Spanish female |
| `em_alex` | Spanish | - | Spanish male |
| `ff_siwis` | French | B- | French female |
| `jf_alpha` | Japanese | - | Japanese female |
| `jm_kumo` | Japanese | - | Japanese male |
| `zf_xiaobei` | Chinese | - | Chinese female |
| `zm_yunjian` | Chinese | - | Chinese male |

Run `ebook-tts list-voices` for the full list with descriptions.

### Voice Naming Convention

- First letter: Language (`a`=American, `b`=British, `e`=Spanish, etc.)
- Second letter: Gender (`f`=female, `m`=male)
- Name: Character name

## Docker

```bash
# Build
docker build -t ebook-tts .

# List voices
docker run ebook-tts list-voices

# Convert (mount volume for files)
docker run -v $(pwd):/data ebook-tts convert \
  --input /data/book.pdf \
  --output /data/book.wav

# With GPU support
docker run --gpus all -v $(pwd):/data ebook-tts convert \
  --input /data/book.pdf \
  --output /data/book.wav
```

## REST API

An optional FastAPI service for remote conversions with job queuing and cloud storage support.

### Installation

```bash
pip install -e ".[api]"
```

### Running the Server

```bash
# Development
uvicorn ebook_tts.api.main:app --reload

# Production
uvicorn ebook_tts.api.main:app --host 0.0.0.0 --port 8000
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Create account |
| `/api/v1/auth/token` | POST | Get JWT token |
| `/api/v1/convert/` | POST | Submit conversion job |
| `/api/v1/convert/{job_id}` | GET | Check job status |
| `/api/v1/voices/` | GET | List available voices |

### Docker

```bash
docker build -f Dockerfile.api -t ebook-tts-api .
docker run -p 8000:8000 -e EBOOK_TTS_USE_LOCAL_STORAGE=true ebook-tts-api
```

See `CLAUDE.md` for environment variables and detailed configuration.

## Development

### Setup

```bash
git clone https://github.com/v0xg/ebook-tts.git
cd ebook-tts
pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src/ebook_tts

# Run specific test file
pytest tests/test_preprocessor.py -v
```

### Linting

```bash
ruff check .
ruff check --fix .
```

### Project Structure

```
ebook-tts/
├── src/ebook_tts/
│   ├── cli.py               # CLI interface
│   ├── converter.py         # Main orchestrator
│   ├── pdf_extractor.py     # PDF text extraction
│   ├── epub_extractor.py    # EPUB text extraction
│   ├── chapter_detector.py  # Chapter detection
│   ├── text_preprocessor.py # Text cleaning for TTS
│   ├── text_chunker.py      # Text splitting
│   ├── audio_synthesizer.py # TTS wrapper
│   ├── audio_writer.py      # Audio output
│   ├── pronunciation_dict.py# Custom dictionaries
│   ├── checkpoint.py        # Resumable conversion state
│   ├── progress.py          # Progress tracking
│   ├── utils.py             # Utilities
│   └── api/                 # REST API (optional)
│       ├── main.py          # FastAPI app
│       ├── config.py        # Settings
│       ├── routers/         # API endpoints
│       ├── services/        # Business logic
│       └── db/              # Database models
├── tests/                   # Test suite
├── examples/                # Sample dictionaries
└── pyproject.toml
```

## Architecture

### Pipeline Flow

```
PDF/EPUB → Extractor → ChapterDetector → TextPreprocessor → TextChunker
                                              ↓
                                    PronunciationDict (optional)
                                              ↓
                              KokoroSynthesizer → StreamingAudioWriter → Output
```

### Key Components

| Component | Purpose |
|-----------|---------|
| `PDFToAudiobook` | Main converter orchestrator |
| `PDFExtractor` | Extract text/TOC from PDFs |
| `EPUBExtractor` | Extract text/TOC from EPUBs |
| `ChapterDetector` | Detect chapters from TOC or patterns |
| `TextPreprocessor` | Clean text for TTS (ligatures, abbreviations) |
| `PronunciationDict` | Load custom pronunciation rules |
| `TextChunker` | Split text at sentence boundaries |
| `KokoroSynthesizer` | Kokoro TTS wrapper |
| `StreamingAudioWriter` | Memory-efficient audio output |
| `CheckpointManager` | Resumable conversion state management |

### Library Usage

```python
from ebook_tts import PDFToAudiobook, PronunciationDict

# Basic conversion
converter = PDFToAudiobook()
result = converter.convert("book.pdf", "book.wav")
print(f"Duration: {result.duration_seconds}s")

# With custom dictionary
converter = PDFToAudiobook(
    dictionary_path="my_dict.yaml",
    voice="bf_emma",
)
result = converter.convert("book.pdf", "book.wav")

# Progress callback
def on_progress(update):
    print(f"{update.stage}: {update.percent:.0f}%")

converter = PDFToAudiobook(progress_callback=on_progress)
converter.convert("book.pdf", "book.wav")
```

## License

MIT
