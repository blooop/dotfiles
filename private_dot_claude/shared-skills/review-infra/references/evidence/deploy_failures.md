# cloud_services deployment errors: what broke, what it cost, what would have caught it

Repo: kinisi-robotics/cloud_services. Data: 782 PRs (2025-11-20 to 2026-11-24), 234 issues,
the last 1000 workflow runs (2026-10-23 to 2026-11-24), failed-run logs in `data/logs/`,
and the local clone at `de9a0d1`. PR links: `https://github.com/kinisi-robotics/cloud_services/pull/N`.

Limits of the evidence:
- Run logs cover one month only. Older errors come from PR and issue text, which the
  fixer wrote. Durations before 2026-10-23 are merge-to-fix-merge times, not measured outages.
- Automatic apply started on 2026-11-11 ([#874](https://github.com/kinisi-robotics/cloud_services/pull/874)).
  Before that, people ran `apply.sh` (or plain `terraform apply`) by hand, so an apply
  failure before 11-11 shows only in the fix PR's text.

## 1. Deployment errors, one per row

Columns: id, date, cause PR, fix PR, symptom, fallout, time to fix, review on the cause PR
(R = other-person review, "-" = none) and whether a review flagged it, the check that would
have caught it, and whether `terraform plan` at PR time shows it (P = visible in plan,
A = apply-time only, R = runtime only, N = not Terraform).

| id | date | cause | fix | symptom | fallout | time to fix | review / flagged | check that catches it pre-merge | plan? |
|---|---|---|---|---|---|---|---|---|---|
| E1 | 2026-02-16 | #205 (import) | #211 issue / fix | apply 400: versioning not allowed on HNS bucket | apply blocked | days (unknown) | - / no | rule table: GCS HNS bucket ⇒ no `versioning`; or `terraform plan` + provider-docs lint | A |
| E2 | 2026-01-08 | #113 (probable) | #114 | alert policy on a log metric with no data failed to create | apply partial | ~same day | - / no | alert on a log metric created in the same apply ⇒ need MQL or `depends_on` + wait | A |
| E3 | 2026-03-26 | #370 | #371 (+ manual `gcloud add-iam-policy-binding`) | Cloud Function redeploy dropped the auto-made `run.invoker`; Eventarc delivery 401 | session registration down | ~1.7 h | - / no | every Eventarc/PubSub-triggered gen2 function must declare its invoker binding in TF | R |
| E4 | 2026-04-09..20 | budget added ~#417 | #447 | PR plan 403 on `google_billing_budget` refresh (CI SA lacks billing.viewer) | every PR's Terraform Plan red | ~11 days | - / no | plan the PR as the CI plan identity (it did, and failed: nobody acted) | P (plan fails) |
| E5 | 2026-04-10 | #429, #431, #433, #434 (LiveKit, 4 PRs in 2 h) | #435, #436, #437 | LiveKit URL-map/backend changes cascaded into HTTPS proxies + SSL cert replace; DNS pointed wrong; cert stuck FAILED_NOT_VISIBLE | all services behind the LBs down; universe.kinisi.com cert lost | outage same day; cert ~2 days | - / no | plan shows `-/+` or `-` on `google_compute_target_https_proxy`, `google_compute_managed_ssl_certificate`, `google_compute_global_forwarding_rule`; require `prevent_destroy` on them (added after) | P |
| E6 | 2026-04-10 | #428 | #430 | billing budget API rejects `disableDefaultIamRecipients` (400) | apply partial, budget missing | ~10 min | - / no | API rejects documented field on self-serve billing accounts | A |
| E7 | 2026-04-23 | local manual apply with google 7.29 | #460 | state written by newer provider than lock file (7.22) | every PR plan and every other engineer blocked | ~1 day | n/a (manual) | manual apply must use the repo lock file (`terraform init` without `-upgrade`); refuse when the lock file is dirty | N |
| E8 | 2026-04-24 | first fix attempt for #466 | #467 | global `user_project_override` ⇒ 403 on every GCS call | PR plan + apply blocked | <1 day | - / no | provider-level change: run the PR plan (it would have failed) | P |
| E9 | 2026-04-20 | kinisi_ros deploys Cloud Run images out of band | #443 | plan wanted to reset images to `:latest` | near miss: an apply rolls prod back | caught in plan | - / no | resources also deployed by another repo need `ignore_changes` on image | P |
| E10 | 2026-05-18 | 72c9612 (labels stripped) | #513 | reserved GPU runner silently lost its labels; stable promotion jobs stuck | kinisi_ros stable CI | days | - / no | label set on a runner pool must match the scaler's routing table (test) | R |
| E11 | 2026-05-18..22 | #501 (rotated `cache_images`) | #530, #531 | Thor `build-*` image bake broken ~4 days; 3 PRs merged over red | runner image bake broken | ~4 days | - / no | make Test Runner Images a required check on packer paths (open issue #532) | N |
| E12 | 2026-05-22 | #533 | #536 | apply 400: `timeout_sec` not supported on serverless-NEG backend service | apply partial (LB step) | ~1 h | - / no | rule: serverless NEG backend ⇒ no `timeout_sec` / `connection_draining_timeout_sec` | A |
| E13 | 2026-05-28 | #541 | #542 | apply 400: `notification_rate_limit` only on log-based alerts | apply partial (1 of 15 missing) | 14 min | R (4 reviews, 5 threads) / no | rule: `notification_rate_limit` only with `condition_matched_log` | A |
| E14 | 2026-07-08 | live out-of-band memory bump | #582 | 4Gi set by hand; next apply would revert to 2Gi | near miss: OOMs return | caught by author | n/a | detect: drift check + "live change ⇒ PR within a day" rule | P (drift) |
| E15 | 2026-07-08 | #580 | #584 (revert) | converter image rebased on 25-30 GB dev image; build: no space left on device | LeRobot converter image build broken | ~14 h | R (31 reviews, 15 threads) / no | image size / runner disk budget check on Dockerfile base change; build the image on the PR | N |
| E16 | 2026-07-15 | unpinned lerobot drifted | #599 | conversions broken after a rebuild | dataset conversion broken | ~1 day | - / no | pin deps in image; rebuild on PR | N |
| E17 | 2026-07-28 | #615 | #624 | apply 409: Valkey replace is create-before-destroy with a fixed `instance_id` | apply blocked for everything queued behind it | ~3 h | - / no | rule: replace of a resource with a fixed name/id + provider CBD ⇒ fails; check plan JSON `actions: [create, delete]` with unchanged name | P (replace visible, failure A) |
| E18 | 2026-07-29 | #629 + #630 (each green) | #632 + `plan_guard.py` | combined plan would wipe all 16 webhook-scaler env vars | near miss: all CI runner scaling stops | caught before apply | - / no | `plan_guard.py` on the plan of main-after-merge (now in apply.sh) | P (hidden in noise) |
| E19 | 2026-08-03 | #644 | #648, #649 | apply: spot `termination_action=DELETE` rejected on MIG; fix then hit `already exists` (hashed template name ignored the derived field) | apply partial, 3 apply cycles | ~2 h | - / no | rule: MIG-managed spot ⇒ STOP; template name hash must cover every field | A |
| E20 | 2026-08-12 | #676 | #687 | startup-script edit under `ignore_changes` ⇒ apply reports no change; probe shipped by hand | silent no-op deploy | 1 day | - / no | flag any edit to an attribute listed in that resource's `ignore_changes` | P (absence of change) |
| E21 | 2026-08-13 | #688 | #690 | `retry_config { retry_count = 0 }` read back as absent ⇒ perpetual diff | drift check red 4 days, alert fatigue | 4 days | - / no | post-apply re-plan must be empty | A (post-apply) |
| E22 | 2026-09-07 | #733 (field added during self-review) | #735, #736 | apply 400: `evaluation_missing_data` invalid on that condition | apply blocked | ~25 min, wrong fix, corrected 1.5 h | - / no | rule table for alert condition fields; plan cannot see it | A |
| E23 | 2026-09-16 | earlier lifecycle rule on source buckets | #770 | age-30 delete hits the live function source zip | latent: redeploy/rollback impossible | caught | - / no | lifecycle Delete on a bucket that holds content-hash objects referenced by state | P |
| E24 | 2026-10-06..26 | runner bump PR not merged | #835 | runner 2.337.0 behind 2.338 for 16-19 days; Bump Actions Runner red 4 days | risk: GitHub refuses old runners ⇒ all self-hosted CI | 20 days | n/a | the bump workflow did catch it; needs an owner | N |
| E25 | 2026-10-28..11-10 | merged-not-applied: #850, #866, #878 era PRs; subnet flow logs set by hand | #874 (auto apply) | nightly drift red 4 of 5 nights | main ≠ live; next apply ships several PRs at once | until 11-11 | mixed | auto-apply after merge (done) | P |
| E26 | 2026-10-29 | #783 + #822 | #859 | apply: Cloud Run refuses a worker pool whose secret volume names a secret with no version | apply partial | ~30 min | R (14 + 10 reviews) / no | rule: a secret mounted by a pool/service must have a version before create | A |
| E27 | 2026-11-09 | #878 | #885 (+ kinisi_ros#15465) | SkyPilot copied API server gcloud config to job VMs; `.boto` path missing | every ktrain launch failed | ~2.5 days | - / no | none in plan; needs a launch smoke test after deploy | R |
| E28 | 2026-11-11..14 | manual IAM grants made over months | access-audit PRs #892-#942 | Access Audit: 47 grants, 1 key, 4 DB logins not in code | drift of IAM (security) | down to 5 in 3 days | n/a | the audit (new) found it | N |
| E29 | 2026-11-12 | #891 | #911 | new "terraform-admin outside CI" alert fired on CI's own apply | false page | same day | - / no | test log filters against a recorded CI apply's audit log | R |
| E30 | 2026-11-13 | #938 | #942 | access audit crashed on first `google_cloud_run_v2_worker_pool_iam_member` | audit blind 1 night | ~4 h | - / no | the audit's own test against the PR's plan JSON | N |
| E31 | 2026-11-14 | out-of-band env `MIGRATE_ON_START` on consumer pool | issue #951 (closed next night) | drift on worker pool env | drift | 1 day | n/a | deploy-by-other-repo fields need `ignore_changes` or must live in TF | P (drift) |
| E32 | 2026-11-17 | #928 | none (re-run 1.5 h later) | apply 404: alert policy names a log metric created in the same apply | apply partial; 3 IAM members destroyed and recreated | ~1.5 h | R (JSmithRobotics, blocking review) / no | rule: new `google_logging_metric` + alert on it in one apply ⇒ `depends_on` + wait, or split PRs | A |
| E33 | 2026-11-18 | #975 (stack #964-#976) | #999 | alert documentation 5,743 chars > 4,000 cap; API accepted the update but left the policy disabled; manual delete then create failed 400 | renewer-errors alert silent ~4 h; every apply blocked ~50 min | ~4 h | R (mfinean approved) / no | rule: log-match alert documentation ≤ 4000 chars (now a test); post-apply `gcloud alpha monitoring policies list --filter='validity:*'` | A (silent) |
| E34 | 2026-10-27..11-20 | none (infra) | none | Rebuild Runner Images: x64-sim `Timeout waiting for SSH` (packer default 5 min) 4 of 70 nights | nightly bake skipped | open | n/a | set `ssh_timeout`; not a review item | N |
| E35 | 2026-11-03 | unknown | none | Cleanup Stale Packer: `compute.disks.delete` denied on one disk | one disk left | open | n/a | — | N |

Not counted as errors: Terraform Apply "cancelled" runs (14). Each was a queued run
superseded by a newer merge, or a pending approval that nobody gave (two waited about
4 h on 2026-11-13). Build LeRobot "cancelled" runs were superseded. 2026-11-10 LeRobot
failure was a transient WIF token error. #1019 was reverted by #1027 before any apply.
#933 is a catch: the PR plan as `terraform-plan@` showed the missing permission before merge.

## 2. Error classes, ranked by frequency × severity

Severity scale: 4 = prod service down or data/security loss, 3 = apply blocked for all or
partial apply, 2 = CI broken for consumers, 1 = noise.

1. **Apply-time API rejection (plan clean, apply fails).** E1, E2, E6, E12, E13, E17, E19,
   E22, E26, E32, E33. 11 events, severity 3 (E33: 4, an alert silently disabled). Score ≈ 35.
   All **A**: invisible in `terraform plan`, `validate`, `tflint`, `tfsec`. The review must
   carry a rule table of known GCP API constraints, and must flag resource types and fields
   new to the repo as "first use: apply risk".
2. **Destroy/replace cascades and env wipes.** E5, E17 (replace part), E18, E32 (IAM
   recreate), plus #981's announced cache wipe. 4 events, severity 4. Score ≈ 16.
   Visible in the plan, but buried. The review must list every `delete`, `-/+` and
   create-before-destroy action from the plan JSON, and every known-after-apply value that
   feeds a map.
3. **Out-of-band live change vs Terraform (drift both ways).** E7, E9, E14, E20, E25, E28,
   E31, E33 (manual delete). 8 events, severity 2-3. Score ≈ 20. Partly visible (the PR
   plan shows a change the PR did not make). The review must compare the plan with the
   diff: a planned change on a resource the PR does not touch is drift, not the PR.
4. **Runtime-only behaviour breaks from config.** E3, E10, E27, E29, E16. 5 events,
   severity 3-4 (E27: 2.5 days of failed training launches). Score ≈ 17. Not visible in a
   plan. Needs a post-apply smoke check, or a review question "what calls this, and as whom?".
5. **CI plan identity / provider / lock breakage.** E4, E7, E8 (+ #82, #933 caught).
   4 events, severity 2 (all PRs blocked, prod fine). Score ≈ 8. Visible: the PR plan fails.
   The gap was that a red plan did not block merge.
6. **Image and bake builds.** E11, E15, E16, E24, E34. 5 events, severity 2. Score ≈ 10.
   Not Terraform. Gate: the image build/test must run on the PR and be required.
7. **Detector noise (perpetual diff, audit crash).** E21, E30, #214, issues #84, #96, #134,
   #346, #484. Severity 1, but it trains people to ignore the drift check.

Apply-time-only (the skill must treat these specially, since no plan shows them):
E1, E2, E6, E12, E13, E17 (failure part), E19, E22, E26, E32, E33, E21 (post-apply), plus
runtime-only E3, E10, E27, E29.

Review data: of 702 merged PRs, 84 had a review from someone other than the author.
Since 2026-10-24, 126 of 162 merged PRs had no approval. Of the 33 errors above, 6 cause
PRs had another person's review (E13, E15, E26, E32, E33, partly E27's stack). No review
comment on any of them flagged the error that happened. Reviewers read code and intent;
none checked API limits, apply ordering or the plan's destroy list.

## 3. Current gates

- `pr-validation.yml` (on PRs to main touching `infra/**`, `tests/**`, `access/**`,
  `pr-validation.yml`, `.pre-commit-config.yaml`, `.tflint.hcl`):
  - pre-commit: `terraform_fmt`, `terraform_validate`, `terraform_tflint`, a module
    `terraform test`, `tfsec`, yaml/merge/key checks.
  - pytest on `tests/` and the webhook scaler (static tests of HCL text, e.g.
    `test_no_log_match_alert_carries_the_steps` after E33).
  - `terraform plan` for infra/dev as `terraform-plan@` (read-only), on the PR merge ref,
    `-lock=false`. Also plans universe bootstrap, cloud-bridge-dev, billing
    (`-refresh=false`) and validates universe platform.
  - The plan text is posted as one PR comment per root. Plan failure fails the job.
  - `plan_guard.py` fails a plan that drops keys from a Cloud Function env map.
- Merge: ruleset on main needs 1 approval and code-owner review, but the admins team has
  bypass. No required status checks: a red or cancelled PR Validation does not block merge
  (#841 merged red; #967 and #975 merged with a cancelled run).
- Deploy: `terraform-apply.yaml` (since 11-11) on push to main for `infra/dev/**` and
  `infra/modules/**`. The plan job runs `apply.sh -plan-only` (plan, plan_guard, hash) on
  main's head; the apply job waits for approval in the `infra-dev` environment (mfinean,
  blooop, eaa3; self-review allowed), re-plans as `terraform-admin@`, and applies only if
  the hash matches. The plan is in the run summary.
- Detectors after the fact: nightly drift (dev and billing only, opens an issue), nightly
  access audit, Artifact Registry retention guard, GCS lifecycle guard, Bump Actions Runner.

## 4. Gaps, mapped to the errors

1. No apply-time knowledge anywhere before apply (class 1). Nothing checks GCP API
   constraints, first use of a resource type or field, same-apply create-then-reference
   ordering, or CBD with fixed names.
2. The plan is posted raw. Nobody is shown the destroy/replace list, the "changes on
   resources the PR does not touch" list, or the known-after-apply values feeding maps.
   PR authors sometimes write "What the plan must show" (#999); nothing checks it.
3. A red plan does not block merge (no required checks) and the admins bypass review.
4. The PR plan goes stale. Stacked PRs (#964-#976) merge at once; the combined plan is
   first seen at apply time. apply.sh's plan_guard covers only env-map wipes.
5. The apply approver is often the author, and approves a plan text with the same blind
   spots as the PR plan.
6. Roots other than infra/dev (universe bootstrap/platform, cloud-bridge-dev, billing) are
   applied by hand. Only dev and billing are drift-checked. Manual applies can use another
   provider version (E7).
7. Workflow files other than `pr-validation.yml` do not trigger PR Validation; there is no
   `actionlint`. Packer changes run Test Runner Images, which is not required (issue #532).
8. No post-apply check: no empty re-plan (E21), no alert-policy `validity` check (E33), no
   smoke test of the changed service (E3, E27).
9. Attributes under `ignore_changes` can be edited with no effect (E20); no check flags it.

## 5. What the review skill must do (derived)

- From the plan JSON: list deletes, replaces (and CBD vs DBC), IAM member recreates,
  changes to resources outside the diff, and unknown values flowing into maps.
- From the diff: flag first-use resource types/fields; apply a rule table of known API
  constraints (the A rows above are the seed list); flag log metric + alert in one PR;
  flag fixed names on replaced resources; flag edits under `ignore_changes`; flag
  resources that other repos deploy (images, env) without `ignore_changes`.
- Ask, for runtime-only risk: who calls this resource, as which identity, and what proves
  it works after apply. Demand a post-apply check line in the PR body.
- Treat a red, cancelled or stale plan as a block, and re-plan stacked PRs together.
