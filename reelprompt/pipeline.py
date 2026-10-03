"""The pipeline: fetch -> frames + transcript -> (optional) LLM analysis -> pack on disk."""
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import analyze as analyze_mod
from .fetch import fetch
from .media import extract_audio, has_audio, pick_frames
from .transcribe import format_transcript, transcribe

log = logging.getLogger("reelprompt")


def default_out_dir() -> Path:
    return Path(os.environ.get("REELPROMPT_HOME", "~/.reelprompt")).expanduser() / "packs"


@dataclass
class Pack:
    path: Path
    meta: dict
    transcript: str
    frames: list  # [(filename, Path)]
    language: str | None = None
    prompt_md: str | None = None
    timings: dict = field(default_factory=dict)
    tokens: tuple = (0, 0)
    cost: float = 0.0

    @property
    def prompt_path(self):
        return self.path / "PROMPT.md"


def _pack_dir(out_root: Path, meta: dict, source: str) -> Path:
    ident = meta.get("id") or hashlib.sha1(source.encode()).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "", (meta.get("platform") or "video").lower())
    return out_root / f"{slug}_{ident}"


def extract(source: str, n_frames: int = 8, out_root: Path | None = None, progress=None) -> Pack:
    """Fetch the video and write frames/, transcript.md, meta.json. No LLM, no API key needed."""
    progress = progress or (lambda msg: None)
    out_root = Path(out_root) if out_root else default_out_dir()
    timings = {}
    work = Path(tempfile.mkdtemp(prefix="reelprompt_"))
    try:
        t = time.time()
        progress("Downloading video")
        video, meta = fetch(source, work)
        timings["fetch"] = time.time() - t

        t = time.time()
        progress("Selecting key frames")
        picked = pick_frames(video, work, n_frames, meta["duration_s"])
        timings["frames"] = time.time() - t

        t = time.time()
        segments, lang = [], None
        if has_audio(video):
            progress("Transcribing audio")
            segments, lang = transcribe(extract_audio(video, work))
        timings["transcribe"] = time.time() - t

        pack_dir = _pack_dir(out_root, meta, source)
        if (pack_dir / "frames").exists():
            shutil.rmtree(pack_dir / "frames")
        (pack_dir / "frames").mkdir(parents=True, exist_ok=True)
        frames = []
        for i, (ts, src) in enumerate(picked, 1):
            name = f"{i:02d}_{int(ts // 60):02d}m{int(ts % 60):02d}s.jpg"
            shutil.copy(src, pack_dir / "frames" / name)
            frames.append((name, pack_dir / "frames" / name))

        transcript = format_transcript(segments)
        (pack_dir / "transcript.md").write_text(transcript or "(no speech detected)")
        (pack_dir / "meta.json").write_text(
            json.dumps({**meta, "language": lang}, indent=2, ensure_ascii=False))
        return Pack(pack_dir, meta, transcript, frames, lang, timings=timings)
    finally:
        shutil.rmtree(work, ignore_errors=True)  # never keep the downloaded video


def analyze(pack: Pack, progress=None) -> Pack:
    """Run the LLM over an extracted pack and write PROMPT.md."""
    (progress or (lambda msg: None))(f"Analyzing with {analyze_mod.provider()}/{analyze_mod.model()}")
    t = time.time()
    md, tok_in, tok_out = analyze_mod.analyze(pack.meta, pack.transcript, pack.frames)
    pack.timings["analyze"] = time.time() - t
    pack.prompt_md, pack.tokens = md, (tok_in, tok_out)
    pack.cost = analyze_mod.estimate_cost(tok_in, tok_out)
    pack.prompt_path.write_text(md)
    return pack


def run(source: str, n_frames: int = 8, out_root: Path | None = None, progress=None) -> Pack:
    return analyze(extract(source, n_frames, out_root, progress), progress)
