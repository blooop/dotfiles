-- Share of sessions with an event in the window that ran in a container.
SELECT avg(container::INT) AS value FROM tele_sessions
WHERE session IN (SELECT session FROM claude_events WHERE in_window(ts));
