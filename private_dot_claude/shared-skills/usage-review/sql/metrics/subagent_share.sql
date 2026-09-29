-- Share of input-side tokens spent in subagent transcripts.
SELECT coalesce(sum(context) FILTER (WHERE session <> parent), 0) / nullif(sum(context), 0) AS value FROM turns WHERE in_window(ts);
