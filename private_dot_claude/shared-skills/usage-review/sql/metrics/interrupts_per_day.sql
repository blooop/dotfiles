-- Times the human interrupted the agent (Esc), per day.
SELECT count(*) / getvariable('days') AS value FROM prompts WHERE in_window(ts) AND is_interrupt;
