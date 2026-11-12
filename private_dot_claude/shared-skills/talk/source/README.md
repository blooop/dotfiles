# Where this procedure came from

Compiled by hand on 2026-11-03 from one Claude Code session that extracted
"Make Your AI Agents Predictable With Graph Engineering" (Zachary Blumenfeld, Neo4j,
AI Engineer NYC 2026, https://www.youtube.com/watch?v=g_NgCLTibiM). The format is AIP
(https://github.com/zach-blumenfeld/aip), the graph-shaped skill format that talk presents.

- `trace.md`: what the session tried, in order, what failed and why, and what worked.
- `skill-v1.md`: the prose version of this skill, written before the compile.
- `yt-talk-v1.sh`: the one-shot script v1 called. Kept as history only: it drifted from the
  step scripts (scene threshold 0.25, which finds no slides) and nothing runs it now.

## What became what

| know-how | step | kind |
|---|---|---|
| metadata and chapters come from the info JSON | fetch-meta | execution |
| captions 429 → audio + Whisper; pasted panel wins | transcript | execution (the fallback is code, not a router: one producer per key) |
| scene threshold 0.05 on a 480 px copy, plus each chapter start, near-duplicates dropped; closing frame | slides | execution |
| QR codes are small, so upscale 2–3× before decoding | qr-links | execution |
| read everything, fix misheard names from slides, read the URL text under QR codes | read-talk | client_task |
| check each link before calling it real | check-links | execution |
| summary or examples | goal → by-goal | decision + router |
| cite [mm:ss], keep speaker / slide / own view apart | summarise | client_task |
| clone as untrusted, run in a throwaway container | examples | client_task |

## Dropped on purpose

- The `--js-runtimes` / deno warning from yt-dlp: downloads worked without it.
- Retrying captions with a sleep: the 429 held after a retry with impersonation.
