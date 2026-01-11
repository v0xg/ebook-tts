"""Audio synthesis using Kokoro TTS."""

from typing import Iterator, Optional

import numpy as np

# Available Kokoro voices by language
KOKORO_VOICES = {
    # American English (best quality)
    "af_heart": ("a", "American English Female - Heart (A grade)"),
    "af_bella": ("a", "American English Female - Bella (A- grade)"),
    "af_nicole": ("a", "American English Female - Nicole"),
    "af_sarah": ("a", "American English Female - Sarah"),
    "af_sky": ("a", "American English Female - Sky"),
    "am_fenrir": ("a", "American English Male - Fenrir"),
    "am_michael": ("a", "American English Male - Michael"),
    "am_puck": ("a", "American English Male - Puck"),
    "am_adam": ("a", "American English Male - Adam"),
    # British English
    "bf_emma": ("b", "British English Female - Emma (B- grade)"),
    "bf_isabella": ("b", "British English Female - Isabella"),
    "bf_alice": ("b", "British English Female - Alice"),
    "bm_george": ("b", "British English Male - George"),
    "bm_lewis": ("b", "British English Male - Lewis"),
    "bm_daniel": ("b", "British English Male - Daniel"),
    # Spanish
    "ef_dora": ("e", "Spanish Female - Dora"),
    "em_alex": ("e", "Spanish Male - Alex"),
    # French
    "ff_siwis": ("f", "French Female - Siwis (B- grade)"),
    # Japanese
    "jf_alpha": ("j", "Japanese Female - Alpha"),
    "jm_kumo": ("j", "Japanese Male - Kumo"),
    # Chinese
    "zf_xiaobei": ("z", "Chinese Female - Xiaobei"),
    "zm_yunjian": ("z", "Chinese Male - Yunjian"),
}


class KokoroSynthesizer:
    """Wrapper for Kokoro-82M text-to-speech synthesis."""

    def __init__(
        self,
        voice: str = "af_heart",
        device: str = "cuda",
    ):
        """
        Initialize the Kokoro synthesizer.

        Args:
            voice: Voice name (e.g., 'af_heart', 'bf_emma')
            device: Device to use ('cuda' or 'cpu')
        """
        self.device = device
        self._pipeline = None
        self._voice = voice
        self._lang_code = self._get_lang_code(voice)

    def _get_lang_code(self, voice: str) -> str:
        """Get language code for a voice."""
        if voice in KOKORO_VOICES:
            return KOKORO_VOICES[voice][0]
        # Infer from voice name prefix
        prefix = voice[:1] if voice else "a"
        lang_map = {"a": "a", "b": "b", "e": "e", "f": "f", "j": "j", "z": "z", "h": "h", "i": "i", "p": "p"}
        return lang_map.get(prefix, "a")

    @property
    def pipeline(self):
        """Lazy load the pipeline on first access."""
        if self._pipeline is None:
            self._load_pipeline()
        return self._pipeline

    @property
    def sample_rate(self) -> int:
        """Get the model's sample rate."""
        return 24000  # Kokoro uses 24kHz

    def _load_pipeline(self) -> None:
        """Load the Kokoro pipeline."""
        import os

        # Force CPU mode if specified (must be set before importing torch)
        if self.device == "cpu":
            os.environ["CUDA_VISIBLE_DEVICES"] = ""

        from kokoro import KPipeline

        self._pipeline = KPipeline(lang_code=self._lang_code, device=self.device)

    def set_voice(
        self,
        voice: str,
        **kwargs,
    ) -> bool:
        """
        Set the voice for synthesis.

        Args:
            voice: Voice name (e.g., 'af_heart', 'bf_emma')

        Returns:
            True if voice is valid
        """
        new_lang_code = self._get_lang_code(voice)

        # Reload pipeline if language changed
        if new_lang_code != self._lang_code:
            self._lang_code = new_lang_code
            self._pipeline = None  # Force reload

        self._voice = voice
        return True

    def synthesize(
        self,
        text: str,
        stream: bool = False,
        speed: float = 1.0,
    ) -> Iterator[np.ndarray]:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            stream: Not used (Kokoro always yields chunks)
            speed: Speech speed multiplier (0.5-2.0)

        Yields:
            Audio chunks as numpy arrays (float32, mono, 24kHz)
        """
        if not text.strip():
            return

        # Ensure pipeline is loaded
        _ = self.pipeline

        # Generate speech
        generator = self._pipeline(text, voice=self._voice, speed=speed)

        # Yield audio chunks
        for _gs, _ps, audio in generator:
            # Convert torch tensor to numpy if needed
            if hasattr(audio, "numpy"):
                audio = audio.numpy()
            elif hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()

            # Ensure correct shape (flatten if needed)
            if audio.ndim > 1:
                audio = audio.squeeze()

            yield audio.astype(np.float32)

    def synthesize_batch(
        self,
        texts: list[str],
        speed: float = 1.0,
    ) -> list[np.ndarray]:
        """
        Synthesize multiple texts.

        Args:
            texts: List of texts to synthesize
            speed: Speech speed multiplier

        Returns:
            List of audio arrays
        """
        results = []
        for text in texts:
            chunks = list(self.synthesize(text, stream=False, speed=speed))
            if chunks:
                results.append(np.concatenate(chunks))
        return results

    def list_speakers(self) -> list[str]:
        """List available Kokoro voices."""
        return list(KOKORO_VOICES.keys())

    @staticmethod
    def get_voice_info(voice: str) -> Optional[str]:
        """Get description for a voice."""
        if voice in KOKORO_VOICES:
            return KOKORO_VOICES[voice][1]
        return None

    @staticmethod
    def list_voices_by_language(lang: str = None) -> dict[str, str]:
        """
        List voices, optionally filtered by language.

        Args:
            lang: Language code filter ('a'=American, 'b'=British, 'e'=Spanish, etc.)

        Returns:
            Dict of voice_name -> description
        """
        result = {}
        for voice, (lang_code, desc) in KOKORO_VOICES.items():
            if lang is None or lang_code == lang:
                result[voice] = desc
        return result


class MockSynthesizer:
    """Mock synthesizer for testing without loading the model."""

    def __init__(self, **kwargs):
        """Initialize mock synthesizer (ignores all arguments)."""
        self._voice = "mock_voice"
        self._sample_rate = 24000

    @property
    def sample_rate(self) -> int:
        """Get the sample rate."""
        return self._sample_rate

    def set_voice(self, voice: str, **kwargs) -> bool:
        """Pretend to set voice."""
        self._voice = voice
        return True

    def synthesize(
        self,
        text: str,
        stream: bool = False,
        speed: float = 1.0,
    ) -> Iterator[np.ndarray]:
        """
        Generate silence proportional to text length.

        Assumes ~150 words per minute speaking rate.
        """
        if not text.strip():
            return

        # Estimate duration: ~150 words per minute
        word_count = len(text.split())
        duration_seconds = (word_count / 150) * 60 / speed

        # Clamp duration
        duration_seconds = max(0.1, min(duration_seconds, 60))

        # Generate silence
        samples = int(duration_seconds * self.sample_rate)
        silence = np.zeros(samples, dtype=np.float32)

        yield silence

    def synthesize_batch(
        self,
        texts: list[str],
        speed: float = 1.0,
    ) -> list[np.ndarray]:
        """Synthesize multiple texts."""
        results = []
        for text in texts:
            chunks = list(self.synthesize(text, stream=False, speed=speed))
            if chunks:
                results.append(np.concatenate(chunks))
        return results

    def list_speakers(self) -> list[str]:
        """Return mock speaker list."""
        return ["mock_speaker"]
