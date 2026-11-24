#!/usr/bin/env python3
"""Scan a cloud_services diff for changes that break at apply time or at run time.

`terraform plan`, `validate`, tflint and tfsec pass every one of these. Each rule
names the incident that taught it (see ../references/incidents.md). Stdlib only.

Usage:
    infra_risks.py [--base REF] [--head REF] [--repo DIR] [--json]

    --base  default: merge-base of origin/main and HEAD
    --head  default: HEAD (the working tree is NOT read; commit first)

Exit status: 2 when any BLOCK finding exists, 1 when only CHECK findings exist,
0 when the diff is clean. A BLOCK is a known apply or run failure: do not approve
until the author fixes it or shows the rule does not apply. A CHECK is a question
the reviewer must answer from the plan, the provider docs or the code, and write
down in the review; it is never posted as-is.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import PurePosixPath

BLOCK, CHECK = "BLOCK", "CHECK"

# Roots that terraform-apply.yaml does NOT apply after merge.
MANUAL_ROOTS = ("infra/universe/", "infra/cloud-bridge-dev/", "infra/billing/")

HEADER = re.compile(
    r'^(resource|data|module|moved|removed|import|locals|variable|output|terraform|provider)\b'
    r'(?:\s+"([^"]+)")?(?:\s+"([^"]+)")?\s*\{\s*$'
)


@dataclass
class Block:
    kind: str
    type: str
    name: str
    path: str
    start: int  # 1-based, inclusive
    end: int
    text: str

    @property
    def addr(self) -> str:
        return f"{self.type}.{self.name}" if self.kind == "resource" else f"{self.kind}.{self.type}"

    @property
    def key(self) -> str:
        """The address within its module directory: type.name repeats across modules."""
        return f"{PurePosixPath(self.path).parent}::{self.addr}"


@dataclass
class Finding:
    level: str
    rule: str
    path: str
    line: int
    message: str
    incident: str

    def render(self) -> str:
        return f"{self.level} {self.rule} {self.path}:{self.line}\n  {self.message}\n  (from {self.incident})"


@dataclass
class Tree:
    """All .tf blocks of one commit."""
    rev: str
    repo: str
    files: dict[str, str] = field(default_factory=dict)
    blocks: list[Block] = field(default_factory=list)

    def load(self) -> "Tree":
        names = git(self.repo, "ls-tree", "-r", "--name-only", self.rev).splitlines()
        for p in names:
            if p.endswith(".tf"):
                try:
                    text = git(self.repo, "show", f"{self.rev}:{p}")
                except subprocess.CalledProcessError:
                    continue
                self.files[p] = text
                self.blocks += parse_blocks(p, text)
        return self

    def resources(self) -> dict[str, Block]:
        return {b.key: b for b in self.blocks if b.kind == "resource"}

    def types(self) -> set[str]:
        return {b.type for b in self.blocks if b.kind == "resource"}


def git(repo: str, *args: str) -> str:
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


def parse_blocks(path: str, text: str) -> list[Block]:
    """Top-level HCL blocks by brace count. Braces inside strings are rare here and balanced."""
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        m = HEADER.match(lines[i])
        if not m:
            i += 1
            continue
        depth, j = 0, i
        while j < len(lines):
            s = strip_comment(lines[j])
            depth += s.count("{") - s.count("}")
            if depth <= 0 and j > i or (depth == 0 and j == i and "}" in s):
                break
            j += 1
        out.append(Block(m.group(1), m.group(2) or "", m.group(3) or "", path, i + 1, j + 1,
                         "\n".join(lines[i:j + 1])))
        i = j + 1
    return out


def strip_comment(line: str) -> str:
    # Good enough for this repo: '#' and '//' comments, no '#' inside strings we care about.
    for tok in ("#", "//"):
        k = line.find(tok)
        if k >= 0 and line[:k].count('"') % 2 == 0:
            line = line[:k]
    return line


def _norm(parts: list[str]) -> list[str]:
    out: list[str] = []
    for p in parts:
        if p in ("", "."):
            continue
        if p == ".." and out:
            out.pop()
        else:
            out.append(p)
    return out


def code(text: str) -> str:
    return "\n".join(strip_comment(l) for l in text.splitlines())


def changed_lines(repo: str, base: str, head: str) -> tuple[dict[str, set[int]], dict[str, set[int]], list[str]]:
    """Per file: post-image line numbers added, pre-image line numbers removed; and all changed paths."""
    diff = git(repo, "diff", "-U0", "--no-color", "--no-renames", f"{base}..{head}")
    added: dict[str, set[int]] = {}
    removed: dict[str, set[int]] = {}
    paths: list[str] = []
    cur_old = cur_new = None
    for line in diff.splitlines():
        if line.startswith("--- "):
            cur_old = None if line[4:] == "/dev/null" else line[6:]
        elif line.startswith("+++ "):
            cur_new = None if line[4:] == "/dev/null" else line[6:]
            paths.append(cur_new or cur_old)
        elif line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            o, oc, n, nc = int(m[1]), int(m[2] or 1), int(m[3]), int(m[4] or 1)
            if cur_old:
                removed.setdefault(cur_old, set()).update(range(o, o + oc))
            if cur_new:
                added.setdefault(cur_new, set()).update(range(n, n + nc))
    return added, removed, paths


def attr(text: str, name: str) -> str | None:
    m = re.search(rf'^\s*{name}\s*=\s*(.+?)\s*$', code(text), re.M)
    return m.group(1) if m else None


def has_block(text: str, name: str) -> bool:
    return re.search(rf'^\s*{name}\s*\{{', code(text), re.M) is not None


def sub_blocks(text: str, name: str) -> list[str]:
    """Text of every nested `name { ... }` block."""
    out, lines = [], code(text).splitlines()
    for i, l in enumerate(lines):
        if re.match(rf'^\s*{name}\s*\{{', l):
            depth, j = 0, i
            while j < len(lines):
                depth += lines[j].count("{") - lines[j].count("}")
                if depth <= 0:
                    break
                j += 1
            out.append("\n".join(lines[i:j + 1]))
    return out


def line_of(b: Block, pattern: str) -> int:
    for k, l in enumerate(b.text.splitlines()):
        if re.search(pattern, strip_comment(l)):
            return b.start + k
    return b.start


def ignore_changes(text: str) -> list[str]:
    m = re.search(r'ignore_changes\s*=\s*\[(.*?)\]', code(text), re.S)
    if not m:
        return []
    return [re.split(r'[\[.]', t.strip())[0] for t in m.group(1).split(",") if t.strip()]


def doc_length(b: Block, head: Tree) -> tuple[int | None, str]:
    """Literal length of documentation.content, or None when it is computed."""
    docs = sub_blocks(b.text, "documentation")
    if not docs:
        return 0, ""
    d = docs[0]
    raw = b.text[b.text.find("documentation"):]
    m = re.search(r'content\s*=\s*<<-?(\w+)\n(.*?)\n\s*\1', raw, re.S)
    if m:
        body = m.group(2)
        # Resolve ${local.x} when x is a literal heredoc in this commit; count others as unknown.
        unknown = []

        def local_len(mm: re.Match) -> str:
            name = mm.group(1)
            for text in head.files.values():
                lm = re.search(rf'^\s*{name}\s*=\s*<<-?(\w+)\n(.*?)\n\s*\1', text, re.S | re.M)
                if lm:
                    return lm.group(2)
            unknown.append(name)
            return ""
        body = re.sub(r'\$\{local\.(\w+)\}', local_len, body)
        if unknown or re.search(r'\$\{(var|file|templatefile|join)\b', body):
            return None, "content interpolates a value this scan cannot render"
        # Each remaining ${...} renders to some text; count it as its own length.
        return len(body), ""
    if re.search(r'content\s*=\s*(file|templatefile|local\.|var\.|join)', d):
        return None, "content is computed"
    m = re.search(r'content\s*=\s*"(.*)"', d)
    return (len(m.group(1)) if m else None), ""


def run_rules(base: Tree, head: Tree, added, removed, paths) -> list[Finding]:
    f: list[Finding] = []
    head_res, base_res = head.resources(), base.resources()
    new_addrs = set(head_res) - set(base_res)
    gone_addrs = set(base_res) - set(head_res)
    base_types = base.types()
    all_head_text = "\n".join(head.files.values())
    moved_from = set(re.findall(r'from\s*=\s*([\w.\[\]"-]+)', all_head_text))
    removed_from = set(re.findall(r'removed\s*\{[^}]*?from\s*=\s*([\w.]+)', all_head_text, re.S))

    def touched(b: Block) -> bool:
        ls = added.get(b.path, set())
        return any(b.start <= n <= b.end for n in ls)

    changed = [b for b in head.blocks if b.kind == "resource" and touched(b)]

    for b in changed:
        t, c = b.text, code(b.text)
        is_new = b.key in new_addrs
        mdir = str(PurePosixPath(b.path).parent)

        # --- Monitoring --------------------------------------------------------
        if b.type == "google_monitoring_alert_policy":
            log_based = "condition_matched_log" in c
            if has_block(t, "notification_rate_limit") and not log_based:
                f.append(Finding(BLOCK, "alert-rate-limit-metric", b.path, line_of(b, "notification_rate_limit"),
                    "notification_rate_limit on a metric-based policy: the API returns 400 "
                    "(only log-based policies may set it). Plan is clean; apply fails.", "#541 -> #542"))
            for cond in sub_blocks(t, r"condition_\w+"):
                if "evaluation_missing_data" in cond:
                    dur = re.search(r'duration\s*=\s*"(\d+)s"', cond)
                    if not dur or dur.group(1) == "0":
                        f.append(Finding(BLOCK, "alert-missing-data-zero-duration", b.path,
                            line_of(b, "evaluation_missing_data"),
                            "evaluation_missing_data on a condition with duration 0s (or unset): the API "
                            "returns 400. Set duration >= 60s or drop the field.", "#733 -> #735, #736"))
            n, why = doc_length(b, head)
            cap = 4000 if log_based else 8192
            if n is None:
                f.append(Finding(CHECK, "alert-doc-length", b.path, line_of(b, "documentation"),
                    f"documentation {why}; render it and confirm <= {cap} chars. Over the cap the API "
                    "accepts the update but leaves the policy disabled (apply reports success).",
                    "#975 -> #999"))
            elif n > cap:
                f.append(Finding(BLOCK, "alert-doc-length", b.path, line_of(b, "documentation"),
                    f"documentation is {n} chars, cap {cap}: the policy is silently disabled on apply.",
                    "#975 -> #999"))
            # Log metric created in the same apply as the alert that reads it.
            for m in re.finditer(r'logging\.googleapis\.com/user/([\w.-]+)|google_logging_metric\.(\w+)', c):
                name = m.group(1) or m.group(2)
                for a in new_addrs:
                    mb = head_res[a]
                    if mb.type == "google_logging_metric" and (
                        (m.group(2) and mb.name == name) or
                        (m.group(1) and attr(mb.text, "name") == f'"{name}"')):
                        f.append(Finding(BLOCK, "alert-on-new-log-metric", b.path, line_of(b, "logging|metric"),
                            f"alert reads log metric {mb.addr}, which this same apply creates. The metric "
                            "takes time to propagate, and the alert create returns 404: partial apply. "
                            "Land the metric in an earlier PR, or add a time_sleep between them.",
                            "#113, #928 (E2, E32)"))
                        break

        if b.type == "google_logging_metric" and "value_extractor" in c and "DISTRIBUTION" not in c:
            f.append(Finding(CHECK, "log-metric-shape", b.path, b.start,
                "value_extractor needs a DISTRIBUTION metric and bucket_options; check the API accepts this "
                "metric_descriptor.", "first-use review"))

        # --- Load balancing ----------------------------------------------------
        if b.type == "google_compute_backend_service" and re.search(
                r'google_compute_region_network_endpoint_group|serverless', c):
            for k in ("timeout_sec", "connection_draining_timeout_sec"):
                km = re.search(rf'^\s*{k}\s*=\s*(\S+)', c, re.M)
                if km:
                    f.append(Finding(CHECK if km.group(1) == "30" and k == "timeout_sec" else BLOCK, "serverless-neg-timeout", b.path, line_of(b, k),
                        f"{k} on a backend service with a serverless NEG: the API returns 400.",
                        "#533 -> #536"))

        # --- Storage -----------------------------------------------------------
        if b.type == "google_storage_bucket":
            hns = any("enabled" in s and "true" in s for s in sub_blocks(t, "hierarchical_namespace"))
            ver = any(re.search(r'enabled\s*=\s*true', s) for s in sub_blocks(t, "versioning"))
            if hns and ver:
                f.append(Finding(BLOCK, "hns-versioning", b.path, line_of(b, "versioning"),
                    "versioning on a hierarchical-namespace bucket: the API returns 400.", "#205 -> #211"))
            if re.search(r'force_destroy\s*=\s*true', c):
                f.append(Finding(CHECK, "force-destroy", b.path, line_of(b, "force_destroy"),
                    "force_destroy = true: a replace or destroy of this bucket deletes every object. "
                    "Is the data re-creatable?", "review-caught class"))
            for rule in sub_blocks(t, "lifecycle_rule"):
                if re.search(r'type\s*=\s*"Delete"', rule) and touched(b):
                    f.append(Finding(CHECK, "lifecycle-delete", b.path, line_of(b, "Delete"),
                        "lifecycle Delete rule: name every object class it deletes. A Delete by age hit "
                        "the live Cloud Function source zip that state still pointed at.", "#770 (E23)"))
                    break

        # --- Compute -----------------------------------------------------------
        if b.type in ("google_compute_instance_template", "google_compute_region_instance_template"):
            if re.search(r'instance_termination_action\s*=\s*(.*DELETE|var\.|local\.|each\.)', c):
                used_by_mig = re.search(rf'{b.type}\.{b.name}\b', all_head_text.replace(b.text, "")) and \
                    "instance_group_manager" in all_head_text
                f.append(Finding(BLOCK if "DELETE" in c else CHECK, "spot-mig-delete", b.path,
                    line_of(b, "instance_termination_action"),
                    "spot VM with termination action DELETE in a MIG: GCE refuses the MIG update (the "
                    "template creates fine). Use STOP." + ("" if used_by_mig else " Confirm no MIG uses it."),
                    "#644 -> #648"))
            if re.search(r'name\s*=\s*.*(md5|sha1|sha256|substr)\(', c):
                f.append(Finding(CHECK, "template-name-hash", b.path, line_of(b, r'name\s*='),
                    "template name is a hash of some inputs: every field that forces a new template must "
                    "feed the hash, or create_before_destroy collides on 'already exists'.", "#644 -> #649"))
            if touched(b) and re.search(r'^\s*scopes\s*=', c, re.M):
                f.append(Finding(CHECK, "oauth-scopes", b.path, line_of(b, "scopes"),
                    "VM OAuth scopes cap what IAM grants: a call outside the scope fails 403 even with the "
                    "role. List each API the VM calls and check the scope covers it.", "review-quality escapes"))

        # --- Cloud Run ---------------------------------------------------------
        if b.type.startswith("google_cloud_run"):
            conc = re.search(r'max_instance_request_concurrency\s*=\s*(\d+)', c)
            cpu = re.search(r'cpu\s*=\s*"(\d+m|0\.\d+)"', c)
            if conc and int(conc.group(1)) > 1 and cpu:
                f.append(Finding(BLOCK, "cloud-run-concurrency-cpu", b.path, line_of(b, "concurrency"),
                    "concurrency > 1 with less than 1 vCPU: the API returns 400.", "review-quality escapes"))
            for m in re.finditer(r'google_secret_manager_secret\.(\w+)', c):
                s = f"google_secret_manager_secret.{m.group(1)}"
                skey = f"{mdir}::{s}"
                has_version = any(
                    x.type == "google_secret_manager_secret_version" and str(PurePosixPath(x.path).parent) == mdir
                    and re.search(rf'secret\s*=\s*{re.escape(s)}\.(id|name|secret_id)\b', x.text)
                    for x in head.blocks)
                if skey in new_addrs and not has_version:
                    f.append(Finding(BLOCK, "secret-without-version", b.path, line_of(b, m.group(1)),
                        f"{s} is new and has no google_secret_manager_secret_version: Cloud Run will not "
                        "create a service, job or pool that reads a secret with no version.", "#783/#822 -> #859"))
                elif skey in new_addrs:
                    f.append(Finding(CHECK, "secret-without-version", b.path, line_of(b, m.group(1)),
                        f"{s} is new: confirm a version exists before the service is created (depends_on "
                        "the version, not the secret).", "#783/#822 -> #859"))
            if b.type in ("google_cloud_run_v2_service", "google_cloud_run_v2_worker_pool", "google_cloud_run_service") \
                    and is_new and \
                    not re.search(r'ignore_changes\s*=\s*\[[^\]]*(image|template|containers)', c):
                f.append(Finding(CHECK, "out-of-band-deploy", b.path, b.start,
                    "new Cloud Run resource without ignore_changes on the image: if another repo deploys "
                    "it, every apply rolls it back.", "#443 (E9), #951 (E31)"))

        if b.type == "google_cloudfunctions2_function" and "event_trigger" in c:
            if not re.search(rf'run\.invoker[\s\S]*{b.type}\.{b.name}|{b.type}\.{b.name}[\s\S]{{0,400}}run\.invoker',
                             all_head_text):
                f.append(Finding(CHECK, "function-invoker", b.path, b.start,
                    "event-triggered gen2 function with no run.invoker binding in Terraform: a redeploy "
                    "drops the auto-made binding and delivery fails 401 at run time.", "#370 -> #371 (E3)"))

        # --- Billing / scheduler --------------------------------------------
        if re.search(r'disable_default_iam_recipients\s*=\s*true', c):
            f.append(Finding(BLOCK, "budget-iam-recipients", b.path, line_of(b, "disable_default_iam_recipients"),
                "disable_default_iam_recipients = true: the API returns 400 on a self-serve billing account.",
                "#428 -> #430"))
        if re.search(r'retry_count\s*=\s*0\b', c):
            f.append(Finding(CHECK, "perpetual-diff", b.path, line_of(b, "retry_count"),
                "retry_count = 0 is not persisted by the API: the next plan proposes it again, forever "
                "(drift check red). Omit the block.", "#688 -> #690"))

        # --- Lifecycle -----------------------------------------------------
        ign = ignore_changes(t)
        if ign and not is_new:
            for n in added.get(b.path, set()):
                if not (b.start <= n <= b.end):
                    continue
                l = strip_comment(head.files[b.path].splitlines()[n - 1])
                mm = re.match(r'\s*(\w+)\s*[={]', l)
                if mm and mm.group(1) in ign:
                    f.append(Finding(BLOCK, "edit-under-ignore-changes", b.path, n,
                        f"edits {mm.group(1)}, which lifecycle.ignore_changes lists: the apply reports no "
                        "change and nothing ships.", "#676 -> #687 (E20)"))
                    break
        if re.search(r'create_before_destroy\s*=\s*true', c) and re.search(
                r'^\s*(name|instance_id|account_id|\w+_id)\s*=\s*"[^"$]+"\s*$', c, re.M):
            f.append(Finding(CHECK, "cbd-fixed-name", b.path, line_of(b, "create_before_destroy"),
                "create_before_destroy with a fixed name: a replace creates the new one first and fails "
                "409 'already exists'. Check the plan for a replace of this address.", "#615 -> #624"))
        if b.key in base_res:
            old = code(base_res[b.key].text)
            if "prevent_destroy" in old and "prevent_destroy" not in c or \
               re.search(r'deletion_protection\s*=\s*true', old) and not re.search(r'deletion_protection\s*=\s*true', c):
                f.append(Finding(CHECK, "destroy-guard-weakened", b.path, b.start,
                    "a destroy guard (prevent_destroy / deletion_protection) is removed: say why in the PR.",
                    "best practice"))

        # --- IAM -----------------------------------------------------------
        if re.match(r'google_\w+_iam_policy$', b.type):
            f.append(Finding(BLOCK, "iam-authoritative", b.path, b.start,
                f"{b.type} is authoritative for the whole resource: it removes every grant not in it, "
                "including ones other roots and Google services made.", "best practice"))
        elif re.match(r'google_\w+_iam_binding$', b.type):
            f.append(Finding(CHECK, "iam-authoritative", b.path, b.start,
                f"{b.type} owns every member of its role: any member granted elsewhere (another root, by "
                "hand, the access page) is removed on apply. Prefer _member.", "best practice"))
        if re.match(r'google_\w+_iam_(member|binding)$', b.type) and is_new:
            role = attr(t, "role") or ""
            if re.search(r'roles/(owner|editor|viewer)"|serviceAccountUser|serviceAccountTokenCreator|allUsers|allAuthenticatedUsers', t):
                f.append(Finding(CHECK, "iam-broad", b.path, b.start,
                    f"broad grant ({role or 'see block'}): check it is scoped to the resource, not the project.",
                    "review-caught class"))

        # --- First use of a resource type ------------------------------------
        if b.type not in base_types:
            f.append(Finding(CHECK, "first-use-type", b.path, b.start,
                f"first {b.type} in the repo. Plan cannot see: the API is enabled, terraform-admin can "
                "create it, and each field is legal for this variant (read the API reference, not only "
                "the provider docs). Also: does the access audit understand it?", "#938 -> #942, E1-E33 'A' rows"))

    # --- Renames, removals, moved/removed blocks --------------------------------
    for k in sorted(gone_addrs):
        b = base_res[k]
        a = b.addr
        if any(s.endswith(a) or (a + "[") in s for s in moved_from):
            continue
        if any(s.endswith(a) for s in removed_from):
            continue
        # A rename keeps the body: compare without the header line.
        def body(x: Block) -> str:
            return re.sub(r"\s+", " ", code(x.text).split("\n", 1)[-1])
        keys = ("name", "role", "member", "bucket", "repository", "account_id", "secret_id", "instance_id")

        def same_thing(x: Block, y: Block) -> bool:
            # Same identity attributes = the same cloud object under a new address.
            kx = {k: attr(x.text, k) for k in keys if attr(x.text, k)}
            ky = {k: attr(y.text, k) for k in keys if attr(y.text, k)}
            if kx or ky:
                return kx == ky
            return difflib.SequenceMatcher(None, body(x), body(y)).ratio() >= 0.8
        same_type_new = [head_res[n].addr for n in new_addrs
                         if head_res[n].type == b.type and same_thing(b, head_res[n])]
        if same_type_new:
            f.append(Finding(BLOCK, "rename-without-moved", b.path, b.start,
                f"{a} is gone and {', '.join(same_type_new[:3])} is new, with no moved block: Terraform "
                "destroys and re-creates it (new IP / lost data / IAM gap).", "review-caught class"))
        else:
            f.append(Finding(CHECK, "resource-removed", b.path, b.start,
                f"{a} is removed, so apply destroys it. Who still uses it? Use a removed block with "
                "destroy = false to only forget it.", "review-quality escapes"))
    for b in changed:
        if b.key in base_res:
            old_fe, new_fe = attr(base_res[b.key].text, "for_each"), attr(b.text, "for_each")
            if old_fe and new_fe and old_fe != new_fe:
                f.append(Finding(CHECK, "for-each-keys", b.path, line_of(b, "for_each"),
                    "for_each expression changed: if any key changes, that instance is destroyed and "
                    "re-created. Compare old and new keys in the plan.", "#928 (E32), review-caught class"))

    # --- Non-.tf files that a resource reads (scripts, function sources) ----------
    for path in sorted(set(paths)):
        if path.endswith(".tf") or path not in added and path not in removed:
            continue
        pp = PurePosixPath(path)
        # Through a module: module "x" { startup_script = templatefile(".../changed.sh") } and the
        # module's resource puts var.startup_script in an attribute that ignore_changes lists.
        for mb in head.blocks:
            if mb.kind != "module" or pp.name not in mb.text:
                continue
            src = re.search(r'source\s*=\s*"(\.[^"]+)"', mb.text)
            ref = next((l for l in mb.text.splitlines() if pp.name in l), "")
            arg = re.match(r'\s*(\w+)\s*=', ref)
            if not (src and arg):
                continue
            mdir = str(PurePosixPath(mb.path).parent / src.group(1))
            mdir = "/".join(_norm(mdir.split("/")))
            # var.X, or a local that is built from var.X (one hop).
            names = [rf'var\.{arg.group(1)}']
            for lb in head.blocks:
                if lb.kind == "locals" and lb.path.startswith(mdir + "/"):
                    for l in code(lb.text).splitlines():
                        lm = re.match(rf'\s*(\w+)\s*=.*\bvar\.{arg.group(1)}\b', l)
                        if lm:
                            names.append(rf'local\.{lm.group(1)}')
            for rb in head.blocks:
                if rb.kind != "resource" or not rb.path.startswith(mdir + "/"):
                    continue
                ign = ignore_changes(rb.text)
                for l in code(rb.text).splitlines():
                    m = re.match(rf'\s*(\w+)\s*=.*\b({"|".join(names)})\b', l)
                    if m and (m.group(1) in ign or "all" in ign):
                        f.append(Finding(BLOCK, "edit-under-ignore-changes", path, min(added.get(path, {1}) or {1}),
                            f"{mb.addr} passes this file as {arg.group(1)}; {rb.path} puts it in "
                            f"{rb.addr}.{m.group(1)}, which lifecycle.ignore_changes lists: the apply reports "
                            "no change and the new file never reaches the VM.", "#676 -> #687 (E20)"))
                        break
        for b in head.blocks:
            if b.kind != "resource" or not b.path.startswith(str(pp.parts[0])):
                continue
            # A file() / templatefile() of the changed file, by name.
            if pp.name in b.text:
                ign = ignore_changes(b.text)
                lines = b.text.splitlines()
                for k, l in enumerate(lines):
                    if pp.name not in l:
                        continue
                    # Walk up to the block's own attribute (two-space indent) that holds this reference.
                    top = None
                    for j in range(k, 0, -1):
                        m = re.match(r'^  (\w+)\s*[={]', lines[j])
                        if m:
                            top = m.group(1)
                            break
                    inner = re.match(r'\s*"?([\w-]+)"?\s*=', l)
                    hit = [x for x in (top, inner and inner.group(1)) if x and x in ign]
                    if hit:
                        f.append(Finding(BLOCK, "edit-under-ignore-changes", path, min(added.get(path, {1}) or {1}),
                            f"{b.addr} reads this file into {hit[0]}, which lifecycle.ignore_changes lists: "
                            "the apply reports no change and the new file never reaches the resource.",
                            "#676 -> #687 (E20)"))
                    break
            # Source of an event-triggered gen2 function that has no invoker binding.
            if b.type == "google_cloudfunctions2_function" and "event_trigger" in code(b.text) and \
                    pp.parent.name and pp.parent.name in head.files.get(b.path, "") and \
                    not re.search(rf'run\.invoker[\s\S]*{b.type}\.{b.name}|{b.type}\.{b.name}[\s\S]{{0,400}}run\.invoker',
                                  "\n".join(head.files.values())):
                f.append(Finding(CHECK, "function-invoker", path, 1,
                    f"this change redeploys {b.addr}, an event-triggered gen2 function with no run.invoker "
                    "binding in Terraform: the redeploy can drop the auto-made binding (401 at run time).",
                    "#370 -> #371 (E3)"))

    # --- Path-level rules -----------------------------------------------------
    p = set(paths)
    for path in sorted(p):
        if path.startswith(MANUAL_ROOTS):
            f.append(Finding(CHECK, "manual-root", path, 1,
                "this root is not applied after merge. The PR must say who applies it, when, and attach "
                "that root's plan.", "deploy_failures gap"))
            break
    for path in sorted(p):
        root = str(PurePosixPath(path).parent)
        is_root = any(fp.startswith(root + "/") and fp.count("/") == root.count("/") + 1 and
                      re.search(r'backend\s+"', t) for fp, t in head.files.items())
        if not is_root:  # a child module's lock or required_providers does not pick the version
            continue
        if path.endswith(".terraform.lock.hcl") or (path.endswith(".tf") and path in head.files and
                re.search(r'required_providers|^provider\s', head.files[path], re.M) and
                any(n for n in added.get(path, set()))):
            if path.endswith(".terraform.lock.hcl") or re.search(r'version\s*=|user_project_override|provider\s',
                    "\n".join(head.files[path].splitlines()[n - 1] for n in added.get(path, set())
                              if n - 1 < len(head.files[path].splitlines()))):
                f.append(Finding(CHECK, "provider-change", path, min(added.get(path, {1}) or {1}),
                    "provider or lock change: plan every root that uses it, read the upgrade guide, and "
                    "never apply by hand with a provider newer than the lock.", "#460, #466 -> #467 (E7, E8)"))
                break
    for path in sorted(p):
        if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml")):
            try:
                text = git(head.repo, "show", f"{head.rev}:{path}")
            except subprocess.CalledProcessError:
                continue
            lines = text.splitlines()
            for n in sorted(added.get(path, set())):
                if n - 1 >= len(lines):
                    continue
                l = lines[n - 1]
                if re.search(r'uses:\s*[\w.-]+/[\w./-]+@(?![0-9a-f]{40}\b)', l):
                    f.append(Finding(CHECK, "action-unpinned", path, n,
                        "third-party action not pinned to a full commit SHA.", "tj-actions 2025; repo convention"))
                if "pull_request_target" in l or "workflow_run" in l:
                    f.append(Finding(BLOCK, "untrusted-trigger", path, n,
                        "pull_request_target/workflow_run runs with secrets on PR-controlled input.", "best practice"))
                if re.search(r'run:.*\$\{\{\s*github\.event\.(pull_request|issue|comment|head_commit)', l):
                    f.append(Finding(BLOCK, "script-injection", path, n,
                        "untrusted github.event text expanded inside run: — pass it through env.", "best practice"))
                if re.search(r'continue-on-error:\s*true|\|\|\s*true\b', l):
                    f.append(Finding(CHECK, "swallowed-failure", path, n,
                        "a failure is swallowed: what turns it red again?", "#841 merged red; best practice"))
                if re.search(r'GITHUB_SHA|github\.sha', l) and "repository_dispatch" in text:
                    f.append(Finding(CHECK, "dispatch-sha", path, n,
                        "on repository_dispatch, GITHUB_SHA is the default branch head, not the sender's commit.",
                        "review-caught class"))
            f.append(Finding(CHECK, "workflow-lint", path, 1,
                "run actionlint and zizmor on this workflow; nothing in CI lints workflows.", "deploy_failures gap"))
    for path in sorted(p):
        name = PurePosixPath(path).name
        if name.startswith("Dockerfile") or name.endswith((".pkr.hcl", ".pkr.json")) or "/packer/" in path:
            f.append(Finding(CHECK, "image-build", path, min(added.get(path, {1}) or {1}),
                "image or bake change: build it on the PR (Test Runner Images is not required), check the "
                "image fits the runner/bake disk, and pin new dependencies.", "#580 -> #584, #501, #599"))
            break
    return f


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    base = a.base or git(a.repo, "merge-base", "origin/main", a.head).strip()
    added, removed, paths = changed_lines(a.repo, base, a.head)
    findings = run_rules(Tree(base, a.repo).load(), Tree(a.head, a.repo).load(), added, removed, paths)
    seen, uniq = set(), []
    for x in findings:
        k = (x.rule, x.path, x.line)
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    uniq.sort(key=lambda x: (x.level != BLOCK, x.path, x.line))
    if a.json:
        print(json.dumps([x.__dict__ for x in uniq], indent=1))
    else:
        print(f"infra_risks: {base[:10]}..{a.head} — "
              f"{sum(x.level == BLOCK for x in uniq)} BLOCK, {sum(x.level == CHECK for x in uniq)} CHECK")
        for x in uniq:
            print(x.render())
    return 2 if any(x.level == BLOCK for x in uniq) else 1 if uniq else 0


if __name__ == "__main__":
    sys.exit(main())
