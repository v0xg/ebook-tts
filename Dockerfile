# Dockerfile for eBook TTS - PDF to Audiobook Converter

FROM python:3.10-slim AS builder

ARG TORCH_VERSION=2.2.2
ARG PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

WORKDIR /app

# Copy package files
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Install the package into a staged prefix with CPU-only torch wheels
RUN printf "torch==%s+cpu\ntorchaudio==%s+cpu\n" "$TORCH_VERSION" "$TORCH_VERSION" > /tmp/constraints-cpu.txt && \
    pip install --no-cache-dir --prefix=/install \
    --extra-index-url ${PYTORCH_INDEX_URL} \
    -c /tmp/constraints-cpu.txt \
    . && \
    pip install --no-cache-dir --prefix=/install \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

FROM python:3.10-slim AS runtime

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install /install

# Copy entrypoint helper
COPY docker/entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Create non-root user for security
RUN useradd -m -u 1000 converter && \
    mkdir -p /app/output /app/models && \
    chown -R converter:converter /app
USER converter

# Cache/model directories in a volume
ENV XDG_CACHE_HOME=/app/models/.cache
ENV HF_HOME=/app/models/hf
ENV HF_HUB_CACHE=/app/models/hf/hub
ENV TORCH_HOME=/app/models/torch
ENV EBOOK_TTS_PREFETCH_MODEL=1
ENV PATH=/install/bin:$PATH
ENV PYTHONPATH=/install/lib/python3.10/site-packages
VOLUME ["/app/models"]

# Set default entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["ebook-tts", "--help"]

# Usage examples:
# docker build -t ebook-tts .
# docker run -v $(pwd)/books:/app/input -v $(pwd)/output:/app/output ebook-tts convert --input /app/input/book.pdf --output /app/output/book.wav --mock
