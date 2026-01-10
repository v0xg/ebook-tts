"""PDF text extraction using PyMuPDF."""

from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from .progress import ExtractedDocument, PageContent, TOCEntry


class PDFExtractor:
    """Extract text and metadata from PDF files."""

    def __init__(self, preserve_layout: bool = False):
        """
        Initialize the extractor.

        Args:
            preserve_layout: If True, try to preserve text layout.
                           If False, extract as flowing text.
        """
        self.preserve_layout = preserve_layout

    def extract(self, pdf_path: str) -> ExtractedDocument:
        """
        Extract text and metadata from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            ExtractedDocument with text, pages, metadata, and TOC
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = fitz.open(pdf_path)

        try:
            # Extract metadata
            metadata = self._extract_metadata(doc)

            # Extract TOC
            toc = self._extract_toc(doc)

            # Extract text from each page
            pages = self._extract_pages(doc)

            # Combine all text
            full_text = "\n\n".join(page.text for page in pages if page.text)

            return ExtractedDocument(
                text=full_text,
                pages=pages,
                metadata=metadata,
                toc=toc,
            )
        finally:
            doc.close()

    def _extract_metadata(self, doc: fitz.Document) -> dict:
        """Extract PDF metadata."""
        meta = doc.metadata or {}
        return {
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "page_count": doc.page_count,
        }

    def _extract_toc(self, doc: fitz.Document) -> Optional[list[TOCEntry]]:
        """Extract table of contents from PDF."""
        raw_toc = doc.get_toc()

        if not raw_toc:
            return None

        toc_entries = []
        for item in raw_toc:
            # TOC format: [level, title, page_num, ...]
            if len(item) >= 3:
                level = item[0]
                title = item[1].strip()
                page_num = item[2]

                # Only include entries with valid page numbers
                if isinstance(page_num, int) and page_num > 0:
                    toc_entries.append(TOCEntry(
                        level=level,
                        title=title,
                        page_num=page_num,
                    ))

        return toc_entries if toc_entries else None

    def _extract_pages(self, doc: fitz.Document) -> list[PageContent]:
        """Extract text from all pages."""
        pages = []
        char_offset = 0

        for page_num in range(doc.page_count):
            page = doc[page_num]

            # Extract text based on layout preference
            if self.preserve_layout:
                text = page.get_text("text", sort=True)
            else:
                # Use blocks for better paragraph detection
                text = self._extract_flowing_text(page)

            pages.append(PageContent(
                page_num=page_num + 1,  # 1-indexed
                text=text.strip(),
                char_offset=char_offset,
            ))

            # Update offset (+2 for paragraph separator between pages)
            char_offset += len(text) + 2

        return pages

    def _extract_flowing_text(self, page: fitz.Page) -> str:
        """Extract text as flowing paragraphs."""
        # Get text blocks (paragraphs)
        blocks = page.get_text("blocks", sort=True)

        paragraphs = []
        for block in blocks:
            # blocks format: (x0, y0, x1, y1, "text", block_no, block_type)
            if len(block) >= 5 and block[6] == 0:  # type 0 = text
                text = block[4].strip()
                if text:
                    # Replace newlines within block with spaces
                    text = " ".join(text.split())
                    paragraphs.append(text)

        return "\n\n".join(paragraphs)

    def get_page_text(
        self,
        pdf_path: str,
        page_num: int,
    ) -> str:
        """
        Get text from a specific page.

        Args:
            pdf_path: Path to PDF file
            page_num: Page number (1-indexed)

        Returns:
            Text content of the page
        """
        doc = fitz.open(pdf_path)
        try:
            if page_num < 1 or page_num > doc.page_count:
                raise ValueError(
                    f"Invalid page number: {page_num}. "
                    f"PDF has {doc.page_count} pages."
                )
            page = doc[page_num - 1]
            return page.get_text("text").strip()
        finally:
            doc.close()

    def get_page_count(self, pdf_path: str) -> int:
        """Get the number of pages in a PDF."""
        doc = fitz.open(pdf_path)
        try:
            return doc.page_count
        finally:
            doc.close()
