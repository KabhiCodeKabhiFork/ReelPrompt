---
description: Copy a UI from a reel / X video / YouTube Short / screen recording into implementation context for your coding agent, then build it in your own project
argument-hint: <video URL or absolute path> [target files or folders, extra instructions]
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, mcp__reelprompt__get_ui_reference, mcp__reelprompt__get_frames_at
---

Copy the UI shown in a video into implementation context, then build it in the user's project. Input: $ARGUMENTS

The first token is the video source (an Instagram reel, X post, YouTube Short/video URL, or a path to a local file such as **your own screen recording**: `.mp4 .mov .mkv .webm .m4v .avi .gif`). Quoted paths, `~`, drag-and-drop escapes and macOS "Screen Recording ... at 10.12.33 AM" names all work. If the path is relative, make it absolute (against the user's working directory) before passing it on, because the server runs elsewhere. Anything after it is the target (files/folders in the user's project to apply the UI to) and/or extra instructions.

If no source was given, ask for one and stop.

## 1. Get the footage and the brief

A screen recording has no caption and usually no audio, so everything comes from the frames: expect to call `get_frames_at(..., width=1280)` often. Prefer the `reelprompt` MCP server: call `get_ui_reference(source, target)` with the rest of the arguments as `target`. It returns the caption, transcript, 16 key frames and a **brief** that is the full procedure (look closer with `get_frames_at`, read the target project, write `UI_REFERENCE.md`, ask what to do, implement). The brief is the source of truth: follow it exactly.

If the MCP tools are not available, use the CLI: `reelprompt "<source>" --ui` (the `reelprompt` on `PATH`, otherwise the `.venv/bin/reelprompt` of your ReelPrompt clone; check `$REELPROMPT_HOME` or `which reelprompt-mcp`). It saves a pack to `~/.reelprompt/packs/<platform>_<id>/` with `UI_REFERENCE_BRIEF.md`, `transcript.md`, `meta.json` and `frames/*.jpg`. Read the brief, then view every frame with the Read tool; extra frames come from `reelprompt "<source>" --ui --at 0:12 0:13`.

If neither works, tell the user to install ReelPrompt and run `claude mcp add reelprompt -- /ABS/PATH/reelprompt/.venv/bin/reelprompt-mcp` (see the README), then stop. If a download fails, try `pip install -U yt-dlp` in the ReelPrompt venv once; for login-gated Instagram posts, tell the user to set `REELPROMPT_COOKIES_BROWSER`. Never guess at content you could not fetch.

## 2. Follow the brief

Write `UI_REFERENCE.md` into the pack folder (and next to the user's code when they are in a project), show it in full, then Use the AskUserQuestion tool to offer: implement it in their project, build a standalone app, keep just the reference, or refine it first. **Do not edit project files before they choose, and apply a project change plan only after they say `apply`.**

## 3. Report

Finish with the short summary the brief asks for, including the pack location (`~/.reelprompt/packs/...`).
