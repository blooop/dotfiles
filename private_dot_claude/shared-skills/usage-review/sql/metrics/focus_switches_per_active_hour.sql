-- pane_focused events per hour that had any telemetry event.
SELECT CASE WHEN (SELECT count(*) FROM herdr_events WHERE in_window(ts)) = 0 THEN NULL
            ELSE (SELECT count(*) FROM herdr_events WHERE in_window(ts) AND ev = 'pane_focused') / nullif(count(*), 0) END AS value
FROM active_hours(getvariable('t0'), getvariable('t1'));
