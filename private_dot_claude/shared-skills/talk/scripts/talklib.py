"""Shared helpers for the talk skill's execution steps (standard library only).

Each step script reads {"state", "assets", "expects"} on stdin and writes its declared
outputs as one JSON object on stdout. Logs go to stderr so stdout stays clean JSON.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# yt-dlp through uvx, impersonating Chrome: plain yt-dlp gets more 429s and bot checks.
YTDLP = ["uvx", "--with", "curl_cffi", "yt-dlp", "--impersonate", "chrome", "--no-warnings"]


def read_state():
    return json.load(sys.stdin)["state"]


def emit(outputs):
    json.dump(outputs, sys.stdout)


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def run(cmd, cwd=None, check=True):
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def fmt(seconds):
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def first(out_dir, prefix):
    """The one file in out_dir whose name starts with prefix, or None."""
    for name in sorted(os.listdir(out_dir)):
        if name.startswith(prefix):
            return os.path.join(out_dir, name)
    return None
