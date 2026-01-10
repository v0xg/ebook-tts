"""Tests for utility functions."""

import pytest

from ebook_tts.utils import (
    detect_language,
    estimate_audio_duration,
    format_time,
    generate_silence,
    get_output_format,
    normalize_chapter_number,
    roman_to_int,
    sanitize_filename,
)


class TestDetectLanguage:
    """Tests for language detection."""

    def test_detect_english(self, sample_english_text: str):
        """Detect English text."""
        result = detect_language(sample_english_text)
        assert result == "en"

    def test_detect_spanish(self, sample_spanish_text: str):
        """Detect Spanish text."""
        result = detect_language(sample_spanish_text)
        assert result == "es"

    def test_detect_short_text_unknown(self):
        """Short text returns unknown."""
        result = detect_language("hello")
        assert result == "unknown"

    def test_detect_mixed_text(self):
        """Mixed text detects dominant language."""
        # Mostly English with some Spanish
        text = "The quick brown fox jumps over the lazy dog. El perro."
        result = detect_language(text)
        assert result == "en"


class TestGetOutputFormat:
    """Tests for output format detection."""

    def test_wav_format(self):
        """Detect WAV format."""
        assert get_output_format("output.wav") == "wav"
        assert get_output_format("output.WAV") == "wav"

    def test_mp3_format(self):
        """Detect MP3 format."""
        assert get_output_format("output.mp3") == "mp3"

    def test_m4b_format(self):
        """Detect M4B format."""
        assert get_output_format("output.m4b") == "m4b"
        assert get_output_format("output.m4a") == "m4b"

    def test_unsupported_format(self):
        """Unsupported format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported output format"):
            get_output_format("output.ogg")


class TestFormatTime:
    """Tests for time formatting."""

    def test_format_seconds(self):
        """Format seconds only."""
        assert format_time(30.5) == "00:00:30.500"

    def test_format_minutes_seconds(self):
        """Format minutes and seconds."""
        assert format_time(90.123) == "00:01:30.123"

    def test_format_hours_minutes_seconds(self):
        """Format hours, minutes, and seconds."""
        assert format_time(3661.0) == "01:01:01.000"

    def test_format_zero(self):
        """Format zero."""
        assert format_time(0.0) == "00:00:00.000"


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_remove_invalid_chars(self):
        """Remove invalid filename characters."""
        result = sanitize_filename('test<>:"/\\|?*file')
        assert "<" not in result
        assert ">" not in result
        assert "test" in result

    def test_replace_spaces(self):
        """Replace spaces with underscores."""
        result = sanitize_filename("test file name")
        assert result == "test_file_name"

    def test_limit_length(self):
        """Limit filename length."""
        long_name = "a" * 200
        result = sanitize_filename(long_name)
        assert len(result) == 100


class TestEstimateAudioDuration:
    """Tests for audio duration estimation."""

    def test_estimate_short_text(self):
        """Estimate duration for short text."""
        # 150 words = 1 minute = 60 seconds
        text = " ".join(["word"] * 150)
        result = estimate_audio_duration(text)
        assert result == pytest.approx(60.0)

    def test_estimate_empty_text(self):
        """Estimate duration for empty text."""
        result = estimate_audio_duration("")
        assert result == 0.0

    def test_custom_words_per_minute(self):
        """Estimate with custom words per minute."""
        text = " ".join(["word"] * 100)
        result = estimate_audio_duration(text, words_per_minute=100)
        assert result == pytest.approx(60.0)


class TestRomanToInt:
    """Tests for Roman numeral conversion."""

    def test_simple_numerals(self):
        """Convert simple Roman numerals."""
        assert roman_to_int("I") == 1
        assert roman_to_int("V") == 5
        assert roman_to_int("X") == 10

    def test_complex_numerals(self):
        """Convert complex Roman numerals."""
        assert roman_to_int("IV") == 4
        assert roman_to_int("IX") == 9
        assert roman_to_int("XLII") == 42
        assert roman_to_int("MCMXCIV") == 1994

    def test_lowercase(self):
        """Handle lowercase input."""
        assert roman_to_int("iv") == 4

    def test_invalid_numeral(self):
        """Invalid numeral returns None."""
        assert roman_to_int("ABC") is None


class TestNormalizeChapterNumber:
    """Tests for chapter number normalization."""

    def test_arabic_numerals(self):
        """Normalize Arabic numerals."""
        assert normalize_chapter_number("1") == 1
        assert normalize_chapter_number("42") == 42
        assert normalize_chapter_number(" 5 ") == 5

    def test_roman_numerals(self):
        """Normalize Roman numerals."""
        assert normalize_chapter_number("IV") == 4
        assert normalize_chapter_number("XII") == 12

    def test_invalid_returns_none(self):
        """Invalid chapter number returns None."""
        assert normalize_chapter_number("abc") is None


class TestGenerateSilence:
    """Tests for silence generation."""

    def test_generate_one_second(self):
        """Generate one second of silence."""
        silence = generate_silence(1.0, sample_rate=24000)
        assert len(silence) == 24000

    def test_generate_half_second(self):
        """Generate half second of silence."""
        silence = generate_silence(0.5, sample_rate=24000)
        assert len(silence) == 12000

    def test_silence_is_zeros(self):
        """Silence should be all zeros."""
        import numpy as np

        silence = generate_silence(0.1)
        assert np.all(silence == 0)

    def test_silence_dtype(self):
        """Silence should be float32."""
        import numpy as np

        silence = generate_silence(0.1)
        assert silence.dtype == np.float32
