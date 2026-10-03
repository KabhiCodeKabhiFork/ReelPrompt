# ReelPrompt

**Turn an Instagram reel, X video or YouTube Short into build context for your coding agent.**

You see a video of a cool UI, app or workflow. You tell Claude Code / Codex / Cursor *"build what's in this reel"*
and paste the link. ReelPrompt downloads the video, pulls out the caption, transcribes the speech, picks the key
frames, and hands all of it to your agent, so the agent can see what you saw.

It runs **locally on your machine** as an [MCP](https://modelcontextprotocol.io) server (plus a CLI). No hosted
service, no subscription, no GPU.

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
                  │ get_video_context: your agent reads it directly     │
                  │ analyze_video:     an LLM writes a PROMPT.md spec   │
                  └─────────────────────────────────────────────────────┘
```

## Two tools

| Tool | What it returns | Needs an API key? |
|---|---|---|
| `get_video_context(source, frames=8)` | Caption, timestamped transcript and key frames (as images) | **No.** Your agent is the LLM |
| `analyze_video(source, frames=8, include_frames=true)` | All of the above plus a finished **`PROMPT.md`**: what the video is, build brief, seen-vs-assumed, open questions, starter prompt | Yes (default: OpenAI `gpt-6-luna`, about $0.002 per video) |

`analyze_video` only appears when an API key is configured. Without one, your agent sees just `get_video_context`
and does the analysis itself on your own agent plan.

`source` is a video URL (Instagram reel, X/Twitter post with a video, YouTube Short or video) **or an absolute path to a
video file** on your machine (`.mp4 .mov .mkv .webm .m4v .avi`).

Every run also saves a pack to `~/.reelprompt/packs/<platform>_<id>/`:

```
PROMPT.md       (analyze_video / CLI only)
transcript.md   timestamped transcript
meta.json       source, title, author, caption, duration
frames/         01_00m00s.jpg, 02_00m12s.jpg, ...
```

The downloaded video itself is deleted after processing.

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org) on your `PATH` (`brew install ffmpeg` / `apt install ffmpeg`)
- An API key **only** if you want `analyze_video` / `PROMPT.md`

## Install

```bash
git clone https://github.com/<your-username>/reelprompt.git
cd reelprompt
python3 -m venv .venv
.venv/bin/pip install -e .            # add ".[anthropic]" to also use Claude as the analysis model
```

> On Apple Silicon, use a native arm64 Python (Homebrew's `python3`). An Intel/Rosetta Python is slow and some
> dependencies have no wheels for it.

The first run downloads the Whisper `base` model (about 140 MB) once.

## Use it as an MCP server

Replace `/ABS/PATH/reelprompt` with where you cloned the repo. Add `OPENAI_API_KEY` only if you want `analyze_video` (or
put it in a `.env` file, see Configuration, and drop the `env` / `-e` parts below).

### Claude Code

```bash
claude mcp add reelprompt -e OPENAI_API_KEY=sk-... -- /ABS/PATH/reelprompt/.venv/bin/reelprompt-mcp
```

Then in a session: *"Here's a reel: https://www.instagram.com/reel/XXXX/ . Use reelprompt and build the UI it shows."*

### Codex (`~/.codex/config.toml`)

```toml
[mcp_servers.reelprompt]
command = "/ABS/PATH/reelprompt/.venv/bin/reelprompt-mcp"
env = { OPENAI_API_KEY = "sk-..." }
```

### Cursor (`~/.cursor/mcp.json`) and Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "reelprompt": {
      "command": "/ABS/PATH/reelprompt/.venv/bin/reelprompt-mcp",
      "env": { "OPENAI_API_KEY": "sk-..." }
    }
  }
}
```

Anything that speaks MCP over stdio works the same way.

## Use it as a CLI

```bash
.venv/bin/reelprompt "https://x.com/someone/status/123"          # full pack incl. PROMPT.md
.venv/bin/reelprompt "https://youtube.com/shorts/abc" --no-llm   # no API key needed
.venv/bin/reelprompt ~/Movies/screen-recording.mp4 --frames 12
```

It prints timings and the token cost of each run.

## Configuration (environment variables)

Instead of exporting variables, you can put them in a `.env` file: either `~/.reelprompt/.env` or a `.env` in the
repo folder (git-ignored). Variables already set in your environment win. Example:

```
OPENAI_API_KEY=sk-...
REELPROMPT_PROVIDER=openai
```

| Variable | Default | Meaning |
|---|---|---|
| `REELPROMPT_PROVIDER` | `openai` | `openai` or `anthropic` (for `PROMPT.md`) |
| `REELPROMPT_MODEL` | `gpt-6-luna` / `claude-haiku-4-5` | Analysis model. `gpt-5.6-luna` and any vision-capable model work |
| `REELPROMPT_EFFORT` | `low` | OpenAI `reasoning_effort` |
| `REELPROMPT_WHISPER_MODEL` | `base` | faster-whisper model: `tiny`, `base`, `small`, ... (bigger = slower, more accurate) |
| `REELPROMPT_COOKIES_BROWSER` | unset | `chrome`, `safari`, `firefox`: use that browser's login for gated Instagram posts |
| `REELPROMPT_HOME` | `~/.reelprompt` | Where packs are stored |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | unset | Credentials for the chosen provider |

## Limitations

- **Video posts only.** Still-image posts and photo carousels are not supported yet.
- **Platform downloads break sometimes.** Instagram and X change often. Update the downloader first:
  `.venv/bin/pip install -U yt-dlp`. Private or login-gated Instagram posts need `REELPROMPT_COOKIES_BROWSER`.
- **Videos with no speech** (music over a screen recording) have an empty transcript. The agent relies on the
  frames and caption, which is why frames are included.
- The analysis model only sees what the frames show. Anything not on screen or in the audio is marked as an
  assumption in `PROMPT.md`, so check the *Open questions* section.
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
