"""Web adapter for video-use's extract → lossless concat → overlays → captions pipeline.

Unlike the standalone helper, web projects can mix silent clips and orientations.
Normalize streams before concat and accept typed operations, never raw filter strings.
"""
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from helpers.grade import get_preset, auto_grade_for_clip
from helpers.render import chunk_words, _words_in_range, TONEMAP_CHAIN
from . import db
from .config import binary, project_dir
from .media import run, probe, validate_timeline
from .transcription import transcribe
from .motion_graphics import render_overlay


def ass_time(t):
    cs = round(max(0, t) * 100)
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02}:{s:02}.{c:02}"


def ass_text(text):
    return text.replace("\\", "＼").replace("{", "(").replace("}", ")").replace("\n", " ").replace("\r", " ")


def make_captions(timeline, transcripts, width, height, path):
    events = []
    offset = 0
    for clip in timeline.clips:
        words = _words_in_range(transcripts.get(clip.asset_id, {}), clip.start, clip.end)
        for chunk in chunk_words(words):
            start = max(clip.start, chunk[0]["start"]) - clip.start + offset
            end = min(clip.end, chunk[-1]["end"]) - clip.start + offset
            if end <= start:
                continue
            text = ass_text(" ".join(w["text"].strip() for w in chunk).upper())
            effect = r"{\fad(50,30)\fscx90\fscy90\t(0,90,\fscx100\fscy100)}" if timeline.captions == "pop" else ""
            events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{effect}{text}")
        offset += clip.end - clip.start
    size = round(height * (0.042 if height > width else 0.055))
    margin = round(height * (0.28 if height > width else 0.10))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,35,35,{margin},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return len(events)


def title_image(text, width, height, target):
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    font = None
    for location in ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if Path(location).exists():
            font = ImageFont.truetype(location, round(width * 0.05))
            break
    font = font or ImageFont.load_default(size=round(width * 0.05))
    # Fit a short heading; text is rasterized, never interpolated into ffmpeg code.
    while d.textbbox((0, 0), text, font=font)[2] > width * 0.84 and getattr(font, "size", 10) > 16:
        font = font.font_variant(size=font.size - 2)
    box = d.textbbox((0, 0), text, font=font)
    x, y = (width - box[2]) / 2, height * 0.18
    d.rounded_rectangle((x - 25, y - 10, x + box[2] + 25, y + box[3] + 22), radius=12, fill=(12, 15, 20, 210))
    d.text((x, y), text, font=font, fill="white", stroke_width=1)
    image.save(target)


def render(project_id, timeline, workspace, preview=True, cancel=None, progress=lambda p, m: None, lossless=False):
    expected = validate_timeline(timeline, project_id, require_clips=True)
    has_visual_composite = bool(timeline.title or timeline.fade_out or timeline.captions != "none" or timeline.motion_graphics)
    width, height = ((1280, 720) if preview else (1920, 1080)) if timeline.aspect == "landscape" else ((720, 1280) if preview else (1080, 1920))
    workspace.mkdir(parents=True, exist_ok=True)
    ffmpeg = binary("ffmpeg")
    (workspace / "timeline.json").write_text(timeline.model_dump_json(indent=2), encoding="utf-8")
    transcripts, segments = {}, []
    edl = {"version": 1, "sources": {}, "ranges": [], "grade": timeline.grade, "total_duration_s": expected}
    for i, clip in enumerate(timeline.clips):
        a = db.asset(clip.asset_id, project_id)
        if timeline.captions != "none" and a["id"] not in transcripts:
            transcripts[a["id"]] = transcribe(a, cancel, lambda m: progress(8, m))
        edl["sources"][a["id"]] = a["path"]
        edl["ranges"].append({"source": a["id"], "start": clip.start, "end": clip.end, "reason": clip.reason})
        dur = clip.end - clip.start
        grade = get_preset(timeline.grade) if timeline.grade != "auto" else auto_grade_for_clip(Path(a["path"]), clip.start, dur)[0]
        filters = []
        if a["metadata"].get("color_transfer") in {"smpte2084", "arib-std-b67"}:
            filters.append(TONEMAP_CHAIN)
        filters += [f"scale={width}:{height}:force_original_aspect_ratio=increase", f"crop={width}:{height}", "setsar=1", "fps=30", "setpts=PTS-STARTPTS"]
        if clip.zoom > 1:
            zw, zh = int(width / clip.zoom) // 2 * 2, int(height / clip.zoom) // 2 * 2
            filters += [f"crop={zw}:{zh}", f"scale={width}:{height}"]
        if grade:
            filters.append(grade)
        target = workspace / f"seg_{i:03}.mp4"
        cmd = [ffmpeg, "-v", "error", "-nostdin", "-y", "-ss", str(clip.start), "-i", a["path"]]
        if not a["metadata"]["has_audio"]:
            cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        # Final graphics/captions need one compositing encode. Preserve the graded
        # intermediate pixels losslessly so that only delivery encoding is lossy.
        segment_crf = "0" if lossless else (("25" if has_visual_composite else "24") if preview else ("0" if has_visual_composite else "20"))
        cmd += ["-t", str(dur), "-map", "0:v:0", "-map", "0:a:0" if a["metadata"]["has_audio"] else "1:a:0",
                "-vf", ",".join(filters), "-af", f"asetpts=PTS-STARTPTS,aresample=48000:async=1:first_pts=0,volume={clip.volume},afade=t=in:d=0.03,afade=t=out:st={max(0,dur-.03)}:d=0.03",
                "-c:v", "libx264", "-preset", "ultrafast" if preview else "fast", "-crf", segment_crf, "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", "-video_track_timescale", "15360", "-movflags", "+faststart", str(target)]
        run(cmd, cancel=cancel)
        segments.append(target)
        progress(15 + 55 * (i + 1) / len(timeline.clips), f"Rendered clip {i+1} of {len(timeline.clips)}")
    (workspace / "edl.json").write_text(json.dumps(edl, indent=2), encoding="utf-8")
    # Relative generated filenames avoid Windows drive-colon and quote parsing issues.
    (workspace / "concat.txt").write_text("".join(f"file '{p.name}'\n" for p in segments), encoding="utf-8")
    run([ffmpeg, "-v", "error", "-nostdin", "-y", "-f", "concat", "-safe", "1", "-i", "concat.txt", "-c", "copy", "base.mp4"], cwd=workspace, cancel=cancel)
    inputs = ["-i", "base.mp4"]
    graph = []
    current = "[0:v]"
    idx = 1
    if timeline.title:
        title_image(timeline.title, width, height, workspace / "title.png")
        inputs += ["-loop", "1", "-i", "title.png"]
        graph.append(f"[{idx}:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st=2.1:d=0.4:alpha=1[title]")
        graph.append(f"{current}[title]overlay=enable='lt(t,2.5)':shortest=1[vtitle]")
        current = "[vtitle]"
        idx += 1
    if timeline.motion_graphics:
        progress(73,"Rendering animated text and graphic overlays")
        overlay,start,end = render_overlay(timeline.motion_graphics,width,height,workspace,cancel)
        inputs += ["-i",overlay.name]
        graph.append(f"[{idx}:v]setpts=PTS-STARTPTS+{start}/TB[graphics]")
        graph.append(f"{current}[graphics]overlay=eof_action=pass:enable='between(t,{start:.3f},{end:.3f})'[vgraphics]")
        current = "[vgraphics]"
        idx += 1
    if timeline.fade_out:
        graph.append(f"{current}fade=t=out:st={max(0,expected-.4)}:d=0.4[vfade]")
        current = "[vfade]"
    cues = 0
    if timeline.captions != "none":
        cues = make_captions(timeline, transcripts, width, height, workspace / "captions.ass")
        if not cues:
            raise ValueError("Captions requested but no speech words were detected. Disable captions or use footage with speech.")
        graph.append(f"{current}ass=filename=captions.ass[vsub]")
        current = "[vsub]"
    if has_visual_composite:
        graph.append(f"{current}null[vout]")
    # Normalize the actual mixed audio. A short/silent signal has undefined LUFS;
    # feeding non-finite measurements into loudnorm can produce NaN samples.
    audio_inputs = ["-i", "base.mp4"]
    audio_parts, audio_labels = [], ["[0:a]"]
    audio_index = 1
    if timeline.music_asset_id:
        music = db.asset(timeline.music_asset_id, project_id)
        audio_inputs += ["-stream_loop", "-1", "-i", music["path"]]
        audio_parts.append(f"[{audio_index}:a]volume={timeline.music_volume}[music]")
        audio_labels.append("[music]")
        audio_index += 1
    scene = next((g for g in timeline.motion_graphics if g.template == "framecraft"), None)
    if scene:
        audio_inputs += ["-i", "framecraft-score.wav"]
        has_source_audio = any(db.asset(c.asset_id, project_id)["metadata"]["has_audio"] and c.volume > 0 for c in timeline.clips)
        score_volume = .13 if has_source_audio else .85
        audio_parts.append(f"[{audio_index}:a]volume={score_volume},adelay={round(scene.start*1000)}:all=1[score]")
        audio_labels.append("[score]")
    audio_filter = "anull"
    if audio_parts:
        audio_parts.append("".join(audio_labels) + f"amix=inputs={len(audio_labels)}:duration=first:normalize=0")
        audio_filter = ";".join(audio_parts)
    run([ffmpeg, "-v", "error", "-nostdin", "-y", *audio_inputs, "-filter_complex", audio_filter,
         "-vn", "-t", str(expected), "-c:a", "pcm_s16le", "-ar", "48000", "audio.wav"], cwd=workspace, cancel=cancel)
    _, loudness_log = run([ffmpeg, "-hide_banner", "-nostats", "-i", "audio.wav", "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"], cwd=workspace, cancel=cancel)
    raw_log = loudness_log.decode(errors="replace")
    measurement = json.loads(raw_log[raw_log.rfind("{"):raw_log.rfind("}")+1])
    finite = all(math.isfinite(float(measurement[k])) for k in ["input_i", "input_tp", "input_lra", "input_thresh", "target_offset"])
    norm = "anull"
    if finite:
        norm = "loudnorm=I=-14:TP=-1:LRA=11"
        if not preview:
            norm += f":measured_I={measurement['input_i']}:measured_TP={measurement['input_tp']}:measured_LRA={measurement['input_lra']}:measured_thresh={measurement['input_thresh']}:offset={measurement['target_offset']}:linear=true"
    inputs += ["-i", "audio.wav"]
    graph.append(f"[{idx}:a]{norm},afade=t=out:st={max(0,expected-.1)}:d=0.1[aout]")
    progress(78, "Compositing title, audio and captions")
    video_encoding = ["-c:v", "libx264", "-preset", "ultrafast" if preview else "fast", "-crf", "0" if lossless else ("24" if preview else "20"), "-pix_fmt", "yuv420p"] if has_visual_composite else ["-c:v", "copy"]
    run([ffmpeg, "-v", "error", "-nostdin", "-y", *inputs, "-filter_complex", ";".join(graph), "-map", "[vout]" if has_visual_composite else "0:v:0", "-map", "[aout]",
         "-t", str(expected), *video_encoding, "-c:a", "aac", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", "output.mp4"], cwd=workspace, cancel=cancel)
    output = workspace / "output.mp4"
    progress(90, "Decoding output and verifying duration, resolution and sync")
    meta = probe(output)
    if meta["codec"] != "h264" or (meta["width"], meta["height"]) != (width, height):
        raise RuntimeError("Export stream or resolution verification failed")
    if abs(meta["duration"] - expected) > 0.35:
        raise RuntimeError("Output duration does not match the approved timeline")
    run([ffmpeg, "-v", "error", "-i", output, "-f", "null", "-"], cancel=cancel)
    stream_raw, _ = run([binary("ffprobe"), "-v", "error", "-show_streams", "-of", "json", output], cancel=cancel)
    streams = json.loads(stream_raw)["streams"]
    times = [float(s.get("duration", meta["duration"])) for s in streams if s["codec_type"] in {"video", "audio"}]
    if max(times) - min(times) > 0.25:
        raise RuntimeError("Audio/video duration difference exceeds 250ms")
    # Bounded contact sheet around every cut plus opening, middle, ending.
    points, offset = {0.1, max(0, expected / 2), max(0, expected - .15)}, 0
    for clip in timeline.clips[:-1]:
        offset += clip.end - clip.start
        points.update({max(0, offset - .08), min(expected - .04, offset + .08)})
    images = []
    for i, t in enumerate(sorted(points)):
        frame = workspace / f"check_{i:03}.jpg"
        run([ffmpeg, "-v", "error", "-y", "-ss", str(t), "-i", output, "-frames:v", "1", "-vf", "scale=320:-2", frame], cancel=cancel)
        if frame.exists():
            with Image.open(frame) as im:
                images.append(im.copy())
    if images:
        sheet = Image.new("RGB", (320 * 4, (images[0].height + 22) * math.ceil(len(images) / 4)), "#10131a")
        d = ImageDraw.Draw(sheet)
        for i, im in enumerate(images):
            x, y = (i % 4) * 320, (i // 4) * (im.height + 22)
            sheet.paste(im, (x, y))
            d.text((x + 5, y + im.height + 3), f"{sorted(points)[i]:.2f}s", fill="white")
        sheet.save(workspace / "verification.jpg")
    verification = {"expected_duration": expected, "actual_duration": meta["duration"], "width": width, "height": height,
                    "decoded": True, "audio_video_duration_delta": max(times)-min(times), "caption_cues": cues,
                    "motion_graphics": len(timeline.motion_graphics),
                    "framecraft_score": bool(scene),
                    "sampled_frames": len(images), "video_encoding": "fast preview" if preview else ("lossless intermediates + one delivery encode" if has_visual_composite else "one segment encode + copy concat/remux"),
                    "loudness_normalization": ("one-pass" if preview else "two-pass") if finite else "skipped: silence or insufficient measurable audio",
                    "limitations": ["Perceptual quality and spoken meaning require human review."]}
    (workspace / "verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    return verification
