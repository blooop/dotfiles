# Best practices for an AI review skill: infra repo (Terraform/GCP, GitHub Actions, Python)

Context: deploy = `terraform apply` after merge, with a human-approved plan. Sources were
checked with web search on 2026-11-24. Items marked (search summary) were confirmed through
search-result text rather than a full read of the primary page.

Format per item: **Practice** — Why (source) — **Check** (what the review skill does).

---

## A. High-value review comments, not nits

### A1. Review finds few bugs per comment; spend the comment budget on defects
- Why: At Microsoft only about 15% of review comments point to a possible defect, fewer to a
  blocking one (Czerwonka, Greiler, Tilford, ICSE 2015,
  https://www.microsoft.com/en-us/research/publication/code-reviews-do-not-find-bugs-how-the-current-code-review-best-practice-slows-us-down/).
  About 75% of defects that reviews find are evolvability, not function (Mäntylä & Lassenius,
  IEEE TSE 2009, https://mmantyla.github.io/wiki/What+Types+of+Defects+Are+Really+Discovered+in+Code+Reviews%253F.html;
  replicated by Beller et al. 2014). Humans already cover style; the scarce output is defects.
- Check: Rank findings by (deploy impact x likelihood). Post functional/deploy defects first.
  Cap evolvability comments (for example at 2) and mark them `nit:`. Post zero comments if
  nothing is real; "no findings" is a valid result.

### A2. Know what "useful" means to the author
- Why: Bosu, Greiler, Bird, MSR 2015 (https://www.microsoft.com/en-us/research/publication/characteristics-of-useful-code-reviews-an-empirical-study-at-microsoft/)
  classified ~1.5M comments; a comment counts as useful when it causes a change in the code
  near it. About a third of comments were not useful. Useful comments identify functional
  defects, validation gaps, API misuse and missed corner cases; not-useful ones are questions
  answered elsewhere, false positives, and vague style remarks. Reviewers who know the
  codebase write more useful comments (useful fraction rises during the first year).
- Check: For each draft comment ask: "Will the author change the code because of this?" If the
  answer is "no" or "maybe", drop it or fold it into a single summary note. Before posting,
  read the surrounding files (module callers, variables, other envs) so the comment has
  codebase context, which is the substitute for reviewer experience.

### A3. Reviews are also for understanding and risk transfer
- Why: Bacchelli & Bird, ICSE 2013 (https://www.microsoft.com/en-us/research/publication/expectations-outcomes-and-challenges-of-modern-code-review/):
  finding defects is the top stated motivation, but the main outcomes are knowledge transfer,
  team awareness and alternative solutions; understanding the change is the main challenge.
- Check: Open the review with a 2-3 line statement of what the change will do in production
  (resources created/changed/destroyed, who gains which access, which workflows change). If
  the skill cannot state this, that is itself the finding: ask for the plan output or the
  intent.

### A4. Google "what to look for" and the `nit:` convention
- Why: Google eng-practices (https://google.github.io/eng-practices/review/reviewer/looking-for.html,
  https://google.github.io/eng-practices/review/reviewer/standard.html,
  https://google.github.io/eng-practices/review/reviewer/comments.html): look at design,
  functionality (edge cases, concurrency), complexity, tests, naming, comments, consistency;
  approve when the change improves code health even if not perfect; prefix optional polish
  with "Nit:"; explain why; give guidance and balance pointing out problems with direct
  instructions; label severity so the author knows what is mandatory.
- Check: Every comment carries a severity label. Only defects block. Never block on
  preference. Code that is better than before and has no defect = approve.

### A5. Label intent: Conventional Comments
- Why: https://conventionalcomments.org/ — `<label> [decorations]: <subject>` with labels
  `issue`, `suggestion`, `question`, `nitpick`, `thought`, `todo`, `praise`, and decorations
  `(blocking)` / `(non-blocking)` / `(if-minor)`. It removes ambiguity about what must change.
- Check: Format each posted comment as `issue (blocking): ...`, `question (non-blocking): ...`,
  `nitpick (non-blocking): ...`. A `question` is used only when the skill truly cannot decide
  from the repo; it must say what answer would make it a defect.

### A6. Phrase the comment so the author fixes it right
- Why: Bosu et al. (A2) — specific, actionable comments with the failure condition get acted
  on; Google comments guide — explain the reasoning. Google ML-edit work shows a concrete
  suggested edit gets applied directly (author resolves ~7.5% of all reviewer comments by
  applying an ML-suggested edit; https://research.google/blog/resolving-code-review-comments-with-ml/).
- Check: Each blocking comment has four parts: (1) the exact line; (2) a concrete failure
  scenario — trigger, sequence, observable result ("on apply, `google_project_iam_binding`
  for roles/editor removes the 3 members added by the console; CI SA loses deploy access");
  (3) the evidence (plan line, doc link, repro output); (4) a suggested fix, as a GitHub
  `suggestion` block when it is under ~10 lines. No comment without a scenario.

### A7. Try to refute each finding before posting (false-positive control)
- Why: Developer trust in automated review depends on a low false-positive rate. Google's
  Tricorder kept analyzer "effective false positive" under ~10% and removed checks that
  exceeded it (Sadowski et al., CACM 2018, https://cacm.acm.org/research/lessons-from-building-static-analysis-tools-at-google/).
  AutoCommenter (Google, LLM best-practice comments) reports ~40% estimated resolution rate
  and very little explicit feedback (https://arxiv.org/abs/2405.13565). SWR-Bench finds that
  most LLM review false positives come from missing context and ignored project conventions
  (https://arxiv.org/pdf/2509.01494). BitsAI-CR (ByteDance) tracks an "Outdated Rate" — the
  share of commented lines later changed — as the real adoption metric.
- Check: For each candidate finding, run a refutation step: search the repo for the guard,
  the caller, the variable default, the other env, the docs of the provider version in the
  lock file. Drop it if any refutes it. Prefer a reproduction (`terraform validate`, `plan`,
  `actionlint`, a unit test) over an argument. Track the skill's own outdated/acted-on rate
  over time and prune comment classes that are rarely acted on.

### A8. Review the author's response, not just the original diff
- Why: Google eng-practices "handling pushback"
  (https://google.github.io/eng-practices/review/reviewer/pushback.html): consider whether the
  author is right; if not, explain again; do not accept "I'll clean it up later". Fix-up
  commits are written fast and reviewed lightly; they are a common source of regressions.
- Check: On re-review, (1) diff the new commits only (`git range-diff` or compare to the last
  reviewed SHA); (2) for each resolved thread verify the fix addresses the failure scenario,
  not just the line; (3) re-run the same checks (plan, linters) on the new head; (4) look for
  collateral: the fix that changed a resource name (now a replace), a widened IAM role, a new
  `ignore_changes`, a `continue-on-error`, a skipped test; (5) re-read the new plan, not the
  old one; (6) if the author disagreed with evidence, re-evaluate and withdraw when they are
  right — say so on the thread.

### A9. Small, focused changes; ask to split
- Why: Google eng-practices small CLs (https://google.github.io/eng-practices/review/developer/small-cls.html).
  In IaC, mixing a refactor (`moved`) with behavior changes hides the replace among the noise.
- Check: Flag a PR that mixes state refactors (moved/removed/import), provider upgrades and
  resource changes. Recommend landing the no-op refactor first, with a plan that shows
  `0 to add, 0 to change, 0 to destroy`.

---

## B. Catching deployment errors before deploy (IaC)

### B1. ~70% of outages come from changes; review the change as an outage risk
- Why: Google SRE book, intro and "Release engineering"
  (https://sre.google/sre-book/introduction/): roughly 70% of outages are due to changes in a
  live system; the remedies are progressive rollout, fast detection, and safe rollback.
  SRE workbook "Canarying releases" (https://sre.google/workbook/canarying-releases/).
- Check: For each change, answer: blast radius (one env/region/project or all?), rollback
  path (is `git revert` + apply enough, or is the destroy one-way?), and detection (how will
  we know it broke?). Missing rollback for a one-way change = blocking.

### B2. Global, instant config pushes cause the large outages
- Why: Google Cloud, 2025-06-12 (https://status.cloud.google.com/incidents/ow5i3PPK96RduMcb1SsW):
  a policy with blank fields replicated globally in seconds and hit a code path without null
  handling and without a feature flag; Google's remediation = flag-protect critical changes,
  audit consumers of globally replicated data, staged rollout of config. CrowdStrike Channel
  File 291 (https://www.crowdstrike.com/wp-content/uploads/2024/08/Channel-File-291-Incident-Root-Cause-Analysis-08.06.2024.pdf):
  a content update with 21 fields met an interpreter that supplied 20; the validator passed
  it; it shipped to all hosts at once; remediation = bounds checks, validator fixes, staged
  content deployment. Cloudflare 2025-11-18 (https://blog.cloudflare.com/18-november-2025-outage/):
  a DB permissions change made a generated feature file double in size, exceeding a hard
  limit in the proxy, and the file propagated network-wide every 5 minutes.
- Check: Flag a change that applies the same new config to every env/region/project in one
  apply (for_each over all envs, a shared module version bump, an org-level policy or folder
  IAM change). Ask for staging first (dev -> staging -> prod workspaces or separate PRs).
  Flag generated config/data consumed by other systems without schema/size validation.
  Treat permissions changes as data-shape changes for downstream consumers (Cloudflare).

### B3. Read the plan, line by line, for the dangerous action symbols
- Why: Terraform plan docs (https://developer.hashicorp.com/terraform/cli/commands/plan):
  `-/+` = destroy then create (replace); `+/-` = create before destroy; `-` = destroy;
  `# forces replacement` names the attribute that caused it; `<= read` = data source read at
  apply (values "known after apply").
- Check: Parse the plan (prefer `terraform show -json plan.out`) and list every `delete` and
  every replace action (`["delete","create"]` or `["create","delete"]`). For each: the
  attribute that forces it, whether the resource is stateful (Cloud SQL, GCS bucket, BigQuery
  dataset/table, Filestore, disks, KMS keys, Secret Manager, Pub/Sub subscriptions with
  backlog, service accounts, projects), and whether the PR description says it is intended.
  Unexplained destroy/replace of a stateful resource = blocking. Also flag: count/for_each
  key changes (index shift recreates N resources), `(known after apply)` on names/IDs that
  feed IAM or DNS, and `~ update in-place` on `labels`/`metadata` that actually restarts VMs.

### B4. Destroy protection is defense in depth, with known gaps
- Why: `lifecycle.prevent_destroy` (https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle)
  fails a plan that would destroy the resource, but it does nothing once the resource block is
  deleted from config. Google provider adds API-side guards: `deletion_protection` on
  `google_sql_database_instance`, `google_bigquery_table`, `google_container_cluster`,
  `google_compute_instance`; `deletion_policy` on `google_project` (default PREVENT in v6+);
  `force_destroy` on `google_storage_bucket` (deletes objects).
- Check: Flag removal of `prevent_destroy`, `deletion_protection = false`,
  `force_destroy = true`, `deletion_policy = "DELETE"` / `"ABANDON"` changes, and stateful
  resources without these guards. Flag a deleted resource block whose type is stateful even
  when it has `prevent_destroy` — the guard went with it.

### B5. State operations: prefer declarative `moved` / `removed` / `import` blocks
- Why: `moved` blocks (https://developer.hashicorp.com/terraform/language/modules/develop/refactoring)
  rename/move addresses with no destroy; `removed` with `lifecycle { destroy = false }`
  (https://developer.hashicorp.com/terraform/language/block/removed, Terraform >= 1.7)
  forgets a resource without destroying it, and shows in the plan, unlike `terraform state rm`;
  `import` blocks (https://developer.hashicorp.com/terraform/language/import, >= 1.5) are
  plan-visible too. Default `removed` without `destroy = false` DESTROYS the object.
- Check: Any renamed resource/module address must have a `moved` block (else plan shows
  destroy+create). `removed` without `destroy = false` = ask. An `import` block must import
  with config that matches reality: the plan after import must show no changes for that
  resource (or only the intended ones). Flag instructions in the PR to run
  `terraform state mv/rm/import` by hand; ask for the block form instead.

### B6. Authoritative vs additive IAM in the google provider
- Why: Provider docs (https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/google_project_iam):
  `google_project_iam_policy` is authoritative for the whole project policy and replaces
  anything not listed (including Google-managed service agent bindings — can lock you out);
  `google_project_iam_binding` is authoritative for one role (removes other members of that
  role); `google_project_iam_member` is additive. `_policy` cannot be mixed with
  `_binding`/`_member`, and `_binding` cannot be mixed with `_member` for the same role, or
  they fight on every apply. Same pattern for org, folder, bucket, SA, secret, etc. IAM.
  `google_project_iam_audit_config` is also authoritative per service.
- Check: Flag any new `*_iam_policy` (blocking unless the project is fully TF-owned and the
  PR says so). Flag `*_iam_binding` on a role that other code, modules or humans also grant
  (search the repo for the same role on the same resource). Flag basic roles
  (`roles/owner`, `roles/editor`, `roles/viewer`), `allUsers`/`allAuthenticatedUsers`,
  `roles/iam.serviceAccountTokenCreator`/`serviceAccountUser` at project level, and
  primitive grants to users instead of groups. Read the plan: a `_binding` update that lists
  members being removed is a revocation.

### B7. Failures that plan cannot show (apply-time only)
- Why/sources:
  - IAM changes are eventually consistent: typically ~2 min, can be 7+ min; group membership
    minutes to hours (https://docs.cloud.google.com/iam/docs/access-change-propagation).
    A resource that uses a just-granted role in the same apply can fail.
  - API not enabled: `google_project_service` must exist and resources must depend on it;
    enabling can take minutes. `disable_on_destroy` (default true in older providers) can
    turn off an API for everyone when the resource is removed
    (https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/google_project_service).
  - Name reuse: deleted project IDs are never reusable; a recreated service account is a new
    identity with a new unique ID and does not inherit roles; old bindings show as
    `deleted:serviceAccount:...?uid=` (https://docs.cloud.google.com/iam/docs/service-accounts-delete-undelete,
    https://docs.cloud.google.com/resource-manager/docs/delete-restore-projects). Cloud SQL
    instance names cannot be reused for about a week after delete; GCS bucket names are global.
    Secret/KMS keyrings cannot be deleted at all (KMS key rings and keys are permanent).
  - Org policy constraints (e.g. `iam.disableServiceAccountKeyCreation`,
    `compute.vmExternalIpAccess`, `gcp.resourceLocations`, domain-restricted sharing) reject
    at apply time (https://docs.cloud.google.com/resource-manager/docs/organization-policy/overview).
  - Quotas and regional capacity (GPUs, IPs, CPUs) fail at apply.
  - Permissions of the apply identity: plan reads with the plan SA; apply may need more.
- Check: For every new resource type in the PR, ask: is its API enabled in this project
  (search for `google_project_service`), is there a `depends_on`/reference to it; does it
  need a new role for the apply SA; does it reuse a name that existed before (git log -S the
  name); does any org policy forbid it (location, public IP, SA keys, external sharing);
  does it need quota (GPU, static IPs). Flag same-apply "grant then use" chains and suggest
  `time_sleep` or a two-step rollout. Flag `google_project_service` removals without
  `disable_on_destroy = false`.

### B8. Plan-in-PR, apply the exact reviewed plan
- Why: Atlantis/TACOS pattern (https://www.runatlantis.io/docs/autoplanning,
  https://www.runatlantis.io/docs/apply-requirements): plan runs on the PR and is posted as a
  comment; apply requires approval and a mergeable PR; locking prevents two PRs planning the
  same state. Terraform: `terraform apply plan.out` applies exactly the saved plan and fails if
  state changed (https://developer.hashicorp.com/terraform/cli/commands/apply).
- Check: Confirm the plan in the PR is for the PR's current head SHA (stale plan after a
  fix-up push = blocking until re-planned). Confirm the post-merge apply uses the saved plan
  or re-plans and stops on difference. Flag apply workflows without `concurrency` on the
  state/workspace. Flag plans that touch more directories/workspaces than the diff explains.

### B9. Drift detection
- Why: `terraform plan -detailed-exitcode` exits 2 when changes exist
  (https://developer.hashicorp.com/terraform/cli/commands/plan); `-refresh-only` shows drift
  without proposing config changes. Drift in a plan on an unrelated PR means someone changed
  infra outside Terraform; applying it reverts their change.
- Check: In the plan, separate changes that the diff explains from changes it does not. Any
  unexplained change (especially IAM, firewall, scaling) = blocking question: "this apply will
  revert an out-of-band change to X; intended?" Suggest a scheduled drift job if none exists.

### B10. Provider and module version changes
- Why: Google provider major upgrades change defaults and force replacements (upgrade guides,
  e.g. https://registry.terraform.io/providers/hashicorp/google/latest/docs/guides/version_6_upgrade,
  version_7_upgrade). `.terraform.lock.hcl` pins exact versions and hashes
  (https://developer.hashicorp.com/terraform/language/files/dependency-lock).
- Check: A provider/module version bump must come with a plan for every affected root module,
  and the PR must show no unexpected diff. Read the upgrade guide sections for resource types
  in this repo. Flag version constraints that are open-ended (`>= 5.0`), lock file changes
  without a version change in config (or vice versa), and module sources by branch instead of
  tag/SHA.

### B11. Policy-as-code and static scanners
- Why: tflint (https://github.com/terraform-linters/tflint, with the google ruleset — invalid
  machine types, deprecated syntax); Checkov (https://www.checkov.io/) and Trivy misconfig
  (https://trivy.dev/latest/docs/scanner/misconfiguration/, tfsec merged into Trivy) for
  public buckets, open firewalls, missing encryption; OPA/conftest
  (https://www.conftest.dev/) on `terraform show -json` to enforce house rules on the plan
  (no deletes of stateful types, no `_iam_policy`, required labels, allowed regions).
- Check: The skill runs (or reads CI results of) `terraform fmt -check`, `terraform validate`,
  tflint, Trivy/Checkov. It does not repeat their findings as comments; it reviews new
  suppressions (`#checkov:skip`, `#trivy:ignore`, `tflint-ignore`) — each needs a reason.
  A conftest rule set on plan JSON is the durable form of the checks in B3/B4/B6.

### B12. Network and exposure
- Why: Same scanners and GCP security best practices.
- Check: Flag firewall rules with `0.0.0.0/0` source on non-HTTP(S) ports, new external IPs,
  `allUsers` on buckets/Cloud Run (`roles/run.invoker`), Cloud SQL public IP without
  authorized networks, Cloud Run `ingress = all` for internal services, and `ignore_changes`
  on security-relevant attributes.

### B13. GitHub Actions safety
- Why: GitHub "Security hardening for GitHub Actions"
  (https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions);
  OWASP GHA cheat sheet (https://cheatsheetseries.owasp.org/cheatsheets/GitHub_Actions_Security_Cheat_Sheet.html);
  zizmor audits (https://docs.zizmor.sh/audits/): template-injection, dangerous-triggers
  (`pull_request_target`, `workflow_run`), excessive-permissions, artipacked
  (persist-credentials), unpinned-uses, cache-poisoning. actionlint
  (https://github.com/rhysd/actionlint) catches syntax, expression type errors, shellcheck in
  `run:`. tj-actions/changed-files (CVE-2025-30066, March 2025,
  https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-github-action-cve-2025-30066):
  all 361 tags repointed to a malicious commit that dumped secrets to logs; only full-SHA pins
  were safe. Trail of Bits reports a 2026 `pull_request_target` exploitation of
  aquasecurity/trivy-action (https://blog.trailofbits.com/2026/05/22/we-hardened-zizmors-github-actions-static-analyzer/).
- Check:
  - `uses:` third-party actions pinned to a 40-char SHA (with a version comment).
  - Top-level `permissions:` set (default `contents: read`); write scopes only on the job
    that needs them; `id-token: write` only on jobs that authenticate to GCP.
  - `${{ github.event.* }}`, `github.head_ref`, PR title/body/branch names never interpolated
    into `run:`; pass via `env:`.
  - `pull_request_target`/`workflow_run` never check out or run PR head code with secrets.
  - `actions/checkout` with `persist-credentials: false` when the job does not push.
  - `concurrency:` group on deploy/apply workflows, with `cancel-in-progress: false` for
    apply (cancelling mid-apply leaves a stale lock and partial state).
  - Apply jobs use a protected `environment:` with required reviewers.
  - Workload Identity Federation: the provider's `attribute_condition` restricts to this
    repo (and ref/environment for apply), not the whole org or all of GitHub
    (https://github.com/google-github-actions/auth#security-considerations). No SA JSON keys
    in secrets.
  - `continue-on-error`, `if: always()`, or `|| true` added around plan/lint/test steps.

### B14. Progressive rollout for infra
- Why: SRE workbook canarying (B1); GCP 2025-06 and CrowdStrike remediations (B2) are all
  "stage it". 
- Check: Changes to shared modules, org/folder-level resources, network, IAM, DNS, or
  anything consumed by all envs should land in dev/staging first, and the PR should say how
  prod follows. A single PR that changes prod and non-prod simultaneously for a risky
  resource = ask to split or gate.

### B15. Python scripts in the infra repo
- Why: These scripts often run with deploy credentials and touch live resources.
- Check: Default to dry-run; destructive operations need an explicit flag; no swallowed
  exceptions (`except Exception: pass`) around API calls; pagination handled on list APIs;
  retries with backoff on 429/5xx and on IAM propagation (403 right after a grant); no
  credentials or project IDs hard-coded that differ per env; subprocess calls without
  `shell=True` on untrusted input.

---

## Checklist: the 25 most important checks (Terraform / GCP / GitHub Actions)

Plan and state
1. Every `delete` and replace (`-/+`, `+/-`) in the plan is listed, with the attribute that forces it, and is explained in the PR. Unexplained stateful destroy/replace blocks.
2. The plan matches the PR's head SHA; a re-push after review requires a fresh plan.
3. Every plan change is explained by the diff; unexplained changes are drift that the apply will revert.
4. Renamed or moved addresses have `moved` blocks; plan shows no destroy for a refactor.
5. `removed` blocks have `lifecycle { destroy = false }` unless destroy is intended; no hand-run `state rm/mv`.
6. `import` blocks produce a no-change plan for the imported resource.
7. `count` -> `for_each` or key/index changes do not recreate N resources.
8. Destroy guards (`prevent_destroy`, `deletion_protection`, `deletion_policy`, `force_destroy`) are not weakened; deleting a guarded block is noticed.

IAM and security
9. No new `*_iam_policy`; `*_iam_binding` only on roles nothing else grants; `_member` preferred.
10. No basic roles, no `allUsers`/`allAuthenticatedUsers`, no project-level `serviceAccountUser`/`TokenCreator`, grants to groups not users.
11. Plan shows no unintended member removals from IAM bindings (a `_binding` update is a revocation list).
12. Firewall/ingress/public IP/public bucket exposure is not widened.

Apply-time failures
13. Every new resource type has its API enabled (`google_project_service`) and a dependency on it; no API disable on destroy.
14. "Grant then use in the same apply" chains are flagged (IAM propagation 2-7+ min).
15. New names do not collide with deleted ones (project IDs, SAs, Cloud SQL, buckets, KMS).
16. Org policy constraints (locations, external IP, SA keys, domain sharing) allow the new resource.
17. The apply identity has the permissions the new resources need; quota exists for GPUs/IPs.

Rollout and versions
18. Blast radius stated; shared module, org/folder, network and all-env changes are staged (dev first).
19. Rollback path stated; one-way changes (destroy, KMS, project delete, data loss) are called out.
20. Provider/module version bumps carry a plan for every affected root and the upgrade guide is checked; versions and module refs are pinned.

GitHub Actions
21. Third-party `uses:` pinned to full commit SHAs.
22. `permissions:` minimal per job; `id-token: write` only where GCP auth happens; WIF `attribute_condition` scoped to this repo/ref/environment; no SA keys.
23. No `${{ }}` untrusted input in `run:`; no `pull_request_target`/`workflow_run` running PR code with secrets; `persist-credentials: false` where not pushing.
24. Apply workflows have `concurrency` (no cancel-in-progress) and a protected environment with required reviewers.
25. No new `continue-on-error`, `|| true`, `if: always()` or scanner suppressions without a stated reason; fix-up commits are re-reviewed for these.

Comment discipline (applies to every check above)
- Post only findings with a concrete failure scenario, evidence and a suggested fix; label
  `issue (blocking)` / `nitpick (non-blocking)`; refute before posting; on re-review, verify
  each fix against its scenario and re-run the checks on the new head.
