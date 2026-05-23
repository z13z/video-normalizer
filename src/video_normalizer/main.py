import logging
import os
import shutil
import sys
from pathlib import Path

import ffmpeg

from .analyzer import analyze, FileAnalysis
from .config import Config
from .converter import convert
from .scanner import scan_video_files


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _log_analysis(path: Path, analysis: FileAnalysis, log: logging.Logger) -> None:
    log.info("  video streams   : %d", len(analysis.video))
    for s in analysis.video:
        mark = "→ encode AV1" if s.needs_transcode else "✓ copy"
        log.info("    [v:%d] %s  %s", s.type_index, s.codec_name, mark)

    log.info("  audio streams   : %d", len(analysis.audio))
    for s in analysis.audio:
        mark = "→ encode AAC" if s.needs_transcode else "✓ copy"
        log.info("    [a:%d] %s  %s", s.type_index, s.codec_name, mark)

    kept = [s for s in analysis.subtitle if not s.drop]
    dropped = [s for s in analysis.subtitle if s.drop]
    log.info("  subtitle streams: %d kept, %d dropped", len(kept), len(dropped))
    for s in kept:
        mark = "→ mov_text" if s.needs_transcode else "✓ copy (→ mov_text)"
        log.info("    [s:%d] %s  %s", s.type_index, s.codec_name, mark)
    for s in dropped:
        log.info("    [s:%d] %s  ✗ dropped (picture-based)", s.type_index, s.codec_name)

    if not analysis.container_is_mp4:
        log.info("  container       : %s → repackage to .mp4", path.suffix)


def process_file(path: Path, config: Config, log: logging.Logger) -> bool:
    """Analyse and, if needed, convert *path* in-place. Returns True on success."""
    log.info("Scanning: %s", path)

    try:
        analysis = analyze(path)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else str(exc)
        log.error("Failed to probe %s: %s", path, stderr)
        return False

    if not analysis.requires_processing:
        log.info("  Already normalised — skipping.")
        return True

    _log_analysis(path, analysis, log)

    tmp_path: Path | None = None
    try:
        log.info("  Converting…")
        tmp_path = convert(path, analysis, config)
        log.info("  Converted to tmp: %s (%.1f MB)",
                 tmp_path, tmp_path.stat().st_size / 1_048_576)

        target = path.with_suffix(".mp4")

        # If the source had a different extension, remove the original first
        # so we don't leave orphan files around.
        if path != target and path.exists():
            path.unlink()
            log.debug("  Removed original: %s", path)

        shutil.move(str(tmp_path), str(target))
        log.info("  Done → %s", target)
        return True

    except RuntimeError as exc:
        log.error("Conversion failed for %s: %s", path, exc)
        return False
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def main() -> None:
    config = Config()
    _setup_logging(config.log_level)
    log = logging.getLogger("video_normalizer")

    log.info("Starting video normalizer")
    log.info("  Media path : %s", config.media_path)
    log.info("  AV1 encoder: %s (crf=%d, speed=%d)",
             config.av1_encoder, config.av1_crf, config.av1_speed)
    log.info("  AAC bitrate: %s", config.aac_bitrate)

    if not os.path.isdir(config.media_path):
        log.error("Media path does not exist or is not a directory: %s", config.media_path)
        sys.exit(1)

    total = ok = skipped = failed = 0

    for video_path in scan_video_files(config.media_path):
        total += 1
        success = process_file(video_path, config, log)
        if success:
            ok += 1
        else:
            failed += 1

    log.info(
        "Finished. Total=%d  OK=%d  Skipped(already normalised counted in OK)  Failed=%d",
        total, ok, failed,
    )

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
