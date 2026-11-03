"""transcript: YouTube captions if they download, else Whisper on the audio.

YouTube often answers the caption endpoint with HTTP 429 from a busy IP, and agents
running in parallel make it worse. The audio comes from a different host and still
downloads, so Whisper is the fallback that works. A pasted "Show transcript" panel
(state key pasted_transcript, non-empty) wins over both.
"""
import os
import re
import shutil

from talklib import HERE, YTDLP, emit, first, log, read_state, run


def vtt_to_lines(path):
    lines, last = [], None
    for block in open(path).read().split("\n\n"):
        m = re.search(r"(\d+):(\d\d):(\d\d)\.\d+ -->", block)
        if not m:
            continue
        text = " ".join(l for l in block.splitlines()[1:] if "-->" not in l)
        text = re.sub(r"<[^>]+>", "", text).strip()
        if text and text != last:
            last = text
            h, mi, s = map(int, m.groups())
            lines.append(f"[{h * 60 + mi:02d}:{s:02d}] {text}")
    return lines


state = read_state()
out = state["work_dir"]
path = os.path.join(out, "transcript.txt")
source, note = None, ""

if state.get("pasted_transcript", "").strip():
    open(path, "w").write(state["pasted_transcript"])
    source = "pasted"

if source is None:
    r = run(YTDLP + ["--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "en",
                     "--sub-format", "vtt", "-o", "src", state["url"]], cwd=out, check=False)
    vtt = first(out, "src.en")
    if r.returncode == 0 and vtt:
        lines = vtt_to_lines(vtt)
        if lines:
            open(path, "w").write("\n".join(lines) + "\n")
            source = "captions"
    else:
        m = re.search(r"HTTP Error \d+[^\n]*", r.stderr)
        note = f"captions failed: {m.group(0) if m else r.stderr.strip()[-200:]}"
        log(note)

if source is None:
    if not first(out, "audio."):
        run(YTDLP + ["-f", "bestaudio", "-o", "audio.%(ext)s", state["url"]], cwd=out)
    run(["uvx", "--python", "3.12", "--with", "faster-whisper", "--with", "nvidia-cublas-cu12",
         "--with", "nvidia-cudnn-cu12", "python", "-I", os.path.join(HERE, "whisper.py"),
         first(out, "audio."), path])
    source = "whisper-gpu" if shutil.which("nvidia-smi") else "whisper-cpu"

emit({
    "transcript_path": path,
    "transcript_source": source,
    "transcript_lines": sum(1 for _ in open(path)),
    "transcript_note": note,
})
