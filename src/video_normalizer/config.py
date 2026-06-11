import os
from dataclasses import dataclass, field

_QUALITY_CRF = {
    "h264": {"high": 18, "medium": 23, "low": 28},
    "av1":  {"high": 23, "medium": 30, "low": 35},
}

_SPEED_PRESET = {
    "h264": {"fast": "veryfast", "medium": "medium", "slow": "veryslow"},
    "av1":  {"fast": 10, "medium": 8, "slow": 6},
}

_WHISPER_MODEL_PRESET = {
    "fast": "large-v3-turbo",
    "medium":  "large-v3-turbo",
    "slow": "large-v3",
}

@dataclass
class Config:
    media_path: str = field(default_factory=lambda: os.getenv("MEDIA_PATH", "/media"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    video_codec: str = field(default_factory=lambda: os.getenv("VIDEO_CODEC", "av1"))
    quality: str = field(default_factory=lambda: os.getenv("CONVERSION_QUALITY", "high"))
    speed: str = field(default_factory=lambda: os.getenv("CONVERSION_SPEED", "medium"))
    aac_bitrate: str = field(default_factory=lambda: os.getenv("AAC_BITRATE", "192k"))
    whisper_device: str = field(default_factory=lambda: os.getenv("WHISPER_DEVICE", "cpu"))
    whisper_model_dir: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL_DIR", "/whisper_models"))
    process_limit: int = field(default_factory=lambda: int(os.getenv("PROCESS_LIMIT", "0")))

    @property
    def crf(self) -> int:
        return _QUALITY_CRF[self.video_codec][self.quality]

    @property
    def preset(self):
        return _SPEED_PRESET[self.video_codec][self.speed]

    @property
    def whisper_model(self):
        return _WHISPER_MODEL_PRESET[os.getenv("WHISPER_MODEL", "fast")]
