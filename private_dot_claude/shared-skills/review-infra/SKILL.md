---
name: review-infra
description: "Review a kinisi-robotics/cloud_services PR (Terraform on GCP, GitHub Actions, the Python jobs it deploys): run the apply gate that catches changes that pass `terraform plan` and then fail, delete or do nothing at apply, then post only blocking defects. Use for any review of a cloud_services PR, a re-review after the author answers, or when asked whether a cloud_services change is safe to deploy. Never edits the branch."
---

# Review a cloud_services PR

The output is one PR review: a verdict on whether the change will apply, and at
most six comments, each one a real defect with its failure scenario. Nits do not
go out.

Why the bar sits where it does (from 782 PRs, Nov 2025 – Nov 2026):

- 35 deployment errors. 11 passed `plan`, `validate`, tflint and tfsec, then failed
  at apply. The causes were an API limit on one field, a fixed name in a
  create-before-destroy replace, a log metric and its alert in one apply, and alert
  text over the size limit. 5 more broke only at run time.
- Reviews that did happen were good: 58% of review findings were real defects,
  deploy risks or security problems. The escapes were classes nobody checked.
- 2 bugs came from the *fix* for a review comment (#541, #866). A fix-up commit
  gets the same gate as the first push.

## Read-only

Read, build, run tests and run `terraform plan -lock=false`. Do not edit, commit,
push, approve, request changes, merge or apply. Post as `event: COMMENT`; the
human approves.

## 1. Set up

```bash
PR=$(gh pr view "${ARG:-}" -R kinisi-robotics/cloud_services --json number -q .number)
gh pr view "$PR" -R kinisi-robotics/cloud_services --json title,body,baseRefOid,headRefOid,files,reviews
git fetch origin "pull/$PR/head" && HEAD=$(git rev-parse FETCH_HEAD)
git fetch origin <baseRefOid> && BASE=$(git merge-base <baseRefOid> "$HEAD")
git diff --stat "$BASE" "$HEAD"
```

Use `baseRefOid`, not `origin/<base>`. A stack branch can be gone, and on a
merged PR `origin/main` already holds the head. Check that the `--stat` file
list matches the PR's `files`.

Done when you have the PR's head SHA, its base, and its stated intent.

## 2. Apply gate

The gate is the review's first job and it is mandatory. It decides one thing:
**will this change apply cleanly and do what it says?** Every BLOCK and every
CHECK below ends **confirmed** (it becomes a finding) or **refuted** (with the
evidence: a doc line, a plan line, a test). An open item means the gate is not
done. A refuted item never appears on the PR.

S=the directory of this file.

**2a. Scan the diff.**

```bash
python3 -I $S/scripts/infra_risks.py --base "$BASE" --head "$HEAD"
```

Each rule names the incident that taught it. A CHECK that needs a rendered value
(the length of alert text, a `templatefile`) gets it from `terraform console` in
a throwaway directory: copy the expression and its inputs as literals into a
`main.tf` there, then `echo 'length(local.x)' | terraform console`. Use
`console` or `plan` only. Never `apply`, even with no provider. Alert text has a
4000-char cap on a log-match policy (`condition_matched_log`) and 8192 on any
other policy. [references/incidents.md](references/incidents.md)
has the incident behind each rule and the API error text to quote.

**2b. Get the plan for this head SHA.** Use the first source that works:

1. The PR Validation comment that starts with `<!-- terraform-plan -->`. It counts
   only when its workflow run's `headSha` (from `gh run view <id> --json headSha`)
   equals `$HEAD`. A plan for an older push is stale. Each root has its own
   comment marker (`terraform-plan-universe-*`).
2. Plan it yourself, for a stale or missing comment, or when a CHECK needs
   rendered values. A person's ADC cannot read bucket IAM, so run it as the plan
   identity (export `GOOGLE_IMPERSONATE_SERVICE_ACCOUNT=terraform-plan@kinisi-robotics.iam.gserviceaccount.com`).
   When impersonation is refused, the gate is NOT RUN for the plan. Say so in
   the verdict.
   ```bash
   git worktree add "$TMP/pr" "$HEAD" && cd "$TMP/pr/infra/dev" && terraform init -input=false
   terraform plan -input=false -lock=false -out="$TMP/tfplan" \
     -var=project_id=kinisi-robotics -var=project_number=257853690162 -var=zerotier_network_id=9f77fc393e07ad6a
   terraform show -json "$TMP/tfplan" > "$TMP/plan.json"
   ```
   The JSON holds secret values from state. Keep it under `$TMP` and delete it,
   and the `-out` file of a failed plan, after the review. Plan any other root
   the PR changes (`infra/universe/*`, `infra/billing`, `infra/cloud-bridge-dev`)
   the same way.

A failed plan is a BLOCK on its own. Once, a red plan stayed red for 11 days
while PRs merged (#447).

**2c. Read the plan.**

```bash
python3 -I $S/scripts/plan_risks.py "$TMP/plan.json"   # or the comment text
```

Then read the plan as a person would, against the PR's stated intent:

- Every delete and replace: what forces it (`replace_paths`, `# forces
  replacement`), and what is lost (data, IP, certificate, IAM access while it is
  re-created). The PR body must explain each one.
- Every change to an address the diff does not touch. This is drift, another
  PR's change, or a module input that leaks. The apply ships it all.
- A replace with create-before-destroy keeps the old object while it creates the
  new one, so a unique name must change.

**2d. Answer what the plan cannot show.** For each new resource type, new field
or changed identity, find the answer and write it down:

- **API constraint**: is the field legal for this variant? Read the GCP REST
  reference for the resource, not only the provider docs. The provider accepts
  what the API rejects.
- **Order inside one apply**: does something read an object that this same apply
  creates? Examples: a metric, a secret version, an IAM grant (which takes up to
  7 min to take effect), or an image tag that is not pushed yet.
- **Who calls it, as which identity, with which OAuth scope**: IAM roles do not
  widen VM scopes. A redeploy can drop a binding that GCP made automatically.
- **Who else writes it**: kinisi_ros deploys images and env out of band, people
  change things by hand, and the access page grants roles. A field another writer
  owns needs `ignore_changes`. A field under `ignore_changes` never ships.
- **Is it applied at all**: only `infra/dev` and `infra/modules` apply after
  merge. Any other root needs a named person and a time.
- **What proves it worked after apply**: the PR body needs one line that names
  the check (a re-plan that is empty, a log line, an alert state, a smoke call).
  A PR with no such line gets that as a finding when the change can fail
  silently.

**2e. Stacked or parallel PRs.** Two green PRs once made a combined plan that
wiped 16 env vars (#629 + #630). When the base is not `main`, or another open PR
touches the same resources, plan them together.

Done when: both scripts ran on `$HEAD`, the plan's SHA is `$HEAD`, and every
BLOCK, every CHECK, and every delete or replace in the plan is confirmed,
refuted or **likely** in your notes. Use likely when only a live call can settle
it and the docs or an earlier incident point one way. A likely item goes out as
`issue (blocking, unproven):`, with the doc line or incident, and with the one
action that would prove it (for example, "apply to a scratch project" or "create
the secret version first").

## 3. Defect review

Read the diff for the defect classes that good reviews on this repo caught:

- A key rename in `for_each` or a map, or an address rename with no `moved`
  block. Terraform destroys and re-creates the object: a new IP for an allowlist,
  a lost key, a gap in IAM.
- `force_destroy`, a lifecycle `Delete` rule, or a disk shrink on data that cannot
  be made again.
- A new service account that is missing from a writer map, or a grant that does
  not narrow access because project `roles/viewer` still allows the read.
- Trust that is too wide: a WIF `principalSet` on the whole repository, a GitHub
  environment that does not exist yet, one SA for dev and live, a shared key.
- An alert that cannot fire, or fires on every deploy (absence per revision, a
  filter that names one of two services, alert maths on streaming RPCs).
- Job states that stick: a row stays `converting` forever, or a late SIGTERM
  overwrites a final state.
- Shell and workflow traps: `$?` after `if !`, `GITHUB_SHA` on
  `repository_dispatch`, untrusted `${{ github.event.* }}` in `run:`, an action
  not pinned to a SHA, `continue-on-error` that hides a red run.
- A gcloud or API call that does not do what the code assumes. Examples:
  `abandon-instances` does not keep the target size, a `list(filter=)` limit, a
  token that cannot `objects.patch`. Prove it from the API reference or a dry run.
- An image change that is too large for the runner or bake disk, or a dependency
  that is not pinned.
- A test that cannot fail.

For each candidate, **try to refute it** before you keep it. Read the
surrounding code, the module, the docs, and the earlier PR that made the
decision. Keep only what survives.

## 4. Re-review after the author answers

On each new push or "fixed in <sha>" reply:

1. Run the whole apply gate (§2) again on the new head. A fix is a new change.
2. For each earlier finding, check the new code against that finding's failure
   scenario. "Changed" is not "fixed".
3. Look at what the fix added: new fields, scopes, permissions, alerts. #541's
   fix added a field the API rejects, and #866's fix called an API that its
   token could not call.

Reply in the thread: resolved (with the evidence), or still open (with the input
that still fails).

## 5. Write the review

Each inline comment carries:

- **Label**: `issue (blocking):` for something that will fail, delete or do
  nothing. `issue:` for a real defect that is not urgent.
- **Failure scenario**: the input or sequence, and the wrong result. For example:
  "on apply, the API returns 400 `Timeout sec is not supported for a backend
  service with Serverless network endpoint groups`, and the LB step stops
  half-applied."
- **Evidence**: the plan line, the API doc line, the incident (`same as #533`),
  or a test you ran.
- **Fix**: one line, when it fits.

Up to **six** inline comments, ranked: apply-breaking, then data loss and
security, then run-time breakage, then other defects. Style, naming, wording and
"consider" go out only as one optional line in the summary body.

The summary body opens with the gate verdict:

```
Apply gate @ <short sha>: SAFE TO APPLY | NOT SAFE (n blocking, m unproven) | NOT RUN (<why>)
- diff scan: n BLOCK / n CHECK — all resolved (refuted: <rule> — <evidence>; ...)
- plan: <source>, <adds>/<changes>/<destroys>; deletes/replaces: <list or none>
- post-apply check: <the PR's line, or "missing">
```

Then 1–3 lines: what the change does, and the one thing that matters most. When
nothing qualifies, post the gate verdict and say what you checked. A short clean
review is a real result.

## 6. Post and report

```bash
gh api repos/kinisi-robotics/cloud_services/pulls/$PR/reviews --input review.json   # event: COMMENT
```

`line` is in the post-image of the diff. A finding with no diff line goes in the
body. With `--dry-run`, write `review.json` to the scratchpad and print it
instead of posting.

Report the review URL, the gate verdict, the comment count, and each refuted
item with its evidence. Delete `$TMP` and the worktree.

## When an incident escapes this gate

Add the rule to `scripts/infra_risks.py` or `scripts/plan_risks.py`, add its row
to `references/incidents.md`, and run the back-test in that file. Every past
cause must still give a BLOCK, and the clean set must stay at one known BLOCK.
