# eBook TTS

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![TTS](https://img.shields.io/badge/TTS-Kokoro--82M-orange.svg)

Convert PDF/EPUB ebooks to audiobooks using Kokoro TTS with 22 pre-built voices.

## Quick Start

```bash
pip install .
ebook-tts convert --input book.pdf --output book.wav
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

```bash
# From source
git clone https://github.com/v0xg/ebook-tts.git && cd ebook-tts && pip install .

# Or directly from GitHub
pip install git+https://github.com/v0xg/ebook-tts.git

# GPU support (optional)
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

### Other Commands

```bash
ebook-tts extract --input book.pdf --output book.txt        # Extract text
ebook-tts extract --input book.pdf --output book.txt --processed  # With preprocessing
ebook-tts chapters --input book.pdf                         # List chapters
ebook-tts preview --input book.pdf --chars 2000             # Preview text
ebook-tts text-to-wav --input text.txt --output audio.wav   # Text file to audio
ebook-tts convert --input book.pdf --output ch1-3.wav --chapters 1,2,3  # Specific chapters
ebook-tts convert --input book.pdf --output test.wav --mock # Test mode (no GPU)
```

### Checkpoint/Resume

For long books, enable checkpointing to resume interrupted conversions:

```bash
ebook-tts convert --input book.pdf --output book.wav --checkpoint         # Enable
ebook-tts convert --input book.pdf --output book.wav --checkpoint         # Resume (auto-detects)
ebook-tts convert --input book.pdf --output book.wav --checkpoint --force # Start fresh
```

## Voices

22 voices available across American, British, Spanish, French, Japanese, and Chinese. Run `ebook-tts list-voices` for the full list.

**Recommended:** `af_heart` (American female), `bf_emma` (British female), `am_adam` (American male)

**Naming convention:** `[lang][gender]_[name]` where lang is `a`=American, `b`=British, `e`=Spanish, etc. and gender is `f`/`m`.

## Docker

```bash
docker build -t ebook-tts .
docker run -v $(pwd):/data ebook-tts convert --input /data/book.pdf --output /data/book.wav
docker run --gpus all -v $(pwd):/data ebook-tts convert --input /data/book.pdf --output /data/book.wav  # GPU
```

## REST API

Optional FastAPI service for remote conversions with job queuing and cloud storage.

```bash
pip install -e ".[api]"
uvicorn ebook_tts.api.main:app --reload
```

**Endpoints:** `/api/v1/auth/register`, `/api/v1/auth/token`, `/api/v1/convert/`, `/api/v1/voices/`

**Docker:**
```bash
docker build -f Dockerfile.api -t ebook-tts-api .
docker run -p 8000:8000 -e EBOOK_TTS_USE_LOCAL_STORAGE=true ebook-tts-api
```

See `CLAUDE.md` for environment variables and configuration.

## Development

```bash
pip install -e ".[dev]"      # Install with dev dependencies
pytest tests/ -v             # Run tests
ruff check .                 # Lint
```

## License

MIT
