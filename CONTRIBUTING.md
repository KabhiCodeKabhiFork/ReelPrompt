# Contributing

Thanks for helping. This is a small project: keep changes focused and simple.

## Setup

```bash
git clone https://github.com/KabhiCodeKabhiFork/video-brief.git && cd video-brief
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

You need `ffmpeg` on your `PATH`. Tests are offline: they generate videos with ffmpeg, use a mock LLM
(`VIDEO_BRIEF_PROVIDER=mock`) and start the real MCP server over stdio.

## Layout

```
video_brief/
  fetch.py        URL (yt-dlp) or local file -> video on disk + metadata/caption
  media.py        ffmpeg: duration, audio, key-frame selection
  transcribe.py   faster-whisper
  analyze.py      LLM providers + the analysis prompt  <- most quality gains are here
  pipeline.py     extract() -> Pack, analyze(), run()
  cli.py          `video-brief`
  mcp_server.py   `video-brief-mcp` (tools: get_video_context, analyze_video)
tests/
```

## Good first contributions

- **Still-image posts and carousels** (Instagram, X): fall back to `gallery-dl`, send the images and caption to the
  model, skip transcription.
- **A new analysis provider** (Gemini, local Ollama vision model): add a function in `analyze.py` and a branch in
  `analyze()`.
- **Better key-frame selection** (`media.pick_frames`): smarter scene detection, or frames at moments where the
  speaker says "here" / "look" / "click".
- **Improve the analysis prompt** and add example outputs to the README.
- **A hosted/remote MCP transport** (streamable HTTP).

## Guidelines

- Platform downloads are the most fragile part. If you fix a download problem, say which URL type it was.
- Never print to stdout from the library code: stdout is the MCP stdio channel. Log to stderr.
- Add a test for new behaviour. Keep tests offline.
- Don't commit API keys or downloaded videos.

## Reporting a bug

Open an issue with: the URL type (reel / X / Short / file, no private links), your OS and Python version,
`pip list | grep -E "yt-dlp|faster-whisper|mcp"`, and the error text.
