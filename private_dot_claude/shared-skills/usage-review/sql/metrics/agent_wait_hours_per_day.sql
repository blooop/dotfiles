-- Hours per day an agent pane sat blocked/done/idle after working, until focused or working again (8 h cap per wait).
SELECT CASE WHEN (SELECT count(*) FROM herdr_events WHERE in_window(ts)) = 0 THEN NULL
            ELSE coalesce(sum(seconds), 0) / 3600 / getvariable('days') END AS value
FROM agent_waits WHERE in_window(start);
