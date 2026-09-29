-- Short prompts per day where the human relays work between agents (regex theme `cross_agent_handoff` in usage_stats.py FRICTION).
SELECT count(*) FILTER (WHERE list_contains(friction, 'cross_agent_handoff')) / getvariable('days') AS value FROM prompts WHERE in_window(ts);
