-- Short prompts per day where the human asks for status (did you / have you) (regex theme `status_check` in usage_stats.py FRICTION).
SELECT count(*) FILTER (WHERE list_contains(friction, 'status_check')) / getvariable('days') AS value FROM prompts WHERE in_window(ts);
