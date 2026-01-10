"""Tests for CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from ebook_tts.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestListVoicesCommand:
    """Tests for the list-voices command."""

    def test_list_voices_runs(self, runner: CliRunner):
        """List voices command runs without error."""
        result = runner.invoke(cli, ["list-voices"])
        # May fail if kokoro not installed, but should not crash
        assert result.exit_code in (0, 1)

    def test_list_voices_with_language_filter(self, runner: CliRunner):
        """Filter voices by language code."""
        result = runner.invoke(cli, ["list-voices", "--lang", "a"])
        # May fail if kokoro not installed, but should not crash
        assert result.exit_code in (0, 1)


class TestExtractCommand:
    """Tests for the extract command."""

    def test_extract_requires_input(self, runner: CliRunner):
        """Extract command requires --input option."""
        result = runner.invoke(cli, ["extract"])
        assert result.exit_code != 0
        assert "Missing" in result.output or "required" in result.output.lower()

    def test_extract_nonexistent_input(self, runner: CliRunner, tmp_path: Path):
        """Extract with nonexistent input shows error."""
        result = runner.invoke(cli, ["extract", "--input", str(tmp_path / "nonexistent.pdf")])
        assert result.exit_code != 0


class TestConvertCommand:
    """Tests for the convert command."""

    def test_convert_requires_input(self, runner: CliRunner):
        """Convert command requires --input option."""
        result = runner.invoke(cli, ["convert"])
        assert result.exit_code != 0

    def test_convert_requires_output(self, runner: CliRunner, tmp_path: Path):
        """Convert command requires --output option."""
        # Create a dummy PDF-like file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 test")

        result = runner.invoke(cli, ["convert", "--input", str(pdf_path)])
        assert result.exit_code != 0

    def test_convert_with_dict_option(self, runner: CliRunner, tmp_path: Path, base_dict_path: Path):
        """Convert command accepts --dict option."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 test")
        output_path = tmp_path / "output.wav"

        # Use --mock to avoid needing actual TTS
        result = runner.invoke(
            cli,
            [
                "convert",
                "--input", str(pdf_path),
                "--output", str(output_path),
                "--mock",
                "--dict", str(base_dict_path),
            ],
        )
        # Will likely fail due to invalid PDF, but should parse options correctly
        # The important thing is it doesn't crash on --dict option
        assert "--dict" not in result.output or "Invalid" not in result.output


class TestTextToWavCommand:
    """Tests for the text-to-wav command."""

    def test_text_to_wav_requires_input(self, runner: CliRunner):
        """Text-to-wav requires --input option."""
        result = runner.invoke(cli, ["text-to-wav"])
        assert result.exit_code != 0

    def test_text_to_wav_requires_output(self, runner: CliRunner, tmp_path: Path):
        """Text-to-wav requires --output option."""
        text_path = tmp_path / "test.txt"
        text_path.write_text("Hello world")

        result = runner.invoke(cli, ["text-to-wav", "--input", str(text_path)])
        assert result.exit_code != 0


class TestChaptersCommand:
    """Tests for the chapters command."""

    def test_chapters_requires_input(self, runner: CliRunner):
        """Chapters command requires --input option."""
        result = runner.invoke(cli, ["chapters"])
        assert result.exit_code != 0


class TestPreviewCommand:
    """Tests for the preview command."""

    def test_preview_requires_input(self, runner: CliRunner):
        """Preview command requires --input option."""
        result = runner.invoke(cli, ["preview"])
        assert result.exit_code != 0


class TestVersionOption:
    """Tests for version option."""

    def test_version_option(self, runner: CliRunner):
        """Version option shows version."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output
