"""slides: one full-size PNG per slide, at each scene change and each chapter start, plus the closing frame.

Scene detection runs on a 480 px copy at threshold 0.05: conference videos show the slide
as part of a larger frame (speaker inset, banner), so a slide change scores low. A light
slide replacing another light slide scores about 0.06, and speaker movement about 0.03.
At 0.08 one talk lost every slide between two chapters; 0.25 finds none at all. Chapter
starts are added because a chapter almost always opens on a new slide, so a missed scene
change still yields that slide. A candidate that looks like the slide before it is dropped.
"""
import os
import re
import subprocess

from talklib import YTDLP, emit, first, fmt, log, read_state, run

SCENE = 0.05
# Mean absolute difference (0-255) on a 64x36 grey thumbnail below which two frames are
# the same slide. On one talk the same slide measured 1.8-3.0 (speaker movement in the
# inset) and a new slide 6.4 or more.
SAME = 4.5


def thumb(path):
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", path, "-vf", "scale=64:36,format=gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout


def diff(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / max(len(a), 1)


def mmss(s):
    m, sec = s.split(":")
    return int(m) * 60 + int(sec)


state = read_state()
out = state["work_dir"]
sdir = os.path.join(out, "slides")
os.makedirs(sdir, exist_ok=True)

if not first(out, "video."):
    run(YTDLP + ["-f", "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080]",
                 "-o", "video.%(ext)s", state["url"]], cwd=out)
video = first(out, "video.")

r = run(["ffmpeg", "-nostats", "-i", video, "-vf", f"scale=480:-1,select='gt(scene,{SCENE})',showinfo",
         "-f", "null", "-"])
times = [0.0] + [float(t) for t in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
times += [float(mmss(c["start"])) for c in state["chapters"]]

paths, last = [], None
for t in sorted(set(times)):
    # Take the frame 2 s after the change, when the slide has settled.
    p = os.path.join(sdir, fmt(t).replace(":", "-") + ".png")
    if p in paths:
        continue  # two candidates in the same second share a file name
    run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t + 2), "-i", video, "-frames:v", "1", p])
    if not os.path.exists(p):
        continue
    th = thumb(p)
    d = diff(th, last) if last is not None else 255.0
    log(f"slide {fmt(t)} differs by {d:.1f}")
    if d < SAME:
        os.remove(p)
        continue
    paths.append(p)
    last = th

# The closing frames usually hold the resources slide.
end = os.path.join(sdir, "zz-end.png")
run(["ffmpeg", "-loglevel", "error", "-y", "-sseof", "-8", "-i", video, "-frames:v", "1", "-update", "1", end])
if os.path.exists(end):
    paths.append(end)

emit({"slides_dir": sdir, "slide_paths": paths})
