-- Median seconds from a Stop to that session's next human prompt (gaps over 8 h dropped).
SELECT quantile_cont(seconds, 0.5) AS value FROM latency_pairs WHERE in_window(stop_ts);
