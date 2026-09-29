"""Tests for usage_stats.py and the SQL metrics, on small fixtures. Run:
    python3 -m unittest discover -s <scripts dir>/tests
The metric tests run ../sql through the `duckdb` CLI, as the script does.
"""
import contextlib, importlib.util, io, json, os, shutil, tempfile, time, unittest
from pathlib import Path

os.environ["TZ"] = "UTC"  # local-day and hour logic (Python and DuckDB) reads the host TZ; pin it
time.tzset()
HERE = Path(__file__).resolve().parent.parent
SRC = next(p for p in (HERE / "usage_stats.py", HERE / "executable_usage_stats.py") if p.exists())
spec = importlib.util.spec_from_file_location("usage_stats", SRC)
us = importlib.util.module_from_spec(spec); spec.loader.exec_module(us)
needs_duckdb = unittest.skipUnless(shutil.which("duckdb"), "duckdb CLI not on PATH")

T0 = us.epoch("2026-09-28T00:00:00Z")  # a Monday
DAY = (T0, T0 + 86400, 1)
def iso(sec): return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(T0 + sec))
def H(h): return h * 3600

def claude_line(sec, sid, ev, container=False, **kw):
    return {"ts": iso(sec), "host": "h", "container": container, "pane": "p", "tab": "t", "dl_ws": "",
            "ev": {"session_id": sid, "cwd": kw.pop("cwd", "/workspaces/kinisi_ros/src"), "hook_event_name": ev, **kw}}

def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for r in rows:
            f.write((r if isinstance(r, str) else json.dumps(r)) + "\n")

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.d = Path(self.tmp.name)
        self.tele, self.cache, self.root = self.d / "telemetry", self.d / "cache", self.d / "projects"
        self.dl = self.d / "events.jsonl"
        for p in (self.tele, self.cache, self.root):
            p.mkdir()
    def tearDown(self): self.tmp.cleanup()
    def src(self, now=T0 + 3 * 86400):
        return dict(telemetry_dir=self.tele, dl_events=self.dl, cache_dir=self.cache, now=now, load_from=T0 - 86400)
    def metrics(self, window=DAY, **kw):
        us.refresh_cache(self.root, self.cache, self.tele)
        return us.evaluate(self.src(**kw), [window])[0][0]
    def report(self, name, window=DAY):
        us.refresh_cache(self.root, self.cache, self.tele)
        return us.evaluate(self.src(), [window], [us.SQL / "reports" / f"{name}.sql"])[1][name]
    def claude(self, rows):
        for r in rows:
            write_jsonl(self.tele / f"claude-{r['ts'][:10]}.jsonl", [r])
    def herdr(self, rows):
        write_jsonl(self.tele / "herdr-2026-09-28.jsonl", [{"ts": iso(s), "ev": e, "data": d} for s, e, d in rows])
    def sql(self, q):
        return us.duck("\n".join([*(f"SET VARIABLE {k} = {us.at(v) if k in ('now', 'load_from') else us.lit(v)};"
                                    for k, v in self.src().items()), (us.SQL / "sources.sql").read_text(), q + ";"]))[0]

@needs_duckdb
class Sources(Base):
    def test_claude_events_skip_null_ev_and_bad_lines(self):
        write_jsonl(self.tele / "claude-2026-09-28.jsonl", ["not json", '{"ts": "2026-09-28T00:00:0', {"ts": iso(5), "ev": None}])
        self.claude([claude_line(10, "s1", "SessionStart", container=True)])
        self.assertEqual(self.sql("SELECT session, hook, container FROM claude_events"),
                         [{"session": "s1", "hook": "SessionStart", "container": True}])

    def test_herdr_view_normalises_the_dotted_status_event(self):
        # herdr's real name for it; logs written before the logger normalised it keep the dot
        self.herdr([(10, "pane.agent_status_changed", {"pane_id": "a", "agent_status": "working"}),
                    (20, "pane_focused", {"pane_id": "a"})])
        self.assertEqual(self.sql("SELECT ev, pane_id, agent_status FROM herdr_events ORDER BY ts"),
                         [{"ev": "pane_agent_status_changed", "pane_id": "a", "agent_status": "working"},
                          {"ev": "pane_focused", "pane_id": "a", "agent_status": None}])

    def test_missing_logs_give_null(self):
        m = self.metrics()
        for k in ("response_latency_p50_s", "agent_wait_hours_per_day", "parallel_agents_p50", "parallel_agents_max",
                  "active_hours_per_day", "focus_switches_per_active_hour", "session_wall_minutes_p50", "container_share",
                  "dl_cold_starts_per_day", "dl_start_seconds_p50", "aid_start_seconds_p50", "agent_start_seconds_p50",
                  "cache_read_share", "poll_share", "bash_error_rate"):
            self.assertIsNone(m[k], k)
        self.assertEqual(m["tokens_per_day"], 0)

    def test_every_metric_and_report_runs_on_empty_sources(self):
        files = us.metric_files()
        self.assertGreater(len(files), 30)
        rows = self.sql("\nUNION ALL\n".join(
            f"SELECT {us.lit(f.stem)} AS name, count(*) AS n, any_value(value)::DOUBLE AS v FROM (\n{us.body(f)}\n)" for f in files))
        self.assertEqual({r["name"]: r["n"] for r in rows}, {f.stem: 1 for f in files})
        per, reports, _ = us.evaluate(self.src(), [DAY], us.report_files())
        self.assertEqual(set(reports), {f.stem for f in us.report_files()})

    def test_every_friction_theme_has_a_metric(self):
        names = {f.stem for f in us.metric_files()}
        for label in us.FRICTION:
            self.assertIn(f"friction_{us.slug(label)}_per_day", names)

    def test_dl_and_aid_start_times(self):
        write_jsonl(self.dl, [
            {"ts": iso(10), "ev": "aid_start", "ws": "w1", "repo": "r", "seconds": 5.0, "stages": {"pick": 1.0, "boot_wait": 4.0}},
            {"ts": iso(20), "ev": "launch", "ws": "w1", "repo": "r", "cold": True, "seconds": 40.0, "stages": None},
            {"ts": iso(100), "ev": "aid_start", "ws": "w2", "repo": "r", "seconds": 7.0, "stages": {"pick": 3.0}},
            {"ts": iso(110), "ev": "launch", "ws": "w2", "repo": "r", "cold": False, "seconds": 4.0, "new_field": 1},
            {"ts": iso(200), "ev": "aid_start", "ws": "w3", "seconds": 9.0},   # no launch follows: not a full start
            {"ts": iso(300), "ev": "stop", "ws": "w1"}, "garbage"])
        m = self.metrics()
        self.assertEqual((m["dl_cold_starts_per_day"], m["dl_start_seconds_p50"]), (1, 22.0))
        self.assertEqual(m["aid_start_seconds_p50"], 7.0); self.assertAlmostEqual(m["aid_start_seconds_p90"], 8.6)
        self.assertEqual(m["agent_start_seconds_p50"], 28.0)  # median of 45 and 11
        stages = {(r["ev"], r["stage"]): r["n"] for r in self.report("start_time_by_stage")}
        self.assertEqual(stages, {("aid_start", "pick"): 2, ("aid_start", "boot_wait"): 1})
        self.assertEqual(self.sql("SELECT (j->>'new_field')::INT AS x FROM dl_events WHERE (j->>'new_field') IS NOT NULL"), [{"x": 1}])

@needs_duckdb
class Telemetry(Base):
    def test_latency_with_overnight_gap_and_subagent_prompt(self):
        self.claude([
            claude_line(H(10), "s1", "Stop"), claude_line(H(10) + 30, "s1", "UserPromptSubmit", prompt="next"),       # 30 s
            claude_line(H(11), "s1", "Stop"), claude_line(H(11) + 5, "s1", "UserPromptSubmit", prompt="<task-notification>"),
            claude_line(H(11) + 90, "s1", "UserPromptSubmit", prompt="ok"),  # a subagent prompt cancelled the Stop
            claude_line(H(12), "s1", "Stop"), claude_line(H(12) + 90, "s2", "UserPromptSubmit", prompt="other"),      # other session
            claude_line(H(12) + 120, "s1", "UserPromptSubmit", prompt="back"),                                        # 120 s
            claude_line(H(22), "s1", "Stop"), claude_line(H(22) + H(10), "s1", "UserPromptSubmit", prompt="morning"),  # overnight
        ])
        m = self.metrics()
        self.assertEqual((m["response_latency_p50_s"], m["response_latency_p90_s"]), (75, 111))
        self.assertEqual(m["active_hours_per_day"], 3)  # hours 10, 11, 12 (the 08:00 next-day prompt is outside)
        self.assertEqual([(r["hour"], r["n"]) for r in self.report("latency_by_hour")], [(10, 1), (12, 1)])

    def test_session_wall_container_share_and_repo(self):
        repo = self.d / "clone"; (repo / ".git").mkdir(parents=True); (repo / "sub").mkdir()
        self.claude([
            claude_line(H(1), "s1", "SessionStart"), claude_line(H(1) + 600, "s1", "SessionEnd"),
            claude_line(H(2), "s2", "SessionStart", container=True), claude_line(H(2) + 1200, "s2", "Stop"),
            claude_line(H(3), "s3", "Stop", cwd=str(repo / "sub")),  # started before telemetry: no wall time
            claude_line(H(4), "s4", "Stop", cwd="/nowhere/x"),
        ])
        m = self.metrics()
        self.assertEqual(m["session_wall_minutes_p50"], 15)
        self.assertEqual(m["container_share"], 0.25)
        self.assertEqual({r["repo"]: r["sessions"] for r in self.report("sessions_by_repo")}, {"kinisi_ros": 2, "clone": 1, "x": 1})

    def test_repo_mapping(self):
        self.assertEqual(us.repo_of("/workspaces/kinisi_ros/src/pkg"), "kinisi_ros")
        self.assertEqual(us.repo_of("/nowhere/on/this/host/myrepo"), "myrepo")
        repo = self.d / "clone"; (repo / ".git").mkdir(parents=True); (repo / "a" / "b").mkdir(parents=True)
        self.assertEqual(us.repo_of(str(repo / "a" / "b")), "clone")
        self.assertEqual(us.repo_of(str(repo / ".claude" / "worktrees" / "agent-1")), "clone")
        self.assertEqual(us.repo_of(None), "?")

    def test_wait_capped_and_closed_by_focus_or_working(self):
        snap = [{"pane_id": "a", "agent_status": "working", "focused": False},
                {"pane_id": "b", "agent_status": "working", "focused": True}]
        self.herdr([
            (H(1), "panes", snap),
            (H(1) + 60, "pane_agent_status_changed", {"pane_id": "a", "agent_status": "blocked"}),
            (H(1) + 660, "pane_focused", {"pane_id": "a"}),                                             # a: 600 s
            (H(2), "pane.agent_status_changed", {"pane_id": "a", "agent_status": "working"}),           # dotted name
            (H(2) + 50, "pane_focused", {"pane_id": "b"}),
            (H(2) + 100, "pane_agent_status_changed", {"pane_id": "b", "agent_status": "done"}),     # focused: no wait
            (H(3) + 10, "pane_agent_status_changed", {"pane_id": "a", "agent_status": "idle"}),
            (H(3) + 20, "pane_agent_status_changed", {"pane_id": "a", "agent_status": "done"}),      # same wait goes on
            (H(15), "pane_focused", {"pane_id": "a"}),                                                  # 12 h -> capped 8 h
        ])
        self.assertEqual(sorted(r["seconds"] for r in self.sql("SELECT seconds FROM agent_waits")), [600, 8 * 3600])
        m = self.metrics()
        self.assertAlmostEqual(m["agent_wait_hours_per_day"], (600 + 8 * 3600) / 3600)
        self.assertEqual(m["focus_switches_per_active_hour"], 0.75)  # 3 focus events over active hours 1, 2, 3, 15

    def test_wait_closed_by_missing_from_snapshot_and_open_wait_ends_at_now(self):
        self.herdr([
            (H(1), "panes", [{"pane_id": "a", "agent_status": "working"}, {"pane_id": "b", "agent_status": "working"}]),
            (H(1) + 100, "pane_agent_status_changed", {"pane_id": "a", "agent_status": "done"}),
            (H(1) + 200, "pane_agent_status_changed", {"pane_id": "b", "agent_status": "done"}),
            (H(1) + 400, "panes", [{"pane_id": "b", "agent_status": "done"}]),  # a is gone
        ])
        self.assertEqual(sorted(r["seconds"] for r in self.sql("SELECT seconds FROM agent_waits")), [300, 8 * 3600])  # b is still open: capped at 8 h
        self.assertEqual(self.metrics(now=T0 + H(1) + 2000)["agent_wait_hours_per_day"], 2100 / 3600)

    def test_parallel_count(self):
        self.herdr([
            (H(1), "panes", [{"pane_id": p, "agent_status": "working"} for p in "abc"]),
            (H(1) + 1800, "pane_agent_status_changed", {"pane_id": "a", "agent_status": "idle"}),
            (H(1) + 2400, "pane_closed", {"pane_id": "b"}),
        ])
        samples = [r["n"] for r in self.sql("SELECT n FROM parallel_samples(to_timestamp(%r), to_timestamp(%r)) ORDER BY tick" % (T0, T0 + 86400))]
        self.assertEqual((len(samples), samples.count(3), samples.count(2), samples.count(1)), (60, 30, 10, 20))
        m = self.metrics()
        self.assertEqual((m["parallel_agents_p50"], m["parallel_agents_max"]), (2.5, 3))

@needs_duckdb
class Transcripts(Base):
    def transcript(self, rows, name="s1", sub=None):
        f = self.root / "-p" / (f"{sub}/subagents/{name}.jsonl" if sub else f"{name}.jsonl")
        write_jsonl(f, rows)
        return f

    @staticmethod
    def turn(sec, mid, ctx, tools=(), cache_read=0, out=10):
        return {"type": "assistant", "timestamp": iso(sec), "message": {"id": mid, "model": "x",
                "usage": {"input_tokens": ctx - cache_read, "cache_read_input_tokens": cache_read, "output_tokens": out},
                "content": [{"type": "tool_use", "id": f"{mid}-{i}", "name": n, "input": inp} for i, (n, inp) in enumerate(tools)]}}

    def test_turn_metrics_and_poll_kinds(self):
        B = lambda cmd, **kw: ("Bash", {"command": cmd, **kw})
        self.transcript([
            {"type": "user", "timestamp": iso(H(1)), "message": {"content": "keep going"}},
            self.turn(H(1) + 1, "m1", 100_000, [B("sleep 5; gh pr checks")], cache_read=90_000),   # settle
            self.turn(H(1) + 2, "m2", 250_000, [B("sleep 30")]),                                    # loop, 50k over 200k
            self.turn(H(1) + 3, "m3", 100_000, [B("until gh pr checks; do sleep 5; done")]),       # loop
            self.turn(H(1) + 4, "m4", 100_000, [B("gh run watch --watch 1")]),                     # watch
            self.turn(H(1) + 5, "m5", 100_000, [("Monitor", {})]),                                  # tool
            self.turn(H(1) + 6, "m6", 100_000, [B("sleep 60", run_in_background=True), B("ls")]),  # not a poll
            {"type": "user", "timestamp": iso(H(1) + 7), "toolUseResult": {}, "message": {"content": [
                {"type": "tool_result", "tool_use_id": "m6-1", "is_error": True, "content": "No such file"}]}},
            "{\"type\": \"assistant\", \"timest",  # truncated line
        ])
        self.transcript([self.turn(H(2), "k1", 250_000)], name="agent-1", sub="s1")
        m = self.metrics()
        self.assertEqual(m["tokens_per_day"], 1_000_000)
        self.assertEqual(m["cache_read_share"], 0.09)
        self.assertEqual(m["poll_share"], 0.65)
        self.assertEqual(m["poll_loop_share"], 0.35)
        self.assertEqual(m["over_200k_share"], 0.1)
        self.assertEqual(m["subagent_share"], 0.25)
        self.assertEqual(m["bash_error_rate"], 1 / 6)
        self.assertEqual((m["friction_nudge_per_day"], m["prompts_per_day"], m["sessions_per_day"]), (1, 1, 1))
        kinds = {r["kind"]: r["turns"] for r in self.report("poll_by_kind")}
        self.assertEqual(kinds, {"settle": 1, "loop": 2, "watch": 1, "tool": 1})
        half = self.metrics(window=(T0, T0 + 2 * 86400, 2))  # a per-day metric halves, a share does not
        self.assertEqual((half["tokens_per_day"], half["poll_share"]), (500_000, 0.65))

    def test_cache_rebuilds_only_when_the_transcript_changes(self):
        f = self.transcript([self.turn(H(1), "m1", 1000)])
        us.refresh_cache(self.root, self.cache, self.tele)
        c = self.cache / "transcripts" / "-p" / "s1.jsonl"
        c.write_text("")  # a stale cache file with the same mtime is kept ...
        os.utime(c, ns=(f.stat().st_mtime_ns,) * 2)
        us.refresh_cache(self.root, self.cache, self.tele)
        self.assertEqual(c.read_text(), "")
        write_jsonl(f, [self.turn(H(2), "m2", 1000)])  # ... and rebuilt when the transcript changes
        us.refresh_cache(self.root, self.cache, self.tele)
        self.assertEqual(len(c.read_text().splitlines()), 2)
        f.unlink(); us.refresh_cache(self.root, self.cache, self.tele)
        self.assertFalse(c.exists())

class Ledger(unittest.TestCase):
    def test_verdicts(self):
        e = dict(metric="poll_share", direction="down", baseline=0.10, target=0.05)
        self.assertEqual(us.verdict(e, {"poll_share": 0.08}), "on-track")
        self.assertEqual(us.verdict(e, {"poll_share": 0.04}), "on-track, target met")
        self.assertEqual(us.verdict(e, {"poll_share": 0.12}), "off-track")
        self.assertEqual(us.verdict(e, {"poll_share": None}), "no-data")
        self.assertEqual(us.verdict(dict(e, metric="nope"), {}), "no-data")
        self.assertEqual(us.verdict(dict(e, direction="up", target=0.2), {"poll_share": 0.12}), "on-track")

    def test_due_line(self):
        led = [dict(id="E001", metric="poll_share", direction="down", baseline=0.1, target=0.05, check="2026-09-28", status="running"),
               dict(id="E002", metric="poll_share", status="kept")]
        lines = us.experiment_lines(led, {"poll_share": 0.2}, "2026-09-29")
        self.assertEqual(len(lines), 1)
        self.assertIn("off-track · DUE", lines[0])

    def test_ledger_metrics_exist(self):
        names = {f.stem for f in us.metric_files()}
        for n in ("friction_nudge_per_day", "over_200k_share", "poll_share"):  # E001-E003
            self.assertIn(n, names)

@needs_duckdb
class EndToEnd(Base):
    def test_main_digest_out_and_month(self):
        tr = [{"type": "user", "timestamp": iso(H(10)), "message": {"content": "keep going"}},
              {"type": "assistant", "timestamp": iso(H(10) + 5), "message": {"id": "m1", "model": "x",
               "usage": {"input_tokens": 100, "cache_read_input_tokens": 900, "output_tokens": 50}, "content": []}}]
        write_jsonl(self.root / "-p" / "s1.jsonl", tr)
        os.utime(self.root / "-p" / "s1.jsonl", (T0 + H(10), T0 + H(10)))
        self.claude([claude_line(H(10), "s1", "Stop"), claude_line(H(10) + 40, "s1", "UserPromptSubmit", prompt="a\nb")])
        ledger = self.d / "reviews" / "experiments.jsonl"
        write_jsonl(ledger, [dict(id="E001", opened="2026-09-20", metric="response_latency_p50_s", direction="down",
                                  baseline=60, target=30, check="2026-10-01", status="running", closed=None, result=None)])
        (self.d / "reviews" / "2026-09-28" / "adhoc").mkdir(parents=True)
        (self.d / "reviews" / "2026-09-28" / "adhoc" / "q.sql").write_text("-- a question\nSELECT 1;\n")
        common = ["--root", str(self.root), "--telemetry", str(self.tele), "--dl-events", str(self.dl), "--cache", str(self.cache),
                  "--ledger", str(ledger), "--now", str(T0 + 86400 + H(9))]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            us.main(common + ["--digest", "--daily-dir", str(self.d / "daily"), "--out", str(self.d / "out")])
        txt = (self.d / "daily" / "2026-09-28.txt").read_text()
        self.assertLessEqual(len(txt.splitlines()), 25)
        self.assertIn("E001 response_latency_p50_s down: now 40", txt)
        st = json.loads((self.d / "out" / "stats.json").read_text())
        m = st["metrics"]
        self.assertEqual((m["tokens_per_day"], m["cache_read_share"], m["friction_nudge_per_day"]), (1000, 0.9, 1))
        self.assertIsNone(m["dl_cold_starts_per_day"])
        self.assertEqual(st["sessions_by_repo"], {"kinisi_ros": 1})
        self.assertEqual(st["tokens"]["cache_read_input_tokens"], 900)  # the old transcript keys stay
        self.assertEqual((self.d / "out" / "prompts_full.txt").read_text(), "s1 10:00 a\\nb\n")
        with contextlib.redirect_stdout(io.StringIO()) as o:
            us.main(common + ["--month"])
        self.assertIn("E001 [running]", o.getvalue())
        self.assertIn("ad-hoc queries: 1", o.getvalue())
        self.assertIn("## sessions_by_repo", o.getvalue())

if __name__ == "__main__":
    unittest.main()
