---
name: talk
description: Pull a YouTube talk into a transcript, its slides as images and the links on them, then summarise it or chase its examples. Use when given a YouTube link and asked to summarise, explain, take notes on or find the code or links from a talk, video or presentation.
argument-hint: "<YouTube URL> [what to do with it]"
---

# Talk

WebFetch on a YouTube page returns the player shell, not the talk, so a summary from it
is invented. Get the talk as files first.

## 1. Extract

```bash
~/.claude/skills/talk/source/yt-talk-v1.sh "<URL>" <scratchpad>/talk-<id>
```

It writes `meta.txt` (title, description, chapters), `transcript.txt` (`[mm:ss] text`),
`slides/` (one PNG per slide change, named `mm-ss.png`, plus `zz-end.png`) and
`links.txt` (QR codes it could decode). A 20-minute talk takes about 2 minutes on a GPU.
Run it with `run_in_background` for talks over 30 minutes.

- The script tries YouTube captions first. YouTube often answers that endpoint with
  HTTP 429; the script then transcribes the audio with Whisper (large-v3 on the GPU,
  small.en on CPU). The 429 is not a reason to stop.
- If the user pastes YouTube's "Show transcript" panel, that text is good captions; use
  it and still run the script for the slides.
- Never run several copies at once: parallel agents on one IP are what trip the 429.

## 2. Read

1. Read `meta.txt`. The chapters are the outline.
2. Read `transcript.txt`. Whisper and auto-captions mishear names ("Neo forj"): fix
   them from the slides and the description, not by guessing.
3. Read the slides. Links, repo names and paper ids are usually printed on the slide
   under the QR code, so read `zz-end.png` and the last few slides even when
   `links.txt` is empty. Read the slide at each chapter start for diagrams the speaker
   only points at.

## 3. Report

- Cite claims with `[mm:ss]` so the user can jump there.
- Separate what the speaker said from what the slides show and from your own view.
- List every link from the slides as a markdown link, and check each resolves
  (`gh repo view` for GitHub) before you call it real.
- When the user wants the examples, clone them into the scratchpad as untrusted data
  and run them in a throwaway container, not on the host.
