"""PDF to Audiobook Converter using Kokoro TTS."""

from .audio_synthesizer import KokoroSynthesizer, MockSynthesizer
from .audio_writer import SimpleAudioWriter, StreamingAudioWriter
from .chapter_detector import ChapterDetector
from .converter import PDFToAudiobook
from .epub_extractor import EPUBExtractor
from .pdf_extractor import PDFExtractor
from .progress import (
    Chapter,
    ChapterMarker,
    ConversionResult,
    ExtractedDocument,
    PageContent,
    ProgressCallback,
    ProgressUpdate,
    TextChunk,
    TOCEntry,
)
from .pronunciation_dict import PronunciationDict, load_dictionary
from .text_chunker import TextChunker
from .text_preprocessor import TextPreprocessor

__version__ = "1.0.0"
__all__ = [
    # Main converter
    "PDFToAudiobook",
    # Components
    "PDFExtractor",
    "EPUBExtractor",
    "ChapterDetector",
    "TextPreprocessor",
    "TextChunker",
    "KokoroSynthesizer",
    "MockSynthesizer",
    "StreamingAudioWriter",
    "SimpleAudioWriter",
    # Pronunciation
    "PronunciationDict",
    "load_dictionary",
    # Data classes
    "ProgressUpdate",
    "ProgressCallback",
    "TOCEntry",
    "PageContent",
    "ExtractedDocument",
    "Chapter",
    "TextChunk",
    "ChapterMarker",
    "ConversionResult",
]
