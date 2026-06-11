import logging
import os
import shutil
import sys
from pathlib import Path

import ffmpeg
import whisper
from whisper import Whisper

from .analyzer import analyze
from .config import Config
from .converter import convert, SUPPORTED_VIDEO_CODECS
from .scanner import scan_video_files
from .subtitle_merger import merge_subtitles
from .whisper_transcriber import transcribe as whisper_transcribe


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def generate_and_merge_missing_subtitles(needs_whisper, srt_paths, tmp_media_path, analysis, config, whisper_model: Whisper):
    if needs_whisper:
        srt_paths.extend(whisper_transcribe(tmp_media_path, analysis, config, whisper_model))
        if srt_paths:
            merged_path = merge_subtitles(tmp_media_path, srt_paths)
            tmp_media_path.unlink(missing_ok=True)
            tmp_media_path = merged_path
    return tmp_media_path


# returns two bools, first one shows if file was processed successfully and second if it was skipped.
# todo fix using proper result wrapper enum
def process_file(path: Path, config: Config, whisper_model: Whisper, log: logging.Logger):
    try:
        analysis = analyze(path, config)
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else str(exc)
        log.error("Failed to probe %s: %s", path, stderr)
        return False, False
    needs_whisper = config.whisper_model != "none" and analysis.needs_subtitle_generation
    if not analysis.requires_processing and not needs_whisper:
        return True, True

    log.info("Processing: %s", path)
    tmp_path: Path | None = None
    srt_paths: list[Path] = []
    try:
        tmp_path = convert(path, analysis, config)
        log.info("  Converted to tmp: %s (%.1f MB)",
                 tmp_path, tmp_path.stat().st_size / 1_048_576)
        tmp_path = generate_and_merge_missing_subtitles(needs_whisper, srt_paths, tmp_path, analysis, config, whisper_model)
        target = path.with_suffix(".mp4")
        if path != target and path.exists():
            path.unlink()

        shutil.move(str(tmp_path), str(target))
        log.info("  Done → %s", target)
        return True, False
    except RuntimeError as exc:
        log.error("Conversion failed for %s: %s", path, exc)
        return False, False
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        for srt in srt_paths:
            srt.unlink(missing_ok=True)


def validate_config(config: Config, log: logging.Logger):
    if config.video_codec not in SUPPORTED_VIDEO_CODECS:
        log.error(
            "Unsupported VIDEO_CODEC %r. Supported values: %s",
            config.video_codec,
            ", ".join(SUPPORTED_VIDEO_CODECS),
        )
        sys.exit(1)


def create_whisper_model(config: Config):
    return whisper.load_model(
        config.whisper_model,
        device=config.whisper_device,
        download_root=config.whisper_model_dir,
    )


def main():
    config = Config()
    _setup_logging(config.log_level)
    log = logging.getLogger("video_normalizer")
    validate_config(config, log)
    log.info("Starting video normalizer, Media path : %s, AAC bitrate: %s", config.media_path, config.aac_bitrate)

    if not os.path.isdir(config.media_path):
        log.error("Media path does not exist or is not a directory: %s", config.media_path)
        sys.exit(1)

    ok_cnt = skipped_cnt = failed_cnt = 0
    whisper_model = create_whisper_model(config)
    for video_path in scan_video_files(config.media_path):
        success, skipped = process_file(video_path, config, whisper_model, log)
        if success:
            ok_cnt += 1
            log.info("\t===============\tProcessed: %d \t===============", ok_cnt)
        elif skipped:
            skipped_cnt += 1
        else:
            failed_cnt += 1
        if 0 < config.process_limit <= (ok_cnt + failed_cnt):
            break

    log.info("Finished. OK=%d  Skipped=%d  Failed=%d", ok_cnt, skipped_cnt, failed_cnt)
    if failed_cnt:
        sys.exit(1)


if __name__ == "__main__":
    main()
