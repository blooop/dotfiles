#!/usr/bin/env python3
"""List every error in a GitHub Actions run, including the ones a green run hides.

A run's conclusion is not the evidence: a step with continue-on-error exits 1 and
still reports success, and a checkout that fails once and passes on retry leaves
only an annotation. This script reads the failure annotations of every job, then
the log of each job that has one, and prints one finding per ##[error] line with
the step that emitted it, the lines just before it, and the lines after it up to
the next command, so a retry's outcome is on the page.

Usage:
  scan_run.py RUN [RUN ...]        run ids or run URLs
  scan_run.py --latest             the newest completed stable promotion and nightly runs on main, and HIL bench run on stable
                                   (a HIL run also lists the rig's own "!" concern lines, pass or fail)
  options: --repo OWNER/REPO (default kinisi-robotics/kinisi_ros), --context N (default 12),
           --save-dir DIR (keep each job log as DIR/<run>-<job>.log, for grepping later)
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

# (workflow, branch, event): stable promotion and the nightly run on main; the HIL
# bench runs on the physical rig after each push to the stable branch.
LATEST_WORKFLOWS = [("stable-promotion.yaml", "main", None), ("ci.yaml", "main", "schedule"),
                    ("hil-bench.yaml", "stable", None)]
# The API's default ordering skips recent runs of these workflows; a created-window
# query is the one that returns them.
LATEST_WINDOW_DAYS = 4
RETRY = re.compile(r"trying again|retrying|Retry(ing)? in|attempt \d+ of \d+", re.I)
ANSI = re.compile(r"(\x1b|\^\[)\[[0-9;]*m")  # gh prints some codes as literal ^[
NEXT_STEP = ("##[group]Run ", "##[error]")
# The HIL rig reports its own problems as plain log lines, not ##[error], and some
# of them (a device that did not converge, an e-stop that did not engage) show up in
# runs that pass. For a HIL run, every rig job log is read and these are listed.
HIL_WORKFLOW = "hil-bench.yaml"
CONCERN = re.compile(r"investigate manually|\bFAIL\s*$|✗|failed on:|^Failed benches:")


def gh(*args):
    for attempt in range(3):
        out = subprocess.run(["gh", *args], capture_output=True, text=True)
        if out.returncode == 0:
            return out.stdout
        # A secondary rate limit clears in about a minute; other failures are brief.
        time.sleep((60 if "rate limit" in out.stderr else 5) * (attempt + 1))
    sys.exit(f"gh {' '.join(args)} failed three times: {out.stderr.strip()}")


def gh_json(path, jq):
    return [json.loads(line) for line in gh("api", "--paginate", path, "-q", f"{jq} | tojson").splitlines() if line]


def latest_runs(repo):
    since = (datetime.date.today() - datetime.timedelta(days=LATEST_WINDOW_DAYS)).isoformat()
    runs = []
    for workflow, branch, event in LATEST_WORKFLOWS:
        query = f"repos/{repo}/actions/workflows/{workflow}/runs?branch={branch}&per_page=100&created=>={since}"
        if event:
            query += f"&event={event}"
        done = gh_json(query, '[.workflow_runs[] | select(.status == "completed" and .conclusion != "cancelled")]'
                              ' | max_by(.created_at) | .id')
        if done and done[0]:
            runs.append(str(done[0]))
        else:
            print(f"(no completed {workflow} run on {branch} since {since})", file=sys.stderr)
    return runs


def step_at(steps, stamp):
    """The first step still open at this log line. Step times have one-second
    resolution, so a step that ends in the same second the next one starts still
    owns its own last line. ISO times sort as strings."""
    for step in steps:
        if step.get("started_at") and step["started_at"] <= stamp <= (step.get("completed_at") or stamp):
            return step
    return {"name": "unknown", "conclusion": "unknown"}


def run_id_of(arg):
    match = re.search(r"runs/(\d+)", arg)
    return match.group(1) if match else arg


def scan(repo, run_id, context, save_dir):
    run = json.loads(gh("api", f"repos/{repo}/actions/runs/{run_id}", "-q",
                        "{name, path, event, conclusion, head_sha, created_at, html_url}"))
    print(f"== {run['name']} | {run['event']} | {run['conclusion']} | {run['created_at']} | "
          f"head {run['head_sha'][:9]} | {run['html_url']}")
    jobs = gh_json(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100",
                   ".jobs[] | {id, name, conclusion}")
    hil = run["path"].endswith(HIL_WORKFLOW)
    findings = 0
    for job in jobs:
        annotations = gh_json(f"repos/{repo}/check-runs/{job['id']}/annotations",
                              '.[] | select(.annotation_level == "failure") | .message')
        rig_job = hil and job["conclusion"] not in ("skipped", None)
        if not annotations and not rig_job and job["conclusion"] not in ("failure", "cancelled", "timed_out"):
            continue
        # gh labels most log lines "UNKNOWN STEP", so place each line by its timestamp.
        steps = json.loads(gh("api", f"repos/{repo}/actions/jobs/{job['id']}", "-q",
                              "[.steps[] | {name, conclusion, started_at, completed_at}]"))
        log = gh("run", "view", run_id, "-R", repo, "--log", "--job", str(job["id"]))
        if save_dir:
            path = os.path.join(save_dir, f"{run_id}-{job['id']}.log")
            with open(path, "w") as f:
                f.write(ANSI.sub("", log))
            print(f"   (log saved: {path})")
        lines = []
        for raw in log.splitlines():
            parts = raw.split("\t", 2)
            if len(parts) == 3:
                stamp, _, text = ANSI.sub("", parts[2]).partition(" ")
                lines.append((step_at(steps, stamp[:19] + "Z"), text))
        for i, (step, text) in enumerate(lines):
            if "##[error]" not in text:
                continue
            findings += 1
            after = []
            for later_step, later in lines[i + 1:i + 1 + context]:
                if later_step is not step or later.startswith(NEXT_STEP):
                    break
                after.append(later)
            print(f"\n-- job: {job['name']} ({job['conclusion']}) | step: {step['name']} "
                  f"(step result: {step['conclusion']}) | retried: {'yes' if RETRY.search(' '.join(after)) else 'no'}")
            print(f"   error: {text.replace('##[error]', '').strip()}")
            for _, before in lines[max(0, i - context):i]:
                if before.strip():
                    print(f"   | {before}")
            for later in after:
                if later.strip():
                    print(f"   > {later}")
        if rig_job:
            concerns = list(dict.fromkeys(text.strip() for _, text in lines if CONCERN.search(text)))
            if concerns:
                print(f"\n!! rig concerns in job {job['name']} ({job['conclusion']}):")
                for concern in concerns:
                    print(f"   ! {concern}")
    print(f"\n{findings} finding(s) in run {run_id}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="*")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--repo", default="kinisi-robotics/kinisi_ros")
    parser.add_argument("--context", type=int, default=12)
    parser.add_argument("--save-dir")
    args = parser.parse_args()
    runs = [run_id_of(r) for r in args.runs] + (latest_runs(args.repo) if args.latest else [])
    if not runs:
        parser.error("give a run id or URL, or --latest")
    if args.save_dir:
        os.makedirs(args.save_dir, exist_ok=True)
    for run_id in runs:
        scan(args.repo, run_id, args.context, args.save_dir)


if __name__ == "__main__":
    main()
