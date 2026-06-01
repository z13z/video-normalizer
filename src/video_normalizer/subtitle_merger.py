import logging
import tempfile
import uuid
from pathlib import Path

import ffmpeg
import time

from video_normalizer.utils import format_duration

logger = logging.getLogger(__name__)


def merge_subtitles(mp4_path: Path, srt_paths: list[Path]) -> Path:
    uid = uuid.uuid4().hex[:8]
    tmp_output = Path(tempfile.gettempdir()) / f"{mp4_path.stem}_submerged_{uid}.mp4"

    inp = ffmpeg.input(str(mp4_path))
    srt_inputs = [ffmpeg.input(str(p)) for p in srt_paths]

    map_args = ["0"] + [f"{i + 1}:s" for i in range(len(srt_paths))]
    codec_kwargs = {"c:v": "copy", "c:a": "copy", "c:s": "mov_text"}

    out = ffmpeg.output(inp, *srt_inputs, str(tmp_output), map=map_args, **codec_kwargs)
    logger.info("Merging subtitles into %s", mp4_path.name)
    start = time.perf_counter()
    try:
        out.run(overwrite_output=True, quiet=True, capture_stderr=True)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        raise RuntimeError(f"ffmpeg subtitle merge failed for {mp4_path}:\n{stderr}") from exc
    finally:
        logging.info(f"Merged subtitles into %s", mp4_path.name, format_duration(time.perf_counter() - start))
    return tmp_output
