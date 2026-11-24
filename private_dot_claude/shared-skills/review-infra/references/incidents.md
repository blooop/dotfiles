# Incidents behind the apply gate

Each rule in `scripts/infra_risks.py` (diff) and `scripts/plan_risks.py` (plan)
names one of these. Quote the API error text in the comment: the author can then
search it. "A" = the error shows only at apply, "R" = only at run time, "P" = the
plan shows it, but people did not see it.

## Apply-time API rejections (plan clean, apply fails or half-applies)

- **hns-versioning** — #205 → #211. A: `versioning` on a hierarchical-namespace
  bucket returns 400.
- **alert-on-new-log-metric** — #113, #928. A: an alert policy that reads a
  `google_logging_metric` created in the same apply gets 404, because the metric
  is not yet visible. On #928 this caused a partial apply, and 3 IAM members were
  destroyed and re-created. The fix is to land the metric in an earlier PR, or to
  add a `time_sleep`.
- **budget-iam-recipients** — #428 → #430. A: `disable_default_iam_recipients =
  true` returns 400 on a self-serve billing account.
- **serverless-neg-timeout** — #533 → #536. A: `timeout_sec` or
  `connection_draining_timeout_sec` on a backend service with a serverless NEG
  returns 400 "Timeout sec is not supported for a backend service with Serverless
  network endpoint groups". The default value 30 appeared on main without a
  failure, so the rule makes it a CHECK, not a BLOCK.
- **alert-rate-limit-metric** — #541 → #542, also #119 → #120. A:
  `notification_rate_limit` returns 400 "only log-based alert policies may
  specify a notification rate limit". #541 added it in the fix for a review
  comment.
- **cbd-fixed-name** — #615 → #624. A: the provider replaces
  `google_memorystore_instance` create-before-destroy. The same `instance_id`
  returns 409 "already exists", and the error stays until someone changes the id.
  The text plan hides an `instance_id` that does not change, so `plan_risks.py`
  makes a BLOCK when a CBD replace shows no changed identifier.
- **spot-mig-delete** — #644 → #648. A: a spot template with
  `instance_termination_action = DELETE` is created without an error, then the
  MIG update fails: "Spot virtual machines with termination action set to DELETE
  cannot be used with Managed Instance Groups". Its fix #649 then hit `already
  exists`, because the hashed template name did not include the changed field
  (**template-name-hash**).
- **alert-missing-data-zero-duration** — #733 → #735, #736. A:
  `evaluation_missing_data` on a condition with `duration = "0s"` returns 400.
  The first fix took out the wrong field. The second set the duration to 60s.
- **secret-without-version** — #783 + #822 → #859. A: Cloud Run will not create a
  worker pool or a revision that mounts a secret with no version.
- **alert-doc-length** — #975 → #999. A, silent: the documentation of a log-match
  policy has a 4000-character cap. Over the cap the API accepts the update and
  disables the policy, and the apply reports success. The alert was off for about
  4 h. A manual delete then blocked every apply for 50 min. The diff scan cannot
  render `${local.*}` built with `join`/`for`, so the plan reader measures the
  rendered text.
- **cloud-run-concurrency-cpu** — review-quality escapes. A: concurrency above 1
  with less than 1 vCPU returns 400.

## Silent no-op and perpetual diff

- **edit-under-ignore-changes** — #676 → #687, and also #428 and #541 (both
  edited startup scripts). P: an edit to an attribute that `ignore_changes` lists,
  or to a file that a module passes into one, ships nothing. The private-service
  module pins `metadata_startup_script`: a script edit needs `-replace` or
  `gcloud compute instances add-metadata`.
- **perpetual-diff** — #688 → #690. A, after apply: the API does not store
  `retry_count = 0`, so every plan proposes it again. The drift check was red for
  4 days.

## Destroy and replace

- **stateful-delete** — #429–#434 (LiveKit, 4 PRs in 2 h) → #435–#437. P, not
  read: URL map changes made the HTTPS proxies and the managed SSL cert be
  replaced. Every service behind the LB went down, and the cert was lost for about
  2 days.
- **known-to-unknown** — #629 + #630 → #632. P, in noise: each PR passed alone.
  The combined plan turned the webhook scaler's env map into an unknown value,
  which applies empty, so the 16 env vars that drive CI runner scaling would go.
  `infra/dev/plan_guard.py` guards function env only.
- **iam-recreate** — #928. A key change in `for_each` destroyed and re-created
  IAM members. The partial apply left the members out until the next apply.
- **rename-without-moved**, **for-each-keys**, **resource-removed** — classes
  that review caught: a new IP that a partner allowlist did not have, the only
  copy of a key, a removed resource that something still used.

## Run-time only (no plan shows it)

- **function-invoker** — #370 → #371. R: a redeploy of an Eventarc-triggered gen2
  function dropped the `run.invoker` binding that GCP made. Session registration
  failed 401 for 1.7 h.
- **oauth-scopes** — #866 → #904. R: a token scope that does not include
  `objects.patch` failed every "posted" mark with 403. The daily report re-posted
  7 days of data to Slack every morning. This came from the fix for a review
  comment.
- **out-of-band-deploy** — #443 (E9), #951 (E31). P: kinisi_ros deploys Cloud Run
  images and env. With no `ignore_changes`, the next apply rolls them back.
- #878 → #885: SkyPilot copied the API server's gcloud config to job VMs, and
  every ktrain launch failed for 2.5 days. Only a smoke launch after deploy
  catches this. Ask for one in the PR body.

## Process and gates

- **plan-failed** — #447 (E4): every PR plan was red for 11 days, and PRs merged
  anyway. No status check is required on `main`, and the admins can bypass the
  approval.
- **provider-change** — #460: a manual apply with google 7.29 against a lock at
  7.22 blocked every plan for a day. #466 → #467: a global `user_project_override`
  gave 403 on every GCS call.
- **manual-root** — only `infra/dev/**` and `infra/modules/**` apply after merge.
  `universe`, `cloud-bridge-dev` and `billing` are applied by hand.
- **image-build** — #580 → #584: a new base image filled the runner disk, and the
  build was broken 14 h. #501: the Thor bake was broken for 4 days. Test Runner
  Images is not a required check (#532).
- **workflow-lint**, **action-unpinned**, **script-injection**,
  **untrusted-trigger**, **swallowed-failure** — CI lints no workflow file.

## Back-test

`scripts/backtest.sh` (run it in a full clone, not a shallow one) checks every
cause above with a landed commit, plus a clean set. Result on 2026-11-24:

- Diff scan: 12 of 12 causes give a BLOCK (#119 included).
- Plan scan: 2 of 2 give a BLOCK (#615, #975).
- Clean control (40 random merged infra PRs that never needed a fix): 1 BLOCK,
  and it is #119, a real hit. About 1.5 CHECKs per PR, which the reviewer must
  resolve and does not post.
- E5 (the LiveKit cascade) is not in any single PR's plan: it came from 4 PRs
  applied together. Section 2e of the skill covers that case, not a script.

## Evidence

The studies behind this skill (2026-11-24) are in `evidence/`:
`review_quality.md` (445 review comments labelled, 44 escaped bugs),
`deploy_failures.md` (35 deployment errors, gates and gaps) and
`best_practices.md` (sources for the comment bar and the IaC checks).
