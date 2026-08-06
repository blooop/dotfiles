#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Claude Code status line — stdlib only, no external deps.

Rate-limit usage is shown as a pacing gauge per window (5h / weekly): a
`used/even` pair on a 0-1 scale, where `even` is the usage you'd have at a
perfectly steady burn (= fraction of the window elapsed). used < even ⇒ headroom
to spare; used > even ⇒ on track to run out before the window resets. E.g.
.10/.15 = .05 to spare.

A window reads `⏳42m/5h 🔥.20/.87`: time-to-reset over window length, then the
pacing pair. Each is a fraction of the same window, so the clock sits beside
the length it counts down rather than trailing the field.

The two halves are coloured by what each one actually measures, and the colour
boundary falls on the space between them so every whitespace-delimited token is
exactly one colour meaning exactly one thing. A leading glyph names the
question, so the halves never read as one run of digits:

    ⏳42m/5h   how much budget is left   → usage_color, on absolute usage
    🔥.20/.87  am I burning too fast     → pace_color, on the pacing margin

So the clock half answers "how much is in the tank?" and the pacing half
answers "will I run dry before the reset?" — two independent questions, neither
able to mask the other. A window can sit deep green on pace yet red on the
clock (nearly spent, but spent evenly), or the reverse (barely touched, but
sprinting). Because each half owns one signal, neither needs the other's
safety-net: pace_color is pure pacing, with no absolute-usage floor mixed in.

Layout is width-conscious for narrow (phone) terminals: colour rather than a
per-level glyph carries the levels, the two emoji that remain are there to name
the halves (2 cells each, spent deliberately), parts are joined by a bare │, and
session cost/duration/diff come last so they get clipped first.
"""

import json
import sys
from datetime import datetime, timezone


def _c(n: int) -> str:
    return f"\033[38;5;{n}m"


# Hue assigns meaning, so the two kinds of field never compete: WARM (the RAMP
# below) is always a live budget gauge worth reacting to, COOL is always an
# inert fact about the session. Grey is reserved for data that is absent — it
# means "nothing here", never "something unimportant", which is why the model
# name and session totals are coloured rather than dimmed.
GREY = _c(245)  # absent data only: `--` placeholders
SEP = _c(243)  # structural dividers only — seen, not read
COST = _c(79)  # aquamarine — session spend
DUR = _c(68)  # steel blue — session wall-clock
RED = "\033[31m"
GREEN = "\033[32m"
RESET = "\033[0m"

# Cool hue per model family, so which model is live registers as colour without
# reading the word. Matched as a substring of the display name, lowercased.
MODEL_COLORS = {
    "opus": _c(141),  # violet
    "sonnet": _c(75),  # sky blue
    "haiku": _c(80),  # cyan
    "fable": _c(212),  # pink
}
MODEL_FALLBACK = _c(111)  # unknown family — still cool, still not grey

# Green → yellow → red gradient for the rate-limit gauges, walked by pace_color.
# Colour alone carries the level now that the traffic-light emoji are gone, and
# dropping them is what allows this many steps: only four circle emoji exist
# (🟢🟡🟠🔴), while the 256-colour cube has a smooth ramp. These indices climb
# the cube's green→yellow face, then its yellow→red one, so hue shifts
# monotonically with pressure and no two steps repeat a hue.
RAMP = [_c(n) for n in (46, 82, 118, 154, 190, 226, 220, 214, 208, 202, 196)]

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
    # context fills up long before it is "spent" the way a rate limit is —
    # compaction looms around 60-70% — so the ramp is walked at 1.6× to reach
    # red near 60% rather than 100%
    p = max(0, min(100, used / size * 100))
    return f"{usage_color(p * 1.6)}{fmt_tokens(used)}/{fmt_tokens(size)}{RESET}"


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


def _ramp(frac: float) -> str:
    """Pick from RAMP by position along it, 0.0 → green, 1.0 → red."""
    frac = max(0.0, min(1.0, frac))
    return RAMP[min(len(RAMP) - 1, int(frac * len(RAMP)))]


def usage_color(usage_pct: float | None) -> str:
    """Colour by how much of a budget is spent — "how much is in the tank?".

    Monotone in usage: spending more only ever moves the colour toward red, so
    the scale is readable without knowing its thresholds — warmer is worse —
    which a bucketed traffic light can't offer.
    """
    if usage_pct is None:
        return GREY
    return _ramp(usage_pct / 100.0)


# Percentage points of "ahead of pace" that saturate the ramp to full red. At
# 30, burning at ~2× an even rate through the window's midpoint reads red.
PACE_SPAN = 30.0

# Glyphs marking which question each half answers. All three are
# Emoji_Presentation with East_Asian_Width=Wide, so every terminal and every
# wcwidth agrees they are exactly 2 cells — the mismatch that overlaps glyphs
# and drifts the cursor comes from emoji that are NOT Emoji_Presentation (⏱ and
# ⏲ report 1 cell while the font draws 2), so those are avoided here.
TIME_GLYPH = "⏳"  # sand still running = window still open

# Pace is a binary "is this rate OK?": 🔥 only once meaningfully ahead of an even
# burn, 🐢 when on pace or banking headroom. Colour still carries magnitude, so
# the glyph only needs the verdict. Both are 2 cells, so the field never changes
# width as the verdict flips — a 1-cell "level" glyph would jitter the layout.
FIRE, TORTOISE = "🔥", "🐢"

# Percentage points ahead of pace before it counts as burning hot. Non-zero so
# trivially-ahead does not read as 🔥, and so the verdict does not flicker while
# the margin hovers around zero.
PACE_DEADBAND = 1.0


def pace_color(usage_pct: float, elapsed_pct: float) -> str:
    """Colour by burn rate vs. an even burn — "will I run dry before reset?".

    At a steady rate, projected usage at reset ≈ usage% / elapsed% × 100, so
    usage% > elapsed% means the budget runs out before the window resets. The
    margin between them, in percentage points, walks the ramp: at or under pace
    is green, and PACE_SPAN ahead is full red.

    Pure pacing, deliberately: no floor for a nearly-exhausted window, because
    the clock half of the field is already coloured on absolute usage and would
    be shouting on its own. Early in a window the margin is noisy (tiny elapsed
    denominators), but it degrades smoothly rather than snapping between steps.
    """
    return _ramp((usage_pct - elapsed_pct) / PACE_SPAN)


def pace_glyph(usage_pct: float, elapsed_pct: float) -> str:
    """Burning-hot verdict on the pacing margin — see PACE_DEADBAND."""
    return FIRE if usage_pct - elapsed_pct > PACE_DEADBAND else TORTOISE


def model_color(display_name: str) -> str:
    """Cool hue for the model family named in the display name."""
    low = display_name.lower()
    for family, color in MODEL_COLORS.items():
        if family in low:
            return color
    return MODEL_FALLBACK


def fmt_frac(x: float) -> str:
    """0-1 fraction to 2 decimals, leading zero stripped: 0.10 → .10."""
    return f"{x:.2f}".lstrip("0") or "0"


def window_part(label: str, window_len: int, sub: dict | None, now: datetime) -> str:
    usage = sub.get("used_percentage") if isinstance(sub, dict) else None
    if usage is None:
        # no data yet (e.g. before the first message) — show the slot anyway
        return f"{GREY}{TIME_GLYPH}{label} --{RESET}"
    used = max(0.0, usage) / 100.0
    reset_dt = parse_reset(sub.get("resets_at"))
    remaining = None
    even = None
    if reset_dt is not None:
        remaining = max(0.0, (reset_dt - now).total_seconds())
        even = max(0.0, min(1.0, (window_len - remaining) / window_len))

    # each half one colour, the boundary on the space between them: the clock
    # takes absolute usage, the fractions take pacing. Slashes are coloured with
    # their own half, so a half never fragments into separate-looking signals.
    tank = usage_color(usage)
    if remaining is None:
        # no reset clock — nothing to count down, and no "even" to pace against,
        # so absolute usage is the only signal available
        return f"{tank}{TIME_GLYPH}{label} {fmt_frac(used)}{RESET}"
    elapsed_pct = even * 100
    pace = pace_color(usage, elapsed_pct)
    return (
        f"{tank}{TIME_GLYPH}{fmt_eta(remaining)}/{label}{RESET} "
        f"{pace}{pace_glyph(usage, elapsed_pct)}{fmt_frac(used)}/{fmt_frac(even)}{RESET}"
    )


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

    parts = [f"{model_color(model)}{model}{RESET}", context_usage(ctx)]

    now = datetime.now(timezone.utc)
    for key, label, window_len in WINDOWS:
        sub = rate.get(key)
        if sub is None and key == "seven_day":
            sub = rate.get("weekly")  # tolerate an alternate weekly key
        parts.append(window_part(label, window_len, sub, now))

    # session metrics last — least important, first to clip on narrow terminals
    if cost:
        parts.append(f"{COST}{cost}{RESET}")
    if duration:
        parts.append(f"{DUR}{duration}{RESET}")
    if added or removed:
        parts.append(f"{GREEN}+{added}{RESET}/{RED}-{removed}{RESET}")

    print(f"{SEP}│{RESET}".join(parts))


main()
