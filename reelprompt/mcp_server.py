"""MCP server (stdio). Exposes two tools to coding agents:

  get_video_context  download + frames + transcript + caption + a category suggestion and system-prompt
                     blueprint. No API key; the calling agent is the LLM.
  get_frames_at      extra frames at chosen timestamps (look closer at a moment).
  get_playbook       the blueprint for any category (software, habits, scheduling, automation, ...).
  analyze_video      same, plus a ready-to-use PROMPT.md written by the configured LLM. Only registered
                     when an API key is configured; otherwise just get_video_context is offered.
"""
import asyncio
import json

from mcp.server.mcpserver import Context, Image, MCPServer

from . import analyze as analyze_mod
from . import pipeline, playbooks
from .config import load_env

_BASE = (
    "Turns a short video (Instagram reel, X/Twitter video, YouTube Short, or a local video file) into "
    "context for doing anything it describes: building an app, following a routine, setting up a schedule or "
    "automation, and so on. When the user shares a video link, call get_video_context and work from the "
    "caption, transcript and frames it returns; it also suggests what kind of thing the video is about and how "
    "to write a tailored, portable system prompt for it (use get_playbook to switch category); get_frames_at grabs extra frames at chosen timestamps. "
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
    sug = pack.suggestion or playbooks.classify(m, pack.transcript)
    ranked = ", ".join(f"{pid} ({score})" for pid, score in sug["ranked"]) or "no keyword matches"
    return (
        f"```json\n{json.dumps(head, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Caption / description\n{m['description'] or '(none)'}\n\n"
        f"## Transcript\n{pack.transcript or '(no speech detected: rely on the frames and caption)'}\n\n"
        f"Need a closer look at a moment the transcript mentions? Call get_frames_at(source, [timestamps]).\n\n"
        f"## Classify, then tailor\n"
        f"Decide what this video is about. Keyword guess: **{sug['category']}** "
        f"({sug['confidence']} confidence; scores: {ranked}). It is only a hint: judge from the content "
        f"and override it if wrong. Categories:\n{playbooks.catalog()}\n\n"
        f"If your category differs from the guess, call get_playbook(category) for its blueprint. "
        f"Blueprint for the guess:\n\n{playbooks.render_blueprint(sug['category'])}\n"
    )


def _images(pack: pipeline.Pack):
    return [Image(path=str(p)) for _, p in pack.frames]


async def get_video_context(source: str, ctx: Context, frames: int = 0) -> list:
    """Extract everything needed to understand a short video: caption, timestamped transcript and
    key frames (returned as images). Needs no API key. Free to call.

    Args:
        source: URL of an Instagram reel, X/Twitter video post, YouTube Short/video, or an absolute
            path to a local video file (.mp4/.mov/.mkv/.webm).
        frames: number of key frames to return. 0 (default) = automatic: about one per 10 seconds of
            video, between 8 and 16. Max 16. To look closer at a moment, use get_frames_at.
    """
    loop = asyncio.get_running_loop()
    pack = await asyncio.to_thread(
        pipeline.extract, source, min(frames, 16) if frames > 0 else None, None, _progress_cb(ctx, loop))
    return [_summary(pack), *_images(pack)]


async def get_frames_at(source: str, timestamps: list[str], ctx: Context) -> list:
    """Look closer at specific moments of a video: returns one frame per timestamp. Use it when the
    transcript mentions something on screen (a UI, code, a chart, a recipe step) that the key frames
    from get_video_context did not capture. Re-downloads the video, so it takes a few seconds.
    No API key needed.

    Args:
        source: the same URL or absolute file path given to get_video_context.
        timestamps: up to 8 moments, as seconds ("75") or mm:ss ("1:15"), e.g. taken from the transcript.
    """
    loop = asyncio.get_running_loop()
    folder, got = await asyncio.to_thread(pipeline.frames_at, source, timestamps, None, _progress_cb(ctx, loop))
    return [f"Frames saved to `{folder}/frames/`: " + ", ".join(n for n, _ in got),
            *[Image(path=str(p)) for _, p in got]]


async def get_playbook(category: str = "") -> str:
    """Get the blueprint for writing a tailored, portable system prompt for one category of video.
    Call with no argument to list all categories. Categories cover building software, personal
    improvement, health and fitness, task scheduling, workflow automation, learning, content creation,
    business, personal finance, creative projects, research, and a general fallback. Free; no API key.

    Args:
        category: a category id, e.g. "task_scheduling". Empty returns the list of categories.
    """
    if not category.strip():
        return f"Categories:\n{playbooks.catalog()}"
    if not playbooks.is_known(category):
        return f"Unknown category {category!r}.\n\nCategories:\n{playbooks.catalog()}"
    return playbooks.render_blueprint(category)


async def analyze_video(source: str, ctx: Context, frames: int = 0, include_frames: bool = True,
                        category: str = "") -> list:
    """Like get_video_context, but also has an LLM classify the video and write a ready-to-use PROMPT.md
    (what the video is, core content, seen-vs-assumed, open questions, a tailored portable system prompt,
    first message) and a standalone SYSTEM_PROMPT.md. Requires the
    server to be configured with OPENAI_API_KEY (or REELPROMPT_PROVIDER=anthropic + ANTHROPIC_API_KEY).
    Costs a fraction of a cent per video with the default model. The pack is also saved to disk.

    Args:
        source: URL of an Instagram reel, X/Twitter video post, YouTube Short/video, or an absolute
            path to a local video file.
        frames: number of key frames to analyze (0 = automatic, about one per 10s, 8 to 16; max 16).
        include_frames: also return the frames as images (default true).
        category: force a category id instead of letting the LLM classify the video (optional).
    """
    loop = asyncio.get_running_loop()
    pack = await asyncio.to_thread(
        pipeline.run, source, min(frames, 16) if frames > 0 else None, None, _progress_cb(ctx, loop), category or None)
    note = (f"\n\n---\nPack saved to `{pack.path}` (PROMPT.md, SYSTEM_PROMPT.md, transcript.md, meta.json, frames/). "
            f"Category: {pack.category}. LLM: {analyze_mod.provider()}/{analyze_mod.model()}, ~${pack.cost:.4f}.")
    return [pack.prompt_md + note, *(_images(pack) if include_frames else [])]


def create_server() -> MCPServer:
    """Build the server. analyze_video is only registered when the LLM provider has credentials."""
    load_env()
    with_llm = analyze_mod.is_configured()
    server = MCPServer("reelprompt", instructions=_BASE + (_ANALYZE if with_llm else ""))
    server.tool()(get_video_context)
    server.tool()(get_frames_at)
    server.tool()(get_playbook)
    if with_llm:
        server.tool()(analyze_video)
    return server


def main():
    create_server().run("stdio")


if __name__ == "__main__":
    main()
