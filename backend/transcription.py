"""Normalize local Whisper words into the existing Scribe-compatible helper format."""
import json
import os
import threading
from pathlib import Path
from .config import STORAGE
from .media import Cancelled

_models = {}
_lock = threading.Lock()


def transcribe(asset, cancel=None, progress=lambda message: None):
    model_name = os.environ.get("WHISPER_MODEL", "base")
    cache = STORAGE / "cache" / "transcripts"
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"{asset['metadata']['sha256']}_{model_name.replace('/', '_')}.json"
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    if not asset["metadata"]["has_audio"]:
        return {"text": "", "words": [], "provider": "none", "diarization": "unsupported"}
    from faster_whisper import WhisperModel
    with _lock:
        if model_name not in _models:
            progress(f"Loading local Whisper {model_name}; first use downloads model weights")
            _models[model_name] = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=4,
                                               download_root=str(STORAGE / "cache" / "models"))
    progress("Transcribing speech locally with word timestamps")
    segments, info = _models[model_name].transcribe(asset["path"], word_timestamps=True, vad_filter=True,
                                                  condition_on_previous_text=False, beam_size=5)
    words = []
    for s in segments:
        if cancel and cancel.is_set():
            raise Cancelled("Cancelled during transcription")
        for w in s.words or []:
            words.append({"type": "word", "text": w.word.strip(), "start": round(w.start, 3),
                          "end": round(w.end, 3), "speaker_id": None, "probability": w.probability})
    result = {"text": " ".join(w["text"] for w in words), "words": words, "language_code": info.language,
              "provider": "faster-whisper", "model": model_name, "diarization": "unsupported",
              "limitations": ["Local Whisper may normalize hesitation words; filler detection is best effort."]}
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return result
