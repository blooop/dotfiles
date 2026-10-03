---
name: stable
description: Triage kinisi_ros stable promotion, nightly and HIL rig runs — find every hidden error, sort each into transient, already fixed, known flake or real, and name the culprit and owner. Use when asked why stable, the nightly or the hilrig failed, what broke overnight, or given a run link from any of those workflows.
argument-hint: "[run URL or id ...] (default: the latest stable, nightly and HIL runs)"
---

# Stable triage

Take the stable promotion (`stable-promotion.yaml`) and nightly (`ci.yaml`, scheduled)
runs on `main`, and the HIL bench (`hil-bench.yaml`) run on the `stable` branch, from
"something is red" to one **finding** per error, each with a class, evidence, and an
owner. Check all three every time: each runs checks the others do not, and the HIL
bench is the only one on the physical rig. The deliverable is a report. A fix is a second, separate decision.

A run's conclusion is not evidence. Many steps carry `continue-on-error`, so a green run
can hide a step that exited 1, and a checkout that fails once and passes on retry leaves
only an annotation. Scan every run, green ones too.

## 1. Scan

The alerts for these runs land in the Slack channel `#humanoid-ci-alerts`
(`C0BFU3DUDQT`). When a Slack tool is attached, read the channel's messages since the
last nightly first: an alert names a run to scan in addition to `--latest`, and a thread
reply may already say who is on it. When no Slack tool is attached, say so in the
report and scan `--latest` only. An alert is a pointer, never evidence: the scan is.

```bash
D=/tmp/claude-$(id -u)/stable-$(date +%F); mkdir -p "$D"
python3 ~/.claude/skills/stable/scripts/scan_run.py --save-dir "$D" ${ARGUMENTS:---latest} | tee "$D/scan.txt"
```

It prints one finding per `##[error]` line: the job, the step, the step's own result,
whether a retry followed, the log lines before the error (`|`) and after it (`>`).
For a HIL run it also lists the rig's own **concerns** (`!` lines), pass or fail. The
job logs stay in `$D` for grepping; fetch them again only for a run not scanned. Done
when every run has its `N finding(s)` line. Zero findings in every run ends the skill:
report that, with the run links.

## 2. Classify

First find the check's **inputs**: the files the failing check itself reads, from the
script or target it runs (an `_INPUT_PATHS` list, a Bazel target's srcs, a digest's
source set). The workflow's `paths:` filter is broader than the inputs; use it only when
the check names no input set.

Give every finding exactly one class, and the evidence that class demands:

- **transient**: the error is infrastructure (a registry or mirror 404,
  `Repository not found` on checkout, a network timeout), and the `>` lines show the
  retry that passed. Evidence: the error line and that retry line. `retried: yes` with
  no passing line after it is not yet transient. An infrastructure error with no retry
  at all is **real**: the defect is the missing retry, and the owner is whoever owns
  that step.
- **already fixed**: a commit on `main` after the run's head touches the inputs, or an
  open PR does. Look in the history first, since a merged fix never shows in a PR
  search: `git log --oneline <head>..origin/main -- <inputs>` in a blobless clone
  (`git clone --filter=blob:none` under `/tmp/claude-$(id -u)/`). Then
  `gh pr list --search "<test or file name>"` for open work. Evidence: the commit or
  PR link.
- **known flake**: an open issue names this test or step. Evidence: the issue link,
  from `gh issue list --search "<test name>"`.
- **real**: none of the above. Find the **culprit**, the commit that first made the
  check fail. The **owner** is that commit's PR author. Evidence: the culprit commit
  and PR links.

Find the culprit with the route that fits the check:

- **A stamp or digest check** (committed hash against a hash of the inputs): find the
  commit that wrote the committed hash with `git log -S '<committed hash>'`, then walk
  first-parent commits after it and report the first that changes the inputs. A run
  history walk is slow here, since the check can stay red for weeks.
- **A test or other check**: walk earlier nightly runs of the same step until one is
  clean. A `continue-on-error` step reports `success` either way, so grep each run's
  log for the check's own pass or fail text. Then run
  `git log <clean head>..<head> -- <inputs>` to narrow it to a commit.
- When the log and history do not settle it, reproduce the check at the culprit and
  at its parent in `dl kinisi-robotics/kinisi_ros@main`.

### HIL runs

A HIL run's `##[error]` says only `bin/kr failed`; the cause is in the `!` concerns.
Scan the newest passing HIL run on `stable` as well, and split the concerns:

- A concern that also appears in the passing run is **standing**: a rig problem that
  every run carries and no run fails on. Report each once, as its own finding, since
  nothing else surfaces it. A concern about motors, the e-stop or anything energised
  goes first in the report, whatever the class of the rest.
- The first concern, in log order, that the passing run lacks is this run's cause.
  Classify it as above. The rig rarely has a culprit commit; when the cause is
  infrastructure, list the recent `stable` HIL runs that hit the same concern instead:
  `gh api "repos/kinisi-robotics/kinisi_ros/actions/workflows/hil-bench.yaml/runs?branch=stable&per_page=10&created=>=<date>"`.

Done when every finding has one class and a link that backs it. A real finding with no
culprit says so, and names the runs or commits you compared.

After the class, check whether `main` still fails: `git log <fix>..origin/main -- <inputs>`
shows whether the inputs moved again after the fix. Push runs on `main` are often
cancelled by concurrency, so the next nightly or a local run of the check is the
evidence, not a push run.

## 3. Report

One bullet per finding, the link first: safety concerns, then real, standing, known
flake, already fixed, transient. Search for an open issue on each real or standing
finding (`gh issue list --search`) and link it when one exists. Name a run by its
workflow and date, "Stable 2026-09-30", "Nightly 2026-09-30" or "HIL 2026-09-30":

```
- [Nightly 2026-09-30 — Check the collision artifacts against their inputs](<run url>)
  real · hidden by continue-on-error · culprit [#NNNN — title](<pr url>) by @owner
  error: The collision inputs no longer match the committed artifacts
  main: still failing — inputs moved again in [#NNNN — title](<pr url>)
```

Name what hid a finding when the step's own result is `success`: "hidden by
continue-on-error" when the step carries it, "hidden by a retry" when a retry passed.
That is the finding a person reading the run page misses. Add the `main:` line whenever
the fix has already been overtaken. End the skill here unless the user asks for a fix.

## 4. Fix (only when asked)

One fix per real root cause, and only where no open PR already carries it: run the
already-fixed search from step 2 again at this point, since other sessions work in
parallel. When the culprit PR is still open, the fix belongs in that PR; tell its owner
instead of stacking a second one.

Build the fix red first with the `tdd` skill: a failing check that reproduces the
finding, then the change that turns it green. The runner is
`dl kinisi-robotics/kinisi_ros@<branch>`, and commits happen inside that container.
Open the PR with the `pr` skill, and link the run and the finding in its body.
