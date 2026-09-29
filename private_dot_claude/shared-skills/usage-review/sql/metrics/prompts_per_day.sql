-- Human prompts (slash commands included, interrupts not) per day.
SELECT count(*) / getvariable('days') AS value FROM prompts WHERE in_window(ts) AND NOT is_interrupt;
