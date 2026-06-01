import logging
import tempfile
import uuid
from pathlib import Path

import ffmpeg
import whisper
import time
from whisper.utils import WriteSRT

from .analyzer import FileAnalysis, StreamInfo
from .config import Config
from .utils import format_duration

logger = logging.getLogger(__name__)

_ENGLISH_LANG_CODES: frozenset[str] = frozenset({"eng", "en", "english"})


def _find_english_audio_stream(analysis: FileAnalysis) -> StreamInfo | None:
    for s in analysis.audio:
        if s.language and s.language.lower() in _ENGLISH_LANG_CODES:
            return s
    if analysis.audio:
        return analysis.audio[0]
    return None


def _extract_audio(input_path: Path, stream: StreamInfo) -> Path:
    uid = uuid.uuid4().hex[:8]
    out_path = Path(tempfile.gettempdir()) / f"{input_path.stem}_a{stream.type_index}_{uid}.wav"
    inp = ffmpeg.input(str(input_path))
    out = ffmpeg.output(inp[f"a:{stream.type_index}"], str(out_path))
    try:
        out.run(overwrite_output=True, quiet=True, capture_stderr=True)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        raise RuntimeError(
            f"Failed to extract audio stream a:{stream.type_index}: {stderr}"
        ) from exc
    return out_path


def transcribe(input_path: Path, analysis: FileAnalysis, config: Config) -> list[Path]:
    if config.whisper_model == "none" or not analysis.needs_subtitle_generation:
        return []

    stream = _find_english_audio_stream(analysis)
    if stream is None:
        logger.warning("  Whisper: no audio streams found in %s, skipping", input_path)
        return []

    wav_path: Path | None = None
    start = time.perf_counter()
    try:
        wav_path = _extract_audio(input_path, stream)
        model = whisper.load_model(
            config.whisper_model,
            device=config.whisper_device,
            download_root=config.whisper_model_dir,
        )
        result = model.transcribe(audio=str(wav_path), fp16=False)

        srt_dir = Path(tempfile.gettempdir())
        writer = WriteSRT(str(srt_dir))
        writer(result, str(wav_path), options={"max_line_width": None, "max_line_count": None, "highlight_words": False})

        srt_path = srt_dir / f"{wav_path.stem}.srt"
        if not srt_path.exists():
            logger.warning("  Whisper: expected SRT at %s not found", srt_path)
            return []
        return [srt_path]
    finally:
        if wav_path and wav_path.exists():
            wav_path.unlink(missing_ok=True)
        srt_path = Path(tempfile.gettempdir()) / f"{wav_path.stem}.srt"
        logging.info(f"Whisper: generated SRT at %s completed in %s", srt_path,
                     format_duration(time.perf_counter() - start))