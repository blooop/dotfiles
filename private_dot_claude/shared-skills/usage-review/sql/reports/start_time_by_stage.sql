-- dl launch and aid start times by stage. `stages` is an object {stage: seconds}; its keys differ
-- between launch (only with DEVLAUNCH_TIMING) and aid_start (pick, pr_lookup, prompt, boot_wait).
SELECT ev, stage, count(*) AS n, round(quantile_cont(s, 0.5), 1) AS p50_s, round(quantile_cont(s, 0.9), 1) AS p90_s
FROM (SELECT ev, stage, TRY_CAST(stages->>stage AS DOUBLE) AS s
      FROM (SELECT ev, stages, unnest(json_keys(stages)) AS stage FROM dl_events
            WHERE in_window(ts) AND ev IN ('launch', 'aid_start') AND json_type(stages) = 'OBJECT'))
GROUP BY ALL ORDER BY ev, p50_s DESC;
