"""Chapter detection from PDF TOC and text patterns."""

import re
from typing import Optional

from .progress import Chapter, ExtractedDocument, TOCEntry
from .utils import normalize_chapter_number


class ChapterDetector:
    """Detect chapter boundaries from TOC or text patterns."""

    # English chapter patterns
    EN_PATTERNS = [
        # Chapter X, CHAPTER 1, etc.
        (r"^Chapter\s+(\d+|[IVXLC]+)(?:\s*[:\-.]?\s*(.*))?$", "Chapter"),
        (r"^CHAPTER\s+(\d+|[IVXLC]+)(?:\s*[:\-.]?\s*(.*))?$", "CHAPTER"),
        # Part X
        (r"^Part\s+(\d+|[IVXLC]+)(?:\s*[:\-.]?\s*(.*))?$", "Part"),
        (r"^PART\s+(\d+|[IVXLC]+)(?:\s*[:\-.]?\s*(.*))?$", "PART"),
        # Special chapters
        (r"^(PROLOGUE)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Prologue)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(EPILOGUE)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Epilogue)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(INTRODUCTION)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Introduction)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(CONCLUSION)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Conclusion)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(PREFACE)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Preface)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(FOREWORD)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Foreword)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(AFTERWORD)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Afterword)(?:\s*[:\-.]?\s*(.*))?$", None),
    ]

    # Spanish chapter patterns
    ES_PATTERNS = [
        # Capítulo X
        (r"^Capítulo\s+(\d+|[IVXLC]+)(?:\s*[:\-.]?\s*(.*))?$", "Capítulo"),
        (r"^CAPÍTULO\s+(\d+|[IVXLC]+)(?:\s*[:\-.]?\s*(.*))?$", "CAPÍTULO"),
        (r"^Capitulo\s+(\d+|[IVXLC]+)(?:\s*[:\-.]?\s*(.*))?$", "Capítulo"),  # Without accent
        (r"^CAPITULO\s+(\d+|[IVXLC]+)(?:\s*[:\-.]?\s*(.*))?$", "CAPÍTULO"),
        # Parte X
        (r"^Parte\s+(\d+|[IVXLC]+)(?:\s*[:\-.]?\s*(.*))?$", "Parte"),
        (r"^PARTE\s+(\d+|[IVXLC]+)(?:\s*[:\-.]?\s*(.*))?$", "PARTE"),
        # Special chapters
        (r"^(PRÓLOGO)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Prólogo)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(PROLOGO)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Prologo)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(EPÍLOGO)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Epílogo)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(EPILOGO)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Epilogo)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(INTRODUCCIÓN)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Introducción)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(INTRODUCCION)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(CONCLUSIÓN)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Conclusión)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(CONCLUSION)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(PREFACIO)(?:\s*[:\-.]?\s*(.*))?$", None),
        (r"^(Prefacio)(?:\s*[:\-.]?\s*(.*))?$", None),
    ]

    def __init__(
        self,
        min_chapter_length: int = 500,
        use_toc_first: bool = True,
    ):
        """
        Initialize the detector.

        Args:
            min_chapter_length: Minimum characters for a valid chapter
            use_toc_first: If True, prefer TOC over pattern matching
        """
        self.min_chapter_length = min_chapter_length
        self.use_toc_first = use_toc_first
        self._all_patterns = self.EN_PATTERNS + self.ES_PATTERNS

    def detect(self, doc: ExtractedDocument) -> list[Chapter]:
        """
        Detect chapters in the document.

        Args:
            doc: Extracted document with text and optional TOC

        Returns:
            List of detected chapters sorted by start position
        """
        chapters = []

        # Try TOC first if available and preferred
        if self.use_toc_first and doc.toc:
            chapters = self._from_toc(doc.toc, doc.pages)

        # Fall back to pattern matching if no TOC chapters found
        if not chapters:
            chapters = self._from_patterns(doc.text)

        # Filter false positives
        chapters = self._filter_false_positives(chapters, doc.text)

        # Set end positions
        chapters = self._set_end_positions(chapters, len(doc.text))

        return chapters

    def _from_toc(
        self,
        toc: list[TOCEntry],
        pages: list,
    ) -> list[Chapter]:
        """Create chapters from TOC entries."""
        chapters = []

        # Only use top-level TOC entries (level 1)
        top_level = [entry for entry in toc if entry.level == 1]

        # If no level 1 entries, use level 2
        if not top_level:
            top_level = [entry for entry in toc if entry.level <= 2]

        for entry in top_level:
            # Find character offset for this page
            char_offset = 0
            for page in pages:
                if page.page_num == entry.page_num:
                    char_offset = page.char_offset
                    break
                elif page.page_num > entry.page_num:
                    # Use previous page's offset
                    break
                char_offset = page.char_offset

            chapters.append(Chapter(
                title=entry.title,
                start_page=entry.page_num,
                start_char=char_offset,
            ))

        return chapters

    def _from_patterns(self, text: str) -> list[Chapter]:
        """Detect chapters using regex patterns."""
        chapters = []
        lines = text.split("\n")
        char_pos = 0

        for line in lines:
            stripped = line.strip()

            for pattern, prefix in self._all_patterns:
                match = re.match(pattern, stripped, re.IGNORECASE)
                if match:
                    # Build chapter title
                    if prefix:
                        # Numbered chapter: "Chapter 1: Title"
                        num = match.group(1)
                        subtitle = match.group(2) if len(match.groups()) > 1 else ""
                        if subtitle:
                            title = f"{prefix} {num}: {subtitle}".strip()
                        else:
                            title = f"{prefix} {num}"
                    else:
                        # Special chapter: "Prologue"
                        title = match.group(1)
                        if len(match.groups()) > 1 and match.group(2):
                            title = f"{title}: {match.group(2)}".strip()

                    chapters.append(Chapter(
                        title=title,
                        start_page=0,  # Unknown from pattern matching
                        start_char=char_pos,
                    ))
                    break

            char_pos += len(line) + 1  # +1 for newline

        return chapters

    def _filter_false_positives(
        self,
        chapters: list[Chapter],
        full_text: str,
    ) -> list[Chapter]:
        """Remove chapters that are likely false positives."""
        if len(chapters) <= 1:
            return chapters

        filtered = []

        for i, chapter in enumerate(chapters):
            # Calculate chapter length
            if i + 1 < len(chapters):
                end_char = chapters[i + 1].start_char
            else:
                end_char = len(full_text)

            chapter_length = end_char - chapter.start_char

            # Skip very short "chapters"
            if chapter_length < self.min_chapter_length:
                continue

            filtered.append(chapter)

        return filtered

    def _set_end_positions(
        self,
        chapters: list[Chapter],
        text_length: int,
    ) -> list[Chapter]:
        """Set end_char for each chapter."""
        for i, chapter in enumerate(chapters):
            if i + 1 < len(chapters):
                chapter.end_char = chapters[i + 1].start_char
            else:
                chapter.end_char = text_length

        return chapters

    def get_chapter_titles(self, chapters: list[Chapter]) -> list[str]:
        """Get list of chapter titles."""
        return [ch.title for ch in chapters]

    def find_chapter_by_number(
        self,
        chapters: list[Chapter],
        number: int,
    ) -> Optional[Chapter]:
        """
        Find a chapter by its number.

        Args:
            chapters: List of chapters
            number: Chapter number to find (1-indexed)

        Returns:
            Chapter if found, None otherwise
        """
        for chapter in chapters:
            # Try to extract number from title
            match = re.search(r"(\d+|[IVXLC]+)", chapter.title)
            if match:
                chapter_num = normalize_chapter_number(match.group(1))
                if chapter_num == number:
                    return chapter
        return None
