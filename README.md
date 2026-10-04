# video-brief

[![Stars](https://img.shields.io/github/stars/KabhiCodeKabhiFork/video-brief?style=flat&logo=github)](https://github.com/KabhiCodeKabhiFork/video-brief/stargazers)
[![Forks](https://img.shields.io/github/forks/KabhiCodeKabhiFork/video-brief?style=flat&logo=github)](https://github.com/KabhiCodeKabhiFork/video-brief/network/members)
[![Downloads](https://img.shields.io/github/downloads/KabhiCodeKabhiFork/video-brief/total?style=flat&logo=github)](https://github.com/KabhiCodeKabhiFork/video-brief/releases)

**Turn an Instagram reel, X video or YouTube Short into context, and a tailored system prompt, for whatever it is about.**

Paste a link and say *"do what's in this reel"*. video-brief downloads the video, pulls the caption, transcribes the
speech, picks key frames, classifies the topic and hands it all to your agent. Not limited to code.

It runs **locally** as an [MCP](https://modelcontextprotocol.io) server (plus a CLI). No hosted service, no GPU,
and **no API key needed**: your agent is the LLM.

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

## Features

- **`/reel <url>`**: classify the video, write a portable system prompt, then ask before starting the workflow.
- **`/reference-ui <url-or-path>`**: copy a UI from a video or your own screen recording into a `UI_REFERENCE.md`
  (tokens, screens, components, motion), then plan or build it in your project.
- **12 categories** (software, habits, health, scheduling, automation, learning, content, business, finance,
  creative, research, general), each with its own blueprint in [video_brief/playbooks.py](video_brief/playbooks.py).
- **Sources**: Instagram reels, X posts, YouTube Shorts/videos, or a local file (`.mp4 .mov .mkv .webm .m4v .avi .gif`).
- **Private**: video is deleted after processing; only frames, transcript and caption are kept in
  `~/.video-brief/packs/<platform>_<id>/`.

## Install

Needs Python 3.10+ and [ffmpeg](https://ffmpeg.org) (`brew install ffmpeg` / `apt install ffmpeg`).

**Easiest: paste this into Claude Code or Codex** and it sets everything up, no key:

```text
Set up video-brief on this machine, globally, so I can use it from any project.

1. Check that python3 (3.10+) and ffmpeg are installed. If ffmpeg is missing, install it
   (brew install ffmpeg / apt install ffmpeg) or tell me how.
2. Get the code into ~/video-brief. First ask me: "Fork video-brief to your GitHub account (public, helps the
   author see usage) or just download it?" Then:
   - Fork (only if `gh auth status` passes): cd ~ && gh repo fork KabhiCodeKabhiFork/video-brief --clone
   - Download: mkdir -p ~/video-brief && curl -L https://github.com/KabhiCodeKabhiFork/video-brief/releases/latest/download/video-brief.tar.gz | tar xz -C ~/video-brief
   - If ~/video-brief already exists, update it instead (git pull for a fork, re-run the download otherwise).
   cd into it, then run: python3 -m venv .venv && .venv/bin/pip install -e .
   (On Apple Silicon use a native arm64 Python.)
   When setup is done, ask me if I'd like to star the repo (gh api -X PUT /user/starred/KabhiCodeKabhiFork/video-brief).
   Only do it if I say yes.
3. Register the MCP server with whichever of these agents I have installed:
   - Claude Code: claude mcp add --scope user video-brief -- ~/video-brief/.venv/bin/video-brief-mcp
     (use the absolute path), then copy ~/video-brief/.claude/commands/reel.md and reference-ui.md to ~/.claude/commands/
   - Codex: append this to ~/.codex/config.toml if not already there (absolute path):
     [mcp_servers.video-brief]
     command = "/ABSOLUTE/PATH/TO/video-brief/.venv/bin/video-brief-mcp"
     then copy the folders ~/video-brief/codex/skills/reel and reference-ui to ~/.codex/skills/
   - Cursor / Claude Desktop: add the same command under "mcpServers" in their MCP config.
4. Verify: run ~/video-brief/.venv/bin/video-brief --help and confirm the MCP entry exists.
5. Tell me to restart the agent, and that I can then use /reel <url> or /reference-ui <url> in Claude Code, $reel / $reference-ui in Codex,
   or just paste a reel / X / YouTube Short link and ask it to build what it shows.

Do not set any API key. Do not edit anything else in my config files.
```

**By hand:**

```bash
git clone https://github.com/KabhiCodeKabhiFork/video-brief.git && cd video-brief
python3 -m venv .venv && .venv/bin/pip install -e .
```

The first run downloads a speech model (about 140 MB).

## Where it works

Replace `/ABS/PATH/video-brief` with your clone.

| Agent | Setup |
|---|---|
| **Claude Code** | `claude mcp add --scope user video-brief -- /ABS/PATH/video-brief/.venv/bin/video-brief-mcp`, then `cp .claude/commands/{reel,reference-ui}.md ~/.claude/commands/` for `/reel` and `/reference-ui` |
| **Codex** | In `~/.codex/config.toml`: `[mcp_servers.video-brief]` with `command = "/ABS/PATH/video-brief/.venv/bin/video-brief-mcp"`. Then `cp -r codex/skills/{reel,reference-ui} ~/.codex/skills/` for `$reel` and `$reference-ui` |
| **Cursor / Claude Desktop** | Add `{"mcpServers": {"video-brief": {"command": "/ABS/PATH/video-brief/.venv/bin/video-brief-mcp"}}}` to `~/.cursor/mcp.json` / `claude_desktop_config.json` |

Any MCP stdio client works. Some may not display returned images; caption and transcript still come through.

## Tools

| Tool | Returns | API key |
|---|---|---|
| `get_video_context(source, frames=0)` | Caption, timestamped transcript, key frames, category guess and blueprint | No |
| `get_frames_at(source, timestamps, width=0)` | Extra frames at moments you pick (`mm:ss`, up to 8) | No |
| `get_ui_reference(source, target="")` | 16 frames plus a brief for writing `UI_REFERENCE.md` | No |
| `get_playbook(category="")` | Blueprint for a category (empty lists them) | No |
| `analyze_video(source, frames=0, include_frames=true, category="")` | The above plus a finished `PROMPT.md` and `SYSTEM_PROMPT.md`, written by the server's own LLM call | Yes (OpenAI or Anthropic), only offered when set |

## CLI

```bash
.venv/bin/video-brief "https://youtube.com/shorts/abc" --no-llm            # pack with frames + transcript, no key
.venv/bin/video-brief "https://x.com/someone/status/123"                   # also writes PROMPT.md (needs a key)
.venv/bin/video-brief ~/Movies/ui-demo.mp4 --ui                            # UI reference mode
.venv/bin/video-brief "https://youtube.com/watch?v=abc" --at 1:15 3:40     # extra frames at those moments
.venv/bin/video-brief "https://x.com/someone/status/123" --category task_scheduling
```

## Optional: API key for `analyze_video`

Set `OPENAI_API_KEY` (default, model `gpt-6-luna`) or `VIDEO_BRIEF_PROVIDER=anthropic` with `ANTHROPIC_API_KEY`
(model `claude-haiku-4-5`; needs `pip install -e ".[anthropic]"`). Put them in `~/.video-brief/.env` or pass
`-e KEY=...` to `claude mcp add`. A Claude/ChatGPT subscription is not an API key. Restart your agent after changing keys.

| Variable | Default | Meaning |
|---|---|---|
| `VIDEO_BRIEF_PROVIDER` | `openai` | `openai` or `anthropic` |
| `VIDEO_BRIEF_MODEL` | provider default | Any vision-capable model |
| `VIDEO_BRIEF_WHISPER_MODEL` | `base` | `tiny`, `base`, `small`, ... |
| `VIDEO_BRIEF_COOKIES_BROWSER` | unset | `chrome`, `safari`, `firefox`, for login-gated Instagram posts |
| `VIDEO_BRIEF_HOME` | `~/.video-brief` | Packs and `.env` location |

## Limitations

- Video posts only; no image carousels.
- Platform downloads break sometimes: `.venv/bin/pip install -U yt-dlp`.
- No speech means an empty transcript; the agent relies on frames and caption.
- Frames cost context (auto: 8 to 16). Use `get_frames_at` / `--at` rather than raising the count.

## Responsible use

For personal use: understanding a video you can already watch. Respect platform terms and creators' rights; don't
redistribute content.

## Development

```bash
.venv/bin/pip install -e ".[dev]" && .venv/bin/python -m pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md). MIT licensed.
