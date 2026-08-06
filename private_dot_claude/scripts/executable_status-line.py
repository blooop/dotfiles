#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Claude Code status line — stdlib only, no external deps.

Rate-limit usage is shown as a pacing gauge per window (5h / weekly): a
`used/even` pair in percent, where `even` is the usage you'd have at a perfectly steady burn (=
percent of the window elapsed). used < even ⇒ headroom to spare; used > even ⇒
on track to run out before the window resets. E.g. 10%/15% = 5 points to spare.

Percent rather than a 0-1 fraction, on two counts: it is the unit the API
already reports (`used_percentage`), so no round-trip through a scale nothing
else speaks; and it is the unit PROJ_GREEN/PROJ_RED and PACE_DEADBAND threshold
in, so the displayed numbers and the constants reading them agree. Width is a
wash rather than a win — 20%/87% ties .20/.87, and 100%/100% ties 1.00/1.00 —
so it is the units that earn the change, not the columns.

A sign on *each* number, not one trailing the pair. `20/87%` is a column
cheaper and reads fine once you know the rule, but `/` is an operator
everywhere else it appears, so a lone trailing sign invites parsing the field
as a quotient — "20 divided by 87 percent" — where a range's `20–30%` would
not. Bracketing the pair as `(20/87)%` scopes it correctly but costs two
columns and lands at `(100/100)%`, wider than the fraction all of this
replaced. Repeating the sign also survives a clip: `20%/8` on a narrow
terminal still says percent, where `20/8` has lost the unit entirely.

A window reads `🔥20%/87% ⏳42m/5h`: the pacing pair, then time-to-reset over
window length. Usage leads because it is the half that constrains what can be
done next — the clock only says when relief arrives, which is worth knowing
second and is the half that should clip first on a narrow terminal. Each is a
percentage of the same window, and the clock still sits beside the length it
counts down.

One colour per window block, spanning the whole block including the clock, and it
tracks the **projected finish**: used/even × 100, i.e. where this window ends up
at reset if the current rate holds. Warmer is worse and that is the entire rule —
readable without recalling a threshold or which half of the field measures what.

The projection rather than the raw pacing margin, though pacing is the thing
being asked about. A margin makes a poor hue: it hovers around zero, flips sign,
and burns an eleven-step ramp on what is really a two-state verdict — and 🔥/🐢
already carries that verdict, so the colour was duplicating the glyph rather than
adding to it. The projection is the same pacing information rescaled to vary
continuously, and every step of the ramp then means something: green is on pace
or better, and the warm half grades how badly the current rate overshoots.

So the glyphs name the two questions, the digits answer them, and the projection
they imply sets the hue:

    🔥20%/87%  am I burning too fast   → projects to 23%, deep green
    ⏳42m/5h   how long until relief

Absolute usage is printed, never hued (bar the no-clock fallback in window_part,
where there is no elapsed to project against). That is a deliberate limit, not an
oversight: an even burn projects to 100 at any level, so a window nearly spent
but spent evenly reads green — at that rate it lasts exactly as long as it has
to. The number tells you the level, the hue tells you the rate. See proj_color.

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
# below) is a live budget gauge worth reacting to, COOL is an inert fact about
# the session. Grey is reserved for data that is absent — it means "nothing
# here", never "something unimportant", which is why the model name and session
# totals are coloured rather than dimmed.
#
# The model slot is the one deliberate exception: it runs a rarity ladder (see
# MODEL_COLORS) whose top rung is warm. Position keeps that from misreading —
# the model is always the leftmost field and always a word, while every warm
# gauge is a digit run wearing a 🔥/🐢 or ⏳. Nothing else may spend warm.
GREY = _c(245)  # absent data only: `--` placeholders
SEP = _c(243)  # structural dividers only — seen, not read
COST = _c(79)  # aquamarine — session spend
DUR = _c(68)  # steel blue — session wall-clock
RED = "\033[31m"
GREEN = "\033[32m"
RESET = "\033[0m"

# One hue per model family, so which model is live registers as colour without
# reading the word. Matched as a substring of the display name, lowercased.
#
# The order is the MMO/ARPG item-rarity ladder — uncommon → rare → epic →
# legendary — so the tiers rank themselves against an association most people
# already hold, rather than against an arbitrary spread of hues. Green, the
# ladder's bottom rung, is skipped: RAMP owns green through red, and a
# common-green model would read as "plenty of headroom". Orange at the top is
# the one warm colour spent outside RAMP; see the exception noted above.
MODEL_COLORS = {
    "haiku": _c(80),  # cyan — uncommon
    "sonnet": _c(75),  # sky blue — rare
    "fable": _c(141),  # violet — epic
    "opus": _c(208),  # orange — legendary
}
MODEL_FALLBACK = _c(111)  # unknown family — unranked, but still not grey

# Green → yellow → red gradient for the rate-limit gauges, walked by proj_color.
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
    which a bucketed traffic light can't offer. Used for the context gauge, and
    as a rate-limit window's fallback when no reset clock means no pace to
    compare against.
    """
    if usage_pct is None:
        return GREY
    return _ramp(usage_pct / 100.0)


# Projected end-of-window usage, in percent, that the ramp spans: at or under
# PROJ_GREEN is fully green, PROJ_RED and beyond fully red.
#
# PROJ_GREEN is 100 rather than something short of it because 100 is not a near
# miss, it is the target: an even burn projects to exactly 100 by definition, so
# anything lower means finishing with budget unspent. Setting it below 100 makes
# every on-pace window warm — 50%/50% at the midpoint would read red — which is
# the opposite of the signal wanted. Only a projected *overshoot* is worth a hue.
#
# PROJ_RED is 200: burning at twice an even rate. That is the same severity the
# old margin ramp was tuned to (PACE_SPAN 30 put 2× at the window midpoint into
# full red), kept so the scale change does not quietly re-tune what "red" means.
PROJ_GREEN, PROJ_RED = 100.0, 200.0

# Elapsed fraction the projection divides by, floored. Very early in a window
# the denominator is tiny and used/elapsed explodes — 1% spent at 1% elapsed
# projects to 100% — so a burst in the first minutes would saturate the ramp
# over nothing. Flooring at 0.15 caps how wild the projection can get while
# still letting a genuinely heavy start register as warm.
PROJ_FLOOR = 0.15

# Glyphs marking which question each half answers. All three are
# Emoji_Presentation with East_Asian_Width=Wide, so every terminal and every
# wcwidth agrees they are exactly 2 cells — the mismatch that overlaps glyphs
# and drifts the cursor comes from emoji that are NOT Emoji_Presentation (⏱ and
# ⏲ report 1 cell while the font draws 2), so those are avoided here.
TIME_GLYPH = "⏳"  # sand still running = window still open

# Pace is a binary "is this rate OK?": 🔥 only once meaningfully ahead of an even
# burn, 🐢 when on pace or banking headroom. The glyph owns that verdict outright
# — it is the one signal here with genuinely two states, which is why the hue is
# spent on the projection instead. Both are 2 cells, so flipping the verdict
# costs no width — the digits beside them already breathe between 1 and 3 columns
# as usage climbs, and the glyph has no business adding to that.
FIRE, TORTOISE = "🔥", "🐢"

# Percentage points ahead of pace before it counts as burning hot. Non-zero so
# trivially-ahead does not read as 🔥, and so the verdict does not flicker while
# the margin hovers around zero.
PACE_DEADBAND = 1.0


def projected_pct(usage_pct: float, elapsed_pct: float) -> float:
    """Where this window lands at reset if the current rate holds.

    At a steady burn, usage grows in step with elapsed time, so usage% /
    elapsed% × 100 is the finish line: 170 means "on track to want 1.7× the
    budget", 60 means "on track to finish with 40% unspent". See PROJ_FLOOR for
    the early-window guard on the denominator.
    """
    return usage_pct / max(elapsed_pct / 100.0, PROJ_FLOOR)


def proj_color(usage_pct: float, elapsed_pct: float) -> str:
    """Colour by projected end-of-window usage — "will I run dry before reset?".

    The signal the whole window block is coloured on. Pacing is what's worth
    reacting to, but the *margin* (usage − elapsed) makes a poor hue: it hovers
    around zero, flips sign, and spends an eleven-step ramp on what is really a
    two-state verdict — which 🔥/🐢 already carries for free. The projection is
    the same pacing information on a scale that varies continuously, anchored to
    a meaning rather than a tuned span: 100 is break-even, 150 is "wants half
    again the budget", 200 is twice the sustainable rate.

    Still pure pacing, and it inherits pacing's blind spot: absolute level is
    invisible to it. An even burn projects to 100 whatever the level, so a window
    at 95% used / 96% elapsed reads the same green as one at 5%/5% — both are
    on-pace, which is all this measures. The printed `used` is what carries the
    level. Older revisions patched that with a `used >= 90 → red` floor; adding
    one back would mean the hue answered two questions again, which is the thing
    that made the split-colour version unreadable.
    """
    proj = projected_pct(usage_pct, elapsed_pct)
    return _ramp((proj - PROJ_GREEN) / (PROJ_RED - PROJ_GREEN))


def pace_glyph(usage_pct: float, elapsed_pct: float) -> str:
    """Burning-hot verdict on the pacing margin — see PACE_DEADBAND."""
    return FIRE if usage_pct - elapsed_pct > PACE_DEADBAND else TORTOISE


def model_color(display_name: str) -> str:
    """Rarity-ladder hue for the model family named in the display name."""
    low = display_name.lower()
    for family, color in MODEL_COLORS.items():
        if family in low:
            return color
    return MODEL_FALLBACK


def fmt_pct(x: float) -> str:
    """Percentage to its nearest whole number, signed: 9.6 → 10%."""
    return f"{x:.0f}%"


def window_part(label: str, window_len: int, sub: dict | None, now: datetime) -> str:
    usage = sub.get("used_percentage") if isinstance(sub, dict) else None
    if usage is None:
        # no data yet (e.g. before the first message) — show the slot anyway
        return f"{GREY}{TIME_GLYPH}{label} --{RESET}"
    # floored, not clamped above: a window reported past 100 should read past
    # 100 rather than be quietly capped into looking merely spent
    used = max(0.0, usage)
    reset_dt = parse_reset(sub.get("resets_at"))
    remaining = None
    even = None
    if reset_dt is not None:
        remaining = max(0.0, (reset_dt - now).total_seconds())
        even = max(0.0, min(100.0, (window_len - remaining) / window_len * 100))

    if remaining is None:
        # no reset clock — nothing to count down, and no "even" to pace against,
        # so the block falls back to absolute usage for its colour. The pace
        # glyph goes rather than being guessed: 🔥/🐢 is a verdict on a comparison
        # there is no second term for. Usage still leads, and ⏳ keeps naming the
        # window it belongs to.
        return f"{usage_color(used)}{fmt_pct(used)} {TIME_GLYPH}{label}{RESET}"
    # one colour for the whole block, on the projected finish — including the
    # separators, the % signs and the clock, so nothing in the field fragments
    # into a second signal
    color = proj_color(used, even)
    return (
        f"{color}{pace_glyph(used, even)}{fmt_pct(used)}/{fmt_pct(even)} "
        f"{TIME_GLYPH}{fmt_eta(remaining)}/{label}{RESET}"
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
