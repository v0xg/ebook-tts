"""Tests for audio writer functionality."""

from pathlib import Path

import numpy as np
import pytest

from ebook_tts.audio_writer import SimpleAudioWriter, StreamingAudioWriter


class TestSimpleAudioWriter:
    """Tests for SimpleAudioWriter."""

    def test_write_wav_file(self, tmp_path: Path):
        """Write audio to WAV file."""
        output_path = tmp_path / "test.wav"

        writer = SimpleAudioWriter(str(output_path), sample_rate=24000)
        # Write 1 second of silence
        samples = np.zeros(24000, dtype=np.float32)
        writer.write(samples)
        writer.finalize()

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_duration_tracking(self, tmp_path: Path):
        """Track duration from written samples."""
        output_path = tmp_path / "test.wav"

        writer = SimpleAudioWriter(str(output_path), sample_rate=24000)
        samples = np.zeros(24000, dtype=np.float32)
        writer.write(samples)

        assert writer.duration_seconds == pytest.approx(1.0, rel=0.01)


class TestStreamingAudioWriter:
    """Tests for StreamingAudioWriter."""

    def test_write_wav_file(self, tmp_path: Path):
        """Write audio to WAV file."""
        output_path = tmp_path / "test.wav"

        with StreamingAudioWriter(str(output_path), sample_rate=24000) as writer:
            # Write 1 second of silence
            samples = np.zeros(24000, dtype=np.float32)
            writer.write(samples)

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_write_multiple_chunks(self, tmp_path: Path):
        """Write multiple audio chunks."""
        output_path = tmp_path / "test.wav"

        with StreamingAudioWriter(str(output_path), sample_rate=24000) as writer:
            # Write 3 chunks of 0.5 seconds each
            for _ in range(3):
                samples = np.zeros(12000, dtype=np.float32)
                writer.write(samples)

        assert output_path.exists()

    def test_write_silence(self, tmp_path: Path):
        """Write silence of specified duration."""
        output_path = tmp_path / "test.wav"

        with StreamingAudioWriter(str(output_path), sample_rate=24000) as writer:
            writer.write_silence(1.0)  # 1 second of silence

            assert writer.duration_seconds == pytest.approx(1.0, rel=0.01)

    def test_add_chapter_marker(self, tmp_path: Path):
        """Add chapter marker."""
        output_path = tmp_path / "test.wav"

        with StreamingAudioWriter(str(output_path), sample_rate=24000) as writer:
            writer.add_chapter("Chapter 1")
            samples = np.zeros(24000, dtype=np.float32)
            writer.write(samples)

            assert len(writer.chapters) == 1
            assert writer.chapters[0].title == "Chapter 1"

    def test_duration_tracking(self, tmp_path: Path):
        """Track audio duration."""
        output_path = tmp_path / "test.wav"

        with StreamingAudioWriter(str(output_path), sample_rate=24000) as writer:
            # Write 2 seconds
            samples = np.zeros(48000, dtype=np.float32)
            writer.write(samples)

            assert writer.duration_seconds == pytest.approx(2.0, rel=0.01)

    def test_sample_count_tracking(self, tmp_path: Path):
        """Track samples through duration."""
        output_path = tmp_path / "test.wav"

        with StreamingAudioWriter(str(output_path), sample_rate=24000) as writer:
            samples = np.zeros(24000, dtype=np.float32)
            writer.write(samples)
            writer.write(samples)

            # 2 seconds of samples at 24000 Hz
            assert writer.duration_seconds == pytest.approx(2.0, rel=0.01)


class TestAudioWriterOutput:
    """Tests for output file validity."""

    def test_output_is_valid_wav(self, tmp_path: Path):
        """Output file is valid WAV format."""
        import soundfile as sf

        output_path = tmp_path / "test.wav"

        with StreamingAudioWriter(str(output_path), sample_rate=24000) as writer:
            samples = np.zeros(24000, dtype=np.float32)
            writer.write(samples)

        # Verify WAV file can be read with soundfile (supports float WAV)
        data, samplerate = sf.read(str(output_path))
        assert samplerate == 24000
        assert len(data) == 24000

    def test_output_file_created(self, tmp_path: Path):
        """Output file is created in existing directory."""
        output_path = tmp_path / "test.wav"

        with StreamingAudioWriter(str(output_path), sample_rate=24000) as writer:
            samples = np.zeros(24000, dtype=np.float32)
            writer.write(samples)

        assert output_path.exists()
        assert output_path.stat().st_size > 0
