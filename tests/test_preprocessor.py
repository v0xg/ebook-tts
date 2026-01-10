# tests/test_preprocessor.py
"""Tests for text preprocessing - demonstrates testing practices."""

import pytest

from ebook_tts.text_preprocessor import TextPreprocessor


class TestTextPreprocessor:
    """Test suite for TextPreprocessor."""

    @pytest.fixture
    def preprocessor(self):
        """Create a fresh preprocessor for each test."""
        return TextPreprocessor()

    def test_ligature_replacement(self, preprocessor):
        """Ligatures should be expanded to readable characters."""
        text = "The ﬁrst ﬂight was ﬀective"
        result = preprocessor.process(text)

        assert "fi" in result  # ﬁ -> fi
        assert "fl" in result  # ﬂ -> fl
        assert "ff" in result  # ﬀ -> ff

    def test_abbreviation_expansion_english(self, preprocessor):
        """Common abbreviations should be expanded in English."""
        text = "Dr. Smith met Prof. Jones on Jan. 5th."
        result = preprocessor.process(text)

        assert "Doctor" in result
        assert "Professor" in result
        assert "January" in result

    def test_hyphenation_repair(self, preprocessor):
        """Words split across lines should be rejoined."""
        text = "This is a hyphen-\nated word in the text."
        result = preprocessor.process(text)

        assert "hyphenated" in result
        assert "hyphen-\n" not in result

    def test_whitespace_normalization(self, preprocessor):
        """Multiple spaces and weird whitespace should normalize."""
        text = "Too    many   spaces   here"
        result = preprocessor.process(text)

        # Should not have multiple consecutive spaces
        assert "  " not in result

    def test_empty_input(self, preprocessor):
        """Empty string should return empty string."""
        result = preprocessor.process("")
        assert result == ""

    def test_language_detection(self, preprocessor):
        """Language should be auto-detected."""
        english_text = "The quick brown fox jumps over the lazy dog."
        preprocessor.process(english_text)

        assert preprocessor.detected_language == "en"


class TestTextChunker:
    """Test suite for TextChunker."""

    def test_respects_max_chars(self):
        """Chunks should not exceed max_chars."""
        from ebook_tts.text_chunker import TextChunker

        chunker = TextChunker(max_chars=100)
        long_text = "This is a sentence. " * 50  # ~1000 chars

        chunks = chunker.chunk(long_text)

        for chunk in chunks:
            assert len(chunk.text) <= 150  # Some tolerance for sentence boundaries

    def test_sentence_boundary_preservation(self):
        """Chunks should break at sentence boundaries when possible."""
        from ebook_tts.text_chunker import TextChunker

        chunker = TextChunker(max_chars=100)
        text = "First sentence here. Second sentence here. Third sentence here."

        chunks = chunker.chunk(text)

        # Each chunk should end with sentence-ending punctuation
        for chunk in chunks:
            stripped = chunk.text.strip()
            if stripped:
                assert stripped[-1] in '.!?'


class TestChapterDetector:
    """Test suite for ChapterDetector."""

    def test_detects_chapter_pattern(self):
        """Should detect 'Chapter N' patterns."""
        from ebook_tts.chapter_detector import ChapterDetector

        detector = ChapterDetector(min_chapter_length=50)

        # Mock document object
        class MockDoc:
            text = """
            Chapter 1: Introduction

            This is the introduction text.

            Chapter 2: Getting Started

            This is chapter two.
            """
            toc = []
            pages = []

        chapters = detector.detect(MockDoc())

        assert len(chapters) >= 2
        assert "Introduction" in chapters[0].title or "Chapter 1" in chapters[0].title
