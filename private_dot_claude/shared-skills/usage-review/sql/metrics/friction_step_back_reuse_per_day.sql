-- Short prompts per day where the human asks to step back or reuse what exists (regex theme `step_back_reuse` in usage_stats.py FRICTION).
SELECT count(*) FILTER (WHERE list_contains(friction, 'step_back_reuse')) / getvariable('days') AS value FROM prompts WHERE in_window(ts);
