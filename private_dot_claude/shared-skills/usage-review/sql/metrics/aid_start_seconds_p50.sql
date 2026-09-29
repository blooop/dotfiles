-- Median seconds an aid start took until the agent was ready.
SELECT quantile_cont(seconds, 0.5) AS value FROM dl_events WHERE in_window(ts) AND ev = 'aid_start';
