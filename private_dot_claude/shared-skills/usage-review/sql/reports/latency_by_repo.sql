-- Response latency by repo (from the session's cwd).
SELECT repo_of(cwd) AS repo, count(*) AS n, round(quantile_cont(seconds, 0.5)) AS p50_s, round(quantile_cont(seconds, 0.9)) AS p90_s
FROM latency_pairs WHERE in_window(stop_ts) GROUP BY ALL ORDER BY n DESC LIMIT 12;
