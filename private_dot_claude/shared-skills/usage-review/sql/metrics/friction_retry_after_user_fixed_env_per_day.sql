-- Short prompts per day where the human fixed the environment and says try now (regex theme `retry_after_user_fixed_env` in usage_stats.py FRICTION).
SELECT count(*) FILTER (WHERE list_contains(friction, 'retry_after_user_fixed_env')) / getvariable('days') AS value FROM prompts WHERE in_window(ts);
