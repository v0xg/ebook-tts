"""EPUB text extraction using ebooklib and BeautifulSoup."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import urldefrag

from bs4 import BeautifulSoup
from ebooklib import epub

from .progress import ExtractedDocument, PageContent, TOCEntry


class EPUBExtractor:
    """Extract text and metadata from EPUB files."""

    def extract(self, epub_path: str) -> ExtractedDocument:
        """
        Extract text and metadata from an EPUB file.

        Args:
            epub_path: Path to the EPUB file

        Returns:
            ExtractedDocument with text, pages, metadata, and TOC
        """
        epub_path = Path(epub_path)
        if not epub_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {epub_path}")

        book = epub.read_epub(str(epub_path))

        pages, full_text, href_map = self._extract_spine_text(book)
        toc = self._extract_toc(book, href_map)

        metadata = {
            "title": self._get_metadata_value(book, "title"),
            "author": self._get_metadata_value(book, "creator"),
            "subject": self._get_metadata_value(book, "subject"),
            "creator": self._get_metadata_value(book, "creator"),
            "producer": self._get_metadata_value(book, "publisher"),
            "page_count": len(pages),
        }

        return ExtractedDocument(
            text=full_text,
            pages=pages,
            metadata=metadata,
            toc=toc,
        )

    def _get_metadata_value(self, book: epub.EpubBook, key: str) -> str:
        values = book.get_metadata("DC", key)
        if not values:
            return ""
        return values[0][0]

    def _extract_spine_text(self, book: epub.EpubBook) -> tuple[list[PageContent], str, dict[str, int]]:
        pages: list[PageContent] = []
        href_map: dict[str, int] = {}
        char_offset = 0

        spine_items = [item for item in book.spine if item[0] != "nav"]

        for idx, (item_id, _linear) in enumerate(spine_items, start=1):
            item = book.get_item_with_id(item_id)
            if item is None:
                continue

            href = getattr(item, "file_name", None) or item.get_name()
            if href:
                href_map[href] = idx
                href_map[Path(href).name] = idx

            content = item.get_content() or b""
            text = self._html_to_text(content)

            pages.append(PageContent(
                page_num=idx,
                text=text,
                char_offset=char_offset,
            ))

            char_offset += len(text) + 2

        full_text = "\n\n".join(page.text for page in pages if page.text)
        return pages, full_text, href_map

    def _html_to_text(self, content: bytes) -> str:
        html = content.decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        return "\n\n".join(lines)

    def _extract_toc(
        self,
        book: epub.EpubBook,
        href_map: dict[str, int],
    ) -> Optional[list[TOCEntry]]:
        toc_entries: list[TOCEntry] = []
        toc = book.toc or []

        for level, entry in self._flatten_toc(toc, level=1):
            href = getattr(entry, "href", None)
            title = getattr(entry, "title", None) or getattr(entry, "label", None)
            if not href or not title:
                continue

            href_base, _fragment = urldefrag(href)
            page_num = href_map.get(href_base) or href_map.get(Path(href_base).name)
            if not page_num:
                continue

            toc_entries.append(TOCEntry(
                level=level,
                title=title.strip(),
                page_num=page_num,
            ))

        return toc_entries if toc_entries else None

    def _flatten_toc(self, toc, level: int):
        for entry in toc:
            if isinstance(entry, tuple) and len(entry) == 2:
                section, children = entry
                yield from self._flatten_toc([section], level)
                yield from self._flatten_toc(children, level + 1)
            elif isinstance(entry, list):
                yield from self._flatten_toc(entry, level)
            else:
                yield level, entry
