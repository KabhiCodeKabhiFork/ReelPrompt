"""Classification layer: what is this video *about*, and what kind of system prompt should it become?

Each Playbook describes one kind of video (an app, a habit system, a scheduling method, an automation...)
and the blueprint for the portable system prompt that video should be turned into. Two consumers:

  * keyless path (MCP / slash command): the calling agent is the LLM. It gets `classify()`'s suggestion
    plus `render_blueprint()` and does the classifying/writing itself.
  * key path (CLI / analyze_video): analyze.py asks an LLM to pick a category, then to write the prompt
    from the chosen blueprint.
"""
import re
from dataclasses import dataclass, field

GENERAL = "general"

# Rules every emitted system prompt follows, whatever the category.
PORTABLE_RULES = """\
The system prompt must be portable: it will be pasted into any assistant (ChatGPT, Claude, Gemini, a coding \
agent, a custom GPT) that cannot see the video or any files. So:
- Write it in the second person ("You are...", "Your job is...") as one self-contained block.
- Embed every fact from the video the assistant needs as plain text: names, steps, numbers, tools, claims, \
text read off the screen. Never refer to "the video", frame filenames, or attachments.
- Mark what is evidenced by the video versus what you inferred, so the assistant does not treat guesses as fact.
- Tell the assistant to ask the user its clarifying questions first (batched, at most 5), then restate the plan \
and wait for a go-ahead before producing the full deliverable.
- State the tone, the output format, and what the assistant must not do (no invented facts, no filler).
- Keep it tight: as long as it needs to be to work, no longer."""


@dataclass(frozen=True)
class Playbook:
    id: str
    name: str
    about: str            # one line: what videos belong here (used in the classifier prompt)
    role: str             # who the assistant becomes
    sections: tuple       # what the emitted system prompt must contain, in order
    questions: tuple      # clarifying questions this kind of system usually needs answered
    deliverable: str      # what a successful session produces
    signals: tuple = field(default=(), repr=False)  # lowercase stems for the keyless heuristic


PLAYBOOKS = (
    Playbook(
        id="software_build",
        name="Software / app / UI build",
        about="an app, website, UI component or effect, tool, script, game, or a coding tutorial to be built",
        role="a senior engineer and product-minded pair programmer building the thing the video shows",
        sections=(
            "Goal and the MVP feature list (scoped to something realistic, not the whole startup)",
            "UI/interaction details, data model, inputs and outputs, as specifically as the video allows",
            "Suggested tech stack with a one-line reason, and an instruction to follow the user's existing stack if any",
            "Any code, text or numbers read off the screen, reproduced verbatim",
            "Working rules: plan before coding, build in small verifiable steps, run it, report what was tested",
        ),
        questions=("Which stack/platform should this use, or is there an existing codebase?",
                   "What is the smallest version you would consider done?",
                   "Any design references, brand colours or constraints?"),
        deliverable="working code in the user's project, plus a short list of assumptions made",
        signals=("app", "apps", "ui", "ux", "website", "frontend", "backend", "react", "python", "javascript",
                 "typescript", "api", "code", "coding", "program", "develop", "software", "github",
                 "component", "animation", "css", "database", "saas", "chrome extension", "vibe cod",
                 "cursor", "claude code", "open source", "deploy", "build this", "prompt"),
    ),
    Playbook(
        id="personal_improvement",
        name="Personal improvement system",
        about="habits, routines, discipline, mindset, productivity-of-self, self-development, morning/night routines",
        role="a pragmatic personal coach who turns a self-improvement idea into a system the user will actually follow",
        sections=(
            "The core principle(s) from the video, stated plainly, with any specific numbers, rules or rituals",
            "How to translate them into a daily/weekly routine sized to the user's real life and energy",
            "A tracking method (what to log, how often, what counts as a miss) and a weekly review ritual",
            "A plan for relapse: what to do after a bad day so one miss never becomes a collapse",
            "Coaching style: direct, encouraging, no shaming, no pseudo-science beyond what the video evidenced",
        ),
        questions=("What do you want to change, and why does it matter to you now?",
                   "What does a normal weekday look like (wake time, work, commitments)?",
                   "What have you tried before and where did it break down?",
                   "How much time and willpower can you realistically spend per day?"),
        deliverable="a personalised routine, a tracker format, and a weekly check-in script",
        signals=("habit", "routine", "discipline", "mindset", "motivation", "productiv", "self improvement",
                 "self-improvement", "morning", "journal", "meditat", "procrastinat", "focus", "confidence",
                 "atomic habits", "dopamine", "willpower", "goal", "level up", "glow up", "consisten"),
    ),
    Playbook(
        id="health_wellness",
        name="Health, fitness & food system",
        about="workouts, training splits, nutrition, meal prep, recipes, sleep, recovery, wellbeing",
        role="a careful fitness-and-nutrition planning assistant (not a doctor) who adapts the video's method to the user",
        sections=(
            "The method from the video: exercises, sets/reps, ingredients, quantities, timings, exactly as given",
            "How to adapt it to the user's level, equipment, dietary needs, schedule and injuries",
            "A progression or weekly plan, and how to track results",
            "Safety rules: flag anything risky or medically sensitive, recommend a professional where appropriate, "
            "and never present the video's claims as medical fact",
        ),
        questions=("What is your goal, current level, and any injuries or medical conditions?",
                   "What equipment, kitchen and time do you have?",
                   "Any allergies, dietary restrictions or foods you dislike?"),
        deliverable="a tailored plan (training or meals) with a progression and a tracking format",
        signals=("workout", "exercise", "gym", "fitness", "protein", "calorie", "diet", "recipe", "meal",
                 "nutrition", "sleep", "stretch", "mobility", "cardio", "weight loss", "muscle", "yoga",
                 "ingredient", "cook", "bake", "skincare", "hydrat", "supplement"),
    ),
    Playbook(
        id="task_scheduling",
        name="Task & schedule planning system",
        about="to-do systems, calendars, time blocking, planners, project/task management, prioritisation frameworks",
        role="a planning assistant who runs the scheduling method from the video on the user's real tasks and calendar",
        sections=(
            "The scheduling/prioritisation method, step by step, with its rules (e.g. buckets, time boxes, limits)",
            "Intake: what the assistant collects from the user (tasks, deadlines, fixed commitments, energy pattern)",
            "How it turns that into a concrete plan: ordering logic, time blocks, buffers, what gets dropped",
            "Output format (a dated table or list the user can copy into their calendar/tool) and a re-plan routine",
            "Rules: never overbook, always leave buffer, flag conflicts instead of silently resolving them",
        ),
        questions=("What are your fixed commitments this week, and what tools do you use (calendar, Notion, paper)?",
                   "List your open tasks with deadlines and rough effort.",
                   "When in the day are you at your best for deep work?"),
        deliverable="a concrete schedule for the period, plus the rules to re-plan when things slip",
        signals=("schedul", "calendar", "time block", "to-do", "todo", "planner", "planning", "prioriti",
                 "deadline", "task", "eisenhower", "pomodoro", "notion", "kanban", "gtd", "agenda",
                 "project manag", "weekly review", "time manag", "organi"),
    ),
    Playbook(
        id="workflow_automation",
        name="Workflow / automation / process",
        about="no-code or AI automations, multi-step business processes, SOPs, agent pipelines, tool-to-tool workflows",
        role="a workflow architect who designs, documents and (where possible) runs the process the video describes",
        sections=(
            "The workflow as an ordered list: trigger, each step, tools/apps used, data passed between steps, outputs",
            "Decision points, error cases and human-approval checkpoints",
            "How the assistant operates it: what it does itself versus what it hands to the user or another tool",
            "A reusable SOP the user can hand to someone else, and how to measure that it works",
        ),
        questions=("What triggers this workflow and how often does it run?",
                   "Which tools and accounts do you already use?",
                   "What must a human approve before anything is sent or changed?",
                   "What does success look like (time saved, error rate)?"),
        deliverable="a documented workflow (and its configuration or script if buildable) with failure handling",
        signals=("automat", "workflow", "zapier", "n8n", "make.com", "pipeline", "integrat", "webhook",
                 "agent", "no-code", "no code", "sop", "process", "trigger", "chatgpt", "gpt", "ai tool",
                 "email sequence", "scrape", "airtable", "google sheets", "streamline", "delegate"),
    ),
    Playbook(
        id="learning_skill",
        name="Learning & skill-building system",
        about="learning methods, study systems, language learning, a course or tutorial in a non-code skill, exam prep",
        role="a tutor and learning designer who teaches the video's subject and builds a study plan around the user",
        sections=(
            "The key concepts, steps or techniques from the video, accurately and in teachable order",
            "A diagnostic: how to find the user's current level before teaching",
            "A learning plan with spaced practice, retrieval questions and projects, not just explanation",
            "Teaching style: explain simply, check understanding, correct gently, admit uncertainty",
        ),
        questions=("What is your current level and your target?",
                   "How much time per week, and by when do you need it?",
                   "How do you learn best (reading, examples, drills, projects)?"),
        deliverable="a leveled study plan, practice material, and periodic quizzes",
        signals=("learn", "study", "tutorial", "course", "lesson", "teach", "language", "memoriz", "flashcard",
                 "exam", "skill", "beginner", "guitar", "piano", "math", "grammar", "vocab", "how to",
                 "explained", "masterclass", "practice"),
    ),
    Playbook(
        id="content_creation",
        name="Content creation & audience growth",
        about="making or growing social/YouTube/newsletter/blog content, posting strategies, hooks, editing styles",
        role="a content strategist and editor who reproduces the video's content approach for the user's own channel",
        sections=(
            "The content formula from the video: format, hook structure, pacing, posting cadence, platform tactics",
            "The user's niche, voice and audience, and how the formula is adapted to them",
            "A content pipeline: idea bank, script/outline template, production checklist, publishing and review loop",
            "Quality rules: original angles, no copying a creator's material, no engagement-bait claims the user can't back",
        ),
        questions=("What is your niche, platform and audience?",
                   "How much time per week can you give to making content?",
                   "Do you show your face, use voiceover, or text only?"),
        deliverable="a repeatable content system with ready-to-use templates and the first batch of ideas or scripts",
        signals=("content", "creator", "followers", "viral", "hook", "youtube", "tiktok", "instagram", "reels",
                 "algorithm", "engagement", "newsletter", "blog", "thumbnail", "script", "edit", "caption",
                 "audience", "subscribers", "posting", "personal brand", "storytelling"),
    ),
    Playbook(
        id="business_growth",
        name="Business, marketing & side-hustle plan",
        about="starting or growing a business, sales, marketing funnels, ecommerce, freelancing, pricing, startup ideas",
        role="a business operator and strategist who stress-tests the video's idea and turns it into an execution plan",
        sections=(
            "The business idea or tactic from the video, with every concrete number, price and claim noted",
            "A sceptical read: which claims are unevidenced, survivorship-biased or illegal/against platform rules",
            "Validation plan: cheapest test of demand, target customer, offer, pricing",
            "A 30-day execution plan with weekly milestones and the metrics that decide go/no-go",
        ),
        questions=("What are your skills, budget and hours per week?",
                   "Who is the customer and how will you reach them first?",
                   "What outcome counts as success in 90 days?"),
        deliverable="a validated offer, a 30-day plan and the metrics to judge it",
        signals=("business", "startup", "customer", "revenue", "profit", "marketing", "sales", "ecommerce",
                 "dropship", "shopify", "freelanc", "client", "agency", "pricing", "funnel", "ads", "brand",
                 "side hustle", "passive income", "entrepreneur", "saas", "launch", "mrr"),
    ),
    Playbook(
        id="money_finance",
        name="Personal finance system",
        about="budgeting, saving, investing, debt payoff, taxes, money habits",
        role="a personal-finance planning assistant (not a licensed adviser) who applies the video's method to the user's numbers",
        sections=(
            "The method or rule from the video, with its figures and assumptions made explicit",
            "Intake: income, fixed costs, debts, savings, goals, time horizon, country (rules differ by jurisdiction)",
            "How to apply the method to those numbers, with arithmetic shown",
            "Guardrails: not individualised financial advice, flag risk and hype, note where a professional is warranted",
        ),
        questions=("What are your monthly income, fixed expenses, debts and savings?",
                   "What is the goal and the time horizon?",
                   "Which country are you in (taxes and accounts differ)?"),
        deliverable="a budget or allocation plan with the arithmetic shown, and a monthly review routine",
        signals=("budget", "invest", "stock", "etf", "savings", "debt", "credit", "mortgage", "tax", "401k",
                 "retire", "index fund", "crypto", "bitcoin", "net worth", "interest", "income", "expense",
                 "financial", "wealth", "money"),
    ),
    Playbook(
        id="creative_project",
        name="Creative / design / DIY project",
        about="art, graphic or interior design, music, writing fiction, photography, crafts, DIY and making things",
        role="a creative collaborator and craftsperson who helps the user make their own version of what the video shows",
        sections=(
            "The technique, style or project from the video: materials, steps, settings, references, as specifically as possible",
            "The user's own concept, constraints (budget, tools, space, skill) and how the technique is adapted to them",
            "A stepwise making plan with checkpoints and a way to give and take feedback",
            "Creative stance: offer options, explain tradeoffs, never imitate a named artist's work too closely",
        ),
        questions=("What do you want to make, and who or what is it for?",
                   "What tools, materials and skill level do you have?",
                   "Any style references you like?"),
        deliverable="a project plan, material/tool list and step-by-step guidance with feedback rounds",
        signals=("design", "art", "draw", "paint", "sketch", "illustrat", "photograph", "music", "song",
                 "beat", "diy", "craft", "woodwork", "sew", "knit", "interior", "decor", "fashion",
                 "poem", "novel", "story", "typography", "figma", "blender", "3d"),
    ),
    Playbook(
        id="research_analysis",
        name="Research, analysis & decision support",
        about="explainers, news, science, comparisons, product reviews, 'should I...' decisions, claims worth verifying",
        role="a careful analyst who checks the video's claims, fills in the missing context and helps the user decide or understand",
        sections=(
            "The claims and facts the video makes, listed individually with who said them and any sources named",
            "How to evaluate each: what would confirm or refute it, what is opinion, what is missing",
            "The user's actual question or decision and the criteria that matter to them",
            "Output: a structured brief with confidence levels, and a clear recommendation when one is asked for",
            "Rules: separate evidence from speculation, state uncertainty, never invent citations",
        ),
        questions=("What do you want to understand or decide?",
                   "How deep should this go (quick summary or thorough brief)?",
                   "Which criteria matter most to you?"),
        deliverable="a sourced-or-flagged brief with confidence levels and a recommendation",
        signals=("research", "study shows", "scientist", "evidence", "explain", "history", "news", "review",
                 "compare", "versus", " vs ", "analysis", "statistic", "data shows", "myth", "fact",
                 "debunk", "theory", "report", "should i", "worth it", "pros and cons"),
    ),
    Playbook(
        id=GENERAL,
        name="General (anything else)",
        about="anything that fits none of the above, or is a mix",
        role="a capable, careful assistant who works out what the user wants to do with this video's subject and helps them do it",
        sections=(
            "A faithful summary of what the video shows and claims, with concrete details preserved",
            "The most plausible things a viewer would want to do with it (offer 2-3), and which you assume",
            "Working rules: ask what the user wants first, then plan, then deliver; state assumptions explicitly",
        ),
        questions=("What did you want to do with this: understand it, copy it, or apply it to your own situation?",
                   "What outcome would make this worthwhile?"),
        deliverable="whatever the user chooses after the first clarifying round",
        signals=(),
    ),
)

_BY_ID = {p.id: p for p in PLAYBOOKS}
def _pattern(sig: str):
    """Stems match as word prefixes ('automat' -> automation); 3-char-or-less signals match whole words."""
    if sig.startswith(" "):
        return re.compile(re.escape(sig))
    sig = sig.strip()
    return re.compile(r"\b" + re.escape(sig) + (r"\b" if len(sig) <= 3 else ""))


_COMPILED = {p.id: [_pattern(s) for s in p.signals] for p in PLAYBOOKS}


def ids() -> list:
    return [p.id for p in PLAYBOOKS]


def get(category: str | None) -> Playbook:
    """Look up a playbook by id (case/space tolerant). Unknown or empty -> general."""
    key = re.sub(r"[\s-]+", "_", (category or "").strip().lower())
    return _BY_ID.get(key, _BY_ID[GENERAL])


def is_known(category: str | None) -> bool:
    return re.sub(r"[\s-]+", "_", (category or "").strip().lower()) in _BY_ID


def classify(meta: dict, transcript: str = "") -> dict:
    """Free, offline keyword suggestion. Title/caption count 3x because creators put the topic there.

    Returns {"category", "confidence" (high|medium|low), "ranked": [(id, score), ...]}. This is only a
    suggestion: the LLM (or calling agent) makes the final call and can override it.
    """
    head = f"{meta.get('title') or ''} {meta.get('description') or ''}".lower()
    body = (transcript or "").lower()
    scores = {}
    for pid, pats in _COMPILED.items():
        total = 0
        for pat in pats:
            total += 3 * min(len(pat.findall(head)), 2) + min(len(pat.findall(body)), 3)
        if total:
            scores[pid] = total
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < 4:
        return {"category": GENERAL, "confidence": "low", "ranked": ranked[:3]}
    top = ranked[0][1]
    runner = ranked[1][1] if len(ranked) > 1 else 0
    confidence = "high" if top >= 10 and top >= 2 * runner else "medium" if top > runner else "low"
    return {"category": ranked[0][0], "confidence": confidence, "ranked": ranked[:3]}


def catalog() -> str:
    """One line per category, for classifier prompts and the agent-facing menu."""
    return "\n".join(f"- {p.id}: {p.about}" for p in PLAYBOOKS)


def render_blueprint(category: str | None) -> str:
    """The category-specific instructions for writing the portable system prompt."""
    p = get(category)
    sections = "\n".join(f"  {i}. {s}" for i, s in enumerate(p.sections, 1))
    questions = "\n".join(f"  - {q}" for q in p.questions)
    return (
        f"Category: {p.id} ({p.name})\n"
        f"The assistant in the system prompt is: {p.role}.\n"
        f"The system prompt must contain, in this order:\n{sections}\n"
        f"Clarifying questions this assistant should ask first (adapt to what the video already answers):\n{questions}\n"
        f"A successful session produces: {p.deliverable}.\n\n{PORTABLE_RULES}"
    )
