#!/usr/bin/env python3

import sys
import json

try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, Exception):
    data = {}

# Color codes
BLUE = '\033[34m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RED = '\033[31m'
DIM = '\033[2m'
RESET = '\033[0m'

# Model
model = "unknown"
if "model" in data:
    model = data["model"].get("display_name", data["model"].get("id", "unknown"))

# Context window
cw = data.get("context_window", {})
max_ctx = cw.get("context_window_size", 200000)
used_pct = cw.get("used_percentage")
total_in = cw.get("total_input_tokens", 0)
total_out = cw.get("total_output_tokens", 0)

if used_pct is None:
    ctx_bar = "○○○○○○○○○○"
    ctx_info = f"{ctx_bar} loading..."
else:
    pct = min(int(used_pct), 100)
    filled = pct // 10
    color = RED if pct > 60 else BLUE
    bar = "".join(f"{color}●{RESET}" if i < filled else "○" for i in range(10))
    used_k = max_ctx * pct // 100 // 1000
    max_k = max_ctx // 1000
    ctx_info = f"{bar} {used_k}k/{max_k}k"

# Token totals
if total_in or total_out:
    tok_info = f"{DIM}{(total_in + total_out) // 1000}k tok{RESET}"
else:
    tok_info = ""

# Session cost
cost = data.get("cost", {})
cost_usd = cost.get("total_cost_usd")
if cost_usd is not None:
    if cost_usd < 0.01:
        cost_str = f"{GREEN}${cost_usd*100:.1f}¢{RESET}"
    else:
        color = RED if cost_usd > 1.0 else YELLOW
        cost_str = f"{color}${cost_usd:.3f}{RESET}"
else:
    cost_str = ""

# Rate limits (Pro/Max only)
rl = data.get("rate_limits", {})
rl_parts = []
for window, label in [("five_hour", "5h"), ("seven_day", "7d")]:
    w = rl.get(window, {})
    pct_used = w.get("used_percentage")
    if pct_used is not None:
        pct_i = int(pct_used)
        c = RED if pct_i > 80 else (YELLOW if pct_i > 50 else DIM)
        rl_parts.append(f"{c}{label}:{pct_i}%{RESET}")
rl_info = " ".join(rl_parts)

# Assemble
parts = [model, ctx_info]
if tok_info:
    parts.append(tok_info)
if cost_str:
    parts.append(cost_str)
if rl_info:
    parts.append(rl_info)

print(" | ".join(parts))
