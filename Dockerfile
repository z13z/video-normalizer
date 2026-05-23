FROM python:3.12-slim

# Install ffmpeg with full codec support.
# The Debian Bookworm ffmpeg package ships with libaom (AV1), libx264,
# libx265, libvpx, and all common subtitle/audio codecs built in.
# libsvtav1 is not yet in Debian repos; if you need it, swap the base
# image for mwader/static-ffmpeg or compile ffmpeg yourself.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

# Make sure the package is importable from /app/src
ENV PYTHONPATH=/app/src

# /media is the default mount point for the video library.
# Override with -e MEDIA_PATH=... at runtime.
VOLUME ["/media"]

CMD ["python", "-m", "video_normalizer.main"]
