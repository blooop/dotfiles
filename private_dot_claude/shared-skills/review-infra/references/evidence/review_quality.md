# cloud_services review quality (782 PRs, Nov 2025 – Nov 2026)

Method: 445 non-author, non-CI-bot comments (282 inline, 120 review bodies, 43 top-level) read and labelled by hand from 260-char excerpts, with full text read for a/b/c/g candidates. Labels: `work/labels.txt`; items: `work/items.json`; thread responses: `work/resp.json`. Escapes: fix/revert PRs that name an earlier merged PR (136 candidate pairs, triaged by hand to 44). The local clone is shallow (from 2026-09-30), so diffs before PR ~#784 come from PR data only.

Caveat: mfinean's comments (and many author replies) carry the structure of an AI review skill (severity markers, "Blocking", file:line citations). Treat "mfinean" as largely "AI-assisted review".

## 1. Comment classification
### Comments per category

| cat | meaning | n |
|---|---|---|
| a | real defect | 58 |
| b | deploy/ops risk | 71 |
| c | security | 26 |
| d | design/maintainability | 76 |
| e | nit/style/wording | 28 |
| f | question | 6 |
| g | wrong | 1 |
| h | summary/ack/housekeeping (not a finding) | 179 |

Findings (all but h): 266. High-value (a+b+c): 155 = 58% of findings. With d: 87%.

### Per reviewer

| reviewer | a | b | c | d | e | f | g | h | findings | hit rate a+b+c |
|---|---|---|---|---|---|---|---|---|---|---|
| mfinean | 29 | 51 | 20 | 55 | 26 | 2 | 1 | 113 | 184 | 54% |
| eaa3 | 16 | 10 | 3 | 10 | 0 | 1 | 0 | 18 | 40 | 72% |
| caleb-kinisi | 3 | 1 | 0 | 3 | 0 | 3 | 0 | 14 | 10 | 40% |
| JSmithRobotics | 1 | 6 | 1 | 4 | 0 | 0 | 0 | 8 | 12 | 66% |
| blooop | 2 | 0 | 2 | 1 | 1 | 0 | 0 | 9 | 6 | 66% |
| copilot-pull-request-reviewer | 3 | 1 | 0 | 1 | 0 | 0 | 0 | 3 | 5 | 80% |
| dennisushi | 0 | 1 | 0 | 2 | 1 | 0 | 0 | 4 | 4 | 25% |
| Jack-Tattershall | 3 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | 4 | 100% |
| miccol | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | - |
| SilverArachnid | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | - |
| brennand | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | - |
| janjachnik | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 100% |
| snknitheesh | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | - |


Only 1 comment is clearly wrong (g): #697, mfinean claimed a fresh-base bake drops the DDS sysctl drop-in from sim images; the author showed the sim platforms never use it. Two more partial errors were self-corrected by the reviewer: #606 (retracted "just use a mounted disk") and #960 ("the consumer's alert already has that step, so it had no gap"). Copilot's #704 claim that the AR repo lacks a writer is probably wrong (runners hold project-wide `repoAdmin`, see #1041), unanswered.

## 2. Responses
### Responses to inline threads (root by a non-author)

| response | all | a | b | c | d | e |
|---|---|---|---|---|---|---|
| fixed | 147 | 31 | 43 | 18 | 43 | 11 |
| fixed(reviewer-pushed/confirmed) | 28 | 8 | 4 | 2 | 5 | 9 |
| unresolved | 27 | 10 | 4 | 1 | 10 | 1 |
| replied | 25 | 2 | 8 | 2 | 7 | 5 |
| pushback | 6 | 2 | 2 | 0 | 2 | 0 |
| resolved-silent | 4 | 0 | 3 | 0 | 1 | 0 |
| unresolved-outdated | 2 | 1 | 0 | 0 | 1 | 0 |


Reading of the "replied"/"pushback" threads: most "replied" are fixes in other words ("Dropped in 19c3332", "Gone with the same change"). Fixed differently (with good reason): #611 (guard widened to `IN ('converting','error')`), #628 (soft-degrade probe instead of hard guard), #628 (CACHEBUST keyed on run id), #737 (degrade not fail-fast), #829 (dropped the robot-CA grant). Pushback with reason: #541 (`:latest` kept, manual deploys), #548 (DRY refactor deferred), #627, #697 (DDS – reviewer wrong). Pushback without reason: none found. Unresolved high-value: 10 (a) + 4 (b) + 1 (c), mostly on closed/superseded PRs (#704 copilot threads, #705, #737, #1038).

### Responses that introduced a new bug (verified from commit timeline + fix PR body)

- [#866](https://github.com/kinisi-robotics/cloud_services/pull/866) — mfinean: "if the dated object is written and the Slack post then fails, the next run ... never posts it". Response commit `8fff723` "a day written but not posted to Slack is posted again next run" added a `posted:false` object + metadata **objects.patch** mark. `objects.patch` rejects a `devstorage.read_write` token → every mark 403, run 500, last 7 days re-posted to Slack every morning from 8 Nov. Fixed by [#904](https://github.com/kinisi-robotics/cloud_services/pull/904). Class: fix uses an API call whose OAuth scope/permission differs from the calls already exercised.
- [#541](https://github.com/kinisi-robotics/cloud_services/pull/541) — mfinean: "No alert on the collector going down". Response `80ffe083` added a metric-based alert with `notification_rate_limit` (only legal on log-based alerts) → `terraform apply` failed, hotfix [#542](https://github.com/kinisi-robotics/cloud_services/pull/542). The log-based container-failure alert added in the same commit never fired (wrong filter fields, no Ops Agent, then no `logging.logWriter`): [#594](https://github.com/kinisi-robotics/cloud_services/pull/594), [#617](https://github.com/kinisi-robotics/cloud_services/pull/617). Class: new monitoring resources added in a review response, never applied/validated before merge.

No other response commit was traced to a later fix. Two response-adjacent risks seen but not proven: #580's reviewer asked for build-time DINOv2 pre-cache (`HF_HOME`) on an image that then overflowed the runner disk (#584), but the disk overflow came from the dev-image base present before review.

## 3. Bugs that escaped review
### Base rates

Merged PRs: 702. Merged with any non-author review or finding: 86 (12%). Unreviewed merged: 616.

Escaped-bug origin PRs: 42; of these reviewed: 5 ([507, 541, 580, 866, 956]); unreviewed: 37.
Escape rate: reviewed 5/86 = 5.8%; unreviewed 37/616 = 6.0%.


Review did not reduce the escape rate measurably (5.8% vs 6.0%), but n=5 for reviewed escapes, and reviewed PRs are the big risky ones. 37 of 42 escape origins had **no review at all** (mostly caleb-kinisi Jan–May and mfinean Jul–Nov self-merges). Every escape, fix PR → origin:

- [#205](https://github.com/kinisi-robotics/cloud_services/pull/205) → fixed by [#212](https://github.com/kinisi-robotics/cloud_services/pull/212): HNS bucket imported with versioning block; apply 400. Review: none.
- [#277](https://github.com/kinisi-robotics/cloud_services/pull/277) → fixed by [#303](https://github.com/kinisi-robotics/cloud_services/pull/303): GPU MIG->standalone migration caused wait-for-job alert flood. Review: none.
- [#335](https://github.com/kinisi-robotics/cloud_services/pull/335) → fixed by [#341](https://github.com/kinisi-robotics/cloud_services/pull/341): max_instances 1->4 broke session affinity (robot/browser split); live drift. Review: none.
- [#350](https://github.com/kinisi-robotics/cloud_services/pull/350) → fixed by [#354](https://github.com/kinisi-robotics/cloud_services/pull/354): module destroy left stale SA name literals in AR IAM bindings. Review: none.
- [#370](https://github.com/kinisi-robotics/cloud_services/pull/370) → fixed by [#371](https://github.com/kinisi-robotics/cloud_services/pull/371): Cloud Function redeploy lost run.invoker binding. Review: none.
- [#417](https://github.com/kinisi-robotics/cloud_services/pull/417) → fixed by [#425](https://github.com/kinisi-robotics/cloud_services/pull/425): billing budget: emails admins, unscoped filter (whole billing account), Slack broken. Review: none.
- [#425](https://github.com/kinisi-robotics/cloud_services/pull/425) → fixed by [#428](https://github.com/kinisi-robotics/cloud_services/pull/428): incomplete fix of #417 (Slack pipeline still broken). Review: none.
- [#439](https://github.com/kinisi-robotics/cloud_services/pull/439) → fixed by [#441](https://github.com/kinisi-robotics/cloud_services/pull/441): IAM fix incomplete: gcsfuse mount not writable by container uid 1000. Review: none.
- [#450](https://github.com/kinisi-robotics/cloud_services/pull/450) → fixed by [#456](https://github.com/kinisi-robotics/cloud_services/pull/456): runner VM lacks cloud-platform scope; IAM right but VM scope missing. Review: none.
- [#463](https://github.com/kinisi-robotics/cloud_services/pull/463) → fixed by [#465](https://github.com/kinisi-robotics/cloud_services/pull/465): apt lock workaround wrong; compute lib too old for proto field. Review: none.
- [#478](https://github.com/kinisi-robotics/cloud_services/pull/478) → fixed by [#479](https://github.com/kinisi-robotics/cloud_services/pull/479): concurrency>1 needs >=1 vCPU; terraform apply failed. Review: none.
- [#488](https://github.com/kinisi-robotics/cloud_services/pull/488) → fixed by [#492](https://github.com/kinisi-robotics/cloud_services/pull/492): latency alert P50/2s REDUCE_MAX picks 500 series: false pages. Review: none.
- [#492](https://github.com/kinisi-robotics/cloud_services/pull/492) → fixed by [#504](https://github.com/kinisi-robotics/cloud_services/pull/504): alert tune kept wrong percentile/threshold. Review: none.
- [#504](https://github.com/kinisi-robotics/cloud_services/pull/504) → fixed by [#518](https://github.com/kinisi-robotics/cloud_services/pull/518): alert metric structurally wrong for streaming RPCs; disabled. Review: none.
- [#507](https://github.com/kinisi-robotics/cloud_services/pull/507) → fixed by [#515](https://github.com/kinisi-robotics/cloud_services/pull/515): startup script used abandon-instances believing it preserves MIG target_size; warm spare never recreated (+ plan drift). Review: reviewed (copilot overview, caleb) — missed: copilot summarised the abandon-instances path as a feature.
- [#501](https://github.com/kinisi-robotics/cloud_services/pull/501) → fixed by [#530](https://github.com/kinisi-robotics/cloud_services/pull/530): cache_images swap broke Thor pre-pull; disk overflow + dpkg cascade. Review: none.
- [#537](https://github.com/kinisi-robotics/cloud_services/pull/537) → fixed by [#538](https://github.com/kinisi-robotics/cloud_services/pull/538): InstancesClient.list(filter=) kwarg invalid; silent reconcile failure. Review: none.
- [#541](https://github.com/kinisi-robotics/cloud_services/pull/541) → fixed by [#542](https://github.com/kinisi-robotics/cloud_services/pull/542): notification_rate_limit invalid on metric-based alert; apply failed. Review: reviewed (mfinean) — response-induced (see §2).
- [#541](https://github.com/kinisi-robotics/cloud_services/pull/541) → fixed by [#594](https://github.com/kinisi-robotics/cloud_services/pull/594): crash-collector log alerts never fired (filter fields wrong, no Ops Agent). Review: reviewed (mfinean) — response-induced (see §2).
- [#594](https://github.com/kinisi-robotics/cloud_services/pull/594) → fixed by [#617](https://github.com/kinisi-robotics/cloud_services/pull/617): Ops Agent log forwarding needs logging.logWriter; alerts still dead. Review: none.
- [#615](https://github.com/kinisi-robotics/cloud_services/pull/615) → fixed by [#624](https://github.com/kinisi-robotics/cloud_services/pull/624): Valkey replacement reused instance id; apply 409 already exists. Review: none.
- [#629](https://github.com/kinisi-robotics/cloud_services/pull/629) → fixed by [#632](https://github.com/kinisi-robotics/cloud_services/pull/632): PR-time plan guard checked stale state; merged green and left main unsafe. Review: none.
- [#644](https://github.com/kinisi-robotics/cloud_services/pull/644) → fixed by [#647](https://github.com/kinisi-robotics/cloud_services/pull/647): preemption rescue used rerun-failed-jobs (reruns whole workflow). Review: none.
- [#644](https://github.com/kinisi-robotics/cloud_services/pull/644) → fixed by [#648](https://github.com/kinisi-robotics/cloud_services/pull/648): spot MIG: GCE refuses instance_termination_action=DELETE; apply failed. Review: none.
- [#648](https://github.com/kinisi-robotics/cloud_services/pull/648) → fixed by [#649](https://github.com/kinisi-robotics/cloud_services/pull/649): create_before_destroy + unchanged name: already exists; partial apply. Review: none.
- [#691](https://github.com/kinisi-robotics/cloud_services/pull/691) → fixed by [#692](https://github.com/kinisi-robotics/cloud_services/pull/692): removed transcode job URI variable that was still needed. Review: none.
- [#709](https://github.com/kinisi-robotics/cloud_services/pull/709) → fixed by [#711](https://github.com/kinisi-robotics/cloud_services/pull/711): first apply pointed at bootstrap image tag that does not exist. Review: none.
- [#727](https://github.com/kinisi-robotics/cloud_services/pull/727) → fixed by [#730](https://github.com/kinisi-robotics/cloud_services/pull/730): Cloud SQL Insights attribution by client address wrong. Review: none.
- [#733](https://github.com/kinisi-robotics/cloud_services/pull/733) → fixed by [#735](https://github.com/kinisi-robotics/cloud_services/pull/735): alert policy evaluation_missing_data rejected; apply failed. Review: none.
- [#735](https://github.com/kinisi-robotics/cloud_services/pull/735) → fixed by [#736](https://github.com/kinisi-robotics/cloud_services/pull/736): fix-forward removed missing-data policy with wrong reasoning. Review: none.
- [#740](https://github.com/kinisi-robotics/cloud_services/pull/740) → fixed by [#741](https://github.com/kinisi-robotics/cloud_services/pull/741): runbook names wrong metric (request_concurrencies). Review: none.
- [#602](https://github.com/kinisi-robotics/cloud_services/pull/602) → fixed by [#742](https://github.com/kinisi-robotics/cloud_services/pull/742): docs still tell operators to set deleted iap_external_users. Review: none.
- [#755](https://github.com/kinisi-robotics/cloud_services/pull/755) → fixed by [#757](https://github.com/kinisi-robotics/cloud_services/pull/757): module lacks required_version; TFLint red on main. Review: none.
- [#802](https://github.com/kinisi-robotics/cloud_services/pull/802) → fixed by [#815](https://github.com/kinisi-robotics/cloud_services/pull/815): reconciler fix incomplete for 16gb-4vcpu label pools. Review: none.
- [#160](https://github.com/kinisi-robotics/cloud_services/pull/160) → fixed by [#825](https://github.com/kinisi-robotics/cloud_services/pull/825): job errors moved to log lines not counted by error metric. Review: none.
- [#878](https://github.com/kinisi-robotics/cloud_services/pull/878) → fixed by [#885](https://github.com/kinisi-robotics/cloud_services/pull/885): skypilot .boto names key path absent on job VMs; every launch failed. Review: none.
- [#866](https://github.com/kinisi-robotics/cloud_services/pull/866) → fixed by [#904](https://github.com/kinisi-robotics/cloud_services/pull/904): daily cost report 'posted' mark never succeeds (objects.patch scope); repost every morning. Review: reviewed (mfinean) — response-induced (see §2).
- [#912](https://github.com/kinisi-robotics/cloud_services/pull/912) → fixed by [#921](https://github.com/kinisi-robotics/cloud_services/pull/921): merged without its last commit. Review: none.
- [#944](https://github.com/kinisi-robotics/cloud_services/pull/944) → fixed by [#948](https://github.com/kinisi-robotics/cloud_services/pull/948): removed controller SA key still held by running jobs. Review: none.
- [#956](https://github.com/kinisi-robotics/cloud_services/pull/956) → fixed by [#958](https://github.com/kinisi-robotics/cloud_services/pull/958): cert provisioning: revoke-before-commit, two defects (merged without review). Review: no review before merge (bypass); mfinean found both defects after merge.
- [#580](https://github.com/kinisi-robotics/cloud_services/pull/580) → fixed by [#584](https://github.com/kinisi-robotics/cloud_services/pull/584): keypoint annotation made converter image build fail; reverted. Review: reviewed by 6 people, 16 reviews — missed: no comment on image size vs runner disk.
- [#162](https://github.com/kinisi-robotics/cloud_services/pull/162) → fixed by [#163](https://github.com/kinisi-robotics/cloud_services/pull/163): cert renewal RPC lacked Private CA IAM for cloud-bridge SA. Review: none.
- [#670](https://github.com/kinisi-robotics/cloud_services/pull/670) → fixed by [#672](https://github.com/kinisi-robotics/cloud_services/pull/672): test fixture used a non-existent real-looking email. Review: none.
- [#85](https://github.com/kinisi-robotics/cloud_services/pull/85) → fixed by [#87](https://github.com/kinisi-robotics/cloud_services/pull/87): content-hash fix left detect_md5hash cosmetic drift. Review: none.

## 4. Defect classes

### Caught by good comments (concrete)
- Terraform identity churn: map/for_each key rename destroys+recreates an IAM binding or a secret holding the only copy of a key (#853, #822); resource replace gives a new static IP that is on a partner allowlist (#783); disk shrink forces data-disk replacement — hash the disk id into the VM trigger (#981).
- `force_destroy = true` / soft delete 0 on a bucket that holds non-regenerable state (#822); unconditional bucket lifecycle `age` rule silently deletes a report (#627); versioning without noncurrent-version rule defeats purge (#826).
- New service account missing from the bucket/AR writer map → 403 on first run or pool that self-deletes at boot (#698, #701, #991, #697).
- Apply ordering: `depends_on` removed drops a transitive wait on a secret's creation (#790); a root that reads another root's new output fails to plan until that root applies (#960, #1012); cross-repo merge order (3 repos) not stated (#697, #628, #580).
- `ignore_changes` on image means a later `image_tag` never applies; gcloud label changes on the template get undone by the next apply (#870, #928, #964, #966).
- Monitoring that cannot fire or fires forever: `condition_absent` per-revision series fires on every redeploy (#772); filter names one of two services (#774); heartbeat logged even while the job is not provisioned (#928); alert only fires while the service is healthy (#822).
- Over-broad trust: WIF `principalSet` on `attribute.repository` admits every branch/tag (#876); GitHub environment that does not exist yet = no protection rules (#977); shared vault secret also decrypts another repo's fleet vault (#977); one SA for dev+live pools gives dev deployers live DB password (#928); PR CI can write a shared cache (#884); unauthenticated reads to all ZeroTier members (#884); `run.admin` on `pr-*` prefix broader than LB routing (#1036).
- Narrowing that does not narrow: removing a bucket binding while project `roles/viewer` still grants read (#853); a grant that is a no-op under existing project-level `storage.admin` (#622).
- Pickle RCE: user-influenced URI reaching `torch.load(weights_only=False)` in a credential-holding job (#580, #704).
- Job state machine: early `sys.exit` / validation outside `try` leaves a DB row `converting` forever (#580, #775); late SIGTERM clobbers terminal state (#611); failed mint deletes revoked cert rows and drops them from the CRL (#941).
- Shell/workflow: `$?` after `if !` is always 0 (#507); `GITHUB_SHA` on `repository_dispatch` is the default-branch sha, so a cachebust never busts (#628); `--build-arg` documented but not passed by CI (#580); unvalidated dispatch input interpolated into a provisioner shell loop (#697).
- Runtime-config semantics: `fps` honoured only on first call of a streaming API (#775); `round(rate)` → 0 → ZeroDivisionError (#737); LIKE `_` wildcard in bound pattern (#705); pg8000.dbapi never raises `IntegrityError` (#941).
- Tests that cannot fail: tautology tests, regexes that pin spelling, tests that never run the new branch (#775, #853, #898, #977, #1041).

### Escaped (no comment saw them)
- Provider/API rejects a valid-looking field at apply, not plan: `versioning` on HNS bucket (#205), `notification_rate_limit` on metric alerts (#541), `evaluation_missing_data` (#733), `instance_termination_action=DELETE` on MIG spot (#644), concurrency>1 needs ≥1 vCPU (#478), Valkey/instance id reuse with `create_before_destroy` (#615, #648), bootstrap image tag that does not exist at first apply (#709). → Skill rule: for every new resource attribute, check the provider/API constraint; plan green ≠ apply green.
- OAuth scope vs IAM: VM `scopes` missing `cloud-platform` (#450); `objects.patch` needs full_control scope (#866).
- IAM completeness after redeploy/rename: run.invoker lost on Cloud Function redeploy (#370); SA name literals left after module destroy (#350); Private CA access for renewal (#162); Ops Agent needs `logging.logWriter` (#594); gcsfuse uid mismatch after IAM fix (#439).
- gcloud/API semantics: `abandon-instances` does not preserve MIG target size (#507); `InstancesClient.list(filter=)` silently wrong (#537); `rerun-failed-jobs` reruns the whole run (#644).
- Alert design: P50/P95 + REDUCE_MAX over streaming RPCs pages forever (#488, #492, #504); per-log-match alert on every disconnect (#544); log alert filter fields that match nothing (#541); wrong metric name in runbook (#740); budget filter scoped to the whole billing account and emailing admins (#417).
- Capacity/disk: image rebase onto a 25–30 GB dev image overflows the CI runner (#580); cache_images change overflows Thor bake disk (#501).
- Scaling changes that break affinity (#335 max_instances 4), removed resources still in use (#944 controller key, #691 job URI), stale docs/tests after deletes (#602, #755).
- Process: merged without last commit (#912); merged via bypass without review (#956); PR-time plan computed on stale state (#629/#630).

## 5. Approvals
### Approvals

| approver | approvals | silent (no body, no finding) | approved PR later needed a fix |
|---|---|---|---|
| mfinean | 41 | 14 | 1 |
| blooop | 9 | 7 | 0 |
| eaa3 | 9 | 3 | 1 |
| caleb-kinisi | 5 | 0 | 1 |
| miccol | 4 | 1 | 0 |
| snknitheesh | 3 | 3 | 0 |
| SilverArachnid | 2 | 0 | 0 |
| lewisspencer | 1 | 1 | 0 |
| dennisushi | 1 | 0 | 0 |
| Jack-Tattershall | 1 | 0 | 0 |
| JSmithRobotics | 1 | 0 | 0 |

Approved merged PRs: 68; later needed a fix: 3. Merged without approval: 634.

The approved PRs that later needed a fix: #507 (caleb-kinisi), #541 (mfinean), #580 (eaa3). 634 of 702 merged PRs (90%) merged with no approval at all; the ruleset requiring one approval came late (#956 notes the bypass).

## 6. Quoted examples
### Top 10 best

- [#627](https://github.com/kinisi-robotics/cloud_services/pull/627) mfinean (b, infra/dev/resources/compute/eval-report.tf):
  > Blocking: this doesn't just make the report stale, it eventually **deletes** it. `gcs_ci_reports` carries an unconditional `lifecycle_rules = [{ age = 90 }]` with no `matches_prefix` (`storage/buckets.tf:290-292`; `action_type` defaults to `Delete`). The daily rewrite is what keeps `eval/latest/index.html` permanently under 90 days — which is exactly what the header comment at lines 15-17 of this file says: *"a repor
- [#701](https://github.com/kinisi-robotics/cloud_services/pull/701) mfinean (b, infra/dev/resources/compute/github-runners.tf):
  > **This pool will never produce a working runner — every instance self-deletes about two minutes in.** `github-runner-sim-test` is a new SA (the plan creates it), and the plan adds **12 resources — the module's own set and nothing else**. No storage bindings. It isn't in `local.ci_runners` (`storage/modules/gcs-bucket/main.tf:7-16`), so it has no access to `kinisi-robotics-ue-ddc`. That matters because the test image 
- [#775](https://github.com/kinisi-robotics/cloud_services/pull/775) mfinean (a, infra/dev/resources/compute/lerobot-converter/entrypoint.py):
  > **The requested rate never takes effect.** `convert_episodes` takes `fps` from the *first* call and ignores it on later ones (its docstring: "Dataset-level config is fixed by the *first* call and later calls' values are ignored: ``fps``, …"). The per-episode call at line 480 still passes `fps=10`, so `LeRobotDataset.create(fps=...)` and the downsampler both still run at 10 whatever `FPS` says. Pass `fps=fps` there, a
- [#580](https://github.com/kinisi-robotics/cloud_services/pull/580) eaa3 (c, infra/dev/resources/compute/lerobot-converter/entrypoint.py):
  > **[Security / Critical] User-influenced `KEYPOINT_WEIGHTS_URI` reaches `torch.load(weights_only=False)` (pickle RCE) inside a credential-holding Job.** This URI is taken verbatim (only `.strip()`, no scheme/bucket/prefix check), packed into `keypoint_predictor_override["weights_uri"]`, and flows to the kinisi_ros selector (`learned_predictor_selector._resolve_weights_uri` accepts **any** gs:// URI, bucket-relative ke
- [#941](https://github.com/kinisi-robotics/cloud_services/pull/941) mfinean (c, scripts/provision_robot_cert.py):
  > **Blocking.** When a step after `register_in_database` fails, `rollback()` has just revoked the new cert, so the live count here is 0 and this deletes the cert row and the robot row. The cloud's revocation cache is a deny-list built from `robot_certificate` joined to `robot` where either is revoked ([`get_revoked_serials`](https://github.com/kinisi-robotics/kinisi_ros/blob/main/cloud/src/kinisi_cloud/services/certifi
- [#977](https://github.com/kinisi-robotics/cloud_services/pull/977) mfinean (c, infra/dev/resources/iam/main.tf):
  > **Blocking.** `ansible-vault-key` is not only kinisi_os's vault password. kinisi-ansible's [`scripts/vault_pass.sh`](https://github.com/kinisi-robotics/kinisi-ansible/blob/bb57ce01b8192aa3844c73d74859fb0f7e2415b4/scripts/vault_pass.sh#L8) reads the same secret to decrypt `inventories/group_vars/all/vault.yaml`, which holds `vault_zerotier_api_token` ([used here](https://github.com/kinisi-robotics/kinisi-ansible/blob/
- [#853](https://github.com/kinisi-robotics/cloud_services/pull/853) mfinean (b, infra/dev/resources/storage/buckets.tf):
  > Renaming the key from `staff_read_group:developers@kinisi.com` to `developers_read` makes the plan destroy and recreate the same developers `objectViewer` binding (the plan comment shows one create and two destroys). The comment above the `moved` blocks lower in this file explains why that's unsafe: the two keys are separate graph nodes, so the create can run first as a no-op and the destroy then removes the live bin
- [#790](https://github.com/kinisi-robotics/cloud_services/pull/790) eaa3 (b, infra/dev/main.tf):
  > Dropping `module.certificates` also drops iam's only wait on `module.database` (it came transitively via certificates -> cloud_bridge), which `project-hub-identity.tf` and `team-tracker-identity.tf` rely on: their bindings name the db password secret by string, so a fresh apply can now bind before the secret exists. Use `depends_on = [module.storage, module.database]` (no cycle, database takes nothing from iam) and u
- [#698](https://github.com/kinisi-robotics/cloud_services/pull/698) mfinean (b, infra/dev/resources/compute/github-runners.tf):
  > **`github-runner-engine` isn't in the GCS writer map, so the final `gcloud storage cp` will 403.** > That bucket isn't managed in this repo, so I can't confirm from here whether `github-runner-engine` will be able to write to it. It is managed here — `infra/dev/resources/storage/buckets.tf:355`, `module "gcs_unreal_releases"`, `name_suffix = "unreal-releases"` → `kinisi-robotics-unreal-releases`, with `ci_runner_writ
- [#507](https://github.com/kinisi-robotics/cloud_services/pull/507) copilot-pull-request-reviewer (a, infra/dev/resources/compute/scripts/github-runner-startup.sh):
  > `$?` in this error message will always print `0` because the `if ! gcloud ...; then` condition inverts the exit status. Capture the `gcloud` exit code before negation (e.g., run the command, store `rc=$?`, then branch on `rc`) so logs report the real failure code. This issue also appears on line 565 of the same file. 

### Top 10 worst (by outcome or value)

The first two comments were correct. They rank here because the fixes made in response to them broke production (§2). The skill lesson: when a comment asks for a new mechanism, the reviewer must also check the fix (scope, provider constraints, apply).


- [#866](https://github.com/kinisi-robotics/cloud_services/pull/866) mfinean (a, infra/dev/resources/billing/daily-cost-reporter/main.py):
  > This stops the duplicate post. The opposite case still loses the day: if the dated object is written and the Slack post then fails, the next run sees the day as `complete` and never posts it. Nothing retries it. The scheduler job has no `retry_config`, and a retry would find nothing to report. If `u
- [#541](https://github.com/kinisi-robotics/cloud_services/pull/541) mfinean (b, infra/dev/resources/compute/crash-collector.tf):
  > 🟠 **No alert on the collector going down.** For a service the design says must "survive months of zero attention," we need a signal. A standard GCP uptime check won't work here — internal-only DNS, no public IP (same reason `monitoring/cloud-bridge.tf` ~L477 removed its uptime check). The in-pattern
- [#697](https://github.com/kinisi-robotics/cloud_services/pull/697) mfinean (g, .github/workflows/rebuild-runner-images.yaml):
  > **A fresh-base bake through this path drops the DDS drop-in from the sim image.** With `use_cached_base=true` — what the dispatcher sends — the sim image inherits `/etc/sysctl.d/90-kinisi-dds.conf` from the cached base, so nothing is lost. But `use_cached_base=false` is reachable here: the manual ch
- [#606](https://github.com/kinisi-robotics/cloud_services/pull/606) mfinean (h):
  > Followed up on my own review — I dug into the write path and the dependency, and I want to correct something I implied earlier. **On the "just use a mounted disk / GCS FUSE" idea — retracting that as easy.** `convert_episodes` delegates output to upstream `LeRobotDataset` (async PNG image-writer → f
- [#451](https://github.com/kinisi-robotics/cloud_services/pull/451) blooop (e, infra/dev/packer/github-runner-unified.pkr.hcl):
  > 0.31.1 is available
- [#338](https://github.com/kinisi-robotics/cloud_services/pull/338) caleb-kinisi (a):
  > tf output shows this isnt a real flag
- [#928](https://github.com/kinisi-robotics/cloud_services/pull/928) mfinean (e, infra/dev/resources/dataplane-consumer/main.tf):
  > **[nit]** Re-wrap the header: this line runs to 121 columns while the rest of the block wraps at about 80.
- [#975](https://github.com/kinisi-robotics/cloud_services/pull/975) mfinean (e, infra/dev/resources/credential-renewer/main.tf):
  > `local.pool_name` now only renames `var.pool_name`; use the variable directly.
- [#548](https://github.com/kinisi-robotics/cloud_services/pull/548) mfinean (e, infra/dev/packer/github-runner-unified.pkr.hcl):
  > Nit: the `only` list now includes `x64-sim-gpu`, but this echo still says `(x64-sim)`. Cosmetic, but it'll mislead anyone reading build logs for the gpu variant. Same for the gcsfuse comment header just above if you want them consistent.
- [#769](https://github.com/kinisi-robotics/cloud_services/pull/769) mfinean (e, tests/test_lerobot_converter.py):
  > After rebasing onto #775, this and `_run_at_rate` are the same env-and-patch runner with different return values. Merge them into one helper.