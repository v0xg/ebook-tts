#!/usr/bin/env bash
set -euo pipefail

if [[ "${EBOOK_TTS_PREFETCH_MODEL:-0}" == "1" ]]; then
  python - <<'PY'
import os

from ebook_tts.audio_synthesizer import KokoroSynthesizer

# Force CPU for prefetch to avoid requiring GPU on startup.
_ = KokoroSynthesizer(device="cpu").pipeline
PY
fi

exec "$@"
