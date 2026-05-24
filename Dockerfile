FROM python:3.12-slim

ARG UID=1000
ARG GID=1000

RUN groupadd -g ${GID} appgroup && \
    useradd -m -u ${UID} -g ${GID} -s /bin/bash appuser

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

ENV PYTHONPATH=/app/src

RUN chown -R appuser:appgroup /app
USER appuser

VOLUME ["/media"]

CMD ["python", "-m", "video_normalizer.main"]