-- Median minutes from SessionStart to SessionEnd (or the last event), for sessions that start in the window.
SELECT quantile_cont(wall_min, 0.5) AS value FROM tele_sessions WHERE in_window(start);
