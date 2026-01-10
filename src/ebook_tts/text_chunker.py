"""Text chunking for TTS synthesis."""

import re
from typing import Optional

from .progress import Chapter, TextChunk


class TextChunker:
    """Split text into TTS-friendly chunks at natural boundaries."""

    def __init__(
        self,
        max_chars: int = 400,
        min_chars: int = 50,
        paragraph_pause_chars: int = 100,
    ):
        """
        Initialize the chunker.

        Args:
            max_chars: Maximum characters per chunk (default 400)
            min_chars: Minimum characters per chunk before merging (default 50)
            paragraph_pause_chars: Add paragraph break marker if paragraph
                                   is longer than this (default 100)
        """
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.paragraph_pause_chars = paragraph_pause_chars
        self._nltk_initialized = False

    def _ensure_nltk(self) -> None:
        """Ensure NLTK punkt tokenizer is downloaded."""
        if self._nltk_initialized:
            return

        import nltk

        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            nltk.download("punkt", quiet=True)
        try:
            nltk.data.find("tokenizers/punkt_tab")
        except LookupError:
            try:
                nltk.download("punkt_tab", quiet=True)
            except Exception:
                pass  # punkt_tab may not be available in all versions

        self._nltk_initialized = True

    def chunk(
        self,
        text: str,
        chapters: Optional[list[Chapter]] = None,
    ) -> list[TextChunk]:
        """
        Split text into chunks suitable for TTS.

        Args:
            text: The full text to chunk
            chapters: Optional list of chapters for chapter-aware chunking

        Returns:
            List of TextChunk objects
        """
        self._ensure_nltk()

        # Split by paragraphs first
        paragraphs = self._split_paragraphs(text)

        all_chunks: list[TextChunk] = []
        current_char_pos = 0

        for para_idx, paragraph in enumerate(paragraphs):
            is_last_paragraph = para_idx == len(paragraphs) - 1

            # Determine chapter index for this position
            chapter_idx = None
            if chapters:
                chapter_idx = self._find_chapter_idx(current_char_pos, chapters)

            # Split paragraph into sentences
            sentences = self._split_sentences(paragraph)

            # Group sentences into chunks
            para_chunks = self._group_sentences(sentences, chapter_idx)

            # Mark last chunk of paragraph for pause (if paragraph is substantial)
            if para_chunks and len(paragraph) >= self.paragraph_pause_chars:
                para_chunks[-1].paragraph_break_after = not is_last_paragraph

            all_chunks.extend(para_chunks)
            current_char_pos += len(paragraph) + 2  # +2 for paragraph separator

        # Post-process: merge very short chunks
        all_chunks = self._merge_short_chunks(all_chunks)

        return all_chunks

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text into paragraphs."""
        # Split on double newlines
        paragraphs = re.split(r"\n\n+", text)
        # Filter empty paragraphs
        return [p.strip() for p in paragraphs if p.strip()]

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences using NLTK."""
        from nltk.tokenize import sent_tokenize

        sentences = sent_tokenize(text)
        return [s.strip() for s in sentences if s.strip()]

    def _group_sentences(
        self,
        sentences: list[str],
        chapter_idx: Optional[int],
    ) -> list[TextChunk]:
        """Group sentences into chunks respecting max_chars."""
        chunks: list[TextChunk] = []
        current_text = ""

        for sentence in sentences:
            # If single sentence exceeds max, split it
            if len(sentence) > self.max_chars:
                # Flush current buffer
                if current_text:
                    chunks.append(TextChunk(
                        text=current_text.strip(),
                        chapter_idx=chapter_idx,
                    ))
                    current_text = ""

                # Split long sentence
                sub_chunks = self._split_long_sentence(sentence)
                for sub in sub_chunks:
                    chunks.append(TextChunk(
                        text=sub.strip(),
                        chapter_idx=chapter_idx,
                    ))
                continue

            # Check if adding sentence would exceed max
            test_text = f"{current_text} {sentence}".strip()
            if len(test_text) > self.max_chars:
                # Flush current buffer
                if current_text:
                    chunks.append(TextChunk(
                        text=current_text.strip(),
                        chapter_idx=chapter_idx,
                    ))
                current_text = sentence
            else:
                current_text = test_text

        # Flush remaining text
        if current_text:
            chunks.append(TextChunk(
                text=current_text.strip(),
                chapter_idx=chapter_idx,
            ))

        return chunks

    def _split_long_sentence(self, sentence: str) -> list[str]:
        """Split a long sentence at natural break points."""
        chunks: list[str] = []

        # Try splitting at commas, semicolons, or conjunctions
        parts = re.split(r"([,;]\s+|\s+(?:and|or|but|because|while|when)\s+)", sentence)

        current = ""
        for part in parts:
            if not part:
                continue

            test = current + part
            if len(test) > self.max_chars and current:
                chunks.append(current.strip())
                current = part
            else:
                current = test

        if current:
            chunks.append(current.strip())

        # If still too long, force split at word boundaries
        final_chunks: list[str] = []
        for chunk in chunks:
            if len(chunk) > self.max_chars:
                final_chunks.extend(self._force_split(chunk))
            else:
                final_chunks.append(chunk)

        return final_chunks

    def _force_split(self, text: str) -> list[str]:
        """Force split text at word boundaries."""
        words = text.split()
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for word in words:
            if current_len + len(word) + 1 > self.max_chars and current:
                chunks.append(" ".join(current))
                current = [word]
                current_len = len(word)
            else:
                current.append(word)
                current_len += len(word) + 1

        if current:
            chunks.append(" ".join(current))

        return chunks

    def _merge_short_chunks(self, chunks: list[TextChunk]) -> list[TextChunk]:
        """Merge very short chunks with neighbors."""
        if not chunks:
            return chunks

        merged: list[TextChunk] = []
        buffer: Optional[TextChunk] = None

        for chunk in chunks:
            if buffer is None:
                buffer = chunk
                continue

            # Try to merge if buffer is too short
            if len(buffer.text) < self.min_chars:
                combined_len = len(buffer.text) + len(chunk.text) + 1
                if combined_len <= self.max_chars:
                    # Merge chunks
                    buffer = TextChunk(
                        text=f"{buffer.text} {chunk.text}",
                        chapter_idx=chunk.chapter_idx,
                        paragraph_break_after=chunk.paragraph_break_after,
                    )
                    continue

            # Can't merge, flush buffer
            merged.append(buffer)
            buffer = chunk

        if buffer:
            merged.append(buffer)

        return merged

    def _find_chapter_idx(
        self,
        char_pos: int,
        chapters: list[Chapter],
    ) -> Optional[int]:
        """Find the chapter index for a given character position."""
        for i, chapter in enumerate(chapters):
            start = chapter.start_char
            end = chapter.end_char if chapter.end_char else float("inf")
            if start <= char_pos < end:
                return i
        return None
