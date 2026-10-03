"""Local speech-to-text with faster-whisper (CPU, no API key)."""
import os

_model = None


def transcribe(wav_path, model_name=None):
    """Return ([(start, end, text)], language)."""
    global _model
    from faster_whisper import WhisperModel

    name = model_name or os.environ.get("REELPROMPT_WHISPER_MODEL", "base")
    if _model is None or _model[0] != name:
        _model = (name, WhisperModel(name, device="cpu", compute_type="int8"))
    segments, info = _model[1].transcribe(str(wav_path), vad_filter=True)
    return [(s.start, s.end, s.text.strip()) for s in segments if s.text.strip()], info.language


def format_transcript(segments) -> str:
    return "\n".join(f"[{int(s // 60):02d}:{int(s % 60):02d}] {t}" for s, _, t in segments)
