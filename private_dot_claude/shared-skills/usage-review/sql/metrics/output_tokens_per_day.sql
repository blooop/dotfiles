-- Output tokens per day, subagents included.
SELECT coalesce(sum(output), 0) / getvariable('days') AS value FROM turns WHERE in_window(ts);
