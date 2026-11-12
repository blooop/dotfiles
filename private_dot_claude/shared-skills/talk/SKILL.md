---
name: talk
description: Pull a YouTube talk into a transcript, its slides as images and the links on them, then summarise it or run its code examples. Use when given a YouTube link and asked to summarise, explain, take notes on, or find the links, code or demos from a talk, video or presentation.
metadata:
  aip-version: "0.6a1"
  author: ags
  version: "3"
---

# AIP runtime — format 0.6a1

You are executing an Agent Instruction Protocol (AIP) procedure: the fenced YAML block in this skill's `SKILL.md`. AIP is a protocol for cheaply, quickly, and accurately executing multi-step tasks as a graph of typed steps. You drive the run and execute every step yourself, following the semantics below.

Critical terminology:

- **Client**: you, the agent running this procedure; the `client_task` step kind is named for it. You supply each step's input, run its script, answer its questions by your own judgment, perform its task, follow its router, and make the final call at every step.
- **State**: the one JSON object a run carries. Each step declares the keys it reads as `inputs`; `execution` and `client_task` steps declare the keys they add as `outputs`, and a `decision` adds one key per question.
- **Step kinds**: `execution` runs a script, `decision` asks typed questions about the state, `client_task` hands work to you, `router` branches on a value in the state, `end` declares the procedure's result.

## Execution

The state starts as the start step's `inputs` and flows along `inputs_to`; each step adds its outputs to it. Every key is produced by exactly one step, so keys accumulate and nothing is overwritten. A step runs only if the state holds every key it declares in `inputs`, with the declared types; check that before each step. A step sees only those keys: give it its declared `inputs` and nothing else from the state. You have the final say at every step.

- **`execution`**: before the first one, check that this machine has everything `requires` names (the interpreter at its minimum version, the packages, the tools); if anything is missing, stop and name all of it. Run `script` from its folder, launched with the step's `command` when it has one and `python <script>` otherwise, with one JSON object on stdin, `{"state": <the step's inputs>, "assets": {<file stem>: <content>}, "expects": <the next step's inputs>}`. The script writes one JSON object to stdout holding exactly the step's `outputs`; add them to the state. A non-zero exit, or output missing a declared key, fails the step: stop there and report it rather than doing the step by hand.
- **`decision`**: answer each question from the step's inputs, and from the run so far only when the step sets `history: true`. Each answer collapses to one value under its question name and is added to the state: a noul to `true`/`false`, a choice to its label, a score to its level number. `thresholds` name the questions where an uncertain answer matters most; when your answer to one is a close call, reconsider it before continuing.
- **`client_task`**: render `template` with `{key}` from the step's inputs, `{assets[stem]}` for its assets, and `{meta.name}` for the skill name. Perform the task, loading `references` if their descriptions apply, and produce the step's `outputs`; add them to the state.
- **`router`**: read the state's `branch_on` key and continue at `branches[value]`. A value with no branch is an error.
- **`end`**: the state must hold `end`'s `inputs`. Those keys are the procedure's result.

```yaml
purpose: >
  Turn a YouTube talk into files an agent can read (metadata, transcript, slides, links),
  read it properly, then either summarise it or run its code examples. Scripts do the
  downloading and the fallbacks; the agent only reads, judges and writes.

trigger_when:
  - The user gives a YouTube link and asks to summarise, explain or take notes on the talk.
  - The user asks for the links, code, repos or papers from a talk or video.
  - The user asks to explore or run the examples shown in a talk.

do_not_use_when:
  - The video is music, a stream with no speech, or the user wants only the video file.
  - The link is not YouTube and yt-dlp does not support the site.

requires:
  interpreter:
    name: python
    version: "3.10"
  tools:
    - uvx
    - ffmpeg
    - gh

steps:
  - name: fetch-meta
    kind: execution
    description: Write title, description and chapters to meta.txt in the work directory.
    inputs:
      - name: url
        type: string
        description: The YouTube URL of the talk.
      - name: out_dir
        type: string
        description: An absolute, empty work directory, in the scratchpad.
      - name: request
        type: string
        description: What the user asked for, in their words.
      - name: pasted_transcript
        type: string
        description: The YouTube "Show transcript" text if the user pasted it, else an empty string.
    script: scripts/fetch_meta.py
    timeout: 120
    outputs:
      - name: work_dir
        type: string
      - name: video_id
        type: string
      - name: title
        type: string
      - name: duration_s
        type: integer
      - name: chapters
        type: list[*]
        description: Each chapter as start (mm:ss) and title; empty when the video has none.
      - name: meta_path
        type: string
    inputs_to: transcript

  - name: transcript
    kind: execution
    description: Use the pasted transcript, else YouTube captions, else Whisper on the audio when captions fail (HTTP 429).
    inputs:
      - name: url
        type: string
      - name: work_dir
        type: string
      - name: pasted_transcript
        type: string
    script: scripts/transcript.py
    timeout: 1800
    outputs:
      - name: transcript_path
        type: string
      - name: transcript_source
        type: string
        description: pasted, captions, whisper-gpu or whisper-cpu.
      - name: transcript_lines
        type: integer
      - name: transcript_note
        type: string
        description: Why captions were not used, or empty.
    inputs_to: slides

  - name: slides
    kind: execution
    description: Download the video and save one full-size PNG per slide change and chapter start, plus the closing frame.
    inputs:
      - name: url
        type: string
      - name: work_dir
        type: string
      - name: chapters
        type: list[*]
    script: scripts/slides.py
    timeout: 1800
    outputs:
      - name: slides_dir
        type: string
      - name: slide_paths
        type: list[*]
    inputs_to: qr-links

  - name: qr-links
    kind: execution
    description: Decode the QR codes on the slides into URLs.
    inputs:
      - name: slide_paths
        type: list[*]
    script: scripts/qr_links.py
    timeout: 600
    outputs:
      - name: qr_links
        type: list[*]
        description: Each decoded QR code as url and the slide it was on.
    inputs_to: read-talk

  - name: read-talk
    kind: client_task
    description: Read the metadata, the whole transcript and the slides; fix misheard names; write notes.md.
    inputs:
      - name: title
        type: string
      - name: meta_path
        type: string
      - name: chapters
        type: list[*]
      - name: transcript_path
        type: string
      - name: transcript_source
        type: string
      - name: transcript_lines
        type: integer
      - name: slides_dir
        type: string
      - name: qr_links
        type: list[*]
    template: assets/read.md
    outputs:
      - name: notes_path
        type: string
      - name: slide_links
        type: list[*]
        description: Every URL printed on a slide, as strings.
      - name: name_fixes
        type: list[*]
    inputs_to: check-links

  - name: check-links
    kind: execution
    description: Confirm each link resolves; GitHub repos through gh, the rest by HTTP.
    inputs:
      - name: qr_links
        type: list[*]
      - name: slide_links
        type: list[*]
    script: scripts/check_links.py
    timeout: 300
    outputs:
      - name: link_report
        type: list[*]
        description: Each link as url, ok and detail.
      - name: broken_links
        type: integer
    inputs_to: goal

  - name: goal
    kind: decision
    description: Decide what the user wants from the talk.
    inputs:
      - name: request
        type: string
    questions:
      goal:
        type: choice
        instructions: >
          What does the user want from the talk? Summary means notes, an explanation, the key
          ideas or the links. Examples means to find, clone, run or try the code or demos the
          talk shows. When the request asks for both, choose examples: its report includes
          the links and the notes stay on disk.
        criteria:
          summary: Notes, an explanation, the main ideas, or the links.
          examples: Find, clone, run or try the code or demos from the talk.
    thresholds:
      goal: 0.6
    inputs_to: by-goal

  - name: by-goal
    kind: router
    description: A summary ends in summary.md; examples end in a report of what ran.
    branch_on: goal
    branches:
      summary: summarise
      examples: examples

  - name: summarise
    kind: client_task
    description: Write summary.md with [mm:ss] cites and every link, the unconfirmed ones marked.
    inputs:
      - name: title
        type: string
      - name: request
        type: string
      - name: notes_path
        type: string
      - name: link_report
        type: list[*]
    template: assets/summarise.md
    outputs:
      - name: summary_path
        type: string
    inputs_to: end

  - name: examples
    kind: client_task
    description: Clone the confirmed repos as untrusted data, run the smallest example in a throwaway container, write examples.md.
    inputs:
      - name: title
        type: string
      - name: request
        type: string
      - name: notes_path
        type: string
      - name: link_report
        type: list[*]
    template: assets/examples.md
    outputs:
      - name: examples_report_path
        type: string
    inputs_to: end

  - name: end
    kind: end
    description: The notes, the checked links and how the transcript was made.
    inputs:
      - name: notes_path
        type: string
      - name: link_report
        type: list[*]
      - name: transcript_source
        type: string

anti_patterns:
  - Summarising from WebFetch of the YouTube page, which holds no transcript.
  - Stopping at a caption HTTP 429 instead of using Whisper on the audio.
  - Starting several downloads of the same video at once from parallel agents.
  - Guessing a misheard name instead of reading it off a slide.
  - Running a talk's example code on the host instead of in a throwaway container.
```
