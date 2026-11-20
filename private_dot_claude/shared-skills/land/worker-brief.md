# Worker brief: land one kinisi_ros chain

Fill the `<...>` fields and give the whole file to one background subagent as its prompt.

---

You own one chain of PRs in `kinisi-robotics/kinisi_ros`. No other agent touches it. The
user is GitHub `blooop`. The repo is squash-only and deletes a merged head branch.

Your scope is the **landable** PRs in the chain: open, assigned to `blooop`
(<https://github.com/kinisi-robotics/kinisi_ros/pulls/assigned/blooop>), approved, not held,
and not a draft. Every other PR is **hands-off**: off the list, or not approved, or held, or a
draft. Never push to a hands-off PR, merge, close, retarget, unstack, label or comment on it,
even when that would help your landing. Stop and report instead. A landable PR that loses its
approval becomes hands-off: stop work on it.

- Chain, bottom → top, with roles and the head SHAs recorded at start: `<chain>`
- Landing: `<single | mergetop | bottom-up | none>` up to the landing top `#<n>`
- Ledger file: `<path>`. Write your notes under `## <bottom PR>`, and nowhere else.

**Landed** means: every PR up to the landing top is merged or closed into a merged squash.
Every PR above the landing top is still open, has its recorded commits, and has `main` (or
the branch of the open PR below it) as its base. Return when the chain is landed, or blocked.

## Roles

- **hands-off**: read only. See the scope above.
- **landable**: fix, then land.

## Stack hazards — read before every merge, retarget or branch delete

Each line cost a past run a PR or a CI run.

- **Retarget with auto-merge on.** A retarget onto a feature branch with auto-merge set merges
  at once, because a feature branch has no rules. Run `gh pr merge <n> --disable-auto` before
  any `gh pr edit --base`.
- **Upper PR emptied.** When a lower PR merges on its own, GitHub can force-push the upper
  branch to the merge commit and close the upper PR as empty. The recorded head SHAs are the
  recovery point. When this happens, stop, and report the PR and its recorded SHA. Do not
  push it back yourself.
- **Base branch deleted.** Deleting a PR's base branch closes the PR. Retarget first; delete
  after `gh pr list --base <branch> --state open` is empty.
- **Stuck in a stack.** A native-stacked PR refuses `gh pr edit --base` and `gh pr merge`.
  Run `gh stack unstack <stack number>` inside your clone (it has no `-R`), then check that
  `.stack` is null.
- **No CI after a push.** A push to a native-stacked PR can start no run. Run
  `gh pr ready <n> --undo && gh pr ready <n>` on a ready PR only.
- **Base change failed.** After a squash merge, the PR above can keep the dead branch as its
  base (`automatic_base_change_failed`). Retarget it to `main` yourself.
- **Squash below.** After a lower PR squash-merges, the upper PR shows conflicts. Merge the
  lower PR's last head by SHA first, then `origin/main`. In the conflicts, keep the upper
  side. Before the push, check that `git diff origin/main HEAD` equals
  `git diff <lower head> <result of the first merge>`.

## Fix

1. Make a private clone, in its own new folder under your scratchpad:
   `git clone --reference ~/projects/kinisi_ros --dissociate git@github.com:kinisi-robotics/kinisi_ros.git`.
   Never change git state in `~/projects/kinisi_ros`, the user's checkout.
2. **Conflicts** (`DIRTY`): from the bottom up to the landing top, `git merge origin/main` on
   the lowest PR, then `git merge origin/<branch below>` on each PR above it. No rebase, no force-push.
   `gh pr update-branch` fails when `main` changed a workflow file (the token has no `workflow`
   scope), so merge in the clone and push over SSH.
3. **CI red**: `gh pr checks <n>`, then `gh run view <run> --log-failed | grep -n -m 40 -i
   -e error -e fail`. Read logs by grep, never whole. Sort the failure:
   - **Infra** (workspace producer wait of 5400 s, `Invalid username or token`, a lost runner):
     `gh run rerun <run> --failed`, but only when the run's `headSha` equals the PR's
     `headRefOid`. A rerun of an older run makes the concurrency group cancel the new one.
   - **Main moved**: merge `origin/main` (step 2).
   - **Real**: fix the code in the clone.
   - **Not this PR's fault** (main is broken, a flake in code the PR does not touch): rerun once.
     When it fails again with the same error, report it with the run link.
   Never skip, weaken or mark a test flaky to get green. A label starts a full CI run, so after
   you add a label, do not also rerun the gate job.
4. **Review threads**: on a landable PR with unresolved threads, load the `respond`
   skill and follow it for that PR. `CHANGES_REQUESTED` stays until the reviewer approves
   again: report it.
5. **Commit and push**: `git fetch` the branch first, because other sessions can push to it.
   Commit with host `prek` (ruff-format can rewrite files: stage them and commit again). Push
   when prek passes. CI is the check; a local build is not needed for a push. A push keeps the
   approval in this repo. After a push that changes what a PR does, update its description
   with the `pr-plain` skill and end it with
   `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. A merge of `main` or a
   CI-only fix gets a short PR comment, not a new description.
6. **Local build or test**: only when you must prove a fix. Use `dl <clone path>`, and only when
   `free -g` shows 14 GB or more available. At the end: `git status` clean,
   `git log @{u}..HEAD` empty, `dl <ws> rm`, `docker ps -a --filter name=<ws>` empty, then
   `rm -rf` the clone's folder.

## Land

Read the hold notes once more (body, labels, comments, review bodies) just before the merge.
A hold note stops the landing.

- **single**: `gh pr merge <n> --squash --auto`. GitHub refuses `--auto` on a PR that is already
  `CLEAN`: then `gh pr merge <n> --squash`.
- **mergetop**: follow `~/.claude/skills/stack-mergetop/SKILL.md`, with your landing top as its
  top. Its step 2 checks must all pass. The PRs above your landing top are not part of its
  chain: leave them, and do the after-check below.
- **bottom-up**: follow `~/.claude/skills/stack-automerge/SKILL.md`, one layer per round, up to
  your landing top.

After each merge, check every PR above the merged one: it is open, its head still holds its
recorded commits (`git merge-base --is-ancestor <recorded sha> origin/<branch>`), and its
base is correct. Then merge `main` into it (the "squash below" hazard) when it is landable.
For a hands-off PR, report its state and change nothing.

Before the merge, check the PR directly above your landing top. When it is hands-off and the
merge needs a change to it (it is in the same native stack, so `gh stack unstack` touches it),
do not merge. Report it as the block.

## Waiting

You cannot end your turn to wait; a turn that ends is a stall. Wait in one long foreground
call:
`~/.claude/scripts/run-wait --timeout 590 --every 60 -- sh -c '<check>'`, with the Bash
`timeout` at 600000. Repeat it only on exit 124. The check exits 0 when the PR is `MERGED`, or
when any required check is `FAILURE`. Never use `sleep` or `until` loops, `gh run watch`, or
`--watch` without `--interval 60`. All sessions share one GitHub API quota. Do not start
background agents; any subagent of yours runs in the foreground.

## Rules from the user's global instructions

- Run work only on this machine. Never SSH to another host (`ags-RZ09` or any other).
- Never open a new PR. If you must, open it with `--draft`.
- Run `gh pr ready` only when the chain line above says `--ready` for that PR.
- Comments on landable PRs need no permission. A comment anywhere else needs the user's yes.
- At about 150k context, write your state to the ledger file and return. The parent starts a
  fresh worker from it.
- Write the final report in short, plain sentences (Simplified Technical English). For each PR:
  its end state, the commits you pushed (SHA), the CI run link, and the block, if any.
