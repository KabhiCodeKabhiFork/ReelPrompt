"""Tiny .env loader (no dependency). Never overrides variables already set in the environment.

Looked up, in order: $VIDEO_BRIEF_HOME/.env (default ~/.video-brief/.env), then a .env in the project root
(the folder containing the `video_brief/` package, which is where you cloned the repo).
"""
import os
from pathlib import Path


def _parse(path: Path):
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        val = val.strip().strip("'\"")
        if key:
            yield key, val


def load_env() -> None:
    if os.environ.get("VIDEO_BRIEF_NO_DOTENV"):  # used by tests; set to skip .env files
        return
    home = Path(os.environ.get("VIDEO_BRIEF_HOME", "~/.video-brief")).expanduser()
    for path in (home / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if path.is_file():
            for key, val in _parse(path):
                os.environ.setdefault(key, val)
