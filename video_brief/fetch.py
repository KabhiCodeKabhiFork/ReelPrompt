"""Get a video onto disk: URL (via yt-dlp) or a local file."""
import os
import re
import shutil
from pathlib import Path

import yt_dlp

from .media import probe_duration

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".gif"}


def resolve_local(source: str) -> Path | None:
    """The local file `source` points at, or None if it is not one (so it is treated as a URL).

    Tolerates what people actually paste for screen recordings: surrounding quotes, `file://`, `~`,
    backslash-escaped spaces from drag-and-drop, and macOS names like "Screen Recording ... at 10.12.33 AM.mov"
    where the space before AM/PM is a narrow no-break space that a typed space does not match.
    """
    raw = source.strip().strip("'\"")
    if raw.startswith(("http://", "https://")):
        return None
    raw = raw.removeprefix("file://")
    for cand in (raw, re.sub(r"\\(.)", r"\1", raw)):
        p = Path(os.path.expanduser(cand))
        if p.is_file():
            return p
        if p.parent.is_dir():  # same name up to which kind of space it uses
            want = _squash_spaces(p.name)
            for sib in p.parent.iterdir():
                if sib.is_file() and _squash_spaces(sib.name) == want:
                    return sib
    return None


def _squash_spaces(name: str) -> str:
    return re.sub(r"[\s\u202f\u00a0]", " ", name)


def is_local_file(source: str) -> bool:
    return resolve_local(source) is not None


def fetch(source: str, workdir: Path):
    """Return (video_path, meta). `source` is a URL or a path to a video file."""
    local = resolve_local(source)
    if local is not None:
        src = local.resolve()
        if src.suffix.lower() not in VIDEO_EXTS:
            raise ValueError(f"Unsupported file type {src.suffix!r}; expected one of {sorted(VIDEO_EXTS)}")
        dst = workdir / f"video{src.suffix.lower()}"
        shutil.copy(src, dst)
        return dst, {
            "source": str(src), "platform": "local file", "id": None,
            "title": src.stem, "uploader": None, "description": "",
            "duration_s": probe_duration(dst),
        }

    opts = {
        "outtmpl": str(workdir / "video.%(ext)s"),
        # low resolution on purpose: we only need frames + audio, and it keeps bandwidth tiny
        "format": "bv*[height<=480]+ba/b[height<=480]/worst",
        "merge_output_format": "mp4",
        "quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
    }
    browser = os.environ.get("VIDEO_BRIEF_COOKIES_BROWSER")  # e.g. "chrome"; helps with private/age-gated IG
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(
            f"Could not download {source}: {e}. This tool needs a post that contains a video. "
            "For login-gated Instagram posts set VIDEO_BRIEF_COOKIES_BROWSER=chrome (or safari/firefox)."
        ) from e
    video = next(workdir.glob("video.*"))
    return video, {
        "source": source,
        "platform": info.get("extractor_key"),
        "id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "description": (info.get("description") or "")[:1500],  # usually the caption
        "duration_s": info.get("duration") or probe_duration(video),
    }
