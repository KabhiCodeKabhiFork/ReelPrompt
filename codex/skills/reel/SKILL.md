---
name: reel
description: Run the full video-brief flow on a reel, X video, YouTube Short or local video file into a tailored system prompt, then start the workflow it describes. Use when the user gives a video URL or path and wants to act on it: build an app, follow a routine, set up a schedule or automation, or anything else it describes.
---

Run the entire video-brief flow for the video the user gave (the text after `$reel`).

The first token of the user's message is the video source (an Instagram reel, X post, YouTube Short/video URL, or an absolute path to a local `.mp4 .mov .mkv .webm .m4v .avi`). Anything after it is extra instructions for what to do with it.

If no source was given, ask for one and stop.

## 1. Get the context

Prefer the `video-brief` MCP server if its tools are available:
- `get_video_context(source)` returns the caption, timestamped transcript and key frames. This needs no API key. Use it by default.
- If the transcript refers to something on screen that the frames don't show, call `get_frames_at(source, [timestamps])` for those moments (CLI: `video-brief "<source>" --at 1:15`).
- Use `analyze_video` only if the user asked for a written spec / `PROMPT.md` and the tool is offered.

If the MCP tools are not available, fall back to the CLI. Use `video-brief` if it is on `PATH`, otherwise the `.venv/bin/video-brief` of your video-brief clone (check `$VIDEO_BRIEF_HOME`, or find it with `which video-brief-mcp` / `~/.codex/config.toml`):

```bash
video-brief "<source>" --no-llm
```

If neither works, tell the user to install video-brief and run the `[mcp_servers.video-brief]` entry from the README in `~/.codex/config.toml` (see the README), then stop.

The CLI saves a pack to `~/.video-brief/packs/<platform>_<id>/` containing `transcript.md`, `meta.json` and `frames/*.jpg`. Read `meta.json` and `transcript.md`, then view each frame by opening each image file.

If the download fails, try `pip install -U yt-dlp` in the video-brief venv once and retry. For login-gated Instagram posts, tell the user to set `VIDEO_BRIEF_COOKIES_BROWSER` (chrome, safari or firefox). Do not guess at content you could not fetch.

## 2. Understand and classify the video

Using the caption, transcript and frames, work out:
- What the video shows and claims, and what is actually visible on screen vs. only said in the audio
- What you are assuming because it is not shown. Keep this list explicit.

Then decide **what kind of thing this is**. It does not have to be software. `get_video_context` returns a keyword guess, the category list and a blueprint; use `get_playbook(category)` if you pick a different category. Categories: `software_build`, `personal_improvement`, `health_wellness`, `task_scheduling`, `workflow_automation`, `learning_skill`, `content_creation`, `business_growth`, `money_finance`, `creative_project`, `research_analysis`, `general`. Judge from the content, not just the guess. (If you used the CLI fallback, the guess is in `meta.json` as `suggested_category`, and the full blueprints are in `video_brief/playbooks.py` of the video-brief clone.)

Videos with no speech have an empty transcript. Rely on the frames and caption in that case.

## 3. Write the tailored system prompt

Following the blueprint for the chosen category, write a **portable system prompt**: second person, self-contained, with every needed fact from the video embedded as text (never "the video" or frame filenames), evidence marked apart from assumptions, and an instruction to ask clarifying questions first and wait for a go-ahead. Save it to `SYSTEM_PROMPT.md` in the pack folder, and show it to the user in full.

## 4. Ask before starting

Do **not** start the work yet. Ask the user directly to confirm, with the category you chose and these options: start the workflow now as that assistant (for `software_build`, start building in the current directory), adjust the plan or category first, or stop here with just the system prompt. Anything after the source in the user's message is extra instructions: apply them to the prompt and the plan.

When the user says go: follow the system prompt you wrote and the answers they gave. Ask its clarifying questions (batched), pick a sensible default and state it when a detail is unseen, and carry out the workflow. For software, build in the current directory; for anything else, produce the deliverable the blueprint names (a routine, schedule, SOP, plan, and so on) as files or in the reply, whichever fits.

## 5. Report

End with a short summary:
- What the video showed and the category you chose
- What was produced and where
- Assumptions and open questions
- Where the pack and `SYSTEM_PROMPT.md` were saved (`~/.video-brief/packs/...`)
