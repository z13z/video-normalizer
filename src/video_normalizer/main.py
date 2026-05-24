import logging
import os
import shutil
import sys
from pathlib import Path

import ffmpeg

from .analyzer import analyze
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

def process_file(path: Path, config: Config, log: logging.Logger) -> bool:
    log.info("Scanning: %s", path)

    try:
        analysis = analyze(path)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else str(exc)
        log.error("Failed to probe %s: %s", path, stderr)
        return False

    tmp_path: Path | None = None
    try:
        log.info("  Converting…")
        tmp_path = convert(path, analysis, config)
        log.info("  Converted to tmp: %s (%.1f MB)",
                 tmp_path, tmp_path.stat().st_size / 1_048_576)

        target = path.with_suffix(".mp4")

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


def main():
    config = Config()
    _setup_logging(config.log_level)
    log = logging.getLogger("video_normalizer")

    log.info("Starting video normalizer, Media path : %s, AAC bitrate: %s", config.media_path, config.aac_bitrate)

    if not os.path.isdir(config.media_path):
        log.error("Media path does not exist or is not a directory: %s", config.media_path)
        sys.exit(1)

    total = ok = failed = 0

    for video_path in scan_video_files(config.media_path):
        total += 1
        success = process_file(video_path, config, log)
        log.info("\t\t\t\tProcessed: %d / %d", success, total)
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
