"""Command line interface: `reelprompt <url-or-file>`."""
import argparse
import logging
import sys

from . import analyze as analyze_mod
from . import pipeline, playbooks
from .config import load_env


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="reelprompt",
        description="Turn a reel / X video / YouTube Short / local video into a context pack for a coding agent.")
    ap.add_argument("source", help="video URL or path to a local video file")
    ap.add_argument("--frames", type=int, default=8, help="number of key frames to keep (default 8)")
    ap.add_argument("--out", default=None, help="output folder (default ~/.reelprompt/packs)")
    ap.add_argument("--no-llm", action="store_true",
                    help="only download + frames + transcript; skip PROMPT.md (no API key needed)")
    ap.add_argument("--category", default=None, choices=playbooks.ids(),
                    help="force what the video is about instead of classifying it (skips the classify call)")
    args = ap.parse_args(argv)
    load_env()

    logging.basicConfig(level=logging.INFO, format="[reelprompt] %(message)s", stream=sys.stderr)
    say = lambda msg: print(f"[reelprompt] {msg}...", file=sys.stderr, flush=True)  # noqa: E731
    try:
        pack = pipeline.extract(args.source, args.frames, args.out, say)
        if not args.no_llm:
            pipeline.analyze(pack, say, args.category)
    except (RuntimeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    m = pack.meta
    print(f"\npack:       {pack.path}")
    print(f"source:     {m['platform']} | {m['title']!r} | {m['duration_s']:.0f}s")
    print(f"transcript: {len(pack.transcript.splitlines())} lines, lang={pack.language}")
    print(f"frames:     {len(pack.frames)}")
    if args.no_llm:
        sug = pack.suggestion
        print(f"category:   {args.category or sug['category']} (keyword guess, {sug['confidence']} confidence)")
    else:
        print(f"category:   {pack.category} ({playbooks.get(pack.category).name})")
    print("timings:    " + ", ".join(f"{k} {v:.1f}s" for k, v in pack.timings.items()))
    if not args.no_llm:
        print(f"tokens:     {pack.tokens[0]} in / {pack.tokens[1]} out -> "
              f"~${pack.cost:.4f} ({analyze_mod.provider()}/{analyze_mod.model()})")
        print(f"prompt:     {pack.prompt_path}")
        print(f"system:     {pack.system_prompt_path if pack.system_prompt else '(model returned no system prompt)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
