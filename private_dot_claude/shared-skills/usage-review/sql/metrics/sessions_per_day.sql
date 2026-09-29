-- Main sessions (not subagents) with a turn or a prompt in the window, per day.
SELECT count(DISTINCT session) / getvariable('days') AS value
FROM (SELECT session, parent, ts FROM turns UNION ALL SELECT session, parent, ts FROM prompts)
WHERE session = parent AND in_window(ts);
