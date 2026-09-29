-- Share of input-side tokens spent on turns that poll: settle, loop, watch and tool (all kinds).
SELECT coalesce(sum(context) FILTER (WHERE is_poll), 0) / nullif(sum(context), 0) AS value FROM turns WHERE in_window(ts);
