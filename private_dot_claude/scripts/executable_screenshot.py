#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["mss"]
# ///
"""Capture a screenshot and save it to a temp file for Claude to read."""

from __future__ import annotations

import sys
from pathlib import Path

import mss
import mss.tools

OUTPUT = Path("/tmp/claude-desktop-screenshot.png")


def main() -> None:
    with mss.mss() as sct:
        # monitor 0 = entire virtual screen (all monitors combined)
        monitor = sct.monitors[0]
        img = sct.grab(monitor)
        mss.tools.to_png(img.rgb, img.size, output=str(OUTPUT))

    print(OUTPUT)


if __name__ == "__main__":
    main()
