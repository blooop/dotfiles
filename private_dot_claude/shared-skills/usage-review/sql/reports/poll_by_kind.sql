-- Polling turns by kind: settle (sleep <= 10 s), loop (until/while or sleep > 10 s), watch (--watch), tool (Monitor/TaskOutput/ReadNotifications).
SELECT poll_kind AS kind, count(*) AS turns, round(sum(context) / 1e6, 1) AS context_M,
       round(sum(context) / (SELECT nullif(sum(context), 0) FROM turns WHERE in_window(ts)), 4) AS share
FROM turns WHERE in_window(ts) AND is_poll GROUP BY ALL ORDER BY share DESC;
