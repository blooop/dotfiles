"""fetch-meta: title, description and chapters from YouTube into <out_dir>/meta.txt."""
import json
import os

from talklib import YTDLP, emit, fmt, read_state, run

state = read_state()
out = os.path.abspath(os.path.expanduser(state["out_dir"]))
os.makedirs(out, exist_ok=True)
run(YTDLP + ["--skip-download", "--write-info-json", "-o", "src", state["url"]], cwd=out)
d = json.load(open(os.path.join(out, "src.info.json")))

chapters = [{"start": fmt(c["start_time"]), "title": c["title"]} for c in d.get("chapters") or []]
lines = [
    d["title"],
    f"{d.get('channel')} | {d.get('upload_date')} | {d.get('duration_string')}",
    d.get("webpage_url", state["url"]),
    "",
    d.get("description", ""),
]
if chapters:
    lines += ["", "CHAPTERS"] + [f"  {c['start']} {c['title']}" for c in chapters]
meta_path = os.path.join(out, "meta.txt")
open(meta_path, "w").write("\n".join(lines) + "\n")

emit({
    "work_dir": out,
    "video_id": d["id"],
    "title": d["title"],
    "duration_s": int(d.get("duration") or 0),
    "chapters": chapters,
    "meta_path": meta_path,
})
