"""Utility functions for the PDF to Audiobook converter."""

import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    import numpy as np


def detect_language(text: str) -> Literal["en", "es", "unknown"]:
    """
    Detect language of text based on common word patterns.

    Uses a simple heuristic based on common words in each language.
    For more accurate detection, consider using langdetect library.
    """
    text_lower = text.lower()

    # Common Spanish words (including accented)
    spanish_markers = [
        r"\bel\b", r"\bla\b", r"\blos\b", r"\blas\b",
        r"\bde\b", r"\bdel\b", r"\bque\b", r"\ben\b",
        r"\by\b", r"\ba\b", r"\bpor\b", r"\bcon\b",
        r"\bpara\b", r"\bsu\b", r"\bse\b", r"\bno\b",
        r"\bcomo\b", r"\bmás\b", r"\bpero\b", r"\bsus\b",
        r"\bes\b", r"\bera\b", r"\bsí\b", r"\byo\b",
    ]

    # Common English words
    english_markers = [
        r"\bthe\b", r"\band\b", r"\bof\b", r"\bto\b",
        r"\ba\b", r"\bin\b", r"\bthat\b", r"\bis\b",
        r"\bwas\b", r"\bhe\b", r"\bfor\b", r"\bit\b",
        r"\bwith\b", r"\bas\b", r"\bhis\b", r"\bon\b",
        r"\bbe\b", r"\bat\b", r"\bby\b", r"\bi\b",
        r"\bthis\b", r"\bhad\b", r"\bnot\b", r"\bare\b",
    ]

    # Count matches
    spanish_count = sum(
        len(re.findall(pattern, text_lower)) for pattern in spanish_markers
    )
    english_count = sum(
        len(re.findall(pattern, text_lower)) for pattern in english_markers
    )

    # Normalize by text length
    text_words = len(text_lower.split())
    if text_words < 5:
        return "unknown"

    spanish_ratio = spanish_count / text_words
    english_ratio = english_count / text_words

    # Threshold for detection
    if spanish_ratio > english_ratio and spanish_ratio > 0.05:
        return "es"
    elif english_ratio > spanish_ratio and english_ratio > 0.05:
        return "en"
    return "unknown"


def get_output_format(output_path: str) -> Literal["wav", "mp3", "m4b"]:
    """Determine output format from file extension."""
    ext = Path(output_path).suffix.lower()
    if ext == ".wav":
        return "wav"
    elif ext == ".mp3":
        return "mp3"
    elif ext in (".m4b", ".m4a", ".aac"):
        return "m4b"
    else:
        raise ValueError(f"Unsupported output format: {ext}. Use .wav, .mp3, or .m4b")


def format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm for FFmpeg."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    # Remove or replace invalid characters
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", "_", name)
    return name[:100]  # Limit length


def estimate_audio_duration(text: str, words_per_minute: float = 150) -> float:
    """
    Estimate audio duration based on text length.

    Args:
        text: The text to estimate duration for
        words_per_minute: Average speaking rate (default 150 wpm)

    Returns:
        Estimated duration in seconds
    """
    word_count = len(text.split())
    return (word_count / words_per_minute) * 60


def roman_to_int(roman: str) -> Optional[int]:
    """Convert Roman numeral to integer."""
    roman_values = {
        "I": 1, "V": 5, "X": 10, "L": 50,
        "C": 100, "D": 500, "M": 1000
    }
    roman = roman.upper()
    total = 0
    prev_value = 0

    for char in reversed(roman):
        if char not in roman_values:
            return None
        value = roman_values[char]
        if value < prev_value:
            total -= value
        else:
            total += value
        prev_value = value

    return total if total > 0 else None


def normalize_chapter_number(num_str: str) -> Optional[int]:
    """
    Normalize a chapter number string to integer.

    Handles both Arabic (1, 2, 3) and Roman (I, II, III) numerals.
    """
    num_str = num_str.strip()

    # Try Arabic numeral first
    if num_str.isdigit():
        return int(num_str)

    # Try Roman numeral
    return roman_to_int(num_str)


def generate_silence(duration_seconds: float, sample_rate: int = 24000) -> "np.ndarray":
    """Generate silence of specified duration."""
    import numpy as np
    samples = int(duration_seconds * sample_rate)
    return np.zeros(samples, dtype=np.float32)


def hash_file(path: str, chunk_size: int = 65536) -> str:
    """
    Compute SHA256 hash of file contents.

    Args:
        path: Path to the file to hash
        chunk_size: Size of chunks to read (default 64KB)

    Returns:
        Hexadecimal SHA256 hash string
    """
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def hash_settings(settings: dict) -> str:
    """
    Hash a settings dictionary for comparison.

    Args:
        settings: Dictionary of settings to hash

    Returns:
        First 16 characters of SHA256 hash (sufficient for comparison)
    """
    settings_json = json.dumps(settings, sort_keys=True)
    return hashlib.sha256(settings_json.encode()).hexdigest()[:16]
