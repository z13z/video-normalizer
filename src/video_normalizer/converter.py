import logging
import uuid
from pathlib import Path

import ffmpeg

from .analyzer import FileAnalysis, StreamInfo
from .config import Config

logger = logging.getLogger(__name__)


def _build_output_kwargs(
    analysis: FileAnalysis,
    config: Config,
) -> tuple[list[str], dict]:
    """
    Return (map_list, codec_kwargs) that drive the ffmpeg output node.

    map_list entries reference streams from input 0 using ffmpeg specifiers
    like "0:v:0", "0:a:1", "0:s:0". codec_kwargs carries per-stream codec
    options that ffmpeg-python forwards verbatim as CLI flags.
    """
    maps: list[str] = []
    kwargs: dict = {}

    out_v = out_a = out_s = 0
    any_av1_encode = False

    for s in analysis.video:
        maps.append(f"0:v:{s.type_index}")
        if s.needs_transcode:
            kwargs[f"c:v:{out_v}"] = config.av1_encoder
            any_av1_encode = True
        else:
            kwargs[f"c:v:{out_v}"] = "copy"
        out_v += 1

    for s in analysis.audio:
        maps.append(f"0:a:{s.type_index}")
        if s.needs_transcode:
            kwargs[f"c:a:{out_a}"] = "aac"
            kwargs[f"b:a:{out_a}"] = config.aac_bitrate
        else:
            kwargs[f"c:a:{out_a}"] = "copy"
        out_a += 1

    kept_subs: list[StreamInfo] = [s for s in analysis.subtitle if not s.drop]
    for s in kept_subs:
        maps.append(f"0:s:{s.type_index}")
        # SRT (subrip) is the only subtitle codec mp4 containers accept natively
        # via the mov_text muxer, but ffmpeg will transcode to mov_text for mp4.
        # We request "srt" here; ffmpeg auto-selects mov_text when writing mp4.
        if s.needs_transcode:
            kwargs[f"c:s:{out_s}"] = "mov_text"
        else:
            # subrip source → mp4 also needs mov_text muxer codec
            kwargs[f"c:s:{out_s}"] = "mov_text"
        out_s += 1

    if any_av1_encode:
        if config.av1_encoder == "libaom-av1":
            # Constant-quality CRF mode requires b:v 0
            kwargs["crf"] = config.av1_crf
            kwargs["b:v"] = 0
            kwargs["cpu-used"] = config.av1_speed
        elif config.av1_encoder == "libsvtav1":
            kwargs["crf"] = config.av1_crf
            kwargs["preset"] = config.av1_speed

    return maps, kwargs


def convert(input_path: Path, analysis: FileAnalysis, config: Config) -> Path:
    """
    Transcode/remux *input_path* according to *analysis* and *config*.

    Writes the result to a unique file under config.tmp_dir and returns
    that path. Raises on ffmpeg failure; the caller is responsible for
    cleanup.
    """
    uid = uuid.uuid4().hex[:8]
    tmp_output = Path(config.tmp_dir) / f"{input_path.stem}_{uid}.mp4"

    maps, codec_kwargs = _build_output_kwargs(analysis, config)

    if not maps:
        raise RuntimeError(f"No streams to include for {input_path}")

    inp = ffmpeg.input(str(input_path))

    # ffmpeg-python passes dict keys verbatim as CLI flags (prefixed with "-"),
    # so keys like "c:v:0" become "-c:v:0" on the command line.
    out = ffmpeg.output(
        inp,
        str(tmp_output),
        map=maps,
        **codec_kwargs,
    )

    cmd = ffmpeg.compile(out, overwrite_output=True)
    logger.debug("ffmpeg command: %s", " ".join(cmd))

    try:
        out.run(overwrite_output=True, quiet=True, capture_stderr=True)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        raise RuntimeError(f"ffmpeg failed for {input_path}:\n{stderr}") from exc

    return tmp_output
