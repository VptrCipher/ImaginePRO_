"""Transcript imports and Windows system narration, without a paid speech service."""
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from . import db
from .config import ROOT
from .media import run


def ingest_text(path, name, project_id, key):
    if path.stat().st_size > 200000:
        raise ValueError("Transcript is too long; use a short script for this video")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("utf-16")
    if Path(name).suffix.lower() in {".srt", ".vtt"}:
        text = "\n".join(line for line in text.splitlines() if line.strip() and not line.strip().isdigit()
                         and "-->" not in line and line.strip() != "WEBVTT")
        text = re.sub(r"<[^>]+>", "", text)
    text = text.strip()
    if not text or len(text) > 20000 or "\x00" in text:
        raise ValueError("Provide a text transcript of 1–20,000 characters")
    metadata = {"text": text, "word_count": len(text.split()), "duration": 0,
                "sha256": hashlib.sha256(raw).hexdigest()}
    with db.connect() as c:
        c.execute("INSERT INTO assets VALUES(?,?,?,?,?,?)", (key, project_id, name[:200], str(path), "text", json.dumps(metadata)))
    return db.asset(key, project_id)


def narrate(text, workspace, cancel=None):
    if os.name != "nt":
        raise RuntimeError("Text narration needs Windows system speech on this build; import a recorded voiceover instead")
    path, target = workspace / "narration.txt", workspace / "narration.wav"
    path.write_text(text, encoding="utf-8")
    shell = shutil.which("powershell.exe")
    if not shell:
        installed = Path(os.environ.get('SystemRoot','C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        if installed.is_file(): shell = str(installed)
    if not shell:
        raise RuntimeError("Windows system speech is unavailable; import a recorded voiceover")
    literal = lambda value: "'" + str(value).replace("'", "''") + "'"
    command = ("Add-Type -AssemblyName System.Speech; "
               "$narrator = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
               "try { $narrator.Rate=0; $narrator.SetOutputToWaveFile(" + literal(target) + "); "
               "$narrator.Speak([System.IO.File]::ReadAllText(" + literal(path) + ", [System.Text.Encoding]::UTF8)) } "
               "finally { $narrator.Dispose() }")
    run([shell, "-NoProfile", "-NonInteractive", "-Command", command],
        cancel=cancel, timeout=120)
    return target
