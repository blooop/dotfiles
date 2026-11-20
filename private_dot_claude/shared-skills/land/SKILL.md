---
name: land
description: Land the open kinisi_ros PRs assigned to blooop — fix CI and conflicts, then auto-merge each approved one; one worker owns each stack, so a stack lands bottom-up, never piecemeal.
disable-model-invocation: true
argument-hint: "[PR numbers to narrow the list] [--ready]"
---

Arguments: "$ARGUMENTS"

**Land** means: a PR reaches its base with green CI, and nothing else breaks on the way. The
list is the open PRs on
<https://github.com/kinisi-robotics/kinisi_ros/pulls/assigned/blooop>; PR numbers in the
arguments narrow it. `--ready` lets you run `gh pr ready` on an approved draft in the list. Without
it, a draft is never marked ready (the user's global rule).

The repo is squash-only and deletes a merged head branch. Every run derives its state from
GitHub, so a second run is safe and picks up where the last one stopped.

The unit of work is the **chain**, not the PR. A chain is every open PR linked by
base → head, including PRs outside the list and PRs of other people. Past agents failed on
stacks because each one owned one PR and acted on a branch that another PR stood on. Here one
worker owns a whole chain, and nothing else touches it.

## 1. Map the chains

1. List: `gh pr list -R kinisi-robotics/kinisi_ros --assignee blooop --state open --limit 100
   --json number,author,isDraft,baseRefName,headRefName,headRefOid,reviewDecision,mergeStateStatus,autoMergeRequest,labels`.
2. For each PR, walk **down** (`gh pr list --head <baseRefName> --state open`) until the base
   is `main` or a branch with no open PR, and **up** (`gh pr list --base <headRefName> --state
   open`) until no PR is above. Read `.stack` (`gh api repos/kinisi-robotics/kinisi_ros/pulls/<n>
   --jq .stack`; null means not native-stacked). Join PRs that share a branch into one chain.
3. Record every PR's `headRefOid` in the run's ledger file (step 4). These SHAs are the
   recovery point when GitHub empties a PR.

Done when every listed PR sits in exactly one chain, ordered bottom → top, each with its
head SHA and stack number.

## 2. Sort each PR

Give each PR in a chain one **role**, from the first rule that matches:

- **foreign**: the author is not `blooop`. Never push to it, merge it or retarget it. A
  foreign PR below one of yours blocks everything above it.
- **held**: the body, labels, comments or review bodies hold a hold note ("do not merge",
  "hold off", "wait for"). Report it; do nothing to it.
- **draft**: a draft, and no `--ready`, or not approved. A draft runs no CI. Report it.
- **busy**: another live session works on it.
  `~/.claude/skills/usage-review/scripts/session_find.py --days 1 --top 5 <n>` shows each
  session's last activity; a session other than this one, active in the last 30 min, makes
  the PR busy. Report the session and its tab title (`herdr agent list`).
- **landable**: approved (`reviewDecision` `APPROVED`), and none of the above.
- **fixable**: none of the above, not approved. CI and conflicts get fixed; it does not merge.

A chain's **landing top** is the highest PR of the unbroken run of landable PRs that starts
at the bottom, where the bottom's base is `main`. A chain whose bottom is foreign, held, draft
or busy has no landing top. Every PR in it is at most fixable, and a busy or held chain gets no
worker at all.

Done when each PR has one role and each chain has its landing top or "none".

## 3. Plan each chain

Pick the **landing** for each chain with a landing top:

- **Single**: the landing top is the bottom. Get it green, then auto-merge it.
- **Mergetop**: two or more landable PRs. Get the landing top green against `main`, then
  merge it as one squash with the `stack-mergetop` procedure
  (`~/.claude/skills/stack-mergetop/SKILL.md`), and close the PRs below it. It is one CI run,
  not one per layer.
- **Bottom-up**: the `stack-automerge` procedure (`~/.claude/skills/stack-automerge/SKILL.md`),
  one layer per round. Pick this only when the user asks for one squash per PR.

The PRs above the landing top stay open. After the landing, each one must still be open, have
its commits, and have `main` as its base. Make that check part of the worker's done-criterion.

Show the plan in chat: one bullet per chain, with the PR links bottom → top, each PR's role,
the landing and the PRs that only get fixes. Go on without asking, because invoking `/land` is
the user's go-ahead for these merges.

## 4. Start the workers

Make the ledger file
`~/.claude/handoffs/<YYYY-MM-DD>-land.md`: the chains, the roles, the recorded SHAs, and one
`## <bottom PR>` section per chain for its worker's notes.

Start one background `general-purpose` subagent per chain that has a landable or fixable PR
and is not busy or held. Its prompt is the brief in [worker-brief.md](worker-brief.md), with
the chain, the roles, the landing and the ledger path filled in. Tell the user how long to
expect: one CI run is about 70 min, and a chain needs one to three runs.

While workers run, keep the heartbeat from the global CLAUDE.md going. A worker that returns
"waiting" has stalled: resume it with SendMessage and tell it to wait in the foreground.

Done when every worker has returned a final state.

## 5. Report

Re-map the chains (step 1). List every PR in the list as a ledger bullet: merged (with the
squash commit), closed as part of a mergetop (with the top PR), auto-merge on and waiting,
fixed and green but not approved, or blocked (and on what). Name each PR you did not touch and
its role. Write the same ledger to the ledger file.
