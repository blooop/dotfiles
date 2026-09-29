-- Short prompts per day where the human restarts a stopped agent (keep going / continue) (regex theme `nudge` in usage_stats.py FRICTION).
SELECT count(*) FILTER (WHERE list_contains(friction, 'nudge')) / getvariable('days') AS value FROM prompts WHERE in_window(ts);
