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

# If first arg starts with `-` or is a known ebook-tts subcommand, prepend ebook-tts.
# This allows: docker run image --help, docker run image convert ..., etc.
if [[ $# -gt 0 && ( "${1#-}" != "$1" || "$1" == "convert" || "$1" == "list-voices" ) ]]; then
  set -- ebook-tts "$@"
fi

exec "$@"
