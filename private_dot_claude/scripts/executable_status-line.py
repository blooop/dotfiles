#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Claude Code status line — stdlib only, no external deps.

Rate-limit usage is shown as a pacing gauge per window (5h / weekly): a
traffic-light dot plus a `used/even` pair on a 0-1 scale, where `even` is the
usage you'd have at a perfectly steady burn (= fraction of the window elapsed).
used < even ⇒ headroom to spare (green); used > even ⇒ on track to run out
before the window resets (amber/red). E.g. 0.10/0.15 = 0.05 to spare.
"""

import json
import sys
from datetime import datetime, timezone

DIM = "\033[2m"
RED = "\033[31m"
YELLOW = "\033[33m"
ORANGE = "\033[38;5;208m"
GREEN = "\033[32m"
RESET = "\033[0m"

# (rate_limits key, short label, window length in seconds)
WINDOWS = [
    ("five_hour", "5h", 5 * 3600),
    ("seven_day", "7d", 7 * 86400),
]


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


def fmt_tokens(n: int) -> str:
    n = int(n)
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        k = n / 1000
        s = f"{k:.1f}".rstrip("0").rstrip(".") if k < 100 else f"{k:.0f}"
        return f"{s}k"
    m = n / 1_000_000
    return f"{m:.1f}".rstrip("0").rstrip(".") + "M"


def context_usage(ctx: dict) -> str:
    used = ctx.get("total_input_tokens") or 0
    size = ctx.get("context_window_size") or 0
    if not size:
        return f"{DIM}--/-- tk{RESET}"
    p = max(0, min(100, int(used / size * 100)))
    if p < 20:
        color = GREEN
    elif p < 40:
        color = YELLOW
    elif p < 60:
        color = ORANGE
    else:
        color = RED
    return f"{color}{fmt_tokens(used)}/{fmt_tokens(size)}{RESET} {DIM}tk{RESET}"


def parse_reset(v) -> datetime | None:
    """Parse a resets_at value (epoch seconds/ms or ISO-8601) to aware UTC."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        ts = v / 1000 if v > 1e12 else v
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return parse_reset(float(s))
        except ValueError:
            pass
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def fmt_eta(seconds: float) -> str:
    s = int(max(0, seconds))
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d}d{h}h"
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m"
    return "<1m"


def pace_dot(usage_pct: float | None, elapsed_pct: float | None) -> str:
    """Traffic-light dot from usage-vs-elapsed pacing.

    At a steady burn, projected usage at reset ≈ usage% / elapsed% × 100, so
    usage% > elapsed% means the budget runs out before the window resets. The
    size of that gap sets the colour.
    """
    if usage_pct is None:
        return "⚪"
    if usage_pct >= 90:
        return "🔴"  # nearly spent regardless of pacing
    if elapsed_pct is None:
        # no reset clock available — colour on absolute usage only
        return "🟢" if usage_pct < 60 else ("🟡" if usage_pct < 80 else "🔴")
    if usage_pct < 10:
        return "🟢"  # negligible near-term risk this early
    margin = usage_pct - elapsed_pct  # >0 ⇒ ahead of pace (exhausts early)
    if margin <= 0:
        return "🟢"
    if margin <= 15:
        return "🟡"
    return "🔴"


def window_part(label: str, window_len: int, sub: dict | None, now: datetime) -> str:
    usage = sub.get("used_percentage") if isinstance(sub, dict) else None
    if usage is None:
        # no data yet (e.g. before the first message) — show the slot anyway
        return f"{DIM}{label}{RESET} ⚪ {DIM}--{RESET}"
    used = max(0.0, usage) / 100.0
    reset_dt = parse_reset(sub.get("resets_at"))
    elapsed_pct = None
    eta = ""
    ratio = f"{used:.2f}"  # used alone until there's a reset clock to pace against
    if reset_dt is not None:
        remaining = max(0.0, (reset_dt - now).total_seconds())
        elapsed_pct = max(0.0, min(100.0, (window_len - remaining) / window_len * 100))
        # "even" = usage at a perfectly steady burn = fraction of the window elapsed
        ratio = f"{used:.2f}/{elapsed_pct / 100:.2f}"
        eta = f" {DIM}⏳{fmt_eta(remaining)}{RESET}"
    dot = pace_dot(usage, elapsed_pct)
    return f"{DIM}{label}{RESET} {dot} {ratio}{eta}"


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

    cost = format_cost(cost_obj.get("total_cost_usd"))
    duration = format_duration(cost_obj.get("total_duration_ms"))
    added = cost_obj.get("total_lines_added", 0) or 0
    removed = cost_obj.get("total_lines_removed", 0) or 0

    parts = [model, context_usage(ctx)]
    if cost:
        parts.append(cost)
    if duration:
        parts.append(duration)
    if added or removed:
        parts.append(f"{GREEN}+{added}{RESET}/{RED}-{removed}{RESET}")

    now = datetime.now(timezone.utc)
    for key, label, window_len in WINDOWS:
        sub = rate.get(key)
        if sub is None and key == "seven_day":
            sub = rate.get("weekly")  # tolerate an alternate weekly key
        parts.append(window_part(label, window_len, sub, now))

    print(" │ ".join(parts))


main()
