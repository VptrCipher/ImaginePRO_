import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from . import db
from .config import binary, project_dir, MAX_SOURCE_SECONDS
from .models import Timeline


class Cancelled(Exception):
    pass


def run(args, cwd=None, cancel=None, timeout=600):
    """No shell; poll cancellation and drain output to files to avoid pipe deadlocks."""
    import tempfile
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        p = subprocess.Popen([str(a) for a in args], cwd=cwd, stdout=stdout, stderr=stderr,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        started = time.monotonic()
        try:
            while p.poll() is None:
                if cancel and cancel.is_set():
                    raise Cancelled("Cancelled by user")
                if time.monotonic() - started > timeout:
                    raise TimeoutError("Processing exceeded its time limit")
                time.sleep(0.15)
            stdout.seek(0)
            stderr.seek(0)
            out, err = stdout.read(), stderr.read()
            if p.returncode:
                raise RuntimeError(err.decode("utf-8", errors="replace")[-3500:])
            return out, err
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()


def probe(path):
    raw, _ = run([binary("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", path], timeout=30)
    data = json.loads(raw)
    video = next((s for s in data["streams"] if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    return {"duration": float(data.get("format", {}).get("duration", 0)),
            "width": video["width"] if video else None, "height": video["height"] if video else None,
            "fps": video.get("avg_frame_rate") if video else None, "has_audio": bool(audio),
            "audio_sample_rate": audio.get("sample_rate") if audio else None,
            "audio_channels": audio.get("channels") if audio else None,
            "codec": video.get("codec_name") if video else None,
            "color_transfer": video.get("color_transfer") if video else None}


def ingest(path: Path, name: str, project_id: str, key: str):
    if Path(name).suffix.lower() in {".txt", ".srt", ".vtt"}:
        from .transcripts import ingest_text
        return ingest_text(path, name, project_id, key)
    from PIL import Image
    try:
        with Image.open(path) as image:
            if image.width * image.height > 40_000_000:
                raise ValueError("Reference images are limited to 40 megapixels")
            image = image.convert("RGB")
            metadata = {"width": image.width, "height": image.height, "duration": 0, "has_audio": False}
            thumb = path.parent / f"{key}.jpg"
            image.thumbnail((640, 360))
            image.save(thumb)
            kind = "image"
    except (OSError, Image.DecompressionBombError):
        metadata = probe(path)
        if not 0 < metadata["duration"] <= MAX_SOURCE_SECONDS:
            raise ValueError(f"Media must be between 0 and {MAX_SOURCE_SECONDS} seconds")
        kind = "video" if metadata["width"] else "audio"
        if kind == "video":
            if metadata["width"] * metadata["height"] > 16_777_216:
                raise ValueError("Video input is limited to 4K")
            run([binary("ffmpeg"), "-v", "error", "-y", "-i", path, "-frames:v", "1", "-vf", "scale=320:-2", path.parent / f"{key}.jpg"], timeout=30)
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    metadata["sha256"] = h.hexdigest()
    with db.connect() as c:
        c.execute("INSERT INTO assets VALUES(?,?,?,?,?,?)", (key, project_id, name[:200], str(path), kind, json.dumps(metadata)))
    return db.asset(key, project_id)


def validate_timeline(timeline: Timeline, project_id: str, require_clips=False):
    from .config import MAX_TIMELINE_SECONDS
    if require_clips and not timeline.clips:
        raise ValueError("Add at least one video to the timeline")
    duration = 0
    for clip in timeline.clips:
        a = db.asset(clip.asset_id, project_id)
        if a["kind"] != "video" or clip.end > a["metadata"]["duration"] + 0.01:
            raise ValueError("A clip range is outside its source video")
        duration += clip.end - clip.start
    if duration > MAX_TIMELINE_SECONDS:
        raise ValueError(f"Timeline is limited to {MAX_TIMELINE_SECONDS} seconds")
    for graphic in timeline.motion_graphics:
        if graphic.start + graphic.duration > duration + 0.01:
            raise ValueError("Animation windows must fit inside the output timeline")
    if timeline.motion_graphics:
        first = min(g.start for g in timeline.motion_graphics)
        last = max(g.start + g.duration for g in timeline.motion_graphics)
        if last - first > 60:
            raise ValueError("Animated overlays must fit within a 60-second output window")
    if timeline.music_asset_id:
        a = db.asset(timeline.music_asset_id, project_id)
        if a["kind"] != "audio":
            raise ValueError("Choose an audio asset for background music")
    return duration
