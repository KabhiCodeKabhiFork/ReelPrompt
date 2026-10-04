from reelprompt import cli, uiref


def test_brief_includes_target():
    assert "src/ui" in uiref.render_brief("src/ui") and "src/ui" not in uiref.render_brief()


def test_cli_ui_flag_writes_brief_with_many_frames(sample_video, tmp_path):
    assert cli.main([str(sample_video), "--ui", "--out", str(tmp_path)]) == 0
    pack = next(tmp_path.iterdir())
    assert (pack / "UI_REFERENCE_BRIEF.md").read_text().startswith("# UI reference mode")
    assert len(list((pack / "frames").glob("*.jpg"))) >= 6


def test_screen_recording_paths_are_resolved(sample_video, tmp_path):
    import shutil

    from reelprompt import fetch
    # macOS names the file with a narrow no-break space before AM/PM; users type a normal one
    real = tmp_path / "Screen Recording 2026-10-04 at 10.12.33 AM.mov"
    shutil.copy(sample_video, real)
    typed = str(tmp_path / "Screen Recording 2026-10-04 at 10.12.33 AM.mov")
    assert fetch.resolve_local(typed) == real
    assert fetch.resolve_local(f"'{real}'") == real                        # quoted
    assert fetch.resolve_local(str(real).replace(" ", "\\ ")) == real      # drag-and-drop escapes
    assert fetch.resolve_local("https://x.com/a/status/1") is None
    assert fetch.resolve_local(str(tmp_path / "nope.mov")) is None


def test_ui_mode_uses_wide_frames(sample_video, tmp_path):
    from PIL import Image
    cli.main([str(sample_video), "--ui", "--out", str(tmp_path)])
    pack = next(tmp_path.iterdir())
    width = Image.open(next((pack / "frames").glob("*.jpg"))).width
    assert width == uiref.UI_WIDTH  # scale filter sets the width exactly
