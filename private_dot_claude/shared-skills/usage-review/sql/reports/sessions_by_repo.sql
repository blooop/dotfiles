-- Claude sessions with a hook event in the window, by repo (from the session's first cwd).
SELECT repo_of(cwd) AS repo, count(*) AS sessions, sum(container::INT) AS in_container
FROM tele_sessions WHERE session IN (SELECT session FROM claude_events WHERE in_window(ts))
GROUP BY ALL ORDER BY sessions DESC, repo;
