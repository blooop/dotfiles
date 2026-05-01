#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Claude Code status line — stdlib only, no external deps."""

import json
import sys


def format_duration(ms: float | None) -> str:
    if not ms:
        return ""
    s = int(ms / 1000)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    h, rem = divmod(s, 3600)
    return f"{h}h{rem // 60:02d}m"


def format_cost(usd: float | None) -> str:
    if usd is None:
        return ""
    if usd < 0.01:
        return f"${usd:.4f}"
    return f"${usd:.2f}"


def context_bar(pct: float | None) -> str:
    if pct is None:
        return "\033[2m??????????\033[0m"
    p = max(0, min(100, int(pct)))
    filled = p // 10
    if p > 80:
        color = "\033[31m"  # red
    elif p > 60:
        color = "\033[33m"  # yellow
    else:
        color = "\033[34m"  # blue
    bar = color + "●" * filled + "\033[0m" + "○" * (10 - filled)
    return f"{bar} {p}%"


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        print("⏳")
        return

    model = (data.get("model") or {}).get("display_name") or "?"
    ctx = data.get("context_window") or {}
    cost_obj = data.get("cost") or {}
    rate = data.get("rate_limits") or {}

    pct = ctx.get("used_percentage")
    cost = format_cost(cost_obj.get("total_cost_usd"))
    duration = format_duration(cost_obj.get("total_duration_ms"))

    added = cost_obj.get("total_lines_added", 0) or 0
    removed = cost_obj.get("total_lines_removed", 0) or 0

    five_hr = (rate.get("five_hour") or {}).get("used_percentage")

    parts = [model, context_bar(pct)]
    if cost:
        parts.append(cost)
    if duration:
        parts.append(duration)
    if added or removed:
        parts.append(f"\033[32m+{added}\033[0m/\033[31m-{removed}\033[0m")
    if five_hr is not None:
        label = f"rate:{int(five_hr)}%"
        if five_hr > 80:
            label = f"\033[31m{label}\033[0m"
        parts.append(label)

    print(" │ ".join(parts))


main()
