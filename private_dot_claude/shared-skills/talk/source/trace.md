# Session trace, 2026-11-03

The decision trace this procedure was distilled from. Host: RTX 5090, uvx, ffmpeg, no
yt-dlp installed.

1. `uvx yt-dlp --write-auto-subs --sub-langs "en.*"` → `HTTP Error 429: Too Many
   Requests` on the caption endpoint. Other agents on the same host hit the same 429 the
   same day.
2. Retry with `--with curl_cffi --impersonate chrome --sleep-subtitles 5` → 429 again.
   Lesson: the caption endpoint is blocked for the IP; retries do not help.
3. `-f 251/bestaudio -x` → audio downloaded at once (48 MB). The audio host is not the
   caption host.
4. faster-whisper large-v3 on CUDA failed twice:
   - missing cuBLAS/cuDNN: fixed by `--with nvidia-cublas-cu12 nvidia-cudnn-cu12` and
     LD_LIBRARY_PATH set before the process starts;
   - `av.open() got an unexpected keyword argument 'metadata_errors'` (PyAV 15+);
     pinning `av<15` tried a source build and failed. Fixed by decoding with ffmpeg to a
     16 kHz int16 array and passing the array.
   Then: 20:35 of talk transcribed in 59 s.
5. The user pasted YouTube's "Show transcript" panel. It is good captions; the procedure
   takes it as `pasted_transcript`.
6. Links: none in the transcript; they are QR codes on slides. Frames at the chapter
   times showed the resources slide. OpenCV decoded no QR at 1× and all 7 at 2–3×. The
   slide also prints each URL as text under its code (the paper id only appears there).
7. Slide changes: ffmpeg scene threshold 0.25 found 0 changes (the slide is about 70% of
   the frame, with a speaker inset); 0.08 on a 480 px copy found 23; 0.04 found 73.
8. Every link was checked with `gh repo view`; all resolved.
9. The talk's AIP example ran in `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`:
   `aip run` paused at the decision, `aip resume` with answers routed and ran the script.

## Run 2: a fresh agent drives the graph (2026-11-03)

The download steps ran on the host (fetch-meta 2 s, transcript 49 s with Whisper after a
caption 429, slides 50 s for 22 slides, qr-links 12 s for 8 links). A fresh agent with
only this skill ran read-talk → check-links (16 links, 0 broken) → goal (summary) →
summarise. Its feedback, and what revision 2 changed:

- slide_paths held duplicates (two changes in one second share a file name) → deduplicated.
- URLs that differed by a trailing slash were checked twice → normalised.
- Unclear whether a paper id belongs in slide_links → read.md says to write it as a URL.
- "The voice the user's instructions ask for" read two ways → summarise.md says chat voice.
- No home for a name no slide confirms → read.md says list it under "Not confirmed".
- Not changed: two QR codes still fail to decode (the slide text carries the URL), and
  the decision step has no confidence key (the runtime block defines that; do not add one).

## Run 3: a review on another talk (2026-11-12)

"What Does an AI Engineer Do Now?" (Aparna Dhinakaran, Arize AI,
https://www.youtube.com/watch?v=ImnZ7s68jw8, 15:27, 14 chapters). Captions 429 again;
Whisper on the GPU took 56 s. What revision 3 changed:

- Slides: threshold 0.08 found 10 frames and none between 04:45 and 10:21, which held five
  slides. Light slides on a light slide score about 0.06; speaker movement about 0.03. Now
  0.05, plus a frame at each chapter start, and a frame whose 64x36 grey thumbnail differs
  from the last kept one by less than 4.5 (mean, 0-255) is dropped. Same slide measured
  1.8-3.0 (speaker, banner swap), new slide 6.4 or more. Result: 20 frames here (every
  slide); 41 on the Neo4j talk (was 23; the extra frames are its live demo).
- Captions: auto-captions roll, so each cue repeats the previous line, and every phrase
  came out two or three times. The parser now keeps only lines the previous cue lacked.
- qr-links: a decoder failure now fails the step instead of returning an empty list.
- `scripts/yt-talk` moved to `source/yt-talk-v1.sh`: it had drifted (threshold 0.25).
- Not changed: `end` does not return `summary_path` or `examples_report_path`. Each is
  produced on one branch only, and `end` inputs must all be present, so the format cannot
  require either. Both files are in `work_dir`.
