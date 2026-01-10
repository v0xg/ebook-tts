"""Main document to audiobook converter orchestrator."""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

import numpy as np

from .audio_synthesizer import KokoroSynthesizer, MockSynthesizer
from .audio_writer import StreamingAudioWriter
from .chapter_detector import ChapterDetector
from .epub_extractor import EPUBExtractor
from .pdf_extractor import PDFExtractor
from .progress import (
    Chapter,
    ChapterMarker,
    ConversionResult,
    ProgressCallback,
    ProgressUpdate,
)
from .pronunciation_dict import load_dictionary
from .text_chunker import TextChunker
from .text_preprocessor import TextPreprocessor

if TYPE_CHECKING:
    from .checkpoint import CheckpointManager


class PDFToAudiobook:
    """Convert PDF/EPUB ebooks to audiobooks using Kokoro TTS."""

    def __init__(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        mock_tts: bool = False,
        device: str = "cuda",
        chunk_size: int = 400,
        paragraph_pause: float = 0.5,
        chapter_pause: float = 1.5,
        voice: str = "af_heart",
        dictionary_path: Optional[str] = None,
        base_dictionary_path: Optional[str] = None,
        checkpoint_manager: Optional["CheckpointManager"] = None,
    ):
        """
        Initialize the converter.

        Args:
            progress_callback: Callback for progress updates
            mock_tts: Use mock synthesizer for testing
            device: Device for TTS ('cuda' or 'cpu')
            chunk_size: Maximum characters per TTS chunk
            paragraph_pause: Pause duration between paragraphs (seconds)
            chapter_pause: Pause duration between chapters (seconds)
            voice: Kokoro voice name (e.g., 'af_heart', 'bf_emma')
            dictionary_path: Path to YAML pronunciation dictionary
            base_dictionary_path: Optional base dictionary to merge with
            checkpoint_manager: Optional checkpoint manager for resumable conversion
        """
        self.progress_callback = progress_callback
        self.paragraph_pause = paragraph_pause
        self.chapter_pause = chapter_pause
        self.voice = voice
        self.checkpoint_manager = checkpoint_manager

        # Load pronunciation dictionary if provided
        dictionary = load_dictionary(dictionary_path, base_dictionary_path)

        # Initialize components
        self.pdf_extractor = PDFExtractor()
        self.epub_extractor = EPUBExtractor()
        self.extractor = self.pdf_extractor
        self.chapter_detector = ChapterDetector()
        self.preprocessor = TextPreprocessor(dictionary=dictionary)
        self.chunker = TextChunker(max_chars=chunk_size)

        # Initialize synthesizer
        if mock_tts:
            self.synthesizer = MockSynthesizer()
        else:
            self.synthesizer = KokoroSynthesizer(
                voice=voice,
                device=device,
            )

    def _report_progress(
        self,
        stage: str,
        percent: float,
        message: str,
        **kwargs,
    ) -> None:
        """Report progress through callback if set."""
        if self.progress_callback:
            update = ProgressUpdate(
                stage=stage,
                percent=percent,
                message=message,
                **kwargs,
            )
            self.progress_callback(update)

    def convert(
        self,
        input_path: str,
        output_path: str,
        chapters_to_convert: Optional[list[int]] = None,
        speed: float = 1.0,
    ) -> ConversionResult:
        """
        Convert a PDF or EPUB to an audiobook.

        Args:
            input_path: Path to the input PDF/EPUB
            output_path: Path for the output audio file
            chapters_to_convert: Optional list of chapter numbers to convert
            speed: Speech speed multiplier (0.5-2.0)

        Returns:
            ConversionResult with output path, duration, and chapters
        """
        # Validate inputs
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Stage 1: Extract text from PDF
        extractor, label = self._select_extractor(input_path)
        self._report_progress("extracting", 0, f"Extracting text from {label}...")
        doc = extractor.extract(str(input_path))
        unit = "sections" if label == "EPUB" else "pages"
        self._report_progress("extracting", 100, f"Extracted {len(doc.pages)} {unit}")

        # Stage 2: Detect chapters
        self._report_progress("extracting", 100, "Detecting chapters...")
        chapters = self.chapter_detector.detect(doc)
        self._report_progress(
            "extracting", 100,
            f"Found {len(chapters)} chapters" if chapters else "No chapters detected"
        )

        # Filter chapters if specific ones requested
        if chapters_to_convert and chapters:
            chapters = [
                ch for i, ch in enumerate(chapters, 1)
                if i in chapters_to_convert
            ]

        # Determine text to process
        if chapters_to_convert and chapters:
            # Extract only requested chapters
            text_parts = []
            for ch in chapters:
                text_parts.append(ch.get_text(doc.text))
            text = "\n\n".join(text_parts)
        else:
            text = doc.text

        # Stage 3: Preprocess text
        self._report_progress("preprocessing", 0, "Cleaning text...")
        text = self.preprocessor.process(text)
        self._report_progress(
            "preprocessing", 50,
            f"Detected language: {self.preprocessor.detected_language}"
        )

        # Stage 4: Chunk text
        self._report_progress("chunking", 0, "Splitting into chunks...")
        chunks = self.chunker.chunk(text, chapters if not chapters_to_convert else None)
        self._report_progress("chunking", 100, f"Created {len(chunks)} chunks")

        # Stage 5: Synthesize and write audio
        self._report_progress("synthesizing", 0, "Starting synthesis...")

        # Set up checkpointing if enabled
        checkpoint_state = None
        completed_chunks: set[int] = set()

        if self.checkpoint_manager:
            if self.checkpoint_manager.exists():
                # Resume from existing checkpoint
                checkpoint_state = self.checkpoint_manager.load_state()
                completed_chunks = set(checkpoint_state.completed_chunks)
            else:
                # Create new checkpoint
                chapters_data = [
                    {"title": ch.title, "start_char": ch.start_char, "start_page": ch.start_page}
                    for ch in (chapters or [])
                ]
                checkpoint_state = self.checkpoint_manager.create_state(
                    input_path=str(input_path),
                    output_path=str(output_path),
                    settings={},  # Settings already verified in CLI
                    total_chunks=len(chunks),
                    chapters=chapters_data,
                    sample_rate=self.synthesizer.sample_rate,
                )
                self.checkpoint_manager.save_state(checkpoint_state)

        with StreamingAudioWriter(
            output_path=str(output_path),
            sample_rate=self.synthesizer.sample_rate,
        ) as writer:
            current_chapter_idx = None

            for i, chunk in enumerate(chunks):
                # Update progress
                progress_pct = (i / len(chunks)) * 100
                chapter_title = None

                # Check for chapter change
                if chunk.chapter_idx is not None and chunk.chapter_idx != current_chapter_idx:
                    # Find chapter
                    if chapters and chunk.chapter_idx < len(chapters):
                        chapter = chapters[chunk.chapter_idx]
                        chapter_title = chapter.title

                        # Add chapter marker
                        writer.add_chapter(chapter.title)

                        # Add pause before new chapter (except first)
                        if current_chapter_idx is not None:
                            writer.write_silence(self.chapter_pause)

                    current_chapter_idx = chunk.chapter_idx

                self._report_progress(
                    "synthesizing",
                    progress_pct,
                    f"Chunk {i + 1}/{len(chunks)}",
                    chapter=chapter_title,
                    chunks_completed=i,
                    chunks_total=len(chunks),
                )

                # Check if chunk already completed (resuming)
                if i in completed_chunks and self.checkpoint_manager:
                    # Load audio from checkpoint
                    audio = self.checkpoint_manager.load_chunk(i)
                    if audio is not None:
                        writer.write(audio)
                        if chunk.paragraph_break_after:
                            writer.write_silence(self.paragraph_pause)
                        continue
                    # Chunk missing/corrupt, will re-synthesize below

                # Synthesize chunk
                audio_parts = []
                for audio in self.synthesizer.synthesize(
                    chunk.text,
                    stream=False,
                    speed=speed,
                ):
                    audio_parts.append(audio)
                    writer.write(audio)

                # Save chunk to checkpoint if enabled
                if self.checkpoint_manager and checkpoint_state and audio_parts:
                    chunk_audio = np.concatenate(audio_parts)
                    self.checkpoint_manager.save_chunk(i, chunk_audio)
                    checkpoint_state.completed_chunks.append(i)
                    self.checkpoint_manager.save_state(checkpoint_state)

                # Add paragraph pause if needed
                if chunk.paragraph_break_after:
                    writer.write_silence(self.paragraph_pause)

            # Add final chapter markers if not already added
            if chapters and not writer.chapters:
                # Estimate chapter positions based on text proportions
                total_duration = writer.duration_seconds
                total_chars = len(text)
                current_time = 0.0

                for ch in chapters:
                    if ch.start_char > 0:
                        current_time = (ch.start_char / total_chars) * total_duration
                    writer.chapters.append(
                        ChapterMarker(
                            title=ch.title,
                            start_time=current_time,
                        )
                    )

            duration = writer.duration_seconds

        # Stage 6: Finalize
        self._report_progress("finalizing", 100, f"Complete! Duration: {duration:.1f}s")

        # Cleanup checkpoint on successful completion
        if self.checkpoint_manager:
            self.checkpoint_manager.cleanup()

        return ConversionResult(
            output_path=str(output_path),
            duration_seconds=duration,
            chapters=writer.chapters,
            chunks_processed=len(chunks),
        )

    def extract_chapters(self, input_path: str) -> list[Chapter]:
        """
        Extract chapter information from a document without converting.

        Args:
            input_path: Path to the PDF/EPUB file

        Returns:
            List of detected chapters
        """
        extractor, _label = self._select_extractor(Path(input_path))
        doc = extractor.extract(input_path)
        return self.chapter_detector.detect(doc)

    def preview_text(
        self,
        input_path: str,
        max_chars: int = 1000,
    ) -> str:
        """
        Preview the processed text from a document.

        Args:
            input_path: Path to the PDF/EPUB file
            max_chars: Maximum characters to return

        Returns:
            Preprocessed text preview
        """
        extractor, _label = self._select_extractor(Path(input_path))
        doc = extractor.extract(input_path)
        text = self.preprocessor.process(doc.text)
        return text[:max_chars] + ("..." if len(text) > max_chars else "")

    def _select_extractor(self, input_path: Path):
        suffix = input_path.suffix.lower()
        if suffix == ".pdf":
            return self.pdf_extractor, "PDF"
        if suffix == ".epub":
            return self.epub_extractor, "EPUB"
        raise ValueError(f"Unsupported input format: {input_path.suffix or 'unknown'}")
