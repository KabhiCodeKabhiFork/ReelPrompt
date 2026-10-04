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


MIN_FRAMES, MAX_FRAMES, SECONDS_PER_FRAME = 8, 16, 10
FRAME_WIDTH = 768  # px; UI mode asks for more so on-screen text stays readable


def auto_frame_count(duration: float) -> int:
    """About one frame per 10s, clamped to 8..16. Reels and Shorts keep 8; longer videos get more."""
    return max(MIN_FRAMES, min(MAX_FRAMES, round((duration or 0) / SECONDS_PER_FRAME)))


def parse_timestamp(value) -> float:
    """Seconds from 75, '75', '75.5', '1:15' or '0:01:15'. Raises ValueError otherwise."""
    if isinstance(value, (int, float)):
        t = float(value)
    else:
        try:
            parts = [float(x) for x in str(value).strip().split(":")]
        except ValueError:
            raise ValueError(f"Bad timestamp {value!r}; use seconds or mm:ss") from None
        if not 1 <= len(parts) <= 3:
            raise ValueError(f"Bad timestamp {value!r}; use seconds or mm:ss")
        t = 0.0
        for part in parts:
            t = t * 60 + part
    if t < 0:
        raise ValueError(f"Bad timestamp {value!r}: negative")
    return t


def frame_at(video: Path, ts: float, dest: Path, width: int = FRAME_WIDTH) -> Path:
    """Grab one frame at `ts` seconds (clamped to the video end) and write it to `dest`."""
    ts = max(0.0, min(ts, max(0.0, probe_duration(video) - 0.1)))
    _run(["ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", str(video), "-frames:v", "1",
          "-vf", f"scale={width}:-2", "-q:v", "3", str(dest)])
    return dest


def pick_frames(video: Path, workdir: Path, n_frames: int, duration: float, width: int = FRAME_WIDTH):
    """Return [(timestamp_s, path)] of up to n_frames representative frames.

    Samples a pool of candidates (60, or 6 per wanted frame if that is more), then keeps half by biggest
    visual change (scene cuts, UI changes) and half evenly spaced, so a long static stretch is still
    represented.
    """
    cand_dir = workdir / "cand"
    cand_dir.mkdir(exist_ok=True)
    interval = max(0.5, duration / max(60, n_frames * 6))
    _run(["ffmpeg", "-y", "-i", str(video), "-vf", f"fps=1/{interval},scale={width}:-2",
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
