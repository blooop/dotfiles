-- 90th percentile seconds of an aid start.
SELECT quantile_cont(seconds, 0.9) AS value FROM dl_events WHERE in_window(ts) AND ev = 'aid_start';
