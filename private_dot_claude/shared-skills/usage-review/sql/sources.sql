-- usage-review sources: one table per event log, then the derived views the metrics share.
--
-- Event contract: a source is JSONL, one flat object per line: {"ts": ISO-8601 UTC, "ev": name, ...}.
-- Each table keeps its whole line as `j` (JSON), so a field a tool adds later is j->>'field'
-- with no change here. A glob that matches no file gives an empty table, not an error.
--
-- usage_stats.py sets the variables below before it reads this file and adds `load_from`
-- so it loads only the days it needs. `usage-db` (in .bash_env) leaves them unset: then
-- every row loads and the window is the last 7 days. The sources are tables, not views,
-- because the digest runs every metric over eight windows and must not re-read the files.
SET VARIABLE telemetry_dir = coalesce(getvariable('telemetry_dir'), '~/.claude/telemetry');
SET VARIABLE dl_events = coalesce(getvariable('dl_events'), '~/.local/state/devlaunch/events.jsonl');
SET VARIABLE cache_dir = coalesce(getvariable('cache_dir'), '~/.cache/usage-review');
SET VARIABLE now = coalesce(getvariable('now'), now());
SET VARIABLE t1 = coalesce(getvariable('t1'), getvariable('now'));
SET VARIABLE days = coalesce(getvariable('days'), 7);
SET VARIABLE t0 = coalesce(getvariable('t0'), getvariable('t1') - to_seconds(getvariable('days') * 86400));
SET VARIABLE load_from = coalesce(getvariable('load_from'), '1970-01-01 00:00:00+00'::TIMESTAMPTZ);

-- The SQL that reads one glob as JSON objects, or an empty result when nothing matches.
-- A truncated line (a file still being written) reads as NULL and is dropped below.
CREATE OR REPLACE MACRO _src(path, n) AS CASE WHEN n > 0
    THEN format('SELECT json AS j FROM read_ndjson_objects({}, ignore_errors=true)', '''' || replace(path, '''', '''''') || '''')
    ELSE 'SELECT NULL::JSON AS j WHERE false' END;
CREATE OR REPLACE MACRO _ts(j) AS TRY_CAST(j->>'ts' AS TIMESTAMPTZ);

-- Claude Code hooks (~/.claude/telemetry/claude-<UTC date>.jsonl): SessionStart,
-- UserPromptSubmit, Notification, Stop, SessionEnd. `ev` is the raw hook input.
SET VARIABLE _p = getvariable('telemetry_dir') || '/claude-*.jsonl';
SET VARIABLE _q = _src(getvariable('_p'), (SELECT count(*) FROM glob(getvariable('_p'))));
CREATE OR REPLACE TABLE claude_events AS
SELECT _ts(j) AS ts, j->>'host' AS host, coalesce(TRY_CAST(j->>'container' AS BOOLEAN), false) AS container,
       j->>'pane' AS pane, j->>'tab' AS tab, j->>'dl_ws' AS dl_ws,
       j->>'$.ev.session_id' AS session, j->>'$.ev.hook_event_name' AS hook,
       j->>'$.ev.prompt' AS prompt, j->>'$.ev.cwd' AS cwd, j
FROM query(getvariable('_q')) WHERE _ts(j) >= getvariable('load_from') AND (j->>'$.ev.session_id') IS NOT NULL;

-- herdr (~/.claude/telemetry/herdr-<UTC date>.jsonl). herdr names one event
-- pane.agent_status_changed; the logger writes pane_agent_status_changed now, and older
-- lines keep the dot, so `ev` turns every "." into "_". A `panes` snapshot has an array in `data`.
SET VARIABLE _p = getvariable('telemetry_dir') || '/herdr-*.jsonl';
SET VARIABLE _q = _src(getvariable('_p'), (SELECT count(*) FROM glob(getvariable('_p'))));
CREATE OR REPLACE TABLE herdr_events AS
SELECT _ts(j) AS ts, replace(j->>'ev', '.', '_') AS ev, j->'data' AS data,
       j->>'$.data.pane_id' AS pane_id, j->>'$.data.agent_status' AS agent_status,
       j->>'$.data.workspace_id' AS workspace_id, j
FROM query(getvariable('_q')) WHERE _ts(j) >= getvariable('load_from');

-- devlaunch and aid (~/.local/state/devlaunch/events.jsonl): dl launch, session_end, stop,
-- kill, remove, prune; aid aid_start, aid_end. `stages` is an object {stage: seconds}.
SET VARIABLE _p = getvariable('dl_events');
SET VARIABLE _q = _src(getvariable('_p'), (SELECT count(*) FROM glob(getvariable('_p'))));
CREATE OR REPLACE TABLE dl_events AS
SELECT _ts(j) AS ts, j->>'ev' AS ev, j->>'ws' AS ws, j->>'repo' AS repo, j->>'branch' AS branch,
       TRY_CAST(j->>'cold' AS BOOLEAN) AS cold, TRY_CAST(j->>'seconds' AS DOUBLE) AS seconds,
       j->'stages' AS stages, TRY_CAST(j->>'exit' AS INTEGER) AS exit, j->>'agent' AS agent, j->>'resume' AS resume, j
FROM query(getvariable('_q')) WHERE _ts(j) >= getvariable('load_from');

-- Transcripts, from the cache usage_stats.py writes (one JSONL per transcript, rebuilt when
-- the transcript's mtime changes). A subagent row has session <> parent.
SET VARIABLE _p = getvariable('cache_dir') || '/transcripts/**/*.jsonl';
SET VARIABLE _q = _src(getvariable('_p'), (SELECT count(*) FROM glob(getvariable('_p'))));
CREATE OR REPLACE TEMP TABLE _tx AS
SELECT _ts(j) AS ts, j->>'kind' AS kind, j->>'session' AS session, j->>'parent' AS parent, j->>'project' AS project, j
FROM query(getvariable('_q')) WHERE _ts(j) >= getvariable('load_from');
CREATE OR REPLACE TABLE turns AS
SELECT ts, session, parent, project, j->>'model' AS model,
       (j->>'input')::BIGINT AS input, (j->>'cache_write')::BIGINT AS cache_write, (j->>'cache_read')::BIGINT AS cache_read,
       (j->>'output')::BIGINT AS output, (j->>'context')::BIGINT AS context, (j->>'over_200k')::BIGINT AS over_200k,
       from_json(j->'tools', '["VARCHAR"]') AS tools, from_json(j->'skills', '["VARCHAR"]') AS skills,
       from_json(j->'tool_errors', '["VARCHAR"]') AS tool_errors,
       (j->>'is_poll')::BOOLEAN AS is_poll, j->>'poll_kind' AS poll_kind
FROM _tx WHERE kind = 'turn';
CREATE OR REPLACE TABLE prompts AS
SELECT ts, session, parent, project, j->>'text' AS text, (j->>'len')::INTEGER AS len,
       from_json(j->'friction', '["VARCHAR"]') AS friction,
       (j->>'is_interrupt')::BOOLEAN AS is_interrupt, (j->>'is_command')::BOOLEAN AS is_command
FROM _tx WHERE kind = 'prompt';
CREATE OR REPLACE TABLE compactions AS SELECT ts, session, parent, project FROM _tx WHERE kind = 'compact';
DROP TABLE _tx;

-- cwd -> repo, written by usage_stats.py because it needs the filesystem (the git toplevel).
SET VARIABLE _p = getvariable('cache_dir') || '/repos.jsonl';
SET VARIABLE _q = _src(getvariable('_p'), (SELECT count(*) FROM glob(getvariable('_p'))));
CREATE OR REPLACE TABLE repo_map AS SELECT DISTINCT j->>'cwd' AS cwd, j->>'repo' AS repo FROM query(getvariable('_q'));

-- ---- helpers --------------------------------------------------------------------------
CREATE OR REPLACE MACRO in_window(ts) AS ts >= getvariable('t0') AND ts < getvariable('t1');
-- Subagent results and task notifications arrive as prompts too; a human one does not start with "<".
CREATE OR REPLACE MACRO is_human(p) AS p IS NOT NULL AND NOT regexp_matches(p, '^\s*<');
-- A cwd the map does not know yet falls back to its last path part.
SET VARIABLE _repos = (SELECT map(list(cwd), list(repo)) FROM repo_map);
CREATE OR REPLACE MACRO repo_of(c) AS coalesce(map_extract_value(getvariable('_repos'), c), nullif(regexp_extract(c, '([^/]+)/*$', 1), ''), '?');
CREATE OR REPLACE MACRO secs(a, b) AS epoch(b) - epoch(a);
-- Hours (as epoch hour numbers) with any telemetry event; snapshots and logger noise do not count.
CREATE OR REPLACE MACRO active_hours(a, b) AS TABLE
    SELECT floor(epoch(ts) / 3600) AS h FROM claude_events WHERE ts >= a AND ts < b
    UNION
    SELECT floor(epoch(ts) / 3600) FROM herdr_events WHERE ts >= a AND ts < b AND ev NOT IN ('panes', 'logger_connected', 'logger_error');

-- ---- derived views --------------------------------------------------------------------
-- Stop -> that session's next human prompt. The next of Stop/UserPromptSubmit/SessionEnd must
-- be the prompt: a later Stop replaces the earlier one, and a subagent's prompt or a SessionEnd
-- cancels it (a Stop in the parent can come before its subagents finish). Gaps over 8 h
-- (overnight) are not responses.
CREATE OR REPLACE VIEW latency_pairs AS
WITH e AS (
    SELECT session, ts, hook, cwd, lead(hook) OVER w AS next_hook, lead(ts) OVER w AS next_ts, lead(prompt) OVER w AS next_prompt
    FROM claude_events WHERE hook IN ('Stop', 'UserPromptSubmit', 'SessionEnd')
    WINDOW w AS (PARTITION BY session ORDER BY ts))
SELECT session, ts AS stop_ts, next_ts AS prompt_ts, secs(ts, next_ts) AS seconds, cwd
FROM e WHERE hook = 'Stop' AND next_hook = 'UserPromptSubmit' AND is_human(next_prompt) AND secs(ts, next_ts) <= 8 * 3600;

-- One row per Claude session in the hook log. Wall time = SessionStart to SessionEnd, or to its last event.
CREATE OR REPLACE VIEW tele_sessions AS
SELECT session, arg_min(cwd, ts) FILTER (WHERE cwd IS NOT NULL) AS cwd, bool_or(container) AS container,
       min(ts) FILTER (WHERE hook = 'SessionStart') AS start, max(ts) FILTER (WHERE hook = 'SessionEnd') AS end_ts, max(ts) AS last_ts,
       secs(min(ts) FILTER (WHERE hook = 'SessionStart'), coalesce(max(ts) FILTER (WHERE hook = 'SessionEnd'), max(ts))) / 60 AS wall_min
FROM claude_events GROUP BY session;

-- herdr pane state. snap_rows: every pane in every snapshot. pane_records: every record
-- that sets a pane's agent status (status events, snapshot rows, close = 'closed').
CREATE OR REPLACE VIEW snap_rows AS
SELECT h.ts, p->>'pane_id' AS pane_id, p->>'agent_status' AS status, coalesce(TRY_CAST(p->>'focused' AS BOOLEAN), false) AS focused, p->>'session' AS session
FROM herdr_events h, unnest(json_extract(h.data, '$[*]')) AS t(p) WHERE h.ev = 'panes';
CREATE OR REPLACE VIEW snapshots AS SELECT DISTINCT ts FROM herdr_events WHERE ev = 'panes';
CREATE OR REPLACE VIEW pane_records AS
SELECT ts, pane_id, agent_status AS status, 'event' AS src FROM herdr_events WHERE ev = 'pane_agent_status_changed'
UNION ALL SELECT ts, pane_id, status, 'snapshot' FROM snap_rows WHERE status IS NOT NULL
UNION ALL SELECT ts, pane_id, 'closed', 'close' FROM herdr_events WHERE ev IN ('pane_closed', 'pane_exited');

-- A wait opens when a pane goes working -> blocked/done/idle while another pane has focus. It
-- ends at the first of: that pane is focused, works again, closes, or is missing from a
-- snapshot. One wait counts at most 8 h; one still open ends at `now`.
CREATE OR REPLACE VIEW agent_waits AS
WITH r AS (SELECT *, lag(status) OVER (PARTITION BY pane_id ORDER BY ts) AS prev FROM pane_records),
f AS (SELECT ts, pane_id FROM herdr_events WHERE ev = 'pane_focused' UNION ALL SELECT ts, pane_id FROM snap_rows WHERE focused),
opens AS (
    SELECT r.pane_id, r.ts AS start FROM r ASOF LEFT JOIN f ON r.ts >= f.ts
    WHERE r.status IN ('blocked', 'done', 'idle') AND r.prev = 'working' AND f.pane_id IS DISTINCT FROM r.pane_id),
ends AS (SELECT ts, pane_id FROM herdr_events WHERE ev = 'pane_focused'
         UNION ALL SELECT ts, pane_id FROM pane_records WHERE status IN ('working', 'closed')),
o AS (
    SELECT pane_id, start, least(
        (SELECT min(e.ts) FROM ends e WHERE e.pane_id = o.pane_id AND e.ts > o.start),
        (SELECT min(s.ts) FROM snapshots s WHERE s.ts > o.start
            AND NOT EXISTS (SELECT 1 FROM snap_rows x WHERE x.ts = s.ts AND x.pane_id = o.pane_id))) AS closed_at
    FROM opens o)
SELECT pane_id, start, least(secs(start, coalesce(closed_at, getvariable('now'))), 8 * 3600) AS seconds, closed_at IS NULL AS still_open FROM o;

-- Working-pane count once a minute, over the minutes of active hours in [a, b) after the first
-- herdr record. A pane counts when its latest record says working and is not older than the
-- latest snapshot (a pane missing from the latest snapshot is gone).
CREATE OR REPLACE MACRO parallel_samples(a, b) AS TABLE
    WITH lo AS (SELECT to_timestamp(ceil(epoch(greatest(a, (SELECT min(ts) FROM herdr_events))) / 60) * 60) AS x),
    ticks AS (SELECT unnest(generate_series(x, b - INTERVAL 1 MICROSECOND, INTERVAL 1 MINUTE)) AS tick FROM lo WHERE x < b),
    t AS (SELECT tick FROM ticks WHERE floor(epoch(tick) / 3600) IN (SELECT h FROM active_hours(a, b)))
    SELECT t.tick, count(*) FILTER (WHERE r.status = 'working' AND (s.ts IS NULL OR r.ts >= s.ts)) AS n
    FROM t LEFT JOIN (SELECT DISTINCT pane_id FROM pane_records) p ON true
    ASOF LEFT JOIN pane_records r ON r.pane_id = p.pane_id AND r.ts <= t.tick
    ASOF LEFT JOIN snapshots s ON s.ts <= t.tick
    GROUP BY t.tick;
