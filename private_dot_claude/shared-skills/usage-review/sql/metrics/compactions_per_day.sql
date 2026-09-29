-- Context compactions per day.
SELECT count(*) / getvariable('days') AS value FROM compactions WHERE in_window(ts);
