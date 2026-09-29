-- Short prompts per day where the human corrects a wrong turn (no, wrong, undo) (regex theme `correction` in usage_stats.py FRICTION).
SELECT count(*) FILTER (WHERE list_contains(friction, 'correction')) / getvariable('days') AS value FROM prompts WHERE in_window(ts);
