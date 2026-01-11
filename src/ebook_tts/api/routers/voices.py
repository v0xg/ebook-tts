"""Voices router for listing available TTS voices."""

from fastapi import APIRouter, Query

from ...audio_synthesizer import KOKORO_VOICES
from ..models.voice import VoiceInfo, VoiceListResponse

router = APIRouter(prefix="/voices", tags=["Voices"])

LANGUAGE_NAMES = {
    "a": "American English",
    "b": "British English",
    "e": "Spanish",
    "f": "French",
    "j": "Japanese",
    "z": "Chinese",
    "h": "Hindi",
    "i": "Italian",
    "p": "Portuguese",
}


@router.get(
    "/",
    response_model=VoiceListResponse,
    summary="List available voices",
)
def list_voices(
    language: str | None = Query(
        default=None,
        description="Filter by language code (a=American, b=British, e=Spanish, etc.)",
    ),
):
    """
    List all available TTS voices.

    Voice naming convention: `[lang][gender]_[name]`
    - First letter: Language (a=American, b=British, e=Spanish, f=French, j=Japanese, z=Chinese)
    - Second letter: Gender (f=female, m=male)
    - Name: Voice character name

    Examples:
    - `af_heart`: American English Female - Heart (highest quality)
    - `bf_emma`: British English Female - Emma
    - `am_adam`: American English Male - Adam
    """
    voices = []
    by_language: dict[str, list[VoiceInfo]] = {}

    for voice_name, (lang_code, description) in KOKORO_VOICES.items():
        # Filter by language if specified
        if language and lang_code != language:
            continue

        voice_info = VoiceInfo(
            name=voice_name,
            description=description,
            language_code=lang_code,
            language_name=LANGUAGE_NAMES.get(lang_code, lang_code),
        )
        voices.append(voice_info)

        if lang_code not in by_language:
            by_language[lang_code] = []
        by_language[lang_code].append(voice_info)

    return VoiceListResponse(voices=voices, by_language=by_language)
