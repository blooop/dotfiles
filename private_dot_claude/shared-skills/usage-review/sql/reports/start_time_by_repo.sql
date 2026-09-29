-- dl launch and aid start times by repo.
SELECT ev, coalesce(repo, '?') AS repo, count(*) AS n, count(*) FILTER (WHERE cold) AS cold,
       round(quantile_cont(seconds, 0.5), 1) AS p50_s, round(quantile_cont(seconds, 0.9), 1) AS p90_s
FROM dl_events WHERE in_window(ts) AND ev IN ('launch', 'aid_start') GROUP BY ALL ORDER BY ev, n DESC;
