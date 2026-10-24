"""Bounded, declarative motion graphics. No AI-generated Python, JS or filter code.

Pillow supplies typography/shapes; FFmpeg encodes one lossless RGBA overlay slot.
The existing video-use PTS-shift/overlay/captions-last rules govern compositing.
"""
import math
import os
import subprocess
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .config import binary
from .media import Cancelled

PALETTES = {
    "cream": {"paper": "#f5f1e8", "ink": "#292824", "muted": "#8b8378", "accent": "#d77b58", "line": "#d9d0c3"},
    "dark": {"paper": "#242328", "ink": "#f4eee4", "muted": "#b4a89b", "accent": "#e49b77", "line": "#51484b"},
}


@lru_cache(maxsize=100)
def font(size, serif=False):
    options = (["C:/Windows/Fonts/georgia.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"] if serif else
               ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for path in options:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def ease(t):
    return 1 - (1 - min(1, max(0, t))) ** 3


def wrap(draw, text, face, max_width):
    lines = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for word in paragraph.split():
            candidate = (current + " " + word).strip()
            if current and draw.textlength(candidate, font=face) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


@lru_cache(maxsize=100)
def panel(template, text, detail, palette, width, height):
    p = PALETTES[palette]
    pw = round(width * (.77 if template == "kinetic_title" else .38 if template == "lower_third" else .43))
    ph = round(height * (.56 if template == "kinetic_title" else .24 if template == "lower_third" else .32))
    image = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    pad = round(pw * .075)
    if template == "kinetic_title":
        # A translucent paper card protects readability on actual footage.
        d.rounded_rectangle((0, 0, pw-1, ph-1), radius=round(width*.015), fill=p["paper"])
        d.line((pad, ph-pad*.75, pw-pad, ph-pad*.75), fill=p["line"], width=max(1,round(width/960)))
        label_y, title_y = round(ph*.105), round(ph*.225)
        d.text((pad, label_y), "A LITTLE MORE POSSIBILITY", font=font(round(height*.019)), fill=p["muted"])
        size = round(height * (.092 if height < width else .060))
        serif = True
    else:
        d.rounded_rectangle((0, 0, pw-1, ph-1), radius=round(width*.012), fill=p["paper"])
        d.rounded_rectangle((0, 0, max(4,round(width*.006)), ph-1), radius=3, fill=p["accent"])
        title_y = round(ph*.17)
        size = round(height * (.054 if height < width else .035))
        serif = template == "callout"
    face = font(max(14,size), serif)
    max_lines = 2
    while size > 14:
        lines = wrap(d, text, face, pw - 2*pad)
        if len(lines) <= max_lines and all(d.textlength(line,font=face) <= pw-2*pad for line in lines):
            break
        size -= 2
        face = font(size, serif)
    step = size * 1.2
    for i, line in enumerate(lines[:max_lines]):
        d.text((pad, title_y + i*step), line, font=face, fill=p["ink"])
    if detail:
        small_size = round(height * (.025 if template == "kinetic_title" else .022))
        small = font(max(12,small_size))
        detail_lines = wrap(d, detail, small, pw-2*pad)[:2]
        y = min(ph - len(detail_lines)*small_size*1.35 - pad*.8, title_y + len(lines[:max_lines])*step + ph*.06)
        for i,line in enumerate(detail_lines):
            d.text((pad,y+i*small_size*1.3),line,font=small,fill=p["muted"])
    return image


def starburst(draw, cx, cy, radius, rotation, color):
    points = []
    for i in range(28):
        angle = rotation + math.pi * 2 * i / 28
        r = radius if i % 2 == 0 else radius*.36
        points.append((cx + math.cos(angle)*r, cy + math.sin(angle)*r))
    draw.polygon(points,fill=color)


def frame(graphics, width, height, output_time):
    canvas = Image.new("RGBA",(width,height),(0,0,0,0))
    for g in graphics:
        local = output_time - g.start
        if not 0 <= local < g.duration:
            continue
        entering = ease(local / min(.5,g.duration/3))
        exiting = ease((g.duration-local) / min(.3,g.duration/3))
        opacity = min(entering,exiting)
        image = panel(g.template,g.text,g.detail,g.palette,width,height).copy()
        pw,ph = image.size
        margin_x,margin_y = round(width*.07),round(height*.08)
        if g.template == "lower_third" or g.position == "lower_left":
            x = width-pw-margin_x if g.position == "right" else margin_x
            y = round(height*.69)-ph//2
        elif g.position == "left":
            x,y = margin_x,round((height-ph)/2)
        elif g.position == "right":
            x,y = width-pw-margin_x,round((height-ph)/2)
        else:
            x,y = (width-pw)//2,(height-ph)//2
        y += round((1-entering)*height*.05 - (1-exiting)*height*.018)
        image.putalpha(image.getchannel("A").point(lambda value:round(value*opacity)))
        canvas.alpha_composite(image,(x,y))
        # Draw accent motion on an independent layer so it respects opacity too.
        accent = Image.new("RGBA",(width,height),(0,0,0,0))
        ad = ImageDraw.Draw(accent)
        radius = min(width,height)*(.041 if g.template=="kinetic_title" else .024)*(.6+.4*entering)
        cx,cy = x+pw-pw*.085,y+ph*.15
        starburst(ad,cx,cy,radius,local*.32,PALETTES[g.palette]["accent"])
        if g.template == "kinetic_title":
            ad.rounded_rectangle((x+pw*.075,y+ph*.91,x+pw*.075+(pw*.85)*min(1,local/g.duration),y+ph*.917),radius=2,fill=PALETTES[g.palette]["accent"])
        accent.putalpha(accent.getchannel("A").point(lambda value:round(value*opacity)))
        canvas.alpha_composite(accent)
    return canvas


def render_overlay(graphics, width, height, workspace, cancel=None):
    if any(g.template == "framecraft" for g in graphics):
        from .framecraft_renderer import render_scene
        return render_scene(graphics[0], width, height, workspace, cancel)
    start = min(g.start for g in graphics)
    end = max(g.start+g.duration for g in graphics)
    frames = math.ceil((end-start)*30)
    target = workspace / "motion-graphics.mov"
    with tempfile.TemporaryFile() as log:
        p = subprocess.Popen([binary("ffmpeg"),"-v","error","-nostdin","-y","-f","rawvideo","-pixel_format","rgba",
                              "-video_size",f"{width}x{height}","-framerate","30","-i","pipe:0","-an","-c:v","png","-pix_fmt","rgba",str(target)],
                             stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        started=time.monotonic()
        try:
            for i in range(frames):
                if cancel and cancel.is_set():
                    raise Cancelled("Animation rendering cancelled")
                if time.monotonic()-started>240:
                    raise TimeoutError("Animation exceeded its four-minute rendering budget")
                p.stdin.write(frame(graphics,width,height,start+i/30).tobytes())
            p.stdin.close()
            while p.poll() is None:
                if cancel and cancel.is_set():
                    raise Cancelled("Animation encoding cancelled")
                if time.monotonic()-started>270:
                    raise TimeoutError("Animation encoding timed out")
                time.sleep(.1)
            if p.returncode:
                log.seek(0)
                raise RuntimeError(log.read().decode(errors="replace")[-1500:])
        except BrokenPipeError:
            log.seek(0)
            raise RuntimeError(log.read().decode(errors="replace")[-1500:])
        finally:
            if p.poll() is None:
                p.kill()
                p.wait()
            if p.stdin and not p.stdin.closed:
                p.stdin.close()
    return target,start,end
