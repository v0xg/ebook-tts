"""Streaming audio output with chapter marker support."""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import soundfile as sf

from .progress import ChapterMarker
from .utils import get_output_format


class StreamingAudioWriter:
    """Memory-efficient streaming audio writer with chapter support."""

    def __init__(
        self,
        output_path: str,
        sample_rate: int = 24000,
        output_format: Optional[Literal["wav", "mp3", "m4b"]] = None,
    ):
        """
        Initialize the audio writer.

        Args:
            output_path: Path for the output file
            sample_rate: Audio sample rate (default 24000 for Kokoro)
            output_format: Output format (auto-detected from extension if None)
        """
        self.output_path = Path(output_path)
        self.sample_rate = sample_rate

        # Determine format
        if output_format:
            self.format = output_format
        else:
            self.format = get_output_format(str(output_path))

        self.chapters: list[ChapterMarker] = []
        self._samples_written: int = 0
        self._temp_wav: Optional[Path] = None
        self._sf_file: Optional[sf.SoundFile] = None

    @property
    def current_time(self) -> float:
        """Get current position in seconds."""
        return self._samples_written / self.sample_rate

    def __enter__(self):
        """Context manager entry."""
        self._open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.finalize()
        return False

    def _open(self) -> None:
        """Open the output file for writing."""
        # Always write to WAV first (we'll convert later if needed)
        if self.format == "wav":
            self._temp_wav = self.output_path
        else:
            # Create temp WAV file
            fd, temp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            self._temp_wav = Path(temp_path)

        # Open soundfile for streaming write
        self._sf_file = sf.SoundFile(
            str(self._temp_wav),
            mode="w",
            samplerate=self.sample_rate,
            channels=1,
            format="WAV",
            subtype="FLOAT",
        )

    def write(self, audio: np.ndarray) -> None:
        """
        Write audio data to the file.

        Args:
            audio: Audio samples as float32 numpy array
        """
        if self._sf_file is None:
            self._open()

        # Ensure correct format
        audio = audio.astype(np.float32)

        # Flatten if needed
        if audio.ndim > 1:
            audio = audio.squeeze()

        # Clip to valid range
        audio = np.clip(audio, -1.0, 1.0)

        # Write to file
        self._sf_file.write(audio)
        self._samples_written += len(audio)

    def write_silence(self, duration_seconds: float) -> None:
        """
        Write silence for the specified duration.

        Args:
            duration_seconds: Duration of silence in seconds
        """
        samples = int(duration_seconds * self.sample_rate)
        silence = np.zeros(samples, dtype=np.float32)
        self.write(silence)

    def add_chapter(self, title: str) -> None:
        """
        Add a chapter marker at the current position.

        Args:
            title: Chapter title
        """
        self.chapters.append(ChapterMarker(
            title=title,
            start_time=self.current_time,
        ))

    def finalize(self) -> None:
        """Close the file and apply any post-processing."""
        if self._sf_file is not None:
            self._sf_file.close()
            self._sf_file = None

        # Convert format if needed
        if self.format == "mp3":
            self._convert_to_mp3()
        elif self.format == "m4b":
            self._convert_to_m4b()

        # Clean up temp file
        if self._temp_wav and self._temp_wav != self.output_path:
            if self._temp_wav.exists():
                self._temp_wav.unlink()

    def _convert_to_mp3(self) -> None:
        """Convert WAV to MP3 with chapter markers."""
        if not self._temp_wav or not self._temp_wav.exists():
            return

        # Build FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-i", str(self._temp_wav),
            "-codec:a", "libmp3lame",
            "-b:a", "192k",
        ]

        # Add metadata if we have chapters
        if self.chapters:
            metadata_file = self._create_ffmpeg_metadata()
            cmd.extend(["-i", str(metadata_file), "-map_metadata", "1"])

        cmd.append(str(self.output_path))

        # Run conversion
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")

    def _convert_to_m4b(self) -> None:
        """Convert WAV to M4B (audiobook) format with chapters."""
        if not self._temp_wav or not self._temp_wav.exists():
            return

        # Build FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-i", str(self._temp_wav),
            "-codec:a", "aac",
            "-b:a", "128k",
        ]

        # Add chapter metadata
        if self.chapters:
            metadata_file = self._create_ffmpeg_metadata()
            cmd.extend(["-i", str(metadata_file), "-map_metadata", "1"])

        # Use mp4 container with .m4b extension
        cmd.extend(["-f", "mp4"])
        cmd.append(str(self.output_path))

        # Run conversion
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg conversion failed: {result.stderr}")

    def _create_ffmpeg_metadata(self) -> Path:
        """Create FFmpeg metadata file for chapters."""
        fd, metadata_path = tempfile.mkstemp(suffix=".txt")

        total_duration_ms = int(self.current_time * 1000)

        with os.fdopen(fd, "w") as f:
            f.write(";FFMETADATA1\n")

            for i, chapter in enumerate(self.chapters):
                start_ms = int(chapter.start_time * 1000)

                # Determine end time
                if i + 1 < len(self.chapters):
                    end_ms = int(self.chapters[i + 1].start_time * 1000)
                else:
                    end_ms = total_duration_ms

                f.write("\n[CHAPTER]\n")
                f.write("TIMEBASE=1/1000\n")
                f.write(f"START={start_ms}\n")
                f.write(f"END={end_ms}\n")
                f.write(f"title={chapter.title}\n")

        return Path(metadata_path)

    @property
    def duration_seconds(self) -> float:
        """Get total duration in seconds."""
        return self._samples_written / self.sample_rate


class SimpleAudioWriter:
    """Simple in-memory audio writer for small files."""

    def __init__(
        self,
        output_path: str,
        sample_rate: int = 24000,
    ):
        """
        Initialize the simple writer.

        Args:
            output_path: Path for the output file
            sample_rate: Audio sample rate
        """
        self.output_path = Path(output_path)
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []

    def write(self, audio: np.ndarray) -> None:
        """Append audio to buffer."""
        self._chunks.append(audio.astype(np.float32))

    def finalize(self) -> None:
        """Write all audio to file."""
        if not self._chunks:
            return

        # Concatenate all chunks
        audio = np.concatenate(self._chunks)

        # Write to file
        sf.write(str(self.output_path), audio, self.sample_rate)

    @property
    def duration_seconds(self) -> float:
        """Get total duration in seconds."""
        total_samples = sum(len(chunk) for chunk in self._chunks)
        return total_samples / self.sample_rate
