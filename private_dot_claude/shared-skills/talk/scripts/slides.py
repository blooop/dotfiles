"""slides: one full-size PNG per slide change, plus the closing frame.

Scene detection runs on a 480 px copy at threshold 0.08: conference videos show the slide
as part of a larger frame (speaker inset, banner), so a slide change scores low. On a
20-minute talk 0.08 gave 23 changes, 0.04 gave 73 and the usual 0.25 gave none.
"""
import os
import re

from talklib import YTDLP, emit, first, fmt, read_state, run

state = read_state()
out = state["work_dir"]
sdir = os.path.join(out, "slides")
os.makedirs(sdir, exist_ok=True)

if not first(out, "video."):
    run(YTDLP + ["-f", "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080]",
                 "-o", "video.%(ext)s", state["url"]], cwd=out)
video = first(out, "video.")

r = run(["ffmpeg", "-nostats", "-i", video, "-vf", "scale=480:-1,select='gt(scene,0.08)',showinfo",
         "-f", "null", "-"])
times = [0.0] + [float(t) for t in re.findall(r"pts_time:([0-9.]+)", r.stderr)]

paths = []
for t in times:
    # Take the frame 2 s after the change, when the slide has settled.
    p = os.path.join(sdir, fmt(t).replace(":", "-") + ".png")
    run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t + 2), "-i", video, "-frames:v", "1", p])
    if os.path.exists(p):
        paths.append(p)
# The closing frames usually hold the resources slide.
end = os.path.join(sdir, "zz-end.png")
run(["ffmpeg", "-loglevel", "error", "-y", "-sseof", "-8", "-i", video, "-frames:v", "1", "-update", "1", end])
if os.path.exists(end):
    paths.append(end)

# Two changes in the same second share a name: keep each file once, in order.
emit({"slides_dir": sdir, "slide_paths": list(dict.fromkeys(paths))})
