"""LLM step: transcript + caption + frames -> PROMPT.md. Providers: openai (default), anthropic, mock."""
import base64
import json
import os

ANALYSIS_PROMPT = """\
You are preparing a hand-off for an AI coding agent (Claude Code, Codex, Cursor). The user saw a short \
social-media video and wants to build, or learn from, whatever it shows. You get the video's transcript \
(with timestamps), its metadata and caption, and key frames (each labelled with its filename).

Write the full contents of PROMPT.md. It will be pasted into a coding agent that cannot see the video, \
so it must stand on its own. Structure it exactly like this:

# <short title>

## What this video is
One of: UI component/effect | full app idea | code tutorial | workflow/automation | design inspiration | other. \
Then 2-3 sentences on what the video shows and what the creator is claiming.

## Build brief
A concrete spec for the agent: goal, MVP feature list, UI/interaction details, data/inputs/outputs, and a \
suggested tech stack. Tie visual details to frames by filename, e.g. "(see frames/03_00m12s.jpg)". \
Scope to a realistic MVP; do not build the whole startup the video implies.

## Seen vs. assumed
Two lists. "Shown or said in the video" (only things evidenced by transcript, caption or frames; include any \
text or code you can read on screen verbatim) and "Assumed / filled in by me" (anything you inferred).

## Open questions
Questions the agent should ask the user before building rather than guessing.

## Starter prompt
A ready-to-paste prompt (in a blockquote) the user can give the coding agent, referencing the frames folder.

Rules: be specific, no marketing fluff, do not invent features. If the transcript is empty or the video has no \
speech, rely on on-screen text and the caption, and say so. Output only the markdown for PROMPT.md."""

# $ per 1M tokens (input, output). Only used for the cost printout; unknown models show $0.
PRICES = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-5.6-luna": (1.0, 6.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}


def provider() -> str:
    p = os.environ.get("REELPROMPT_PROVIDER", "openai").strip().lower()
    if p not in ("openai", "anthropic", "mock"):
        raise ValueError(f"Unknown REELPROMPT_PROVIDER {p!r} (use 'openai' or 'anthropic')")
    return p


def is_configured() -> bool:
    """True if the chosen provider has credentials (so analyze_video can be offered)."""
    try:
        prov = provider()
    except ValueError:
        return False
    return prov == "mock" or bool(os.environ.get({"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}[prov]))


def model() -> str:
    default = {"openai": "gpt-6-luna", "anthropic": "claude-haiku-4-5", "mock": "mock"}[provider()]
    return os.environ.get("REELPROMPT_MODEL", default)


def estimate_cost(tok_in: int, tok_out: int) -> float:
    pin, pout = PRICES.get(model(), (0.0, 0.0))
    return (tok_in * pin + tok_out * pout) / 1e6


def analyze(meta: dict, transcript: str, frames):
    """frames: [(filename, Path)]. Returns (markdown, input_tokens, output_tokens)."""
    prompt = (f"Metadata and caption:\n{json.dumps(meta, indent=2, ensure_ascii=False)}\n\n"
              f"Transcript:\n{transcript or '(no speech detected)'}\n\n{ANALYSIS_PROMPT}")
    b64 = [(name, base64.standard_b64encode(path.read_bytes()).decode()) for name, path in frames]
    prov = provider()
    if prov == "mock":  # offline stand-in used by the test-suite
        return f"# Mock analysis\n\nframes: {[n for n, _ in b64]}\n", 0, 0
    if prov == "openai":
        return _openai(prompt, b64)
    if prov == "anthropic":
        return _anthropic(prompt, b64)
    raise AssertionError(prov)  # provider() already validated


def _openai(prompt, b64):
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set (or use REELPROMPT_PROVIDER=anthropic).")
    from openai import OpenAI

    content = []
    for name, data in b64:
        content.append({"type": "text", "text": f"Frame: frames/{name}"})
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{data}", "detail": "auto"}})
    content.append({"type": "text", "text": prompt})
    resp = OpenAI().chat.completions.create(
        model=model(),
        max_completion_tokens=8000,  # reasoning tokens count against this
        reasoning_effort=os.environ.get("REELPROMPT_EFFORT", "low"),
        messages=[{"role": "user", "content": content}],
    )
    return resp.choices[0].message.content or "", resp.usage.prompt_tokens, resp.usage.completion_tokens


def _anthropic(prompt, b64):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set (or use REELPROMPT_PROVIDER=openai).")
    import anthropic

    content = []
    for name, data in b64:
        content.append({"type": "text", "text": f"Frame: frames/{name}"})
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    content.append({"type": "text", "text": prompt})
    resp = anthropic.Anthropic().messages.create(
        model=model(), max_tokens=4000, messages=[{"role": "user", "content": content}])
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, resp.usage.input_tokens, resp.usage.output_tokens
