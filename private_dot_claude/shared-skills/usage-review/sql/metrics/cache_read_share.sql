-- Share of input-side tokens read from the prompt cache.
SELECT sum(cache_read) / nullif(sum(context), 0) AS value FROM turns WHERE in_window(ts);
