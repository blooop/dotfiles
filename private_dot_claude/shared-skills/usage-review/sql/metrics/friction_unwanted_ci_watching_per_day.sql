-- Short prompts per day where the human says there is no need to watch CI (regex theme `unwanted_ci_watching` in usage_stats.py FRICTION).
SELECT count(*) FILTER (WHERE list_contains(friction, 'unwanted_ci_watching')) / getvariable('days') AS value FROM prompts WHERE in_window(ts);
