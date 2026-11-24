#!/usr/bin/env python3
"""Read a Terraform plan and list what will break, delete or silently fail at apply.

Input is either the JSON of `terraform show -json tfplan` (best: values are
rendered, actions are exact) or the text plan the PR Validation workflow posts
as the `<!-- terraform-plan -->` comment (fallback: fewer checks).

Usage:
    plan_risks.py PLAN [--json]

Exit status: 2 when any BLOCK, 1 when only CHECK, 0 when clean. Each finding
names the incident that taught it (see ../references/incidents.md).
"""
from __future__ import annotations

import argparse
import json
import re
import sys

BLOCK, CHECK = "BLOCK", "CHECK"

# Deleting or replacing one of these loses data, an address, a certificate or a
# credential that something outside Terraform depends on.
STATEFUL = re.compile(
    r"google_(storage_bucket|sql_database_instance|sql_database|sql_user|redis_instance|memorystore_instance|"
    r"compute_disk|compute_address|compute_global_address|compute_managed_ssl_certificate|"
    r"certificate_manager_\w+|compute_target_https_proxy|compute_url_map|compute_global_forwarding_rule|"
    r"secret_manager_secret|kms_\w+|bigquery_dataset|bigquery_table|firestore_\w+|"
    r"artifact_registry_repository|service_account|service_account_key|dns_managed_zone|"
    r"filestore_instance|compute_instance|compute_network|compute_subnetwork|project\w*)$"
)
NAME_FIELDS = ("name", "instance_id", "account_id", "secret_id", "repository_id", "dataset_id", "table_id",
               "bucket", "service_id", "job_id", "certificate_id")


def finding(level, rule, addr, msg, incident):
    return {"level": level, "rule": rule, "address": addr, "message": msg, "incident": incident}


def alert_checks(addr: str, after: dict) -> list[dict]:
    out = []
    conds = after.get("conditions") or []
    log_based = any(c.get("condition_matched_log") for c in conds)
    for d in after.get("documentation") or []:
        n = len(d.get("content") or "")
        cap = 4000 if log_based else 8192
        if n > cap:
            out.append(finding(BLOCK, "alert-doc-length", addr,
                f"documentation renders to {n} chars, cap {cap}: the API accepts the update and leaves the "
                "policy disabled; apply reports success.", "#975 -> #999"))
    for s in after.get("alert_strategy") or []:
        if s.get("notification_rate_limit") and not log_based:
            out.append(finding(BLOCK, "alert-rate-limit-metric", addr,
                "notification_rate_limit on a metric-based policy: 400 at apply.", "#541 -> #542"))
    for c in conds:
        for kind, body in c.items():
            if not isinstance(body, list) or not body or not isinstance(body[0], dict):
                continue
            b = body[0]
            if b.get("evaluation_missing_data") and (b.get("duration") in (None, "", "0s")):
                out.append(finding(BLOCK, "alert-missing-data-zero-duration", addr,
                    "evaluation_missing_data with duration 0s: 400 at apply.", "#733 -> #735"))
    return out


def from_json(plan: dict) -> list[dict]:
    out: list[dict] = []
    rcs = plan.get("resource_changes") or []
    creating = {rc["address"]: rc for rc in rcs if rc["change"]["actions"] == ["create"]}
    new_metric_names = {(rc["change"]["after"] or {}).get("name") for a, rc in creating.items()
                        if rc["type"] == "google_logging_metric"}
    new_secrets = {a for a, rc in creating.items() if rc["type"] == "google_secret_manager_secret"}
    new_versions = [rc for a, rc in creating.items() if rc["type"] == "google_secret_manager_secret_version"]

    for rc in rcs:
        a, t, ch = rc["address"], rc["type"], rc["change"]
        acts = ch["actions"]
        before, after = ch.get("before") or {}, ch.get("after") or {}
        unknown = ch.get("after_unknown") or {}
        if rc.get("mode") == "data" or acts == ["no-op"] or acts == ["read"]:
            continue
        reason = rc.get("action_reason", "")
        if "delete" in acts:
            replace = "create" in acts
            cbd = acts == ["create", "delete"]
            verb = ("replaced (create first, then delete)" if cbd else "replaced (delete first)") if replace else "destroyed"
            why = ", ".join("/".join(map(str, p)) for p in (ch.get("replace_paths") or [])) or reason or "removed from config"
            if re.search(r"_iam_(member|binding|policy)$", t):
                out.append(finding(CHECK, "iam-recreate", a,
                    f"IAM grant {verb} ({why}): the member has no access between delete and create, and a "
                    "partial apply leaves it out. Is the key change needed? A moved block keeps it.",
                    "#928 (E32)"))
            elif STATEFUL.search(t):
                out.append(finding(BLOCK, "stateful-delete", a,
                    f"{t} is {verb} because of {why}. Data, IP, certificate or credential is lost unless the PR "
                    "says how it is kept. Block until the PR explains it.", "#429 cascade (E5), review-caught class"))
            else:
                out.append(finding(CHECK, "delete", a, f"{verb} because of {why}.", "plan review"))
            if cbd:
                fixed = [f for f in NAME_FIELDS if before.get(f) and before.get(f) == after.get(f)]
                if fixed:
                    out.append(finding(BLOCK, "cbd-fixed-name", a,
                        f"create-before-destroy with the same {fixed[0]} '{before[fixed[0]]}': the create returns "
                        "409 'already exists' and every later apply is blocked. Change the id on replace.",
                        "#615 -> #624, #644 -> #649"))
        if "update" in acts or "create" in acts:
            # A known map/list that becomes unknown can come back empty (env wipe; see plan_guard.py).
            for k in ("env", "environment_variables", "labels", "metadata"):
                if before.get(k) and unknown.get(k) is True:
                    out.append(finding(CHECK, "known-to-unknown", a,
                        f"{k} goes from known to '(known after apply)': it can apply empty. plan_guard.py "
                        "covers function env only.", "#629 + #630 -> #632 (E18)"))
        if t == "google_monitoring_alert_policy" and after:
            out += alert_checks(a, after)
            if "create" in acts:
                text = json.dumps(after.get("conditions"))
                for name in new_metric_names:
                    if name and f"logging.googleapis.com/user/{name}" in text:
                        out.append(finding(BLOCK, "alert-on-new-log-metric", a,
                            f"reads log metric '{name}', which this same apply creates: 404 at create, partial "
                            "apply. Land the metric first or add a time_sleep.", "#113, #928"))
        if t.startswith("google_cloud_run") and "create" in acts and new_secrets:
            text = json.dumps(after)
            for s in new_secrets:
                sid = (creating[s]["change"]["after"] or {}).get("secret_id")
                if sid and sid in text and not any(
                        sid in json.dumps(v["change"]["after"]) for v in new_versions):
                    out.append(finding(BLOCK, "secret-without-version", a,
                        f"mounts new secret '{sid}' with no version created in this apply: Cloud Run refuses it.",
                        "#783/#822 -> #859"))
        if t == "google_billing_budget" and "disable_default_iam_recipients\": true" in json.dumps(after):
            out.append(finding(BLOCK, "budget-iam-recipients", a, "400 on self-serve billing accounts.", "#428 -> #430"))

    drift = [r["address"] for r in plan.get("resource_drift") or []]
    if drift:
        out.append(finding(CHECK, "drift", ", ".join(drift[:8]) + (" …" if len(drift) > 8 else ""),
            f"{len(drift)} resources changed outside Terraform; this apply reverts them. Who changed them?",
            "E14, E25, E31"))
    return out


SECTION = re.compile(r"^  # (\S+) (will be created|will be destroyed|will be updated in-place|must be replaced|"
                     r"will be replaced[^\n]*|is tainted[^\n]*)", re.M)


def from_text(text: str) -> list[dict]:
    out: list[dict] = []
    if "Terraform plan failed" in text or "Error:" in text and "Plan:" not in text:
        return [finding(BLOCK, "plan-failed", "-", "the PR plan failed: nothing about this PR is known to apply. "
                        "A red plan was ignored for 11 days once.", "#447 (E4), #841")]
    heads = list(SECTION.finditer(text))
    created_metrics = set()
    for i, m in enumerate(heads):
        a, what = m.group(1), m.group(2)
        body = text[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        t = a.split("[")[0].split(".")[-2] if "." in a else a
        sig = re.search(r"^\s*([-+/~]+) resource", body, re.M)
        cbd = bool(sig and sig.group(1) == "+/-")
        if what == "will be created" and t == "google_logging_metric":
            nm = re.search(r'\+ name\s*=\s*"([^"]+)"', body)
            if nm:
                created_metrics.add(nm.group(1))
        if what == "will be destroyed" or "replaced" in what:
            if re.search(r"_iam_(member|binding|policy)$", t):
                out.append(finding(CHECK, "iam-recreate", a, f"IAM grant {what}.", "#928 (E32)"))
            elif STATEFUL.search(t):
                out.append(finding(BLOCK, "stateful-delete", a, f"{t} {what}; say how the data/IP/cert is kept.",
                                   "E5, review-caught class"))
            else:
                out.append(finding(CHECK, "delete", a, what, "plan review"))
            if cbd:
                for f in NAME_FIELDS:
                    mm = re.search(rf'^\s*{f}\s*=\s*"([^"]+)"\s*$', body, re.M)  # unchanged line, no ~/+/-
                    if mm:
                        out.append(finding(BLOCK, "cbd-fixed-name", a,
                            f"create-before-destroy keeps {f} '{mm.group(1)}': 409 at apply.", "#615 -> #624"))
                        break
                else:
                    # The text plan hides unchanged attributes, so a hidden name is an unchanged name.
                    # Top-level attributes only (six spaces). A concrete new value, or a
                    # name_prefix, makes the new resource's name unique; "(known after apply)"
                    # alone is usually the computed full path of the same id (Memorystore).
                    ids = "|".join(NAME_FIELDS)
                    concrete = re.search(rf'^      [~+] ({ids})\s*=\s*(?:"[^"]*"\s*->\s*)?"[^"]+"\s*(#.*)?$', body, re.M)
                    # name_prefix leaves a 26-digit suffix; the new one is generated, so unique.
                    prefixed = re.search(rf'^      ~ ({ids})\s*=\s*"[^"]*[0-9a-f]{{26}}"\s*->\s*\(known after apply\)', body, re.M)
                    if concrete or prefixed:
                        out.append(finding(CHECK, "cbd", a,
                            f"create-before-destroy; {(concrete or prefixed).group(1)} changes, so no 409 here. "
                            "If the name is a hash of inputs, check every replacing field feeds the hash.",
                            "#644 -> #649"))
                    else:
                        out.append(finding(BLOCK, "cbd-fixed-name", a,
                            "create-before-destroy and no identifier changes (the text plan hides unchanged "
                            "ones): the create returns 409 'already exists' unless this type has no unique "
                            "name. Confirm from the config.", "#615 -> #624"))
        if t == "google_monitoring_alert_policy" and what != "will be destroyed":
            log_based = "condition_matched_log" in body
            cap = 4000 if log_based else 8192
            for doc in re.finditer(r"content\s*=\s*<<-?EOT\n(.*?)\n\s*EOT", body, re.S):
                lines = [re.sub(r"^\s{0,14}[-+~ ]?\s*", "", l) for l in doc.group(1).splitlines()
                         if not re.match(r"^\s*-\s", l)]  # the post-image only
                n = len("\n".join(lines))
                if n > cap:
                    out.append(finding(BLOCK, "alert-doc-length", a,
                        f"documentation is about {n} chars after this change, cap {cap}: silently disabled.",
                        "#975 -> #999"))
            if "notification_rate_limit" in body and not log_based and not re.search(r"-\s+notification_rate_limit", body):
                out.append(finding(BLOCK, "alert-rate-limit-metric", a, "400 at apply.", "#541 -> #542"))
            if what == "will be created":
                for nm in created_metrics | set(re.findall(r'logging\.googleapis\.com/user/([\w.-]+)', body)):
                    if nm in created_metrics and f"user/{nm}" in body:
                        out.append(finding(BLOCK, "alert-on-new-log-metric", a,
                            f"reads log metric '{nm}', created in this same apply: 404, partial apply.",
                            "#113, #928"))
    # A metric declared after the alert in the text: second pass.
    for m in heads:
        pass
    if "Objects have changed outside of Terraform" in text:
        out.append(finding(CHECK, "drift", "-", "the plan reports changes made outside Terraform; this apply reverts them.",
                           "E14, E25, E31"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    raw = open(a.plan).read()
    try:
        out = from_json(json.loads(raw))
        src = "json"
    except json.JSONDecodeError:
        out = from_text(raw)
        src = "text (fewer checks: no rendered values for module inputs, no exact actions)"
    out.sort(key=lambda x: x["level"] != BLOCK)
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"plan_risks ({src}): {sum(x['level'] == BLOCK for x in out)} BLOCK, "
              f"{sum(x['level'] == CHECK for x in out)} CHECK")
        for x in out:
            print(f"{x['level']} {x['rule']} {x['address']}\n  {x['message']}\n  (from {x['incident']})")
    return 2 if any(x["level"] == BLOCK for x in out) else 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
