import pytest

from reelprompt import analyze, playbooks


@pytest.mark.parametrize("title,caption,transcript,expected", [
    ("Build this", "React app with a glassmorphism UI component, github link below", "", "software_build"),
    ("My morning routine", "build a daily habit stack, discipline and consistency", "", "personal_improvement"),
    ("Time blocking", "plan your week with a calendar and a to-do list, prioritise tasks", "", "task_scheduling"),
    ("Automate it", "n8n workflow: trigger a webhook, integrate Google Sheets, automate email", "", "workflow_automation"),
    ("Leg day", "workout: squat sets and reps, protein and calories", "", "health_wellness"),
    ("Budgeting", "budget your income, pay off debt, invest in an index fund", "", "money_finance"),
])
def test_keyword_classifier(title, caption, transcript, expected):
    got = playbooks.classify({"title": title, "description": caption}, transcript)
    assert got["category"] == expected


def test_unclear_video_falls_back_to_general():
    got = playbooks.classify({"title": "wow", "description": "lol"}, "")
    assert got["category"] == playbooks.GENERAL and got["confidence"] == "low"


def test_short_signals_match_whole_words_only():
    # "apply"/"approach" must not count as the software signal "app"
    got = playbooks.classify({"title": "", "description": "apply this approach"}, "")
    assert got["category"] == playbooks.GENERAL


def test_every_playbook_renders_a_portable_blueprint():
    assert playbooks.GENERAL in playbooks.ids() and len(playbooks.ids()) >= 10
    for pid in playbooks.ids():
        bp = playbooks.render_blueprint(pid)
        assert bp.startswith(f"Category: {pid}") and "portable" in bp
    assert playbooks.get("Task Scheduling").id == "task_scheduling"
    assert playbooks.get("unknown").id == playbooks.GENERAL


def test_extract_system_prompt():
    md = "# t\n\n## System prompt\n<system_prompt>\nYou are a coach.\n</system_prompt>\n"
    assert analyze.extract_system_prompt(md) == "You are a coach."
    assert analyze.extract_system_prompt("no tags here") is None


def test_classify_llm_reply_is_validated(monkeypatch):
    monkeypatch.setenv("REELPROMPT_PROVIDER", "openai")
    meta = {"title": "Time blocking", "description": "plan your week with a calendar"}
    replies = iter(['{"category": "learning_skill", "reason": "x"}', '{"category": "bogus"}', "not json"])
    monkeypatch.setattr(analyze, "_complete", lambda *a, **k: (next(replies), 10, 5))
    assert analyze.classify(meta, "")[0] == "learning_skill"
    assert analyze.classify(meta, "")[0] == "task_scheduling"  # unknown id -> heuristic
    assert analyze.classify(meta, "")[0] == "task_scheduling"  # unparseable -> heuristic
