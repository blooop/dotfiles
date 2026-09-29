-- Median seconds a dl launch took until the workspace was ready.
SELECT quantile_cont(seconds, 0.5) AS value FROM dl_events WHERE in_window(ts) AND ev = 'launch';
