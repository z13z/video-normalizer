import logging
import uuid
from pathlib import Path

import ffmpeg
import tempfile
import os

from .analyzer import FileAnalysis, StreamInfo
from .config import Config

logger = logging.getLogger(__name__)


def _build_output_kwargs(
    analysis: FileAnalysis,
    config: Config,
) -> tuple[list[str], dict]:
    maps: list[str] = []
    kwargs: dict = {}

    append_video_processing_params(maps, kwargs, analysis.video, config.av1_crf, config.cpu_count)
    append_audio_processing_params(maps, kwargs, analysis.audio, config.aac_bitrate)
    append_subtitle_processing_params(maps, kwargs, analysis.subtitle)

    return maps, kwargs


def append_subtitle_processing_params(maps, kwargs, subtitle_streams):
    kept_subs: list[StreamInfo] = [s for s in subtitle_streams if not s.drop]
    out_s = 0
    for s in kept_subs:
        maps.append(f"0:s:{s.type_index}")
        if s.needs_transcode:
            kwargs[f"c:s:{out_s}"] = "mov_text"
        else:
            kwargs[f"c:s:{out_s}"] = "mov_text"
        out_s += 1


def append_video_processing_params(maps, kwargs, video_streams, av1_crf, cpu_count):
    out_v = 0
    any_av1_encode = False

    for s in video_streams:
        maps.append(f"0:v:{s.type_index}")
        if s.needs_transcode:
            kwargs[f"c:v:{out_v}"] = "libaom-av1"
            any_av1_encode = True
        else:
            kwargs[f"c:v:{out_v}"] = "copy"
        out_v += 1

    if any_av1_encode:
        kwargs["crf"] = av1_crf
        kwargs["b:v"] = 0
        kwargs["cpu-used"] = cpu_count


def append_audio_processing_params(maps, kwargs, audio_streams, aac_bitrate):
    out_a = 0
    for s in audio_streams:
        maps.append(f"0:a:{s.type_index}")
        if s.needs_transcode:
            kwargs[f"c:a:{out_a}"] = "aac"
            kwargs[f"b:a:{out_a}"] = aac_bitrate
        else:
            kwargs[f"c:a:{out_a}"] = "copy"
        out_a += 1


def convert(input_path: Path, analysis: FileAnalysis, config: Config) -> Path:
    uid = uuid.uuid4().hex[:8]
    tmp_output = f"{tempfile.gettempdir()}{os.sep}{input_path.stem}_{uid}.mp4"

    maps, codec_kwargs = _build_output_kwargs(analysis, config)

    if not maps:
        raise RuntimeError(f"No streams to include for {input_path}")

    inp = ffmpeg.input(str(input_path))
    out = ffmpeg.output(
        inp,
        tmp_output,
        map=maps,
        **codec_kwargs,
    )

    try:
        out.run(overwrite_output=True, quiet=True, capture_stderr=True)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        raise RuntimeError(f"ffmpeg failed for {input_path}:\n{stderr}") from exc

    return Path(tmp_output)
