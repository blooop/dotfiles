-- Human prompts by weekday and local hour (columns are hours 0-23; "." is none).
WITH p AS (SELECT isodow(ts) AS d, hour(ts) AS h, count(*) AS n FROM claude_events
           WHERE in_window(ts) AND hook = 'UserPromptSubmit' AND is_human(prompt) GROUP BY ALL),
g AS (SELECT d, h FROM range(1, 8) AS a(d), range(24) AS b(h))
SELECT ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][g.d] AS day,
       string_agg(lpad(coalesce(p.n::VARCHAR, '.'), 3, ' '), '' ORDER BY g.h) AS "  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23"
FROM g LEFT JOIN p USING (d, h) GROUP BY g.d ORDER BY g.d;
