import os
from pathlib import Path
from typing import Iterator

VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv",
    ".webm", ".ts", ".m4v", ".3gp", ".mpg", ".mpeg",
    ".m2ts", ".mts", ".vob", ".ogv", ".rm", ".rmvb",
    ".divx", ".f4v", ".m2v", ".mp2", ".mpe", ".mpv",
    ".asf", ".dv",
})


def scan_video_files(media_path: str) -> Iterator[Path]:
    """Yield every video file found recursively under media_path."""
    for root, _dirs, files in os.walk(media_path):
        for name in sorted(files):
            path = Path(root) / name
            if path.suffix.lower() in VIDEO_EXTENSIONS:
                yield path
