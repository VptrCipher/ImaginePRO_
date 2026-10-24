"""One request → real Codex decisions/illustrations → verified media → timeline."""
import json
import math
import re
from pathlib import Path
from types import SimpleNamespace
from PIL import Image, ImageDraw
from . import db
from .agent import plan_edit
from .composition import compose
from .config import binary, project_dir
from .framecraft_renderer import render_scene
from .media import run, probe, ingest, validate_timeline, Cancelled
from .models import Timeline, Clip
from .rendering import render, make_captions
from .styles import style_text
from .transcription import transcribe
from .transcripts import narrate


def register(path, name, project_id, generated=False):
    key = db.uid()
    ingest(path, name, project_id, key)
    asset = db.asset(key, project_id)
    if generated:
        asset["metadata"]["generated"] = True
        with db.connect() as c:
            c.execute("UPDATE assets SET metadata=? WHERE id=?", (json.dumps(asset["metadata"]), key))
    return db.asset(key, project_id)


def generate(project_id, payload, workspace, cancel, progress):
    project = payload["project_snapshot"]
    prompt = payload["prompt"]
    style = style_text(payload.get("style_id"), project_id)
    width, height = (1080, 1920) if payload.get("aspect") == "portrait" else (1920, 1080)
    input_ids = set(payload.get("input_asset_ids", []))
    source_assets = [a for a in project["assets"] if not input_ids or a["id"] in input_ids]
    selected = {c["asset_id"] for c in project["timeline"]["clips"] if any(a["id"] == c["asset_id"] for a in source_assets)}
    videos = [a for a in source_assets if a["kind"] == "video" and (not selected or a["id"] in selected)]
    # With an empty timeline prefer original footage over earlier generated revisions.
    if not selected and any(not a["metadata"].get("generated") for a in videos):
        videos = [a for a in videos if not a["metadata"].get("generated")]
    audio = [a for a in source_assets if a["kind"] == "audio" and not a["metadata"].get("generated")]
    text_assets = [a for a in source_assets if a["kind"] == "text"]
    script = text_assets[-1]["metadata"]["text"] if text_assets else ""
    transcripts, words, narration, base, caption_path, cues = {}, [], None, None, None, 0
    progress(5, "Reading your media and script")
    for a in videos + ([] if videos else audio):
        full = db.asset(a["id"], project_id)
        transcripts[a["id"]] = transcribe(full, cancel, lambda m: progress(10, m))
    if videos:
        progress(22, "Codex is directing your footage")
        snapshot = dict(project, assets=videos + audio)
        if input_ids and not selected:
            snapshot["timeline"] = Timeline().model_dump()
        plan = plan_edit(snapshot, prompt + "\nThis is automatic generation. Use the uploaded footage. A separate scene composer creates any new illustrations/overlays: keep motion_graphics empty and legacy title empty. Preserve speech. Choose captions if useful.",
                         style, transcripts, workspace / "edit-agent", cancel)
        plan.timeline.aspect = payload.get("aspect", "portrait")
        plan.timeline.motion_graphics = []
        plan.timeline.title = ""
        duration = validate_timeline(plan.timeline, project_id, True)
        (workspace / "edit-plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        clock = 0
        for clip in plan.timeline.clips:
            for word in transcripts.get(clip.asset_id, {}).get("words", []):
                if clip.start <= word["start"] < clip.end:
                    words.append(dict(word, start=word["start"]-clip.start+clock, end=min(word["end"],clip.end)-clip.start+clock))
            clock += clip.end - clip.start
        script = script or " ".join(w["text"] for w in words)
        base_timeline = plan.timeline.model_copy(deep=True)
        base_timeline.captions = "none"
        base_dir = workspace / "footage"
        render(project_id, base_timeline, base_dir, preview=False, cancel=cancel,
               progress=lambda p,m: progress(25+p*.2,m), lossless=True)
        base = base_dir / "output.mp4"
        if plan.timeline.captions != "none" and words:
            caption_path = workspace / "captions.ass"
            cues = make_captions(plan.timeline, transcripts, width, height, caption_path)
    else:
        if audio:
            candidates = [(a, transcripts[a["id"]]) for a in audio]
            chosen, tr = max(candidates, key=lambda pair: len(pair[1].get("words", [])))
            narration = db.asset(chosen["id"], project_id)
            words = tr.get("words", [])
            script = script or tr.get("text", "")
        elif script:
            progress(15, "Creating narration from your transcript")
            path = narrate(script, workspace, cancel)
            narration = register(path, "Generated narration.wav", project_id, generated=True)
            tr = transcribe(narration, cancel, lambda m: progress(20,m))
            words = tr.get("words", [])
        requested = re.search(r"\b(\d{1,2}(?:\.\d+)?)\s*[- ]?(?:seconds?|secs?|s)\b", prompt, re.I)
        target = min(60, max(3, float(requested.group(1)))) if requested else 8
        if narration:
            target = max(target if requested else 3, narration["metadata"]["duration"]+.25)
        duration = math.ceil(target*30)/30
        if duration > 60:
            raise ValueError("Please use a transcript or voiceover up to one minute for animated generation")
        if narration and words and re.search(r"caption|subtitle", prompt, re.I):
            caption_path = workspace / "captions.ass"
            fake = Timeline(clips=[Clip(asset_id=narration["id"],start=0,end=min(duration,narration["metadata"]["duration"]))], captions="pop", aspect=payload.get("aspect", "portrait"))
            cues = make_captions(fake,{narration["id"]:{"words":words}},width,height,caption_path)
    if cancel.is_set(): raise Cancelled("Generation cancelled")
    progress(48, "Codex is creating your animation and timing")
    images = []
    if videos:
        a = db.asset(videos[0]["id"], project_id)
        thumbnail = Path(a["path"]).parent / (a["id"]+".jpg")
        if thumbnail.exists(): images = [str(thumbnail)]
    film = compose(prompt, style, script, words, duration, width, height, workspace / "scene-agent", cancel,
                   overlay=bool(videos), images=images)
    (workspace / "composition.json").write_text(film.model_dump_json(indent=2), encoding="utf-8")
    progress(63, "Drawing your animated scenes")
    graphic = SimpleNamespace(duration=duration,text="",detail="",start=0)
    render_scene(graphic,width,height,workspace,cancel,composition=film)
    progress(80, "Finishing picture, narration and sound")
    ffmpeg = binary("ffmpeg")
    inputs = ["-i",str(base)] if base else []
    scene_index = 1 if base else 0
    inputs += ["-i","motion-graphics.mov","-i","composition-score.wav"]
    score_index = scene_index+1
    parts, video_label = [], f"[{scene_index}:v]"
    if base:
        parts.append("[0:v][1:v]overlay=eof_action=pass[vscene]")
        video_label = "[vscene]"
    if caption_path:
        parts.append(f"{video_label}ass=filename=captions.ass[vcaptions]")
        video_label = "[vcaptions]"
    parts.append(f"{video_label}format=yuv420p[vout]")
    score_volume = .10 if base or narration else .8
    parts.append(f"[{score_index}:a]volume={score_volume}[bed]")
    labels = ["[bed]"]
    if base: labels.append("[0:a]")
    if narration:
        inputs += ["-i",narration["path"]]
        parts.append(f"[{score_index+1}:a]apad,atrim=duration={duration}[voice]")
        labels.append("[voice]")
    parts.append("".join(labels)+f"amix=inputs={len(labels)}:duration=longest:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=out:st={max(0,duration-.12)}:d=0.12[aout]")
    run([ffmpeg,"-v","error","-nostdin","-y",*inputs,"-filter_complex",";".join(parts),"-map","[vout]","-map","[aout]",
         "-t",str(duration),"-r","30","-c:v","libx264","-preset","fast","-crf","20","-pix_fmt","yuv420p",
         "-c:a","aac","-b:a","192k","-ar","48000","-ac","2","-movflags","+faststart","output.mp4"],cwd=workspace,cancel=cancel)
    output = workspace / "output.mp4"
    progress(93,"Checking the finished video")
    meta = probe(output)
    if abs(meta["duration"]-duration)>.15 or (meta["width"],meta["height"])!=(width,height):
        raise RuntimeError("Generated video did not pass duration/resolution checks")
    run([ffmpeg,"-v","error","-i",output,"-f","null","-"],cancel=cancel)
    run([ffmpeg,"-v","error","-y","-i",output,"-vf","fps=2,scale=180:-2,tile=6x2","-frames:v","1",workspace/"verification.jpg"],cancel=cancel)
    # Real media is put on the editable timeline only after the entire job succeeds.
    if cancel.is_set(): raise Cancelled("Generation cancelled")
    asset = register(output,"Generated video.mp4",project_id,generated=True)
    thumbnail = output.parent / (asset["id"]+".jpg")
    run([ffmpeg,"-v","error","-y","-ss",str(max(0,duration-.5)),"-i",output,"-frames:v","1","-vf","scale=640:-2",thumbnail],cancel=cancel)
    timeline = Timeline(clips=[Clip(asset_id=asset["id"],start=0,end=duration,reason="Generated from your prompt and selected style")],aspect=payload.get("aspect","portrait"))
    if cancel.is_set(): raise Cancelled("Generation cancelled")
    saved = db.save_timeline(project_id,payload["base_revision"],timeline)
    result = {"summary":film.summary,"revision":saved["revision"],"asset_id":asset["id"],"decoded":True,
              "actual_duration":meta["duration"],"expected_duration":duration,"width":width,"height":height,
              "scene_count":len(film.scenes),"element_count":sum(len(s.elements) for s in film.scenes),"caption_cues":cues,
              "narration":bool(narration),"footage_edited":bool(videos),"style_id":payload.get("style_id"),
              "video_encoding":"lossless illustration/footage intermediates + one delivery encode"}
    (workspace/"verification.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result
