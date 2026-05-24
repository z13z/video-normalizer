from dataclasses import dataclass
from pathlib import Path

import ffmpeg


CONVERTIBLE_SUBTITLE_CODECS: frozenset[str] = frozenset({
    "subrip",
    "webvtt",
    "ass",
    "ssa",
    "mov_text",
    "tx3g",
})

@dataclass(frozen=True)
class StreamInfo:
    global_index: int
    type_index: int
    codec_type: str
    codec_name: str
    needs_transcode: bool
    drop: bool


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
            if codec in CONVERTIBLE_SUBTITLE_CODECS:
                subtitle.append(StreamInfo(
                    global_index=global_idx,
                    type_index=type_idx,
                    codec_type="subtitle",
                    codec_name=codec,
                    needs_transcode=codec != "subrip",
                    drop=False,
                ))
            else:
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
