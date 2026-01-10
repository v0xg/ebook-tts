"""Tests for PronunciationDict class."""

from pathlib import Path

import pytest

from ebook_tts.pronunciation_dict import PronunciationDict, load_dictionary


class TestPronunciationDictLoading:
    """Tests for dictionary loading and validation."""

    def test_load_base_dictionary(self, base_dict_path: Path):
        """Load base English pronunciation dictionary."""
        d = PronunciationDict.load(base_dict_path)

        assert d.version == 1
        assert d.language == "en"
        assert len(d.words) > 0
        assert len(d.abbreviations) > 0
        assert len(d.acronyms) > 0
        assert len(d.patterns) > 0

    def test_load_story_dictionary(self, story_dict_path: Path):
        """Load story-specific pronunciation dictionary."""
        d = PronunciationDict.load(story_dict_path)

        assert d.language == "en"
        assert "hearken" in d.words
        assert d.words["hearken"] == "HAR-ken"

    def test_load_nonexistent_file(self, tmp_path: Path):
        """Loading nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            PronunciationDict.load(tmp_path / "nonexistent.yaml")

    def test_load_empty_file(self, tmp_path: Path):
        """Loading empty file raises ValueError."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")

        with pytest.raises(ValueError, match="Empty pronunciation dictionary"):
            PronunciationDict.load(empty_file)

    def test_load_invalid_yaml(self, tmp_path: Path):
        """Loading invalid YAML structure raises ValueError."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("just a string")

        with pytest.raises(ValueError, match="Invalid dictionary format"):
            PronunciationDict.load(invalid_file)


class TestPronunciationDictMerging:
    """Tests for dictionary merging."""

    def test_merge_dictionaries(self, base_dict_path: Path, story_dict_path: Path):
        """Merge base and story dictionaries."""
        base = PronunciationDict.load(base_dict_path)
        story = PronunciationDict.load(story_dict_path)

        merged = PronunciationDict.merge(base, story)

        # Should have words from both
        assert "cache" in merged.words  # from base
        assert "hearken" in merged.words  # from story

        # Override should take priority
        assert merged.language == "en"

    def test_merge_override_takes_precedence(self):
        """Override dictionary values take precedence in merge."""
        base = PronunciationDict(
            words={"test": "base-pronunciation"},
            abbreviations={"Dr.": "Doctor"},
        )
        override = PronunciationDict(
            words={"test": "override-pronunciation"},
        )

        merged = PronunciationDict.merge(base, override)

        assert merged.words["test"] == "override-pronunciation"
        assert merged.abbreviations["Dr."] == "Doctor"


class TestPronunciationDictApplication:
    """Tests for applying dictionary transformations."""

    @pytest.fixture
    def sample_dict(self) -> PronunciationDict:
        """Create a sample dictionary for testing."""
        return PronunciationDict(
            words={"Nguyen": "win", "cache": "cash"},
            abbreviations={"Dr.": "Doctor", "Mr.": "Mister"},
            acronyms={"FBI": "F. B. I.", "NASA": "NASA", "SQL": "sequel"},
            patterns=[
                (r"(\d+)km", r"\1 kilometers"),
                (r"\$(\d+)", r"\1 dollars"),
            ],
        )

    def test_apply_words(self, sample_dict: PronunciationDict):
        """Apply word replacements."""
        text = "Nguyen uses the cache"
        result = sample_dict.apply_words(text)

        assert "win" in result
        assert "cash" in result

    def test_apply_abbreviations(self, sample_dict: PronunciationDict):
        """Apply abbreviation expansions."""
        text = "Dr. Smith and Mr. Jones"
        result = sample_dict.apply_abbreviations(text)

        assert "Doctor Smith" in result
        assert "Mister Jones" in result

    def test_apply_acronyms(self, sample_dict: PronunciationDict):
        """Apply acronym pronunciations."""
        text = "The FBI and NASA use SQL"
        result = sample_dict.apply_acronyms(text)

        assert "F. B. I." in result
        assert "NASA" in result  # Pronounced as word
        assert "sequel" in result

    def test_apply_patterns(self, sample_dict: PronunciationDict):
        """Apply regex pattern replacements."""
        text = "Ran 5km and spent $20"
        result = sample_dict.apply_patterns(text)

        assert "5 kilometers" in result
        assert "20 dollars" in result

    def test_apply_all(self, sample_dict: PronunciationDict):
        """Apply all transformations in order."""
        text = "Dr. Nguyen ran 5km with the FBI"
        result = sample_dict.apply_all(text)

        assert "Doctor" in result
        assert "win" in result
        assert "5 kilometers" in result
        assert "F. B. I." in result


class TestLoadDictionaryFunction:
    """Tests for the load_dictionary convenience function."""

    def test_load_dictionary_with_path(self, base_dict_path: Path):
        """Load dictionary from path."""
        d = load_dictionary(str(base_dict_path))

        assert d is not None
        assert isinstance(d, PronunciationDict)

    def test_load_dictionary_none_returns_none(self):
        """Passing None returns None."""
        result = load_dictionary(None)
        assert result is None

    def test_load_dictionary_with_base_merge(
        self, base_dict_path: Path, story_dict_path: Path
    ):
        """Load and merge custom dictionary with base."""
        d = load_dictionary(str(story_dict_path), str(base_dict_path))

        assert d is not None
        # Should have content from both
        assert "cache" in d.words  # from base
        assert "hearken" in d.words  # from story
