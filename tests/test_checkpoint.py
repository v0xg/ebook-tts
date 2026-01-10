"""Tests for checkpoint functionality."""

import json
from pathlib import Path

import numpy as np
import pytest

from ebook_tts.checkpoint import CheckpointManager, CheckpointState
from ebook_tts.utils import hash_file, hash_settings


class TestHashFunctions:
    """Tests for hashing utilities."""

    def test_hash_file(self, tmp_path: Path):
        """Hash a file and verify consistency."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        hash1 = hash_file(str(test_file))
        hash2 = hash_file(str(test_file))

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_hash_file_different_content(self, tmp_path: Path):
        """Different content produces different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("Content A")
        file2.write_text("Content B")

        assert hash_file(str(file1)) != hash_file(str(file2))

    def test_hash_settings(self):
        """Hash settings dictionary."""
        settings = {"voice": "af_heart", "speed": 1.0}
        hash1 = hash_settings(settings)
        hash2 = hash_settings(settings)

        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated hash

    def test_hash_settings_order_independent(self):
        """Settings hash is order-independent."""
        settings1 = {"voice": "af_heart", "speed": 1.0}
        settings2 = {"speed": 1.0, "voice": "af_heart"}

        assert hash_settings(settings1) == hash_settings(settings2)

    def test_hash_settings_different_values(self):
        """Different settings produce different hashes."""
        settings1 = {"voice": "af_heart", "speed": 1.0}
        settings2 = {"voice": "bf_emma", "speed": 1.0}

        assert hash_settings(settings1) != hash_settings(settings2)


class TestCheckpointState:
    """Tests for CheckpointState dataclass."""

    def test_from_dict(self):
        """Create CheckpointState from dictionary."""
        data = {
            "version": 1,
            "input_hash": "abc123",
            "input_path": "/path/to/input.pdf",
            "output_path": "/path/to/output.wav",
            "settings_hash": "def456",
            "total_chunks": 100,
            "completed_chunks": [0, 1, 2],
            "chapters": [{"title": "Chapter 1", "start_char": 0}],
            "sample_rate": 24000,
            "created_at": "2025-01-01T00:00:00Z",
        }

        state = CheckpointState.from_dict(data)

        assert state.version == 1
        assert state.input_hash == "abc123"
        assert state.total_chunks == 100
        assert len(state.completed_chunks) == 3

    def test_to_dict(self):
        """Convert CheckpointState to dictionary."""
        state = CheckpointState(
            version=1,
            input_hash="abc123",
            input_path="/path/to/input.pdf",
            output_path="/path/to/output.wav",
            settings_hash="def456",
            total_chunks=100,
            completed_chunks=[0, 1, 2],
            chapters=[],
            sample_rate=24000,
            created_at="2025-01-01T00:00:00Z",
        )

        data = state.to_dict()

        assert data["version"] == 1
        assert data["input_hash"] == "abc123"
        assert data["total_chunks"] == 100


class TestCheckpointManager:
    """Tests for CheckpointManager."""

    @pytest.fixture
    def checkpoint_dir(self, tmp_path: Path) -> Path:
        """Temporary checkpoint directory."""
        return tmp_path / ".test.checkpoint"

    @pytest.fixture
    def manager(self, checkpoint_dir: Path) -> CheckpointManager:
        """Create a CheckpointManager instance."""
        return CheckpointManager(checkpoint_dir)

    @pytest.fixture
    def sample_input_file(self, tmp_path: Path) -> Path:
        """Create a sample input file."""
        input_file = tmp_path / "sample.pdf"
        input_file.write_bytes(b"PDF content here")
        return input_file

    def test_get_checkpoint_dir(self):
        """Get checkpoint directory from output path."""
        result = CheckpointManager.get_checkpoint_dir("/path/to/book.wav")
        assert result == Path("/path/to/.book.checkpoint")

    def test_get_checkpoint_dir_with_subdirs(self):
        """Checkpoint dir handles paths with subdirectories."""
        result = CheckpointManager.get_checkpoint_dir("/home/user/audiobooks/my_book.mp3")
        assert result == Path("/home/user/audiobooks/.my_book.checkpoint")

    def test_exists_false_initially(self, manager: CheckpointManager):
        """Checkpoint doesn't exist initially."""
        assert manager.exists() is False

    def test_save_and_load_state(self, manager: CheckpointManager, sample_input_file: Path):
        """Save and load checkpoint state."""
        state = manager.create_state(
            input_path=str(sample_input_file),
            output_path="/tmp/output.wav",
            settings={"voice": "af_heart"},
            total_chunks=50,
            chapters=[{"title": "Chapter 1"}],
            sample_rate=24000,
        )

        manager.save_state(state)

        assert manager.exists()

        loaded = manager.load_state()
        assert loaded.total_chunks == 50
        assert loaded.input_path == str(sample_input_file)

    def test_save_and_load_chunk(self, manager: CheckpointManager):
        """Save and load audio chunk."""
        # Create checkpoint dir
        manager.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        manager.chunks_dir.mkdir(parents=True, exist_ok=True)

        audio = np.random.randn(24000).astype(np.float32)
        manager.save_chunk(0, audio)

        loaded = manager.load_chunk(0)

        assert loaded is not None
        assert np.allclose(audio, loaded)

    def test_load_missing_chunk_returns_none(self, manager: CheckpointManager):
        """Loading non-existent chunk returns None."""
        manager.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        result = manager.load_chunk(999)
        assert result is None

    def test_chunk_path(self, manager: CheckpointManager):
        """Chunk path uses zero-padded index."""
        assert manager.chunk_path(0) == manager.chunks_dir / "000000.npy"
        assert manager.chunk_path(42) == manager.chunks_dir / "000042.npy"
        assert manager.chunk_path(999999) == manager.chunks_dir / "999999.npy"

    def test_verify_matching_checkpoint(
        self, manager: CheckpointManager, sample_input_file: Path
    ):
        """Verify checkpoint with matching settings."""
        settings = {"voice": "af_heart", "speed": 1.0}

        state = manager.create_state(
            input_path=str(sample_input_file),
            output_path="/tmp/output.wav",
            settings=settings,
            total_chunks=10,
            chapters=[],
            sample_rate=24000,
        )
        manager.save_state(state)

        valid, msg = manager.verify(str(sample_input_file), settings)

        assert valid is True

    def test_verify_input_file_changed(
        self, manager: CheckpointManager, sample_input_file: Path, tmp_path: Path
    ):
        """Verify fails when input file changes."""
        settings = {"voice": "af_heart"}

        state = manager.create_state(
            input_path=str(sample_input_file),
            output_path="/tmp/output.wav",
            settings=settings,
            total_chunks=10,
            chapters=[],
            sample_rate=24000,
        )
        manager.save_state(state)

        # Modify the input file
        sample_input_file.write_bytes(b"Different content")

        valid, msg = manager.verify(str(sample_input_file), settings)

        assert valid is False
        assert "changed" in msg.lower()

    def test_verify_settings_changed(
        self, manager: CheckpointManager, sample_input_file: Path
    ):
        """Verify fails when settings change."""
        original_settings = {"voice": "af_heart"}
        new_settings = {"voice": "bf_emma"}

        state = manager.create_state(
            input_path=str(sample_input_file),
            output_path="/tmp/output.wav",
            settings=original_settings,
            total_chunks=10,
            chapters=[],
            sample_rate=24000,
        )
        manager.save_state(state)

        valid, msg = manager.verify(str(sample_input_file), new_settings)

        assert valid is False
        assert "settings" in msg.lower()

    def test_cleanup(self, manager: CheckpointManager, sample_input_file: Path):
        """Cleanup removes checkpoint directory."""
        state = manager.create_state(
            input_path=str(sample_input_file),
            output_path="/tmp/output.wav",
            settings={},
            total_chunks=10,
            chapters=[],
            sample_rate=24000,
        )
        manager.save_state(state)
        manager.save_chunk(0, np.zeros(100, dtype=np.float32))

        assert manager.exists()
        assert manager.checkpoint_dir.exists()

        manager.cleanup()

        assert not manager.checkpoint_dir.exists()

    def test_get_progress(self, manager: CheckpointManager, sample_input_file: Path):
        """Get progress from checkpoint."""
        state = manager.create_state(
            input_path=str(sample_input_file),
            output_path="/tmp/output.wav",
            settings={},
            total_chunks=100,
            chapters=[],
            sample_rate=24000,
        )
        state.completed_chunks = [0, 1, 2, 3, 4]
        manager.save_state(state)

        completed, total = manager.get_progress()

        assert completed == 5
        assert total == 100

    def test_get_progress_no_checkpoint(self, manager: CheckpointManager):
        """Get progress when no checkpoint exists."""
        completed, total = manager.get_progress()

        assert completed == 0
        assert total == 0

    def test_verify_recovers_missing_chunks(
        self, manager: CheckpointManager, sample_input_file: Path
    ):
        """Verify removes missing chunks from completed list."""
        settings = {"voice": "af_heart"}

        state = manager.create_state(
            input_path=str(sample_input_file),
            output_path="/tmp/output.wav",
            settings=settings,
            total_chunks=10,
            chapters=[],
            sample_rate=24000,
        )
        # Mark chunks as completed but don't actually save them
        state.completed_chunks = [0, 1, 2, 3, 4]
        manager.save_state(state)

        # Save only chunks 0 and 1
        manager.save_chunk(0, np.zeros(100, dtype=np.float32))
        manager.save_chunk(1, np.zeros(100, dtype=np.float32))

        valid, msg = manager.verify(str(sample_input_file), settings)

        # Should still be valid but with recovered message
        assert valid is True

        # Reload and check completed chunks were updated
        reloaded = manager.load_state()
        assert 0 in reloaded.completed_chunks
        assert 1 in reloaded.completed_chunks
        assert 2 not in reloaded.completed_chunks

    def test_atomic_state_write(self, manager: CheckpointManager, sample_input_file: Path):
        """State file is written atomically."""
        state = manager.create_state(
            input_path=str(sample_input_file),
            output_path="/tmp/output.wav",
            settings={},
            total_chunks=10,
            chapters=[],
            sample_rate=24000,
        )
        manager.save_state(state)

        # Verify state file is valid JSON
        with open(manager.state_file) as f:
            data = json.load(f)

        assert data["version"] == 1
        assert data["total_chunks"] == 10


class TestCheckpointIntegration:
    """Integration tests for checkpointing with converter."""

    @pytest.fixture
    def sample_pdf(self, tmp_path: Path) -> Path:
        """Create a minimal test PDF."""
        # This is a minimal valid PDF structure
        pdf_content = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj
4 0 obj << /Length 44 >> stream
BT /F1 12 Tf 100 700 Td (Hello World) Tj ET
endstream endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000214 00000 n
trailer << /Size 5 /Root 1 0 R >>
startxref
307
%%EOF"""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(pdf_content)
        return pdf_path

    def test_convert_with_checkpoint_creates_files(
        self, sample_pdf: Path, tmp_path: Path
    ):
        """Conversion with checkpoint creates checkpoint files."""
        from ebook_tts.checkpoint import CheckpointManager
        from ebook_tts.converter import PDFToAudiobook

        output_path = tmp_path / "output.wav"
        checkpoint_dir = CheckpointManager.get_checkpoint_dir(str(output_path))
        checkpoint_manager = CheckpointManager(checkpoint_dir)

        converter = PDFToAudiobook(
            mock_tts=True,
            checkpoint_manager=checkpoint_manager,
        )

        # Start conversion - since we're using mock TTS, it completes quickly
        # and checkpoint is cleaned up on success
        result = converter.convert(
            input_path=str(sample_pdf),
            output_path=str(output_path),
        )

        # Checkpoint should be cleaned up after successful completion
        assert not checkpoint_manager.exists()
        assert result.output_path == str(output_path)
