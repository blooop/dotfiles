-- Short prompts per day where the human asks for simpler or plainer prose (regex theme `ask_for_plainer_prose` in usage_stats.py FRICTION).
SELECT count(*) FILTER (WHERE list_contains(friction, 'ask_for_plainer_prose')) / getvariable('days') AS value FROM prompts WHERE in_window(ts);
