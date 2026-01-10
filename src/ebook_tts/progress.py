"""Progress reporting dataclasses for the document to audiobook converter."""

from dataclasses import dataclass, field
from typing import Callable, Literal, Optional


@dataclass
class ProgressUpdate:
    """Represents a progress update during conversion."""

    stage: Literal["extracting", "preprocessing", "chunking", "synthesizing", "finalizing"]
    percent: float
    message: str
    chapter: Optional[str] = None
    chunks_completed: int = 0
    chunks_total: int = 0

    def __str__(self) -> str:
        if self.chapter:
            return f"[{self.stage}] {self.percent:.1f}% - {self.chapter}: {self.message}"
        return f"[{self.stage}] {self.percent:.1f}% - {self.message}"


ProgressCallback = Callable[[ProgressUpdate], None]


@dataclass
class TOCEntry:
    """Represents a table of contents entry from a document."""

    level: int
    title: str
    page_num: int


@dataclass
class PageContent:
    """Represents the content of a single document section."""

    page_num: int
    text: str
    char_offset: int  # Global character offset for chapter detection


@dataclass
class ExtractedDocument:
    """Represents the complete extracted content from a document."""

    text: str
    pages: list[PageContent]
    metadata: dict
    toc: Optional[list[TOCEntry]] = None


@dataclass
class Chapter:
    """Represents a detected chapter in the document."""

    title: str
    start_page: int
    start_char: int
    end_char: Optional[int] = None

    def get_text(self, full_text: str) -> str:
        """Extract chapter text from the full document text."""
        if self.end_char is not None:
            return full_text[self.start_char:self.end_char]
        return full_text[self.start_char:]


@dataclass
class TextChunk:
    """Represents a chunk of text ready for TTS synthesis."""

    text: str
    chapter_idx: Optional[int] = None
    paragraph_break_after: bool = False  # Insert pause after this chunk


@dataclass
class ChapterMarker:
    """Represents a chapter marker for audio output."""

    title: str
    start_time: float  # In seconds


@dataclass
class ConversionResult:
    """Result of a document to audiobook conversion."""

    output_path: str
    duration_seconds: float
    chapters: list[ChapterMarker] = field(default_factory=list)
    chunks_processed: int = 0

    @property
    def duration_formatted(self) -> str:
        """Return duration as HH:MM:SS format."""
        hours = int(self.duration_seconds // 3600)
        minutes = int((self.duration_seconds % 3600) // 60)
        seconds = int(self.duration_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
