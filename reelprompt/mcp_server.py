"""MCP server (stdio). Exposes two tools to coding agents:

  get_video_context  download + frames + transcript + caption. No API key; the calling agent is the LLM.
  analyze_video      same, plus a ready-to-use PROMPT.md written by the configured LLM. Only registered
                     when an API key is configured; otherwise just get_video_context is offered.
"""
import asyncio
import json

from mcp.server.mcpserver import Context, Image, MCPServer

from . import analyze as analyze_mod
from . import pipeline
from .config import load_env

_BASE = (
    "Turns a short video (Instagram reel, X/Twitter video, YouTube Short, or a local video file) into "
    "build context. When the user shares a video link and wants to build or learn from what it shows, call "
    "get_video_context and work from the caption, transcript and frames it returns. "
    "Only posts that contain a video are supported (not still-image posts)."
)
_ANALYZE = (" analyze_video is also available: it has an LLM write a finished PROMPT.md spec; "
            "use it when the user asks for a standalone prompt/spec file.")


def _progress_cb(ctx: Context, loop):
    stages = {"Downloading": 0.1, "Selecting": 0.35, "Transcribing": 0.5, "Analyzing": 0.8}

    def cb(msg: str):
        frac = next((v for k, v in stages.items() if msg.startswith(k)), 0.0)
        asyncio.run_coroutine_threadsafe(ctx.report_progress(frac, 1.0, msg), loop)

    return cb


def _summary(pack: pipeline.Pack) -> str:
    m = pack.meta
    head = {
        "platform": m["platform"], "title": m["title"], "author": m["uploader"],
        "duration_s": round(m["duration_s"] or 0), "source": m["source"],
        "language": pack.language, "pack_folder": str(pack.path),
        "frames": [f"frames/{n}" for n, _ in pack.frames],
    }
    return (
        f"```json\n{json.dumps(head, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Caption / description\n{m['description'] or '(none)'}\n\n"
        f"## Transcript\n{pack.transcript or '(no speech detected: rely on the frames and caption)'}\n"
    )


def _images(pack: pipeline.Pack):
    return [Image(path=str(p)) for _, p in pack.frames]


async def get_video_context(source: str, ctx: Context, frames: int = 8) -> list:
    """Extract everything needed to understand a short video: caption, timestamped transcript and
    key frames (returned as images). Needs no API key. Free to call.

    Args:
        source: URL of an Instagram reel, X/Twitter video post, YouTube Short/video, or an absolute
            path to a local video file (.mp4/.mov/.mkv/.webm).
        frames: number of key frames to return (default 8, max 16).
    """
    loop = asyncio.get_running_loop()
    pack = await asyncio.to_thread(
        pipeline.extract, source, max(1, min(frames, 16)), None, _progress_cb(ctx, loop))
    return [_summary(pack), *_images(pack)]


async def analyze_video(source: str, ctx: Context, frames: int = 8, include_frames: bool = True) -> list:
    """Like get_video_context, but also has an LLM write a ready-to-use PROMPT.md build spec
    (what the video is, build brief, seen-vs-assumed, open questions, starter prompt). Requires the
    server to be configured with OPENAI_API_KEY (or REELPROMPT_PROVIDER=anthropic + ANTHROPIC_API_KEY).
    Costs a fraction of a cent per video with the default model. The pack is also saved to disk.

    Args:
        source: URL of an Instagram reel, X/Twitter video post, YouTube Short/video, or an absolute
            path to a local video file.
        frames: number of key frames to analyze (default 8, max 16).
        include_frames: also return the frames as images (default true).
    """
    loop = asyncio.get_running_loop()
    pack = await asyncio.to_thread(
        pipeline.run, source, max(1, min(frames, 16)), None, _progress_cb(ctx, loop))
    note = (f"\n\n---\nPack saved to `{pack.path}` (PROMPT.md, transcript.md, meta.json, frames/). "
            f"LLM: {analyze_mod.provider()}/{analyze_mod.model()}, ~${pack.cost:.4f}.")
    return [pack.prompt_md + note, *(_images(pack) if include_frames else [])]


def create_server() -> MCPServer:
    """Build the server. analyze_video is only registered when the LLM provider has credentials."""
    load_env()
    with_llm = analyze_mod.is_configured()
    server = MCPServer("reelprompt", instructions=_BASE + (_ANALYZE if with_llm else ""))
    server.tool()(get_video_context)
    if with_llm:
        server.tool()(analyze_video)
    return server


def main():
    create_server().run("stdio")


if __name__ == "__main__":
    main()
