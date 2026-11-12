#!/usr/bin/env bash
# yt-talk URL [OUTDIR] — pull a talk off YouTube into files an agent can read.
#
# Writes OUTDIR/ (default ./talk-<id>):
#   meta.txt        title, channel, date, length, description, chapters
#   transcript.txt  "[mm:ss] text" lines: YouTube captions if they download, else Whisper
#   slides/         one PNG per slide change (scene detection), named by timestamp
#   links.txt       URLs decoded from QR codes on the slides (may be empty)
#
# YouTube often answers the caption endpoint with HTTP 429 from busy IPs; the audio
# and video come from another host and still download, so the Whisper path is the
# reliable one. Set YT_TALK_WHISPER=1 to skip the caption attempt.
set -euo pipefail
url=${1:?usage: yt-talk URL [OUTDIR]}
here=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
ytdlp=(uvx --with curl_cffi yt-dlp --impersonate chrome --no-warnings)

id=$("${ytdlp[@]}" --print id "$url")
out=$(readlink -f "${2:-talk-$id}")
mkdir -p "$out/slides"
cd "$out"

echo "== metadata" >&2
"${ytdlp[@]}" --skip-download --write-info-json -o "src" "$url" >/dev/null
python3 -I - src.info.json >meta.txt <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
print(f"{d['title']}\n{d.get('channel')} | {d.get('upload_date')} | {d.get('duration_string')}\n{d.get('webpage_url')}\n")
print(d.get("description", ""))
ch = d.get("chapters") or []
if ch:
    print("\nCHAPTERS")
    for c in ch:
        s = int(c["start_time"]); print(f"  {s//60:02d}:{s%60:02d} {c['title']}")
EOF

got_subs=0
if [[ -z ${YT_TALK_WHISPER:-} ]]; then
  echo "== captions" >&2
  if "${ytdlp[@]}" --skip-download --write-subs --write-auto-subs --sub-langs en \
       --sub-format vtt -o "src" "$url" >/dev/null 2>caption.err && ls src.*.vtt >/dev/null 2>&1; then
    python3 -I - src.*.vtt >transcript.txt <<'EOF'
import re, sys
last = None
for block in open(sys.argv[1]).read().split("\n\n"):
    m = re.search(r"(\d+):(\d\d):(\d\d)\.\d+ -->", block)
    if not m: continue
    text = " ".join(l for l in block.splitlines()[1:] if "-->" not in l)
    text = re.sub(r"<[^>]+>", "", text).strip()
    if not text or text == last: continue
    last = text
    h, mi, s = map(int, m.groups())
    print(f"[{h*60+mi:02d}:{s:02d}] {text}")
EOF
    [[ -s transcript.txt ]] && got_subs=1
  else
    echo "   captions failed: $(grep -o 'HTTP Error [0-9]*.*' caption.err | head -1) — using Whisper" >&2
  fi
fi

echo "== audio + video" >&2
"${ytdlp[@]}" -f "bestaudio" -o "audio.%(ext)s" "$url" >/dev/null
"${ytdlp[@]}" -f "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080]" -o "video.%(ext)s" "$url" >/dev/null

if [[ $got_subs == 0 ]]; then
  echo "== whisper" >&2
  uvx --python 3.12 --with faster-whisper --with opencv-python-headless \
      --with nvidia-cublas-cu12 --with nvidia-cudnn-cu12 \
      python -I "$here/whisper.py" audio.* transcript.txt
fi

echo "== slides" >&2
# One frame per scene change; showinfo gives the timestamp of each kept frame.
ffmpeg -loglevel info -nostats -i video.* -vf "select='gt(scene,0.25)',showinfo" -vsync vfr \
  slides/tmp-%04d.png 2>&1 | grep -o 'pts_time:[0-9.]*' | cut -d: -f2 >slides/times.txt || true
n=0
while read -r t; do
  n=$((n + 1)); s=${t%.*}
  mv "slides/tmp-$(printf %04d $n).png" "slides/$(printf %02d-%02d $((s / 60)) $((s % 60))).png" 2>/dev/null || true
done <slides/times.txt
# The closing frames usually hold the resources slide.
ffmpeg -loglevel error -sseof -8 -i video.* -frames:v 1 -update 1 slides/zz-end.png || true
rm -f slides/times.txt slides/tmp-*.png

uvx --with opencv-python-headless python -I "$here/qr.py" slides/*.png >links.txt || true

echo "$out"
echo "  $(wc -l <transcript.txt) transcript lines ($([[ $got_subs == 1 ]] && echo captions || echo whisper)), $(ls slides | wc -l) slides, $(wc -l <links.txt) QR links" >&2
