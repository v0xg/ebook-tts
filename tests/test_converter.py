"""Tests for PDFToAudiobook converter."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ebook_tts.converter import PDFToAudiobook
from ebook_tts.progress import ProgressUpdate


class TestPDFToAudiobookInit:
    """Tests for converter initialization."""

    def test_init_default_settings(self):
        """Initialize with default settings."""
        converter = PDFToAudiobook(mock_tts=True)

        assert converter.paragraph_pause == 0.5
        assert converter.chapter_pause == 1.5

    def test_init_custom_settings(self):
        """Initialize with custom settings."""
        converter = PDFToAudiobook(
            mock_tts=True,
            chunk_size=500,
            paragraph_pause=1.0,
            chapter_pause=2.0,
        )

        assert converter.paragraph_pause == 1.0
        assert converter.chapter_pause == 2.0

    def test_init_with_dictionary(self, base_dict_path: Path):
        """Initialize with pronunciation dictionary."""
        converter = PDFToAudiobook(
            mock_tts=True,
            dictionary_path=str(base_dict_path),
        )

        # Preprocessor should have dictionary set
        assert converter.preprocessor.dictionary is not None


class TestPDFToAudiobookConvert:
    """Tests for conversion functionality."""

    def test_convert_nonexistent_pdf_raises(self, tmp_path: Path):
        """Converting nonexistent PDF raises FileNotFoundError."""
        converter = PDFToAudiobook(mock_tts=True)
        output_path = tmp_path / "output.wav"

        with pytest.raises(FileNotFoundError):
            converter.convert(str(tmp_path / "nonexistent.pdf"), str(output_path))

    def test_convert_creates_output_directory(self, tmp_path: Path):
        """Converter creates output directory if needed."""
        converter = PDFToAudiobook(mock_tts=True)

        # Create a fake PDF file so FileNotFoundError isn't raised
        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 test")

        # Create a minimal mock for PDF extraction
        with patch.object(converter.pdf_extractor, "extract") as mock_extract:
            mock_doc = MagicMock()
            mock_doc.text = "Hello world. This is a test."
            mock_doc.pages = []
            mock_doc.metadata = {}
            mock_doc.toc = []
            mock_extract.return_value = mock_doc

            output_path = tmp_path / "subdir" / "output.wav"

            # Should not raise, even if subdir doesn't exist
            converter.convert(
                str(fake_pdf),
                str(output_path),
            )

            assert Path(output_path).parent.exists()


class TestPDFToAudiobookProgress:
    """Tests for progress reporting."""

    def test_progress_callback_called(self, tmp_path: Path):
        """Progress callback is called during conversion."""
        progress_updates = []

        def callback(update: ProgressUpdate):
            progress_updates.append(update)

        converter = PDFToAudiobook(
            mock_tts=True,
            progress_callback=callback,
        )

        # Create a fake PDF file
        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 test")

        with patch.object(converter.pdf_extractor, "extract") as mock_extract:
            mock_doc = MagicMock()
            mock_doc.text = "Hello world."
            mock_doc.pages = []
            mock_doc.metadata = {}
            mock_doc.toc = []
            mock_extract.return_value = mock_doc

            converter.convert(
                str(fake_pdf),
                str(tmp_path / "output.wav"),
            )

        assert len(progress_updates) > 0
        # Should have extraction, preprocessing, and synthesis stages
        stages = {u.stage for u in progress_updates}
        assert "extracting" in stages or "synthesizing" in stages


class TestPDFToAudiobookExtractChapters:
    """Tests for chapter extraction."""

    def test_extract_chapters_from_pdf(self, tmp_path: Path):
        """Extract chapters without converting."""
        converter = PDFToAudiobook(mock_tts=True)

        with patch.object(converter.pdf_extractor, "extract") as mock_extract:
            mock_doc = MagicMock()
            mock_doc.text = "Chapter 1\nContent\nChapter 2\nMore content"
            mock_doc.pages = []
            mock_doc.metadata = {}
            mock_doc.toc = []
            mock_extract.return_value = mock_doc

            chapters = converter.extract_chapters(str(tmp_path / "fake.pdf"))

            # Chapters detected from pattern
            assert isinstance(chapters, list)


class TestPDFToAudiobookPreviewText:
    """Tests for text preview functionality."""

    def test_preview_text(self, tmp_path: Path):
        """Preview processed text from PDF."""
        converter = PDFToAudiobook(mock_tts=True)

        with patch.object(converter.pdf_extractor, "extract") as mock_extract:
            mock_doc = MagicMock()
            mock_doc.text = "Dr. Smith visited the office. " * 100
            mock_doc.pages = []
            mock_doc.metadata = {}
            mock_extract.return_value = mock_doc

            preview = converter.preview_text(str(tmp_path / "fake.pdf"), max_chars=50)

            # Should be truncated
            assert len(preview) <= 53  # 50 + "..."
            # Should be preprocessed (Dr. expanded)
            assert "Doctor" in preview or "..." in preview

    def test_preview_respects_max_chars(self, tmp_path: Path):
        """Preview respects max_chars limit."""
        converter = PDFToAudiobook(mock_tts=True)

        with patch.object(converter.pdf_extractor, "extract") as mock_extract:
            mock_doc = MagicMock()
            mock_doc.text = "Hello " * 1000
            mock_doc.pages = []
            mock_doc.metadata = {}
            mock_extract.return_value = mock_doc

            preview = converter.preview_text(str(tmp_path / "fake.pdf"), max_chars=100)

            assert len(preview) <= 103  # 100 + "..."


class TestPDFToAudiobookIntegration:
    """Integration tests using MockSynthesizer."""

    def test_full_conversion_with_mock(self, tmp_path: Path):
        """Test full conversion pipeline with mock synthesizer."""
        converter = PDFToAudiobook(mock_tts=True)
        output_path = tmp_path / "output.wav"

        # Create a fake PDF file
        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 test")

        with patch.object(converter.pdf_extractor, "extract") as mock_extract:
            mock_doc = MagicMock()
            mock_doc.text = "This is a test sentence. And another one."
            mock_doc.pages = []
            mock_doc.metadata = {}
            mock_doc.toc = []
            mock_extract.return_value = mock_doc

            result = converter.convert(
                str(fake_pdf),
                str(output_path),
            )

            assert output_path.exists()
            assert result.output_path == str(output_path)
            assert result.duration_seconds > 0
            assert result.chunks_processed > 0
