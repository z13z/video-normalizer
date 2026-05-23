import os
from dataclasses import dataclass, field


@dataclass
class Config:
    media_path: str = field(default_factory=lambda: os.getenv("MEDIA_PATH", "/media"))
    tmp_dir: str = field(default_factory=lambda: os.getenv("TMP_DIR", "/tmp"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # AV1 encoder: libaom-av1 (reference, slow) or libsvtav1 (fast)
    av1_encoder: str = field(default_factory=lambda: os.getenv("AV1_ENCODER", "libaom-av1"))
    # CRF quality: lower = better quality, higher = smaller file
    av1_crf: int = field(default_factory=lambda: int(os.getenv("AV1_CRF", "30")))
    # Speed preset: libaom-av1 cpu-used 0-8 (8=fastest), libsvtav1 preset 0-13 (13=fastest)
    av1_speed: int = field(default_factory=lambda: int(os.getenv("AV1_SPEED", "6")))

    aac_bitrate: str = field(default_factory=lambda: os.getenv("AAC_BITRATE", "192k"))
