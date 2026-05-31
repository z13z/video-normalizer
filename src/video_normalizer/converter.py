import logging
import uuid
from pathlib import Path

import ffmpeg
import tempfile
import os
import time

from .analyzer import FileAnalysis, StreamInfo
from .config import Config
from .utils import format_duration

logger = logging.getLogger(__name__)

def _build_output_kwargs(
    analysis: FileAnalysis,
    config: Config,
) -> tuple[list[str], dict]:
    maps: list[str] = []
    kwargs: dict = {}
    append_video_processing_params(maps, kwargs, analysis.video, config)
    append_audio_processing_params(maps, kwargs, analysis.audio, config.aac_bitrate)
    append_subtitle_processing_params(maps, kwargs, analysis.subtitle)
    return maps, kwargs


def append_subtitle_processing_params(maps, kwargs, subtitle_streams):
    kept_subs: list[StreamInfo] = [s for s in subtitle_streams if not s.drop]
    out_s = 0
    for s in kept_subs:
        maps.append(f"s:{s.type_index}")
        if s.needs_transcode:
            kwargs[f"c:s:{out_s}"] = "mov_text"
        else:
            kwargs[f"c:s:{out_s}"] = "mov_text"
        out_s += 1


def _apply_video_encode_params(kwargs: dict, codec: str, config: Config):
    if codec == "av1":
        kwargs["crf"] = config.crf
        kwargs["b:v"] = 0
        kwargs["preset"] = config.preset
    elif codec == "h264":
        kwargs["crf"] = config.crf
        kwargs["preset"] = config.preset


SUPPORTED_VIDEO_CODECS = {"av1": "libsvtav1", "h264": "libx264"}


def append_video_processing_params(maps, kwargs, video_streams, config: Config):
    codec = config.video_codec
    ffmpeg_encoder = SUPPORTED_VIDEO_CODECS[codec]
    out_v = 0
    any_transcode = False

    for s in video_streams:
        maps.append(f"v:{s.type_index}")
        if s.needs_transcode:
            kwargs[f"c:v:{out_v}"] = ffmpeg_encoder
            any_transcode = True
        else:
            kwargs[f"c:v:{out_v}"] = "copy"
        out_v += 1

    if any_transcode:
        _apply_video_encode_params(kwargs, codec, config)


def append_audio_processing_params(maps, kwargs, audio_streams, aac_bitrate):
    out_a = 0
    for s in audio_streams:
        maps.append(f"a:{s.type_index}")
        if s.needs_transcode:
            kwargs[f"c:a:{out_a}"] = "aac"
            kwargs[f"b:a:{out_a}"] = aac_bitrate
        else:
            kwargs[f"c:a:{out_a}"] = "copy"
        out_a += 1


def append_external_subtitle_files(srt_paths, streams, codec_kwargs, maps):
    if srt_paths:
        existing_sub_count = sum(1 for m in maps if m.startswith("s:"))
        for i, srt_path in enumerate(srt_paths):
            srt_inp = ffmpeg.input(str(srt_path))
            streams.append(srt_inp["s"])
            codec_kwargs[f"c:s:{existing_sub_count + i}"] = "mov_text"


def convert(
    input_path: Path,
    analysis: FileAnalysis,
    config: Config,
    srt_paths: list[Path],
) -> Path:
    uid = uuid.uuid4().hex[:8]
    tmp_output = f"{tempfile.gettempdir()}{os.sep}{input_path.stem}_{uid}.mp4"

    maps, codec_kwargs = _build_output_kwargs(analysis, config)

    if not maps:
        raise RuntimeError(f"No streams to include for {input_path}")

    inp = ffmpeg.input(str(input_path))
    streams = [inp[m] for m in maps]
    append_external_subtitle_files(srt_paths, streams, codec_kwargs, maps)
    out = ffmpeg.output(*streams, tmp_output, **codec_kwargs)
    logger.info(f"maps={maps} codec_kwargs={codec_kwargs}")

    try:
        start = time.perf_counter()
        out.run(overwrite_output=True, quiet=True, capture_stderr=True)
        elapsed = time.perf_counter() - start
        logging.info(f"Normalization of %s completed in %s", input_path, format_duration(elapsed))
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        raise RuntimeError(f"ffmpeg failed for {input_path}:\n{stderr}") from exc

    return Path(tmp_output)
