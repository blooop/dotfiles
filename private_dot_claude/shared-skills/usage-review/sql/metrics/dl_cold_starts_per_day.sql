-- dl launches that built a cold workspace, per day. NULL until the dl log has any event.
SELECT CASE WHEN (SELECT count(*) FROM dl_events) = 0 THEN NULL
            ELSE count(*) FILTER (WHERE ev = 'launch' AND cold) / getvariable('days') END AS value
FROM dl_events WHERE in_window(ts);
