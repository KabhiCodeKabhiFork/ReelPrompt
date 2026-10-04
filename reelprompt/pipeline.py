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
from . import playbooks
from .fetch import fetch
from .media import auto_frame_count, extract_audio, frame_at, has_audio, parse_timestamp, pick_frames
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
    system_prompt: str | None = None
    suggestion: dict = field(default_factory=dict)  # free keyword guess: {category, confidence, ranked}
    category: str | None = None  # final category (set by the LLM step, or by the caller)
    timings: dict = field(default_factory=dict)
    tokens: tuple = (0, 0)
    cost: float = 0.0

    @property
    def prompt_path(self):
        return self.path / "PROMPT.md"

    @property
    def system_prompt_path(self):
        return self.path / "SYSTEM_PROMPT.md"


def _pack_dir(out_root: Path, meta: dict, source: str) -> Path:
    ident = meta.get("id") or hashlib.sha1(source.encode()).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "", (meta.get("platform") or "video").lower())
    return out_root / f"{slug}_{ident}"


def extract(source: str, n_frames: int | None = None, out_root: Path | None = None, progress=None) -> Pack:
    """Fetch the video and write frames/, transcript.md, meta.json. No LLM, no API key needed.
    `n_frames` None/0 = automatic: about one per 10s of video, between 8 and 16."""
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
        n_frames = max(1, min(n_frames, 32)) if n_frames else auto_frame_count(meta["duration_s"])
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
        suggestion = playbooks.classify(meta, transcript)
        (pack_dir / "meta.json").write_text(
            json.dumps({**meta, "language": lang, "suggested_category": suggestion["category"]},
                       indent=2, ensure_ascii=False))
        return Pack(pack_dir, meta, transcript, frames, lang, suggestion=suggestion, timings=timings)
    finally:
        shutil.rmtree(work, ignore_errors=True)  # never keep the downloaded video


def frames_at(source: str, timestamps: list, out_root: Path | None = None, progress=None) -> tuple:
    """Grab extra frames at specific moments (seconds or 'mm:ss'), e.g. ones the transcript points to.
    Re-fetches the video (it is never kept), saves them into the pack's frames/ folder as at_MMmSSs.jpg,
    and returns (pack_dir, [(filename, Path)]). Max 8 per call."""
    progress = progress or (lambda msg: None)
    times = [parse_timestamp(t) for t in timestamps][:8]
    if not times:
        raise ValueError("Give at least one timestamp (seconds or mm:ss).")
    out_root = Path(out_root) if out_root else default_out_dir()
    work = Path(tempfile.mkdtemp(prefix="reelprompt_"))
    try:
        progress("Downloading video")
        video, meta = fetch(source, work)
        pack_dir = _pack_dir(out_root, meta, source)
        (pack_dir / "frames").mkdir(parents=True, exist_ok=True)
        progress("Selecting key frames")
        out = []
        for ts in times:
            name = f"at_{int(ts // 60):02d}m{int(ts % 60):02d}s.jpg"
            out.append((name, frame_at(video, ts, pack_dir / "frames" / name)))
        return pack_dir, out
    finally:
        shutil.rmtree(work, ignore_errors=True)


def analyze(pack: Pack, progress=None, category: str | None = None) -> Pack:
    """Classify, then run the LLM over an extracted pack. Writes PROMPT.md and SYSTEM_PROMPT.md.
    `category` forces a playbook id and skips the classify call."""
    (progress or (lambda msg: None))(f"Analyzing with {analyze_mod.provider()}/{analyze_mod.model()}")
    t = time.time()
    md, tok_in, tok_out, pack.category = analyze_mod.analyze(
        pack.meta, pack.transcript, pack.frames, category or pack.category)
    pack.timings["analyze"] = time.time() - t
    pack.prompt_md, pack.tokens = md, (tok_in, tok_out)
    pack.cost = analyze_mod.estimate_cost(tok_in, tok_out)
    pack.prompt_path.write_text(md)
    pack.system_prompt = analyze_mod.extract_system_prompt(md)
    if pack.system_prompt:
        pack.system_prompt_path.write_text(pack.system_prompt + "\n")
    meta_path = pack.path / "meta.json"
    meta_path.write_text(json.dumps({**json.loads(meta_path.read_text()), "category": pack.category},
                                    indent=2, ensure_ascii=False))
    return pack


def run(source: str, n_frames: int | None = None, out_root: Path | None = None, progress=None,
        category: str | None = None) -> Pack:
    return analyze(extract(source, n_frames, out_root, progress), progress, category)
