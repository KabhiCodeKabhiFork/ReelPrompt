from reelprompt import cli, uiref


def test_brief_includes_target():
    assert "src/ui" in uiref.render_brief("src/ui") and "src/ui" not in uiref.render_brief()


def test_cli_ui_flag_writes_brief_with_many_frames(sample_video, tmp_path):
    assert cli.main([str(sample_video), "--ui", "--out", str(tmp_path)]) == 0
    pack = next(tmp_path.iterdir())
    assert (pack / "UI_REFERENCE_BRIEF.md").read_text().startswith("# UI reference mode")
    assert len(list((pack / "frames").glob("*.jpg"))) >= 6
