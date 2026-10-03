"""Get a video onto disk: URL (via yt-dlp) or a local file."""
import os
import shutil
from pathlib import Path

import yt_dlp

from .media import probe_duration

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


def is_local_file(source: str) -> bool:
    p = Path(os.path.expanduser(source.removeprefix("file://")))
    return p.is_file()


def fetch(source: str, workdir: Path):
    """Return (video_path, meta). `source` is a URL or a path to a video file."""
    if is_local_file(source):
        src = Path(os.path.expanduser(source.removeprefix("file://"))).resolve()
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
    browser = os.environ.get("REELPROMPT_COOKIES_BROWSER")  # e.g. "chrome"; helps with private/age-gated IG
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(
            f"Could not download {source}: {e}. This tool needs a post that contains a video. "
            "For login-gated Instagram posts set REELPROMPT_COOKIES_BROWSER=chrome (or safari/firefox)."
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
