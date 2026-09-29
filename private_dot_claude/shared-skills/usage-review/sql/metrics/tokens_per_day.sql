-- Input-side tokens (uncached + cache write + cache read) per day, subagents included.
SELECT coalesce(sum(context), 0) / getvariable('days') AS value FROM turns WHERE in_window(ts);
