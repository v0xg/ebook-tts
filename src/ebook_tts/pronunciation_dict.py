"""Pronunciation dictionary for custom TTS word replacements."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class PronunciationDict:
    """Custom pronunciation dictionary loaded from YAML files.

    Supports four types of replacements:
    - words: Direct word-to-pronunciation mappings (case-sensitive)
    - abbreviations: Abbreviation expansions (e.g., Dr. → Doctor)
    - acronyms: Acronym pronunciations (e.g., NASA, FBI → F.B.I.)
    - patterns: Regex-based replacements for systematic fixes
    """

    version: int = 1
    language: str = "en"
    words: dict[str, str] = field(default_factory=dict)
    abbreviations: dict[str, str] = field(default_factory=dict)
    acronyms: dict[str, str] = field(default_factory=dict)
    patterns: list[tuple[str, str]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | str) -> "PronunciationDict":
        """Load pronunciation dictionary from YAML file.

        Args:
            path: Path to YAML pronunciation dictionary file.

        Returns:
            PronunciationDict instance with loaded data.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the YAML structure is invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Pronunciation dictionary not found: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ValueError(f"Empty pronunciation dictionary: {path}")

        if not isinstance(data, dict):
            type_name = type(data).__name__
            raise ValueError(f"Invalid dictionary format: expected mapping, got {type_name}")

        # Parse patterns from list of dicts to list of tuples
        raw_patterns = data.get("patterns", [])
        patterns = []
        if raw_patterns:
            for p in raw_patterns:
                if isinstance(p, dict) and "pattern" in p and "replacement" in p:
                    patterns.append((p["pattern"], p["replacement"]))

        return cls(
            version=data.get("version", 1),
            language=data.get("language", "en"),
            words=data.get("words", {}) or {},
            abbreviations=data.get("abbreviations", {}) or {},
            acronyms=data.get("acronyms", {}) or {},
            patterns=patterns,
        )

    @classmethod
    def merge(cls, base: "PronunciationDict", override: "PronunciationDict") -> "PronunciationDict":
        """Merge two dictionaries, with override taking precedence.

        Args:
            base: Base dictionary (lower priority).
            override: Override dictionary (higher priority).

        Returns:
            New PronunciationDict with merged content.
        """
        return cls(
            version=override.version,
            language=override.language,
            words={**base.words, **override.words},
            abbreviations={**base.abbreviations, **override.abbreviations},
            acronyms={**base.acronyms, **override.acronyms},
            patterns=base.patterns + override.patterns,
        )

    def apply_patterns(self, text: str) -> str:
        """Apply regex pattern replacements to text.

        Args:
            text: Input text to transform.

        Returns:
            Text with pattern replacements applied.
        """
        for pattern, replacement in self.patterns:
            try:
                text = re.sub(pattern, replacement, text)
            except re.error:
                # Skip invalid patterns silently
                continue
        return text

    def apply_acronyms(self, text: str) -> str:
        """Apply acronym replacements to text.

        Acronyms are matched as whole words (case-sensitive).

        Args:
            text: Input text to transform.

        Returns:
            Text with acronym replacements applied.
        """
        if not self.acronyms:
            return text

        # Sort by length (longest first) to avoid partial matches
        sorted_acronyms = sorted(self.acronyms.keys(), key=len, reverse=True)
        for acronym in sorted_acronyms:
            replacement = self.acronyms[acronym]
            # Match whole word only
            pattern = rf"\b{re.escape(acronym)}\b"
            text = re.sub(pattern, replacement, text)
        return text

    def apply_abbreviations(self, text: str) -> str:
        """Apply abbreviation expansions to text.

        Abbreviations often end with periods, so we use word boundary
        matching that accounts for this.

        Args:
            text: Input text to transform.

        Returns:
            Text with abbreviation expansions applied.
        """
        if not self.abbreviations:
            return text

        # Sort by length (longest first) to avoid partial matches
        sorted_abbrevs = sorted(self.abbreviations.keys(), key=len, reverse=True)
        for abbrev in sorted_abbrevs:
            replacement = self.abbreviations[abbrev]
            # Escape the abbreviation for regex (handles periods)
            escaped = re.escape(abbrev)
            # Match at word boundaries
            pattern = rf"\b{escaped}"
            text = re.sub(pattern, replacement, text)
        return text

    def apply_words(self, text: str) -> str:
        """Apply custom word pronunciations to text.

        Word replacements are case-sensitive and match whole words.

        Args:
            text: Input text to transform.

        Returns:
            Text with word replacements applied.
        """
        if not self.words:
            return text

        # Sort by length (longest first) to avoid partial matches
        sorted_words = sorted(self.words.keys(), key=len, reverse=True)
        for word in sorted_words:
            replacement = self.words[word]
            pattern = rf"\b{re.escape(word)}\b"
            text = re.sub(pattern, replacement, text)
        return text

    def apply_all(self, text: str) -> str:
        """Apply all dictionary transformations to text.

        Order of application:
        1. Patterns (regex-based, most flexible)
        2. Acronyms (before abbreviations to handle overlaps)
        3. Abbreviations (expand Dr., Mr., etc.)
        4. Words (final word-level replacements)

        Args:
            text: Input text to transform.

        Returns:
            Text with all transformations applied.
        """
        text = self.apply_patterns(text)
        text = self.apply_acronyms(text)
        text = self.apply_abbreviations(text)
        text = self.apply_words(text)
        return text

    def __repr__(self) -> str:
        return (
            f"PronunciationDict(language={self.language!r}, "
            f"words={len(self.words)}, abbreviations={len(self.abbreviations)}, "
            f"acronyms={len(self.acronyms)}, patterns={len(self.patterns)})"
        )


def load_dictionary(
    dictionary_path: Optional[str | Path] = None,
    base_dictionary_path: Optional[str | Path] = None,
) -> Optional[PronunciationDict]:
    """Convenience function to load and optionally merge dictionaries.

    Args:
        dictionary_path: Path to custom pronunciation dictionary.
        base_dictionary_path: Optional path to base dictionary to merge with.

    Returns:
        PronunciationDict if dictionary_path is provided, None otherwise.
    """
    if not dictionary_path:
        return None

    custom_dict = PronunciationDict.load(dictionary_path)

    if base_dictionary_path:
        base_dict = PronunciationDict.load(base_dictionary_path)
        return PronunciationDict.merge(base_dict, custom_dict)

    return custom_dict
