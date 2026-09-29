-- 90th percentile seconds from a Stop to that session's next human prompt.
SELECT quantile_cont(seconds, 0.9) AS value FROM latency_pairs WHERE in_window(stop_ts);
