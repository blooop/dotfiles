-- Most panes in `working` at one sampled minute.
SELECT CASE WHEN (SELECT count(*) FROM herdr_events WHERE in_window(ts)) = 0 THEN NULL ELSE max(n) END AS value
FROM parallel_samples(getvariable('t0'), getvariable('t1'));
