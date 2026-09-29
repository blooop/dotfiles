-- Clock hours with at least one human prompt, per day. NULL when the hook log has no event in the window.
SELECT CASE WHEN count(*) = 0 THEN NULL
            ELSE count(DISTINCT floor(epoch(ts) / 3600)) FILTER (WHERE hook = 'UserPromptSubmit' AND is_human(prompt)) / getvariable('days') END AS value
FROM claude_events WHERE in_window(ts);
