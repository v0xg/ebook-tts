"""Tests for EPUBExtractor."""

from pathlib import Path

from ebooklib import epub

from ebook_tts.epub_extractor import EPUBExtractor


def _build_epub(tmp_path: Path) -> Path:
    book = epub.EpubBook()
    book.set_identifier("id123")
    book.set_title("Sample Book")
    book.add_author("Test Author")

    chapter1 = epub.EpubHtml(title="Chapter 1", file_name="chap1.xhtml")
    chapter1.content = "<h1>Chapter 1</h1><p>First paragraph.</p>"

    chapter2 = epub.EpubHtml(title="Chapter 2", file_name="chap2.xhtml")
    chapter2.content = "<h1>Chapter 2</h1><p>Second paragraph.</p>"

    book.add_item(chapter1)
    book.add_item(chapter2)

    book.toc = (
        epub.Link("chap1.xhtml", "Chapter 1", "chap1"),
        epub.Link("chap2.xhtml", "Chapter 2", "chap2"),
    )

    book.spine = ["nav", chapter1, chapter2]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    output_path = tmp_path / "sample.epub"
    epub.write_epub(str(output_path), book)
    return output_path


def test_epub_extractor_extracts_text_and_toc(tmp_path: Path):
    epub_path = _build_epub(tmp_path)
    extractor = EPUBExtractor()

    doc = extractor.extract(str(epub_path))

    assert "Chapter 1" in doc.text
    assert "First paragraph." in doc.text
    assert doc.metadata.get("title") == "Sample Book"
    assert doc.toc is not None
    assert len(doc.toc) == 2
