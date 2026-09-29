-- Share of input-side tokens on foreground wait loops only (until/while, or sleep > 10 s).
SELECT coalesce(sum(context) FILTER (WHERE poll_kind = 'loop'), 0) / nullif(sum(context), 0) AS value FROM turns WHERE in_window(ts);
