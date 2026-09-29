-- Median count of panes in `working`, sampled each minute of the active hours.
SELECT CASE WHEN (SELECT count(*) FROM herdr_events WHERE in_window(ts)) = 0 THEN NULL ELSE quantile_cont(n, 0.5) END AS value
FROM parallel_samples(getvariable('t0'), getvariable('t1'));
