#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Claude Code status line — stdlib only, no external deps.

Rate-limit usage is shown as a pacing gauge per window (5h / weekly): a
`used/even` pair on a 0-1 scale, traffic-light coloured, where `even` is the
usage you'd have at a perfectly steady burn (= fraction of the window elapsed).
used < even ⇒ headroom to spare (green); used > even ⇒ on track to run out
before the window resets (amber/red). E.g. .10/.15 = .05 to spare.

A window reads `🟢42m/5h .20/.87`: time-to-reset over window length, then the
pacing pair. Each is a fraction of the same window, so the clock sits beside
the length it counts down rather than trailing the field.

Two independently-coloured signals interleave. The glyph, label and `used` take
the pacing colour above; the ETA and `even` — both readings of the same clock —
are coloured by how much of the window is left to run (see eta_color): red
early on, green as the reset approaches.

Layout is width-optimised for narrow (phone) terminals: every glyph is a single
cell, parts are joined by a bare │, and session cost/duration/diff come last so
they get clipped first.
"""

import json
import sys
from datetime import datetime, timezone

# Secondary text uses a light grey rather than the faint attribute (\033[2m),
# which many terminals render at too low a contrast to read on a phone screen.
GREY = "\033[38;5;250m"  # readable secondary text: cost, duration, no-data slots
SEP = "\033[38;5;243m"  # structural dividers only — seen, not read
RED = "\033[31m"
YELLOW = "\033[33m"
ORANGE = "\033[38;5;208m"
GREEN = "\033[32m"
RESET = "\033[0m"

# Large circle marking the start of a rate-limit field. These are emoji, so they
# cost 2 cells each (vs 1 for ⬤ / ●) but render far bigger and carry their own
# colour, which survives terminals that wash out ANSI foreground colours.
# Only these four steps exist as circle emoji — there is no lime/yellow-green
# between 🟢 and 🟡, so the pacing scale tops out at four levels plus ⚪ no-data.
GLYPH = {GREEN: "🟢", YELLOW: "🟡", ORANGE: "🟠", RED: "🔴", GREY: "⚪"}

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
        return f"{GREY}--/--{RESET}"
    p = max(0, min(100, int(used / size * 100)))
    if p < 20:
        color = GREEN
    elif p < 40:
        color = YELLOW
    elif p < 60:
        color = ORANGE
    else:
        color = RED
    return f"{color}{fmt_tokens(used)}/{fmt_tokens(size)}{RESET}"


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


def pace_color(usage_pct: float | None, elapsed_pct: float | None) -> str:
    """Traffic-light colour from usage-vs-elapsed pacing, applied to the ratio.

    At a steady burn, projected usage at reset ≈ usage% / elapsed% × 100, so
    usage% > elapsed% means the budget runs out before the window resets. The
    size of that gap (the margin, in percentage points) sets the colour:
    ≤0 green, ≤10 yellow, ≤25 orange, above that red.
    """
    if usage_pct is None:
        return GREY
    if usage_pct >= 90:
        return RED  # nearly spent regardless of pacing
    if elapsed_pct is None:
        # no reset clock available — colour on absolute usage only
        if usage_pct < 60:
            return GREEN
        return YELLOW if usage_pct < 75 else ORANGE
    if usage_pct < 10:
        return GREEN  # negligible near-term risk this early
    margin = usage_pct - elapsed_pct  # >0 ⇒ ahead of pace (exhausts early)
    if margin <= 0:
        return GREEN
    if margin <= 10:
        return YELLOW
    if margin <= 25:
        return ORANGE
    return RED


def eta_color(remaining_frac: float) -> str:
    """Colour the time-to-reset by how much of the window is still to run.

    Scoped to the window, not absolute, so 5h and 7d read the same way: a lot
    left to ration is pressure (red), nearly-reset means relief is imminent
    (green). 15m of a 5h window and 8h of a 7d window are both ~5% ⇒ green.
    """
    if remaining_frac <= 0.25:
        return GREEN
    if remaining_frac <= 0.50:
        return YELLOW
    if remaining_frac <= 0.75:
        return ORANGE
    return RED


def fmt_frac(x: float) -> str:
    """0-1 fraction to 2 decimals, leading zero stripped: 0.10 → .10."""
    return f"{x:.2f}".lstrip("0") or "0"


def window_part(label: str, window_len: int, sub: dict | None, now: datetime) -> str:
    usage = sub.get("used_percentage") if isinstance(sub, dict) else None
    if usage is None:
        # no data yet (e.g. before the first message) — show the slot anyway
        return f"{GREY}{GLYPH[GREY]}{label}--{RESET}"
    used = max(0.0, usage) / 100.0
    reset_dt = parse_reset(sub.get("resets_at"))
    elapsed_pct = None
    remaining = None
    if reset_dt is not None:
        remaining = max(0.0, (reset_dt - now).total_seconds())
        elapsed_pct = max(0.0, min(100.0, (window_len - remaining) / window_len * 100))

    # leading circle anchors the start of the field so the eye can find the
    # window boundaries at a glance; label + used share its pacing colour, so
    # the signal survives being clipped
    pace = pace_color(usage, elapsed_pct)
    glyph = f"{pace}{GLYPH.get(pace, GLYPH[GREY])}{RESET}"
    gauge = f"{pace}{label} {fmt_frac(used)}{RESET}"
    if remaining is None:
        # no reset clock to pace against — window length and used, nothing to
        # count down and no "even" to compare with
        return f"{glyph}{gauge}"

    # the ETA and "even" (usage at a perfectly steady burn) are two readings of
    # the same clock, so they share the time colour — a second signal in the
    # field, independent of pacing. Grey / dividers separate each pair.
    time_color = eta_color(remaining / window_len)
    eta = f"{time_color}{fmt_eta(remaining)}{RESET}"
    even = f"{time_color}{fmt_frac(elapsed_pct / 100)}{RESET}"
    slash = f"{SEP}/{RESET}"
    return f"{glyph}{eta}{slash}{gauge}{slash}{even}"


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

    now = datetime.now(timezone.utc)
    for key, label, window_len in WINDOWS:
        sub = rate.get(key)
        if sub is None and key == "seven_day":
            sub = rate.get("weekly")  # tolerate an alternate weekly key
        parts.append(window_part(label, window_len, sub, now))

    # session metrics last — least important, first to clip on narrow terminals
    if cost:
        parts.append(f"{GREY}{cost}{RESET}")
    if duration:
        parts.append(f"{GREY}{duration}{RESET}")
    if added or removed:
        parts.append(f"{GREEN}+{added}{RESET}/{RED}-{removed}{RESET}")

    print(f"{SEP}│{RESET}".join(parts))


main()
