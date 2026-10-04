---
description: Run the full ReelPrompt flow on a reel / X video / YouTube Short / local video, then build what it shows
argument-hint: <video URL or absolute path> [extra instructions]
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, mcp__reelprompt__get_video_context, mcp__reelprompt__analyze_video
---

Run the entire ReelPrompt flow for: $ARGUMENTS

The first token of the arguments is the video source (an Instagram reel, X post, YouTube Short/video URL, or an absolute path to a local `.mp4 .mov .mkv .webm .m4v .avi`). Anything after it is extra instructions for what to build.

If no source was given, ask for one and stop.

## 1. Get the context

Prefer the `reelprompt` MCP server if its tools are available:
- `get_video_context(source, frames=8)` returns the caption, timestamped transcript and key frames. This needs no API key. Use it by default.
- Use `analyze_video` only if the user asked for a written spec / `PROMPT.md` and the tool is offered.

If the MCP tools are not available, fall back to the CLI. Use `reelprompt` if it is on `PATH`, otherwise the `.venv/bin/reelprompt` of your ReelPrompt clone (check `$REELPROMPT_HOME`, or find it with `which reelprompt-mcp` / `claude mcp get reelprompt`):

```bash
reelprompt "<source>" --no-llm
```

If neither works, tell the user to install ReelPrompt and run `claude mcp add reelprompt -- /ABS/PATH/reelprompt/.venv/bin/reelprompt-mcp` (see the README), then stop.

The CLI saves a pack to `~/.reelprompt/packs/<platform>_<id>/` containing `transcript.md`, `meta.json` and `frames/*.jpg`. Read `meta.json` and `transcript.md`, then view each frame with the Read tool.

If the download fails, try `pip install -U yt-dlp` in the ReelPrompt venv once and retry. For login-gated Instagram posts, tell the user to set `REELPROMPT_COOKIES_BROWSER` (chrome, safari or firefox). Do not guess at content you could not fetch.

## 2. Understand the video

Using the caption, transcript and frames, work out:
- What the video is (app, UI, workflow, tool, demo)
- What is actually visible on screen vs. only said in the audio
- What you are assuming because it is not shown. Keep this list explicit.

Videos with no speech have an empty transcript. Rely on the frames and caption in that case.

## 3. Build it

Build what the video shows in the current working directory, following any extra instructions in the arguments. If the video is not about something buildable (no UI, app or workflow), summarize it instead and ask what the user wants.

If an important detail is ambiguous or unseen, pick a sensible default, build, and list it under assumptions rather than stalling.

## 4. Report

End with a short summary:
- What the video showed
- What you built and where
- Assumptions and open questions
- Where the pack was saved (`~/.reelprompt/packs/...`)
