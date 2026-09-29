-- Median seconds for a full agent start: aid_start.seconds plus the next dl launch.seconds on the
-- same workspace (aid's time ends at the hand-off to dl, and dl's launch times from there).
-- A launch more than 1 h after the aid_start is not its pair.
WITH a AS (SELECT ts, ws, seconds FROM dl_events WHERE ev = 'aid_start' AND in_window(ts) AND ws IS NOT NULL),
l AS (SELECT ts, ws, seconds FROM dl_events WHERE ev = 'launch')
SELECT quantile_cont(a.seconds + l.seconds, 0.5) AS value
FROM a ASOF JOIN l ON l.ws = a.ws AND l.ts >= a.ts
WHERE secs(a.ts, l.ts) <= 3600;
