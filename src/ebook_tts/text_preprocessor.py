"""Text preprocessing for optimal TTS output."""

import re
from typing import TYPE_CHECKING, Literal, Optional

from .utils import detect_language

if TYPE_CHECKING:
    from .pronunciation_dict import PronunciationDict


class TextPreprocessor:
    """Clean and normalize text for TTS synthesis."""

    # Common PDF ligatures
    LIGATURES = {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "st",
        "\ufb06": "st",
    }

    # English abbreviations (expanded for TTS clarity)
    EN_ABBREVIATIONS = {
        "Dr.": "Doctor",
        "Mr.": "Mister",
        "Mrs.": "Missus",
        "Ms.": "Miss",
        "Prof.": "Professor",
        "vs.": "versus",
        "etc.": "etcetera",
        "St.": "Saint",
        "Jr.": "Junior",
        "Sr.": "Senior",
        "Ltd.": "Limited",
        "Inc.": "Incorporated",
        "Corp.": "Corporation",
        "Ave.": "Avenue",
        "Blvd.": "Boulevard",
        "Apt.": "Apartment",
        "Vol.": "Volume",
        "Ch.": "Chapter",
        "Fig.": "Figure",
        "approx.": "approximately",
        "govt.": "government",
        "dept.": "department",
        "Mt.": "Mount",
        "i.e.": "that is",
        "e.g.": "for example",
        "a.m.": "A M",
        "p.m.": "P M",
        "A.M.": "A M",
        "P.M.": "P M",
        # Month abbreviations
        "Jan.": "January",
        "Feb.": "February",
        "Mar.": "March",
        "Apr.": "April",
        "Jun.": "June",
        "Jul.": "July",
        "Aug.": "August",
        "Sep.": "September",
        "Sept.": "September",
        "Oct.": "October",
        "Nov.": "November",
        "Dec.": "December",
    }

    # Spanish abbreviations
    ES_ABBREVIATIONS = {
        "Dr.": "Doctor",
        "Dra.": "Doctora",
        "Sr.": "Señor",
        "Sra.": "Señora",
        "Srta.": "Señorita",
        "Prof.": "Profesor",
        "Profa.": "Profesora",
        "Lic.": "Licenciado",
        "Lda.": "Licenciada",
        "Ing.": "Ingeniero",
        "Arq.": "Arquitecto",
        "Abog.": "Abogado",
        "Gral.": "General",
        "Cnel.": "Coronel",
        "Tte.": "Teniente",
        "Cpt.": "Capitán",
        "Ud.": "Usted",
        "Uds.": "Ustedes",
        "S.A.": "Sociedad Anónima",
        "Cía.": "Compañía",
        "Pág.": "Página",
        "págs.": "páginas",
        "Cap.": "Capítulo",
        "Vol.": "Volumen",
        "Núm.": "Número",
        "núm.": "número",
        "etc.": "etcétera",
        "Ej.": "Ejemplo",
        "ej.": "ejemplo",
        "a.m.": "de la mañana",
        "p.m.": "de la tarde",
        "A.M.": "de la mañana",
        "P.M.": "de la tarde",
    }

    def __init__(
        self,
        language: Optional[Literal["en", "es"]] = None,
        dictionary: Optional["PronunciationDict"] = None,
    ):
        """
        Initialize preprocessor.

        Args:
            language: Force language for abbreviation expansion.
                      If None, language is auto-detected.
            dictionary: Optional custom pronunciation dictionary for
                        additional word/abbreviation/acronym/pattern replacements.
        """
        self.language = language
        self.dictionary = dictionary
        self._detected_language: Optional[str] = None

    def process(self, text: str) -> str:
        """
        Process text through all preprocessing steps.

        Args:
            text: Raw text from PDF extraction

        Returns:
            Cleaned and normalized text ready for TTS
        """
        # Detect language if not specified
        if self.language is None:
            self._detected_language = detect_language(text)
        else:
            self._detected_language = self.language

        # Apply preprocessing steps in order
        text = self._fix_ligatures(text)
        text = self._fix_encoding_issues(text)
        text = self._rejoin_hyphenated_words(text)
        text = self._remove_page_artifacts(text)
        text = self._expand_abbreviations(text)
        text = self._apply_dictionary(text)
        text = self._expand_numbers(text)
        text = self._normalize_punctuation(text)
        text = self._normalize_whitespace(text)

        return text

    def _fix_ligatures(self, text: str) -> str:
        """Replace PDF ligatures with standard characters."""
        for ligature, replacement in self.LIGATURES.items():
            text = text.replace(ligature, replacement)
        return text

    def _fix_encoding_issues(self, text: str) -> str:
        """Fix common PDF encoding problems."""
        # Smart quotes to regular quotes
        replacements = {
            "\u2018": "'",  # Left single quote
            "\u2019": "'",  # Right single quote
            "\u201c": '"',  # Left double quote
            "\u201d": '"',  # Right double quote
            "\u2013": "-",  # En dash
            "\u2014": " - ",  # Em dash (with spaces for pause)
            "\u2026": "...",  # Ellipsis
            "\u00a0": " ",  # Non-breaking space
            "\u00ad": "",  # Soft hyphen
            "\ufeff": "",  # BOM
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _rejoin_hyphenated_words(self, text: str) -> str:
        """Rejoin words hyphenated at line breaks."""
        # Pattern: word- followed by newline and continuation
        # e.g., "extra-\nordinary" -> "extraordinary"
        text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)
        return text

    def _remove_page_artifacts(self, text: str) -> str:
        """Remove headers, footers, and page numbers."""
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # Skip lines that are just page numbers
            if re.match(r"^\d+$", stripped):
                continue

            # Skip common header/footer patterns
            if re.match(r"^(Page\s+)?\d+\s*$", stripped, re.IGNORECASE):
                continue

            # Skip lines that are just dashes or underscores (separators)
            if re.match(r"^[-_=]{3,}$", stripped):
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _expand_abbreviations(self, text: str) -> str:
        """Expand abbreviations for clearer TTS pronunciation."""
        # Choose abbreviation set based on detected language
        if self._detected_language == "es":
            abbrevs = self.ES_ABBREVIATIONS
        else:
            abbrevs = self.EN_ABBREVIATIONS

        # Sort by length (longest first) to avoid partial replacements
        for abbrev, expansion in sorted(abbrevs.items(), key=lambda x: -len(x[0])):
            # Use word boundary matching to avoid partial matches
            pattern = re.escape(abbrev)
            text = re.sub(rf"\b{pattern}", expansion, text)

        return text

    def _apply_dictionary(self, text: str) -> str:
        """Apply custom pronunciation dictionary transformations.

        The dictionary can override built-in abbreviations and add
        custom patterns, acronyms, and word pronunciations.
        """
        if self.dictionary is None:
            return text

        return self.dictionary.apply_all(text)

    def _expand_numbers(self, text: str) -> str:
        """
        Handle common number patterns for TTS.

        Note: Kokoro handles basic number-to-speech conversion,
        but we help with some edge cases.
        """
        # Currency symbols before amounts (add space for clarity)
        text = re.sub(r"\$(\d)", r"$ \1", text)
        text = re.sub(r"€(\d)", r"€ \1", text)

        # Decades (e.g., "1990s" -> "nineteen nineties" handled by TTS)
        # Just ensure proper spacing

        # Phone numbers - add pauses between groups
        text = re.sub(
            r"(\d{3})-(\d{3})-(\d{4})",
            r"\1, \2, \3",
            text
        )

        return text

    def _normalize_punctuation(self, text: str) -> str:
        """Normalize punctuation for natural TTS pauses."""
        # Multiple periods to ellipsis-like pause
        text = re.sub(r"\.{2,}", "...", text)

        # Multiple exclamation/question marks
        text = re.sub(r"!{2,}", "!", text)
        text = re.sub(r"\?{2,}", "?", text)

        # Ensure space after punctuation (except at end of string)
        text = re.sub(r"([.!?])([A-Za-z])", r"\1 \2", text)

        # Handle parentheses - add slight pause indication
        text = re.sub(r"\s*\(\s*", " (", text)
        text = re.sub(r"\s*\)\s*", ") ", text)

        # Semicolons to periods for clearer TTS phrasing
        text = text.replace(";", ".")

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace while preserving paragraph breaks."""
        # Replace multiple newlines with paragraph marker
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Replace single newlines with space (rejoin lines)
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

        # Multiple spaces to single space
        text = re.sub(r"[ \t]+", " ", text)

        # Clean up space around paragraph breaks
        text = re.sub(r" *\n\n *", "\n\n", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    @property
    def detected_language(self) -> Optional[str]:
        """Return the detected language after processing."""
        return self._detected_language
