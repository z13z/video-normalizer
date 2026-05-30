import logging
import tempfile
import uuid
from pathlib import Path

import ffmpeg
import pytesseract
from PIL import Image, ImageOps
from pgsreader import PGSReader

from .analyzer import FileAnalysis, StreamInfo

logger = logging.getLogger(__name__)

_PGS_CLOCK = 90_000


def _format_srt_timestamp(ms: int) -> str:
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1_000
    millis = ms % 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


def _preprocess_for_ocr(image: Image.Image) -> Image.Image:
    if image.mode == "RGBA":
        bg = Image.new("RGBA", image.size, (0, 0, 0, 255))
        bg.paste(image, mask=image.split()[3])
        image = bg.convert("RGB")
    elif image.mode != "RGB":
        image = image.convert("RGB")
    return ImageOps.invert(image.convert("L"))


def _ocr_image(image: Image.Image) -> str:
    return pytesseract.image_to_string(_preprocess_for_ocr(image), config="--psm 6").strip()


def _extract_subtitle_stream(input_path: Path, stream: StreamInfo) -> Path:
    uid = uuid.uuid4().hex[:8]
    out_path = Path(tempfile.gettempdir()) / f"{input_path.stem}_s{stream.type_index}_{uid}.sup"
    inp = ffmpeg.input(str(input_path))
    out = ffmpeg.output(inp[f"s:{stream.type_index}"], str(out_path), c="copy")
    try:
        out.run(overwrite_output=True, quiet=True, capture_stderr=True)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        raise RuntimeError(
            f"Failed to extract subtitle stream s:{stream.type_index}: {stderr}"
        ) from exc
    return out_path


def _pgs_to_srt(sup_path: Path, stream_index: int) -> Path | None:
    srt_path = sup_path.with_suffix(".srt")
    pgs = PGSReader(str(sup_path))

    entries: list[tuple[int, int, str]] = []
    pending_start_ms: int | None = None
    pending_image: Image.Image | None = None

    for ds in pgs.get_display_sets():
        ts_ms = int(ds.pcs.presentation_timestamp * 1000 / _PGS_CLOCK)

        if ds.has_image:
            if pending_image is not None:
                try:
                    text = _ocr_image(pending_image)
                    if text:
                        entries.append((pending_start_ms, ts_ms, text))
                except Exception as exc:
                    logger.warning("OCR failed at %dms (stream s:%d): %s", ts_ms, stream_index, exc)
            pending_start_ms = ts_ms
            try:
                pending_image = ds.get_image()
            except Exception as exc:
                logger.warning("Failed to decode image at %dms (stream s:%d): %s", ts_ms, stream_index, exc)
                pending_image = None
        else:
            if pending_image is not None:
                try:
                    text = _ocr_image(pending_image)
                    if text:
                        entries.append((pending_start_ms, ts_ms, text))
                except Exception as exc:
                    logger.warning("OCR failed at %dms (stream s:%d): %s", ts_ms, stream_index, exc)
                pending_start_ms = None
                pending_image = None

    if not entries:
        logger.warning("OCR produced no text for subtitle stream s:%d", stream_index)
        return None

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(entries, 1):
            f.write(f"{i}\n")
            f.write(f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n")
            f.write(f"{text}\n\n")

    return srt_path


def extract_and_ocr(input_path: Path, analysis: FileAnalysis) -> list[Path]:
    ocr_streams = [s for s in analysis.subtitle if s.needs_ocr]
    srt_paths: list[Path] = []

    for stream in ocr_streams:
        logger.info("  OCR: extracting subtitle stream s:%d (%s)", stream.type_index, stream.codec_name)
        sup_path: Path | None = None
        try:
            sup_path = _extract_subtitle_stream(input_path, stream)
            if stream.codec_name == "hdmv_pgs_subtitle":
                srt_path = _pgs_to_srt(sup_path, stream.type_index)
                if srt_path:
                    srt_paths.append(srt_path)
            else:
                logger.warning(
                    "  OCR: no handler for codec %s (stream s:%d), skipping",
                    stream.codec_name, stream.type_index,
                )
        except Exception as exc:
            logger.error("  OCR: failed for stream s:%d: %s", stream.type_index, exc)
        finally:
            if sup_path and sup_path.exists():
                sup_path.unlink(missing_ok=True)

    return srt_paths
