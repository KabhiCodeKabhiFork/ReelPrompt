"""UI reference mode: turn a video of a UI into implementation context for a coding agent.

The keyless counterpart of the playbooks: no LLM is called here. `render_brief()` is the instruction
set the *calling agent* follows after looking at the frames: write a self-contained UI_REFERENCE.md
(tokens, screens, components, behavior, motion), then implement it in the user's project. Used by the
`get_ui_reference` MCP tool, the `--ui` CLI flag and the /reference-ui command.

Adapted from the MIT-licensed video-to-ui skill by mmohajer9.
"""

UI_FRAMES = 16  # UI work needs more detail than the automatic 8-16 frames

BRIEF = """\
# UI reference mode

The video shows a UI the user wants to copy. Your job: write a precise, self-contained UI reference an LLM can \
implement from without seeing the video, then (if the user wants) implement it in their project.

## 1. Look closely
The key frames are a sample. Call get_frames_at(source, [timestamps]) (up to 8 per call, as many calls as needed) \
for every distinct screen, every state change (hover, pressed, open/closed, loading, empty, error) and the \
start/middle/end of each animation. Do not guess at what you have not seen.

## 2. Read the target project first (if any)
If the user named files/folders or the working directory is a frontend project, read it before writing: stack, \
styling approach, component library, animation library, existing design tokens (CSS variables, Tailwind theme, \
theme objects), primitives (Button, Card, Modal...) and type/spacing/radius scales. Cite real names later.

## 3. Write UI_REFERENCE.md
Text-only and self-contained: never "see frame 3" as the only source of a fact. Mark each fact Seen (visible), \
Heard (only in transcript/caption) or Assumed (inferred). Use exact values; prefix guesses with ~ (e.g. ~#6E5BFF, \
~12px). No adjectives like "modern" or "clean", no brand analogies: observable signal only. Sections, in order:
1. Summary: what the UI is, platform (mobile/desktop/web), viewport shape, light or dark.
2. Design tokens: palette by role (background/surface/text/accent/status) with hex, type scale (sizes, weights, \
family if recognisable), spacing unit and multiples, radius scale, shadows/borders/blur, icon style and sizes.
3. Screen inventory: one entry per distinct screen, in order: name, role, layout (grid/stack/sidebar, alignment, \
max widths), every component with its copy verbatim, and the timestamps where it appears.
4. Components: each reusable piece (buttons by variant, cards, inputs, nav, rows, toasts, sheets...) with fills, \
strokes, radii, padding and every state shown.
5. Behavior and interactions: trigger -> result for each (tap/click/hover/scroll/type/timer): navigation, state \
changes, simulated or streaming data and its pacing.
6. Motion: each animation: what moves, direction, approximate duration, easing (spring/ease-out/linear), stagger, \
trigger. Say when you estimated from frame spacing.
7. Assumptions and unknowns: hover states, responsive behavior, empty/error states, exact fonts, assets to \
recreate or source. Flag paid fonts and costly effects (shaders, WebGL, Lottie).
8. Implementation notes (only if a project was read): map the design to existing tokens and primitives by name, \
list what is new. If the project has no token system, say so under a "Prerequisite" heading and recommend \
introducing tokens first rather than inventing parallel ones.
Never draw device chrome (status bars, notches, tab bars, browser frames) into components unless the project \
already has it; if the video shows a phone, put the frame at route/layout level only.
Save it as UI_REFERENCE.md in the pack folder (and next to the user's code if they are in a project), and show \
it in full.

## 4. Ask before touching anything
Offer: (a) implement it in the user's project, (b) build a standalone app, (c) keep just the reference, \
(d) refine it first. Do not edit project files before they choose.

(a) Implement in the project: write a change plan per file, using existing token/component names, each entry \
citing the timestamp/screen that justifies it, with concrete verbs (replace, tighten, add, swap), never "update". \
Flag mismatches instead of half-merging (a completely different palette family, screens the project lacks, a paid \
font). Wait for the user to say `apply`; only then edit, following the project's conventions and reusing its \
primitives, and finish with a file-by-file summary.

(b) Standalone app (./reference-ui-app/): Vite, React 18, TypeScript, Tailwind with the section-2 tokens under \
theme.extend, react-router-dom, Framer Motion. Exact pinned versions (no ^, no latest) and no other dependencies. \
One component per screen; real state and handlers for every interaction in section 5 (no static stubs); a mock \
data layer with realistic timing for simulated/streaming behavior; tokens by name, not raw hex; phone frame at \
layout level only; keep the video's real copy, invent nothing. Write files only; do not run npm install, tell the \
user to run `cd reference-ui-app && npm install && npm run dev`.

## 5. Report
What UI it was and how many screens/interactions you captured; what you produced and where; assumptions and \
open questions; where the pack was saved.
"""


def render_brief(target: str = "") -> str:
    """The agent-facing instructions, optionally with the user's target files/instructions appended."""
    extra = f"\n## User's target / extra instructions\n{target.strip()}\n" if target.strip() else ""
    return BRIEF + extra


def write_brief(pack) -> "Path":  # noqa: F821
    """Save the brief into the pack folder so any agent can be pointed at it (CLI users)."""
    path = pack.path / "UI_REFERENCE_BRIEF.md"
    path.write_text(render_brief())
    return path
