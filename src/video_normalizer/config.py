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


@dataclass
class Config:
    media_path: str = field(default_factory=lambda: os.getenv("MEDIA_PATH", "/media"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    video_codec: str = field(default_factory=lambda: os.getenv("VIDEO_CODEC", "av1"))
    quality: str = field(default_factory=lambda: os.getenv("CONVERSION_QUALITY", "high"))
    speed: str = field(default_factory=lambda: os.getenv("CONVERSION_SPEED", "medium"))
    aac_bitrate: str = field(default_factory=lambda: os.getenv("AAC_BITRATE", "192k"))

    @property
    def crf(self) -> int:
        return _QUALITY_CRF[self.video_codec][self.quality]

    @property
    def preset(self):
        return _SPEED_PRESET[self.video_codec][self.speed]
