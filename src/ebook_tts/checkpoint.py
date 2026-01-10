"""Checkpoint management for resumable conversions."""

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from .utils import hash_file, hash_settings


@dataclass
class CheckpointState:
    """State information for a checkpoint."""

    version: int
    input_hash: str
    input_path: str
    output_path: str
    settings_hash: str
    total_chunks: int
    completed_chunks: list[int]
    chapters: list[dict]
    sample_rate: int
    created_at: str
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointState":
        """Create CheckpointState from a dictionary."""
        return cls(
            version=data["version"],
            input_hash=data["input_hash"],
            input_path=data["input_path"],
            output_path=data["output_path"],
            settings_hash=data["settings_hash"],
            total_chunks=data["total_chunks"],
            completed_chunks=data["completed_chunks"],
            chapters=data["chapters"],
            sample_rate=data["sample_rate"],
            created_at=data["created_at"],
            updated_at=data.get("updated_at", data["created_at"]),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class CheckpointManager:
    """Manages checkpoint files for resumable conversions."""

    VERSION = 1

    def __init__(self, checkpoint_dir: Path):
        """
        Initialize the checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.state_file = self.checkpoint_dir / "state.json"
        self.chunks_dir = self.checkpoint_dir / "chunks"

    @staticmethod
    def get_checkpoint_dir(output_path: str) -> Path:
        """
        Get the checkpoint directory for a given output path.

        Creates a hidden directory next to the output file.
        Example: /path/to/book.wav -> /path/to/.book.checkpoint/
        """
        output = Path(output_path)
        return output.parent / f".{output.stem}.checkpoint"

    def exists(self) -> bool:
        """Check if a valid checkpoint exists."""
        return self.state_file.exists()

    def load_state(self) -> CheckpointState:
        """
        Load checkpoint state from disk.

        Returns:
            CheckpointState object

        Raises:
            FileNotFoundError: If no checkpoint exists
            ValueError: If checkpoint is invalid or corrupted
        """
        if not self.state_file.exists():
            raise FileNotFoundError(f"No checkpoint found at {self.checkpoint_dir}")

        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)

            if data.get("version") != self.VERSION:
                raise ValueError(
                    f"Unsupported checkpoint version: {data.get('version')} "
                    f"(expected {self.VERSION})"
                )

            return CheckpointState.from_dict(data)

        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted checkpoint state file: {e}") from e

    def save_state(self, state: CheckpointState) -> None:
        """
        Save checkpoint state to disk atomically.

        Uses a temp file + rename to ensure atomicity.
        """
        # Ensure directories exist
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

        # Update timestamp
        state.updated_at = datetime.now(timezone.utc).isoformat()

        # Write atomically
        fd, temp_path = tempfile.mkstemp(dir=self.checkpoint_dir, suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
            os.replace(temp_path, self.state_file)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def chunk_path(self, idx: int) -> Path:
        """Get the path for a chunk file."""
        return self.chunks_dir / f"{idx:06d}.npy"

    def save_chunk(self, idx: int, audio: np.ndarray) -> None:
        """
        Save a synthesized audio chunk.

        Args:
            idx: Chunk index
            audio: Audio data as numpy array
        """
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        np.save(self.chunk_path(idx), audio.astype(np.float32))

    def load_chunk(self, idx: int) -> Optional[np.ndarray]:
        """
        Load a previously saved chunk.

        Args:
            idx: Chunk index

        Returns:
            Audio data as numpy array, or None if chunk doesn't exist or is corrupt
        """
        path = self.chunk_path(idx)
        if not path.exists():
            return None

        try:
            return np.load(path)
        except Exception:
            return None

    def verify(self, input_path: str, settings: dict) -> tuple[bool, str]:
        """
        Verify that a checkpoint matches the current conversion parameters.

        Args:
            input_path: Path to the input file
            settings: Dictionary of conversion settings

        Returns:
            Tuple of (is_valid, message)
        """
        if not self.exists():
            return False, "No checkpoint exists"

        try:
            state = self.load_state()
        except (FileNotFoundError, ValueError) as e:
            return False, str(e)

        # Verify input file hash
        current_hash = hash_file(input_path)
        if current_hash != state.input_hash:
            return False, "Input file has changed since checkpoint was created"

        # Verify settings hash
        current_settings_hash = hash_settings(settings)
        if current_settings_hash != state.settings_hash:
            return False, "Conversion settings have changed"

        # Verify chunk files exist for completed chunks
        missing_chunks = []
        for idx in state.completed_chunks:
            chunk = self.load_chunk(idx)
            if chunk is None:
                missing_chunks.append(idx)

        if missing_chunks:
            # Remove missing chunks from completed list
            state.completed_chunks = [
                idx for idx in state.completed_chunks if idx not in missing_chunks
            ]
            self.save_state(state)
            return True, f"Recovered from {len(missing_chunks)} missing chunk(s)"

        return True, "Checkpoint is valid"

    def cleanup(self) -> None:
        """Remove the checkpoint directory and all its contents."""
        if self.checkpoint_dir.exists():
            shutil.rmtree(self.checkpoint_dir)

    def create_state(
        self,
        input_path: str,
        output_path: str,
        settings: dict,
        total_chunks: int,
        chapters: list[dict],
        sample_rate: int,
    ) -> CheckpointState:
        """
        Create a new checkpoint state.

        Args:
            input_path: Path to input file
            output_path: Path to output file
            settings: Conversion settings dictionary
            total_chunks: Total number of chunks to process
            chapters: List of chapter dictionaries
            sample_rate: Audio sample rate

        Returns:
            New CheckpointState object
        """
        now = datetime.now(timezone.utc).isoformat()
        return CheckpointState(
            version=self.VERSION,
            input_hash=hash_file(input_path),
            input_path=str(input_path),
            output_path=str(output_path),
            settings_hash=hash_settings(settings),
            total_chunks=total_chunks,
            completed_chunks=[],
            chapters=chapters,
            sample_rate=sample_rate,
            created_at=now,
            updated_at=now,
        )

    def get_progress(self) -> tuple[int, int]:
        """
        Get current progress from checkpoint.

        Returns:
            Tuple of (completed_chunks, total_chunks)
        """
        if not self.exists():
            return 0, 0

        state = self.load_state()
        return len(state.completed_chunks), state.total_chunks
