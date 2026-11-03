"""check-links: confirm each link resolves; GitHub repos through gh, the rest by HTTP."""
import re
import urllib.request

from talklib import emit, read_state, run

state = read_state()
seen, report = set(), []
for item in state["qr_links"] + state["slide_links"]:
    url = item["url"] if isinstance(item, dict) else item
    url = (url if url.startswith("http") else "https://" + url).rstrip("/")
    if url in seen:
        continue
    seen.add(url)
    m = re.match(r"https://github\.com/([^/]+/[^/#?]+)", url)
    if m:
        r = run(["gh", "repo", "view", m.group(1), "--json", "description,updatedAt",
                 "-q", '.description + " (updated " + .updatedAt[:10] + ")"'], check=False)
        ok, detail = r.returncode == 0, (r.stdout or r.stderr).strip()[:200]
    else:
        try:
            req = urllib.request.Request(url, method="GET", headers={"User-Agent": "talk-skill"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                ok, detail = resp.status < 400, f"HTTP {resp.status} -> {resp.url}"
        except Exception as e:  # noqa: BLE001 - any failure means the link is not confirmed
            ok, detail = False, str(e)[:200]
    report.append({"url": url, "ok": ok, "detail": detail})

emit({"link_report": report, "broken_links": sum(not r["ok"] for r in report)})
