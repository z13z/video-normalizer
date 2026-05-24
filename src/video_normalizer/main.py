import logging
import os
import shutil
import sys
from pathlib import Path

import ffmpeg

from .analyzer import analyze
from .config import Config
from .converter import convert, SUPPORTED_VIDEO_CODECS
from .scanner import scan_video_files


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

# returns two bools, first one shows if file was processed successfully and second if it was skipped.
# todo fix using proper result wrapper enum
def process_file(path: Path, config: Config, log: logging.Logger):
    log.info("Scanning: %s", path)

    try:
        analysis = analyze(path, config)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else str(exc)
        log.error("Failed to probe %s: %s", path, stderr)
        return False, False
    if not analysis.requires_processing:
        return True, True

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
        return True, False

    except RuntimeError as exc:
        log.error("Conversion failed for %s: %s", path, exc)
        return False, False
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def validate_config(config: Config, log: logging.Logger) -> bool:
    if config.video_codec not in SUPPORTED_VIDEO_CODECS:
        log.error(
            "Unsupported VIDEO_CODEC %r. Supported values: %s",
            config.video_codec,
            ", ".join(SUPPORTED_VIDEO_CODECS),
        )
        sys.exit(1)


def main():
    config = Config()
    _setup_logging(config.log_level)
    log = logging.getLogger("video_normalizer")
    validate_config(config, log)
    log.info("Starting video normalizer, Media path : %s, AAC bitrate: %s", config.media_path, config.aac_bitrate)

    if not os.path.isdir(config.media_path):
        log.error("Media path does not exist or is not a directory: %s", config.media_path)
        sys.exit(1)

    total_cnt = ok_cnt = skipped_cnt = failed_cnt = 0

    for video_path in scan_video_files(config.media_path):
        total_cnt += 1
        success, skipped = process_file(video_path, config, log)
        if success:
            ok_cnt += 1
        elif skipped:
            skipped_cnt += 1
        else:
            failed_cnt += 1
        log.info("\t===============\tProcessed: %d / %d\t===============", ok_cnt, total_cnt)

    log.info(
        "Finished. Total=%d  OK=%d  Skipped=%d  Failed=%d",
        total_cnt, ok_cnt, skipped_cnt, failed_cnt,
    )

    if failed_cnt:
        sys.exit(1)


if __name__ == "__main__":
    main()
