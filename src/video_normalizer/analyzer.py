from dataclasses import dataclass
from pathlib import Path

import ffmpeg


# Subtitle codecs that can be losslessly converted to SRT inside an mp4 container.
CONVERTIBLE_SUBTITLE_CODECS: frozenset[str] = frozenset({
    "subrip",   # SRT — already target, just copy
    "webvtt",   # VTT
    "ass",      # ASS
    "ssa",      # SSA
    "mov_text", # MP4TT / TXTT (native mp4 text subtitle)
    "tx3g",     # alternate name for MP4TT
})

# Picture-based or otherwise incompatible subtitle codecs — must be dropped.
DROPPABLE_SUBTITLE_CODECS: frozenset[str] = frozenset({
    "eia_608",
    "eia_708",
    "dvd_subtitle",      # VobSub
    "dvb_subtitle",
    "dvb_teletext",
    "hdmv_pgs_subtitle", # PGS
    "pgssub",
    "xsub",
    "s_hdmv/pgs",
    "microdvd",          # frame-based, unreliable conversion
    "dvb_subtitle",
})


@dataclass(frozen=True)
class StreamInfo:
    global_index: int       # index in the container's full stream list
    type_index: int         # 0-based index within streams of the same codec_type
    codec_type: str         # "video" | "audio" | "subtitle"
    codec_name: str
    needs_transcode: bool   # True when the codec must be changed
    drop: bool              # True for picture-based subtitles


@dataclass(frozen=True)
class FileAnalysis:
    video: list[StreamInfo]
    audio: list[StreamInfo]
    subtitle: list[StreamInfo]
    container_is_mp4: bool

    @property
    def requires_processing(self) -> bool:
        if not self.container_is_mp4:
            return True
        if any(s.needs_transcode for s in self.video):
            return True
        if any(s.needs_transcode for s in self.audio):
            return True
        # Any subtitle that must be dropped or transcoded means we need to remux
        if any(s.drop or s.needs_transcode for s in self.subtitle):
            return True
        return False


def analyze(path: Path) -> FileAnalysis:
    probe = ffmpeg.probe(str(path))

    video: list[StreamInfo] = []
    audio: list[StreamInfo] = []
    subtitle: list[StreamInfo] = []

    type_counters: dict[str, int] = {"video": 0, "audio": 0, "subtitle": 0}

    for raw in probe["streams"]:
        ctype: str = raw.get("codec_type", "")
        if ctype not in type_counters:
            continue

        codec: str = raw.get("codec_name", "unknown").lower()
        type_idx = type_counters[ctype]
        type_counters[ctype] += 1
        global_idx: int = raw["index"]

        if ctype == "video":
            video.append(StreamInfo(
                global_index=global_idx,
                type_index=type_idx,
                codec_type="video",
                codec_name=codec,
                needs_transcode=codec != "av1",
                drop=False,
            ))

        elif ctype == "audio":
            audio.append(StreamInfo(
                global_index=global_idx,
                type_index=type_idx,
                codec_type="audio",
                codec_name=codec,
                needs_transcode=codec != "aac",
                drop=False,
            ))

        elif ctype == "subtitle":
            if codec in DROPPABLE_SUBTITLE_CODECS:
                subtitle.append(StreamInfo(
                    global_index=global_idx,
                    type_index=type_idx,
                    codec_type="subtitle",
                    codec_name=codec,
                    needs_transcode=False,
                    drop=True,
                ))
            elif codec in CONVERTIBLE_SUBTITLE_CODECS:
                subtitle.append(StreamInfo(
                    global_index=global_idx,
                    type_index=type_idx,
                    codec_type="subtitle",
                    codec_name=codec,
                    needs_transcode=codec != "subrip",
                    drop=False,
                ))
            else:
                # Unknown subtitle codec — drop it to be safe
                subtitle.append(StreamInfo(
                    global_index=global_idx,
                    type_index=type_idx,
                    codec_type="subtitle",
                    codec_name=codec,
                    needs_transcode=False,
                    drop=True,
                ))

    return FileAnalysis(
        video=video,
        audio=audio,
        subtitle=subtitle,
        container_is_mp4=path.suffix.lower() == ".mp4",
    )
