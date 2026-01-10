"""Shared test fixtures for ebook-tts tests."""

from pathlib import Path

import pytest


@pytest.fixture
def examples_dir() -> Path:
    """Path to the examples directory."""
    return Path(__file__).parent.parent / "examples"


@pytest.fixture
def base_dict_path(examples_dir: Path) -> Path:
    """Path to base English pronunciation dictionary."""
    return examples_dir / "base_en.yaml"


@pytest.fixture
def story_dict_path(examples_dir: Path) -> Path:
    """Path to Tell-Tale Heart pronunciation dictionary."""
    return examples_dir / "tell_tale_heart.yaml"


@pytest.fixture
def sample_text_path(examples_dir: Path) -> Path:
    """Path to sample text file."""
    return examples_dir / "tell_tale_heart.txt"


@pytest.fixture
def sample_english_text() -> str:
    """Sample English text for testing."""
    return """
    The quick brown fox jumps over the lazy dog.
    Dr. Smith visited the FBI headquarters in Washington.
    He walked 5km and drank a $10 coffee.
    """


@pytest.fixture
def sample_spanish_text() -> str:
    """Sample Spanish text for testing."""
    return """
    El rápido zorro marrón salta sobre el perro perezoso.
    El Dr. García fue a la oficina del gobierno.
    Era un día muy bonito para pasear por la ciudad.
    """


@pytest.fixture
def temp_audio_path(tmp_path: Path) -> Path:
    """Temporary path for audio output."""
    return tmp_path / "test_output.wav"
