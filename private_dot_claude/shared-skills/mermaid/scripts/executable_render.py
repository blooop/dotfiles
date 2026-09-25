#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.47"]
# ///
"""Render Mermaid diagrams through GitHub's own viewer, light and dark, and check them.

The PNGs are a self-check and go to a throwaway directory; the deliverable is the source.
Takes a .mmd file, or a .md file whose ```mermaid fences are each rendered.
Exit 0 is clean, 1 is a finding (parse error, clipped label, too wide), 2 is a bad input.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

# GitHub's comment column, roughly; a wider diagram is scaled down and its text shrinks with it.
GITHUB_WIDTH = 880
VIEWER = "https://viewscreen.githubusercontent.com/markdown/mermaid?docs_host=https%3A%2F%2Fdocs.github.com&color_mode={mode}#{ident}"
# The viewer only takes the diagram from a github.com parent, so the parent is served at one.
PARENT_URL = "https://github.com/__mermaid_self_check"
IDENT = "selfcheck"
BACKGROUND = {"light": "#ffffff", "dark": "#0d1117"}

PARENT = """<html><body style="margin:0;background:{bg}">
<iframe id="f" src="{viewer}" style="width:{width}px;height:2400px;border:0"></iframe>
<script>
const SRC = {src};
const f = document.getElementById('f');
window.status_ = [];
function cmd(name, payload) {{
  f.contentWindow.postMessage(JSON.stringify(
    {{type: 'render:cmd', identity: '{ident}', body: {{cmd: name, [name]: payload}}}}), '*');
}}
window.addEventListener('message', e => {{
  let d = e.data; try {{ d = typeof d === 'string' ? JSON.parse(d) : d; }} catch {{}}
  if (!d || d.type !== 'render') return;
  window.status_.push(d.body);
  if (d.body === 'hello') cmd('ack', {{}});
  if (d.body === 'code_rendering_service:markdown:get_data') cmd('code_rendering_service:data:ready', {{data: SRC, width: {width}}});
  if (d.body === 'code_rendering_service:container:get_size') cmd('code_rendering_service:container:size', {{width: {width}}});
  if (d.body === 'ready') {{
    if (d.payload && d.payload.height) f.style.height = Math.ceil(d.payload.height) + 'px';
    cmd('code_rendering_service:ready:ack', {{}});
  }}
}});
</script></body></html>"""

# Mermaid sizes each label box from a measurement; GitHub's CSS can then draw the text wider.
INSPECT = """() => {
  const svg = document.querySelector('svg[id^="mermaid"], .mermaid-view svg');
  if (!svg) return {svg: false, error: document.body.innerText.slice(0, 400)};
  if (svg.getAttribute('aria-roledescription') === 'error')
    return {svg: false, error: 'syntax error: ' + [...svg.querySelectorAll('.error-text')].map(t => t.textContent).join(' ')};
  const clipped = [...svg.querySelectorAll('foreignObject')].map(fo => {
    const d = fo.firstElementChild;
    const w = fo.width.baseVal.value;
    return d && d.scrollWidth > w + 1 ? `${d.textContent.trim().slice(0, 60)} (${Math.round(d.scrollWidth)}px text in ${Math.round(w)}px)` : null;
  }).filter(Boolean);
  return {svg: true, width: Math.round(svg.viewBox.baseVal.width),
          nodes: svg.querySelectorAll('g.node').length, clipped};
}"""


def diagrams(path: Path) -> list[str]:
    text = path.read_text()
    if path.suffix == ".md":
        return re.findall(r"^```mermaid\n(.*?)^```", text, re.S | re.M)
    return [text]


def render(page, src: str, mode: str, png: Path) -> dict:
    parent = PARENT.format(bg=BACKGROUND[mode], width=GITHUB_WIDTH, ident=IDENT, src=json.dumps(src),
                           viewer=VIEWER.format(mode=mode, ident=IDENT))
    page.unroute(PARENT_URL)
    page.route(PARENT_URL, lambda r: r.fulfill(status=200, content_type="text/html", body=parent))
    page.goto(PARENT_URL)
    try:
        page.wait_for_function("window.status_.includes('ready') || window.status_.some(s => String(s).startsWith('error'))",
                               timeout=30000)
    except Exception:
        return {"svg": False, "error": "GitHub's viewer did not answer; the check needs network access"}
    page.wait_for_timeout(500)
    frame = next(f for f in page.frames if "viewscreen" in f.url)
    result = frame.evaluate(INSPECT)
    page.screenshot(path=str(png), full_page=True)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path)
    ap.add_argument("--out", type=Path, help="directory for the PNGs (default: a new temp dir)")
    args = ap.parse_args()
    sources = diagrams(args.source)
    if not sources:
        print(f"no mermaid diagram in {args.source}", file=sys.stderr)
        return 2
    out = args.out or Path(tempfile.mkdtemp(prefix="mermaid-check-"))
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True, capture_output=True)
    findings = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": GITHUB_WIDTH + 20, "height": 900})
        for i, src in enumerate(sources, 1):
            for mode in ("light", "dark"):
                png = out / f"diagram{i}-{mode}.png"
                res = render(page, src, mode, png)
                if not res["svg"]:
                    print(f"diagram {i} {mode}: NO DIAGRAM: {res['error']}")
                    findings += 1
                    break
                print(f"diagram {i} {mode}: {png}")
                for c in res["clipped"]:
                    print(f"  WARN clipped label: {c}")
                findings += len(res["clipped"])
            else:
                w, n = res["width"], res["nodes"]
                print(f"diagram {i}: {n} nodes, {w}px wide")
                if w > GITHUB_WIDTH / 0.9:
                    print(f"  WARN GitHub shrinks it to {GITHUB_WIDTH / w:.0%}; text becomes hard to read")
                    findings += 1
                if n > 20:
                    print("  WARN more than 20 nodes; split it")
                    findings += 1
        browser.close()
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
