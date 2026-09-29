-- Short prompts per day where the human reports CPU, RAM or a crash (regex theme `host_resources` in usage_stats.py FRICTION).
SELECT count(*) FILTER (WHERE list_contains(friction, 'host_resources')) / getvariable('days') AS value FROM prompts WHERE in_window(ts);
