import subprocess

import pytest


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory):
    """A 6s synthetic clip with a tone and visible scene changes (no network needed)."""
    out = tmp_path_factory.mktemp("media") / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=480x854:rate=24:duration=6",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
         "-vf", "hue=h=t*60", "-shortest", "-pix_fmt", "yuv420p", str(out)],
        check=True, capture_output=True)
    return out


@pytest.fixture(scope="session")
def silent_video(tmp_path_factory):
    out = tmp_path_factory.mktemp("media") / "silent.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x568:rate=24:duration=4",
         "-an", "-pix_fmt", "yuv420p", str(out)], check=True, capture_output=True)
    return out
