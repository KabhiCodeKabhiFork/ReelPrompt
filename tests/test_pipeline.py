import json

import pytest

from reelprompt import pipeline
from reelprompt.fetch import fetch, is_local_file


def test_local_file_detection(sample_video, tmp_path):
    assert is_local_file(str(sample_video))
    assert is_local_file(f"file://{sample_video}")
    assert not is_local_file("https://example.com/x")


def test_rejects_unsupported_file(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hi")
    with pytest.raises(ValueError):
        fetch(str(f), tmp_path)


def test_extract_local_video(sample_video, tmp_path):
    pack = pipeline.extract(str(sample_video), n_frames=5, out_root=tmp_path)
    assert pack.path.parent == tmp_path
    assert 1 <= len(pack.frames) <= 5
    assert all(p.exists() and p.suffix == ".jpg" for _, p in pack.frames)
    meta = json.loads((pack.path / "meta.json").read_text())
    assert meta["platform"] == "local file" and meta["duration_s"] > 5
    assert (pack.path / "transcript.md").exists()
    assert not list(tmp_path.glob("**/video.*"))  # downloaded/copied video is never kept


def test_silent_video_has_no_transcript(silent_video, tmp_path):
    pack = pipeline.extract(str(silent_video), n_frames=4, out_root=tmp_path)
    assert pack.transcript == ""
    assert (pack.path / "transcript.md").read_text() == "(no speech detected)"
    assert len(pack.frames) >= 1


def test_run_with_mock_llm(sample_video, tmp_path, monkeypatch):
    monkeypatch.setenv("REELPROMPT_PROVIDER", "mock")
    pack = pipeline.run(str(sample_video), n_frames=3, out_root=tmp_path)
    assert pack.prompt_path.read_text().startswith("# Mock analysis")
    assert pack.system_prompt and pack.system_prompt_path.read_text().startswith("Mock system prompt")
    assert json.loads((pack.path / "meta.json").read_text())["category"] == pack.category


def test_run_with_forced_category(sample_video, tmp_path, monkeypatch):
    monkeypatch.setenv("REELPROMPT_PROVIDER", "mock")
    pack = pipeline.run(str(sample_video), n_frames=2, out_root=tmp_path, category="task_scheduling")
    assert pack.category == "task_scheduling" and "task_scheduling" in pack.system_prompt


def test_missing_api_key_is_a_clear_error(sample_video, tmp_path, monkeypatch):
    monkeypatch.setenv("REELPROMPT_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        pipeline.run(str(sample_video), n_frames=2, out_root=tmp_path)


def test_env_file_loader(tmp_path, monkeypatch):
    from reelprompt.config import load_env

    (tmp_path / ".env").write_text("# c\nFOO_RP = bar\nexport BAZ_RP='qux'\nKEEP_RP=new\n")
    monkeypatch.setenv("REELPROMPT_HOME", str(tmp_path))
    monkeypatch.delenv("REELPROMPT_NO_DOTENV", raising=False)
    monkeypatch.setenv("KEEP_RP", "old")
    monkeypatch.delenv("FOO_RP", raising=False)
    monkeypatch.delenv("BAZ_RP", raising=False)
    load_env()
    import os
    assert (os.environ["FOO_RP"], os.environ["BAZ_RP"], os.environ["KEEP_RP"]) == ("bar", "qux", "old")


def test_provider_is_case_insensitive_and_validated(monkeypatch):
    from reelprompt import analyze

    monkeypatch.setenv("REELPROMPT_PROVIDER", " OpenAI ")
    assert analyze.provider() == "openai"
    monkeypatch.setenv("REELPROMPT_PROVIDER", "gemini")
    with pytest.raises(ValueError, match="gemini"):
        analyze.provider()


def test_auto_frame_count_scales_with_duration():
    from reelprompt.media import auto_frame_count
    assert [auto_frame_count(d) for d in (0, 30, 80, 130, 400, 3600)] == [8, 8, 8, 13, 16, 16]


def test_longer_video_gets_more_frames_by_default(sample_video, long_video, tmp_path):
    short = pipeline.extract(str(sample_video), out_root=tmp_path / "a")
    long = pipeline.extract(str(long_video), out_root=tmp_path / "b")
    assert len(short.frames) <= 8 < len(long.frames) <= 10  # 100s -> 10 frames
    forced = pipeline.extract(str(long_video), n_frames=5, out_root=tmp_path / "c")
    assert len(forced.frames) <= 5


def test_parse_timestamp():
    from reelprompt.media import parse_timestamp
    assert [parse_timestamp(x) for x in (75, "75", "1:15", "0:01:15", "1.5")] == [75, 75, 75, 75, 1.5]
    for bad in ("abc", "-3", "1:2:3:4"):
        with pytest.raises(ValueError):
            parse_timestamp(bad)


def test_frames_at(sample_video, tmp_path):
    folder, got = pipeline.frames_at(str(sample_video), ["1", "0:03", 999], out_root=tmp_path)
    assert [n for n, _ in got] == ["at_00m01s.jpg", "at_00m03s.jpg", "at_16m39s.jpg"]
    assert all(p.exists() and p.stat().st_size > 0 for _, p in got)  # 999s is clamped to the last frame
    assert not list(tmp_path.glob("**/video.*"))
    with pytest.raises(ValueError):
        pipeline.frames_at(str(sample_video), [], out_root=tmp_path)
