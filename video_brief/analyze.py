"""LLM step: classify the video, then transcript + caption + frames -> PROMPT.md with a tailored system prompt.
Providers: openai (default), anthropic, mock."""
import base64
import json
import os
import re

from . import playbooks

CLASSIFY_PROMPT = """\
Classify what this short video is about, so the right kind of assistant can be set up for it. It may be \
about anything: building software, a habit or self-improvement system, a scheduling method, an automation \
workflow, fitness, finance, art, a business idea, and so on. Pick exactly one category id.

Categories:
{catalog}

Keyword heuristic suggests: {suggestion} (a weak hint; override it when the content says otherwise).

Reply with only JSON: {{"category": "<id>", "reason": "<one short sentence>"}}"""

ANALYSIS_PROMPT = """\
You are preparing a hand-off from a short social-media video. The user saw it and wants to act on what it \
shows, which may be anything (an app to build, a routine to follow, a workflow to run, a plan to adopt). \
You get the video's transcript (with timestamps), its metadata and caption, and key frames (each labelled \
with its filename). The video has been classified; tailor everything to that category.

{blueprint}

Write the full contents of PROMPT.md, structured exactly like this:

# <short title>

## What this video is
The category name, then 2-3 sentences on what the video shows and what the creator is claiming.

## Core content
The substance a person would need to act on it: steps, rules, numbers, tools, UI details, claims. Quote on-screen \
text or code verbatim. Tie visual details to frames by filename, e.g. "(see frames/03_00m12s.jpg)".

## Seen vs. assumed
Two lists. "Shown or said in the video" (only what the transcript, caption or frames evidence) and \
"Assumed / filled in by me" (anything inferred).

## Open questions
What must be asked of the user rather than guessed.

## System prompt
The tailored system prompt, wrapped in <system_prompt> and </system_prompt> tags, following the blueprint above. \
The text between the tags is extracted and used on its own, so it must not depend on anything outside it.

## First message
One or two sentences the user can send as their first message after pasting the system prompt.

Rules: be specific, no marketing fluff, do not invent details. If the transcript is empty or the video has no \
speech, rely on on-screen text and the caption, and say so. Output only the markdown for PROMPT.md."""

_SYSTEM_PROMPT_RE = re.compile(r"<system_prompt>\s*(.*?)\s*</system_prompt>", re.DOTALL)


def extract_system_prompt(markdown: str) -> str | None:
    """Pull the portable system prompt out of PROMPT.md (None if the model left the tags out)."""
    m = _SYSTEM_PROMPT_RE.search(markdown or "")
    return m.group(1) if m and m.group(1) else None


# $ per 1M tokens (input, output). Only used for the cost printout; unknown models show $0.
PRICES = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-5.6-luna": (1.0, 6.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}


def provider() -> str:
    p = os.environ.get("VIDEO_BRIEF_PROVIDER", "openai").strip().lower()
    if p not in ("openai", "anthropic", "mock"):
        raise ValueError(f"Unknown VIDEO_BRIEF_PROVIDER {p!r} (use 'openai' or 'anthropic')")
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
    return os.environ.get("VIDEO_BRIEF_MODEL", default)


def estimate_cost(tok_in: int, tok_out: int) -> float:
    pin, pout = PRICES.get(model(), (0.0, 0.0))
    return (tok_in * pin + tok_out * pout) / 1e6


def classify(meta: dict, transcript: str, hint: dict | None = None) -> tuple:
    """Text-only LLM call (cheap, no frames) picking a playbook. Returns (category_id, in_tokens, out_tokens).
    Falls back to the keyword heuristic if the reply cannot be parsed."""
    hint = hint or playbooks.classify(meta, transcript)
    if provider() == "mock":
        return hint["category"], 0, 0
    prompt = (f"Title: {meta.get('title')}\nCaption: {(meta.get('description') or '')[:1500]}\n"
              f"Transcript (start):\n{(transcript or '(no speech detected)')[:3000]}\n\n"
              + CLASSIFY_PROMPT.format(catalog=playbooks.catalog(), suggestion=hint["category"]))
    text, tok_in, tok_out = _complete(prompt, [], max_out=1500)
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    try:
        category = json.loads(m.group(0)).get("category") if m else None
    except (json.JSONDecodeError, AttributeError):
        category = None
    return (category if playbooks.is_known(category) else hint["category"]), tok_in, tok_out


def analyze(meta: dict, transcript: str, frames, category: str | None = None) -> tuple:
    """frames: [(filename, Path)]. Classifies (unless `category` is forced), then writes PROMPT.md.
    Returns (markdown, input_tokens, output_tokens, category_id)."""
    tok_in = tok_out = 0
    if playbooks.is_known(category):
        category = playbooks.get(category).id
    else:
        category, tok_in, tok_out = classify(meta, transcript)
    prompt = (f"Metadata and caption:\n{json.dumps(meta, indent=2, ensure_ascii=False)}\n\n"
              f"Transcript:\n{transcript or '(no speech detected)'}\n\n"
              + ANALYSIS_PROMPT.format(blueprint=playbooks.render_blueprint(category)))
    b64 = [(name, base64.standard_b64encode(path.read_bytes()).decode()) for name, path in frames]
    if provider() == "mock":  # offline stand-in used by the test-suite
        md = (f"# Mock analysis\n\ncategory: {category}\nframes: {[n for n, _ in b64]}\n\n"
              f"<system_prompt>\nMock system prompt for {category}.\n</system_prompt>\n")
        return md, tok_in, tok_out, category
    md, i, o = _complete(prompt, b64)
    return md, tok_in + i, tok_out + o, category


def _complete(prompt, b64, max_out=None):
    prov = provider()
    if prov == "openai":
        return _openai(prompt, b64, max_out or 10000)
    if prov == "anthropic":
        return _anthropic(prompt, b64, max_out or 6000)
    raise AssertionError(prov)  # provider() already validated


def _openai(prompt, b64, max_out):
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set (or use VIDEO_BRIEF_PROVIDER=anthropic).")
    from openai import OpenAI

    content = []
    for name, data in b64:
        content.append({"type": "text", "text": f"Frame: frames/{name}"})
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{data}", "detail": "auto"}})
    content.append({"type": "text", "text": prompt})
    resp = OpenAI().chat.completions.create(
        model=model(),
        max_completion_tokens=max_out,  # reasoning tokens count against this
        reasoning_effort=os.environ.get("VIDEO_BRIEF_EFFORT", "low"),
        messages=[{"role": "user", "content": content}],
    )
    return resp.choices[0].message.content or "", resp.usage.prompt_tokens, resp.usage.completion_tokens


def _anthropic(prompt, b64, max_out):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set (or use VIDEO_BRIEF_PROVIDER=openai).")
    import anthropic

    content = []
    for name, data in b64:
        content.append({"type": "text", "text": f"Frame: frames/{name}"})
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    content.append({"type": "text", "text": prompt})
    resp = anthropic.Anthropic().messages.create(
        model=model(), max_tokens=max_out, messages=[{"role": "user", "content": content}])
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, resp.usage.input_tokens, resp.usage.output_tokens
