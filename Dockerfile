# Dockerfile for eBook TTS - PDF to Audiobook Converter

FROM python:3.10-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package files
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir .

# Create non-root user for security
RUN useradd -m -u 1000 converter
RUN mkdir -p /app/output && chown -R converter:converter /app
USER converter

# Set default entrypoint
ENTRYPOINT ["ebook-tts"]
CMD ["--help"]

# Usage examples:
# docker build -t ebook-tts .
# docker run -v $(pwd)/books:/app/input -v $(pwd)/output:/app/output ebook-tts convert --input /app/input/book.pdf --output /app/output/book.wav --mock
