# ReelPrompt

**Turn an Instagram reel, X video or YouTube Short into build context for your coding agent.**

You see a video of a cool UI, app or workflow. You tell Claude Code / Codex / Cursor *"build what's in this reel"*
and paste the link. ReelPrompt downloads the video, pulls out the caption, transcribes the speech, picks the key
frames, and hands all of it to your agent, so the agent can see what you saw.

It runs **locally on your machine** as an [MCP](https://modelcontextprotocol.io) server (plus a CLI). No hosted
service, no subscription, no GPU, and **no API key needed**.

```
reel / X post / Short / local file
        │  yt-dlp (lowest quality: small and fast)
        ▼
   video.mp4 ──► ffmpeg ──► key frames (scene changes + even coverage)
        │                        │
        └──► faster-whisper ─► transcript        caption (from the post)
                                 └───────────┬───────────┘
                                             ▼
                  ┌──────────────────────────┴──────────────────────────┐
                  │ get_video_context: your agent reads it directly     │  ← no API key
                  │ analyze_video:     an LLM writes a PROMPT.md spec   │  ← optional, needs a key
                  └─────────────────────────────────────────────────────┘
```

## Do I need an API key? (No)

**For the normal MCP setup, no key is needed.** Everything the server does itself is free and local:
downloading (yt-dlp), frame extraction (ffmpeg) and transcription (Whisper, running on your CPU).

The server does **not** contain or call an LLM in that mode. It returns the caption, transcript and frames
to your coding agent, and **the agent is the LLM**. It reads them using whatever model and plan you already
use (your Claude Code subscription, your Codex plan, Cursor, and so on). ReelPrompt adds nothing to your bill.

An API key is only for one optional extra tool, `analyze_video`, which has *the server* call a model to write a
finished `PROMPT.md` file. If you don't set a key, that tool simply isn't offered, and nothing breaks.

> A Claude Pro/Max or ChatGPT subscription is **not** an API key, and the server can't use it for its own calls.
> API keys are billed separately, per use. That's why the key-free `get_video_context` is the default.

## Two tools

| Tool | What it returns | Who runs the LLM | API key |
|---|---|---|---|
| `get_video_context(source, frames=8)` | Caption, timestamped transcript and key frames (as images) | **Your coding agent**, on your own plan | **Not needed** |
| `analyze_video(source, frames=8, include_frames=true)` | The same, plus a finished **`PROMPT.md`** (what the video is, build brief, seen-vs-assumed, open questions, starter prompt) | **ReelPrompt itself**, calling OpenAI or Anthropic | **Required.** Only appears when a key is set |

`source` is a video URL (Instagram reel, X/Twitter post with a video, YouTube Short or video) **or an absolute path
to a video file** on your machine (`.mp4 .mov .mkv .webm .m4v .avi`).

Every run also saves a pack to `~/.reelprompt/packs/<platform>_<id>/`:

```
PROMPT.md       (analyze_video / CLI with a key only)
transcript.md   timestamped transcript
meta.json       source, title, author, caption, duration
frames/         01_00m00s.jpg, 02_00m12s.jpg, ...
```

The downloaded video itself is deleted after processing.

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org) on your `PATH` (`brew install ffmpeg` / `apt install ffmpeg`)

## Install

```bash
git clone https://github.com/<your-username>/reelprompt.git
cd reelprompt
python3 -m venv .venv
.venv/bin/pip install -e .
```

> On Apple Silicon, use a native arm64 Python (Homebrew's `python3`). An Intel/Rosetta Python is slow and some
> dependencies have no wheels for it.

The first run downloads the Whisper `base` model (about 140 MB) once.

## Add it to your coding agent (no API key)

Replace `/ABS/PATH/reelprompt` with the folder you cloned into.

### Claude Code

```bash
claude mcp add reelprompt -- /ABS/PATH/reelprompt/.venv/bin/reelprompt-mcp
```

Then, in a session:

> Here's a reel: https://www.instagram.com/reel/XXXX/ . Use reelprompt to look at it and build the UI it shows.

Claude Code calls `get_video_context`, reads the caption, transcript and frames with your own Claude plan, and
starts building.

### Codex (`~/.codex/config.toml`)

```toml
[mcp_servers.reelprompt]
command = "/ABS/PATH/reelprompt/.venv/bin/reelprompt-mcp"
```

### Cursor (`~/.cursor/mcp.json`) and Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "reelprompt": {
      "command": "/ABS/PATH/reelprompt/.venv/bin/reelprompt-mcp"
    }
  }
}
```

Anything that speaks MCP over stdio works the same way. Some agents may not display images returned by MCP
tools. In that case the caption and transcript still come through.

## Optional: let ReelPrompt write `PROMPT.md` itself (needs an API key)

Add a key if you want the `analyze_video` tool: one call that returns a finished spec, written by a model the
**server** calls (not your agent). You choose which provider with `REELPROMPT_PROVIDER`:

| | **OpenAI (default)** | **Anthropic** |
|---|---|---|
| `REELPROMPT_PROVIDER` | `openai` | `anthropic` |
| Model called | **`gpt-6-luna`** (OpenAI Luna) | **`claude-haiku-4-5`** (Claude Haiku) |
| Key variable | `OPENAI_API_KEY` | `ANTHROPIC_API_KEY` |
| Extra install | none | `.venv/bin/pip install -e ".[anthropic]"` |
| Rough cost per video | about $0.0015 | about $0.01 |
| How well tested | Run end to end on real X and Instagram videos | Supported, but not yet run against the live API |

Costs are rough estimates for an 8-frame video and depend on current provider pricing. Both providers' models
accept images, which `analyze_video` needs. Override the model with `REELPROMPT_MODEL` (for example
`gpt-5.6-luna` or `claude-sonnet-5-5`).

**With OpenAI Luna (Claude Code):**

```bash
claude mcp add reelprompt -e OPENAI_API_KEY=sk-... -- /ABS/PATH/reelprompt/.venv/bin/reelprompt-mcp
```

**With Claude Haiku (Claude Code):**

```bash
.venv/bin/pip install -e ".[anthropic]"
claude mcp add reelprompt -e REELPROMPT_PROVIDER=anthropic -e ANTHROPIC_API_KEY=sk-ant-... \
  -- /ABS/PATH/reelprompt/.venv/bin/reelprompt-mcp
```

For Codex, add the same variables under the server entry (`env = { OPENAI_API_KEY = "sk-..." }`). For Cursor and
Claude Desktop, add an `"env": { ... }` object next to `"command"`.

Or skip the `-e` flags and put the variables in a `.env` file, see [Configuration](#configuration). Restart your
agent after changing keys, because the tool list is read when the server starts.

With a key set, the agent sees both tools and picks the one that fits: `get_video_context` for "look at this
video and build it", `analyze_video` for "write me a spec for this video".

## Use it as a CLI

```bash
.venv/bin/reelprompt "https://youtube.com/shorts/abc" --no-llm   # no API key: pack with frames + transcript
.venv/bin/reelprompt "https://x.com/someone/status/123"          # also writes PROMPT.md (needs a key)
.venv/bin/reelprompt ~/Movies/screen-recording.mp4 --frames 12
```

It prints timings and, when an LLM was used, the token cost of the run.

## Configuration

Instead of exporting variables, you can put them in a `.env` file: either `~/.reelprompt/.env` or a `.env` in the
repo folder (git-ignored). Variables already set in your environment win. Example:

```
OPENAI_API_KEY=sk-...
REELPROMPT_PROVIDER=openai
```

| Variable | Default | Meaning |
|---|---|---|
| `REELPROMPT_PROVIDER` | `openai` | `openai` (Luna) or `anthropic` (Haiku), only used by `analyze_video` / the CLI's `PROMPT.md` |
| `REELPROMPT_MODEL` | `gpt-6-luna` / `claude-haiku-4-5` | Analysis model; any vision-capable model works |
| `REELPROMPT_EFFORT` | `low` | OpenAI `reasoning_effort` |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | unset | Credentials for the chosen provider. Without one, `analyze_video` is not offered |
| `REELPROMPT_WHISPER_MODEL` | `base` | faster-whisper model: `tiny`, `base`, `small`, ... (bigger = slower, more accurate) |
| `REELPROMPT_COOKIES_BROWSER` | unset | `chrome`, `safari`, `firefox`: use that browser's login for gated Instagram posts |
| `REELPROMPT_HOME` | `~/.reelprompt` | Where packs and the optional `.env` live |

## Limitations

- **Video posts only.** Still-image posts and photo carousels are not supported yet.
- **Platform downloads break sometimes.** Instagram and X change often. Update the downloader first:
  `.venv/bin/pip install -U yt-dlp`. Private or login-gated Instagram posts need `REELPROMPT_COOKIES_BROWSER`.
- **Videos with no speech** (music over a screen recording) have an empty transcript. The agent relies on the
  frames and caption, which is why frames are included.
- Frames cost context: returning 8 images uses some of your agent's context and plan usage. Lower it with the
  `frames` argument if needed.
- When an LLM writes `PROMPT.md`, it only sees what the frames show. Anything not on screen or in the audio is
  marked as an assumption, so check the *Open questions* section.
- Transcription runs on CPU. A 40-second clip takes a few seconds with the default model.

## Responsible use

ReelPrompt is meant for **personal use**: understanding a video you can already watch. It downloads at low
quality to a temporary folder, deletes the video afterwards and keeps only frames, a transcript and the caption.
Respect each platform's terms and the original creator's rights, and don't use it to redistribute content.

## Development

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest        # offline: local videos, MCP server over stdio, mock LLM
```

See [CONTRIBUTING.md](CONTRIBUTING.md). MIT licensed.
