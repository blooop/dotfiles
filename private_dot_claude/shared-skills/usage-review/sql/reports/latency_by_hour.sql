-- Response latency by local hour of the Stop.
SELECT hour(stop_ts) AS hour, count(*) AS n, round(quantile_cont(seconds, 0.5)) AS p50_s, round(quantile_cont(seconds, 0.9)) AS p90_s
FROM latency_pairs WHERE in_window(stop_ts) GROUP BY ALL ORDER BY hour;
