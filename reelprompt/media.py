"""ffmpeg helpers: probing, audio extraction, key-frame selection."""
import subprocess
from pathlib import Path

from PIL import Image, ImageChops


def _run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def probe_duration(video: Path) -> float:
    return float(_run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                       "-of", "csv=p=0", str(video)]).strip())


def has_audio(video: Path) -> bool:
    out = _run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                "stream=index", "-of", "csv=p=0", str(video)])
    return bool(out.strip())


def extract_audio(video: Path, workdir: Path) -> Path:
    wav = workdir / "audio.wav"
    _run(["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)])
    return wav


def _delta(a, b) -> float:
    return sum(ImageChops.difference(a, b).tobytes()) / 1024


def pick_frames(video: Path, workdir: Path, n_frames: int, duration: float):
    """Return [(timestamp_s, path)] of up to n_frames representative frames.

    Samples ~60 candidates, then keeps half by biggest visual change (scene cuts, UI changes)
    and half evenly spaced, so a long static stretch is still represented.
    """
    cand_dir = workdir / "cand"
    cand_dir.mkdir(exist_ok=True)
    interval = max(0.5, duration / 60)
    _run(["ffmpeg", "-y", "-i", str(video), "-vf", f"fps=1/{interval},scale=768:-2",
          "-q:v", "3", str(cand_dir / "c_%04d.jpg")])
    files = sorted(cand_dir.glob("c_*.jpg"))
    if not files:
        return []
    thumbs = [Image.open(p).convert("L").resize((32, 32)) for p in files]
    diffs = [0.0] + [_delta(thumbs[i], thumbs[i - 1]) for i in range(1, len(files))]

    keep = {0}
    n_even = max(1, n_frames // 2)
    for k in range(1, n_even):  # evenly spaced anchors
        keep.add(min(len(files) - 1, round(k * len(files) / n_even)))
    for i in sorted(range(1, len(files)), key=lambda i: -diffs[i]):  # biggest changes
        if len(keep) >= n_frames:
            break
        if diffs[i] >= 4:  # skip near-duplicates of the previous candidate
            keep.add(i)
    keep = sorted(keep)[:n_frames] if len(keep) > n_frames else sorted(keep)
    return [(i * interval, files[i]) for i in keep]
