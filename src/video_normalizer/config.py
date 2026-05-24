import os
from dataclasses import dataclass, field


@dataclass
class Config:
    media_path: str = field(default_factory=lambda: os.getenv("MEDIA_PATH", "/media"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    av1_crf: int = field(default_factory=lambda: int(os.getenv("AV1_CRF", "26")))
    av1_preset: int = field(default_factory=lambda: int(os.getenv("AV1_PRESET", "4")))
    aac_bitrate: str = field(default_factory=lambda: os.getenv("AAC_BITRATE", "192k"))
    ffmpeg_threads: int = field(default_factory=lambda: int(os.getenv("FFMPEG_THREADS", "0")))
