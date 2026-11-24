---
name: land
description: Land only the approved open kinisi_ros PRs assigned to blooop — fix CI and conflicts, then merge; one worker owns each stack, and every other PR is never changed.
disable-model-invocation: true
argument-hint: "[PR numbers to narrow the list] [--ready]"
---

Arguments: "$ARGUMENTS"

**Land** means: a PR reaches its base with green CI, and nothing else breaks on the way. The
**list** is the open PRs on
<https://github.com/kinisi-robotics/kinisi_ros/pulls/assigned/blooop>; PR numbers in the
arguments narrow it. Only a **landable** PR (on the list and approved, step 2) gets a push, a
merge, a retarget, a label, a comment or a close. Every other PR is **hands-off**: the skill
reads it, and changes nothing on it.

A draft counts as **ready** in two cases. A ready (non-draft) PR on the list stands above it in
the same chain: marking the top ready says the whole stack under it is ready. Or the arguments
hold `--ready`. Only a draft that counts as ready may get `gh pr ready`; every other draft
stays a draft (the user's global rule).

The repo is squash-only and deletes a merged head branch. Every run derives its state from
GitHub, so a second run is safe and picks up where the last one stopped.

The unit of work is the **chain**, not the PR. A chain is every open PR linked by
base → head. The map includes hands-off PRs only to show what stands below and above each
landable PR. Past agents failed on stacks because each one owned one PR and acted on a branch that
another PR stood on. Here one worker owns a whole chain, and nothing else touches it.

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

A PR is **landable** when it passes every test below. Otherwise it is hands-off, and its
**reason** is the first test it fails:

- **off-list**: it is on the list.
- **unapproved**: `reviewDecision` is `APPROVED`.
- **held**: no hold note ("do not merge", "hold off", "wait for") in the body, labels,
  comments or review bodies, and no open condition on the approval. Read the body of the
  latest approving review in full: a request to do something first ("before the merge",
  "please still", "once X is in the body") is a hold until the PR shows it done. Points
  the reviewer moves to "a follow-up" are not a hold.
- **draft**: it is not a draft, or it is a draft that counts as ready (see above).
- **busy**: no other live session works on it.
  `~/.claude/skills/usage-review/scripts/session_find.py --days 1 --top 5 --herdr <n>` lists
  the sessions that mention the PR, each with its herdr status and tab title. A session
  other than this one whose status is `working` makes the PR busy. `idle` and `done` do not,
  however recent the transcript: a session that ended its turn is not working. A
  dl-container agent has no session id in herdr; `herdr agent list` names it
  `kinisi-ros@<branch>`, so a `working` row for the PR's head branch also makes it busy.
  Report the session and its tab title.

A chain's **landing top** is the highest PR of the unbroken run of landable PRs that starts
at the bottom, where the bottom's base is `main`. A hands-off PR below a landable PR blocks
it: a chain whose bottom is hands-off has no landing top, and gets no worker.

Done when each PR is landable or hands-off with its reason, and each chain has its landing
top or "none".

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
When a hands-off PR stands above the landing top, the landing must not need any change to it.
When it does (a native stack that must be unstacked, a base that GitHub did not move), the
worker stops before the merge and reports it.

Show the plan in chat: one bullet per chain, with the PR links bottom → top, each PR's role,
the landing and the hands-off PRs with their reasons. Go on without asking, because invoking `/land` is
the user's go-ahead for these merges.

## 4. Start the workers

Make the ledger file
`~/.claude/handoffs/<YYYY-MM-DD>-land.md` (when it exists from an earlier run, use
`-land-2.md`, `-land-3.md` and so on; never write into another run's file): the chains, the roles, the recorded SHAs, and one
`## <bottom PR>` section per chain for its worker's notes.

Start one background `general-purpose` subagent per chain that has a landing top. Its prompt is the brief in [worker-brief.md](worker-brief.md), with
the chain, the roles, the landing and the ledger path filled in. Tell the user how long to
expect: one CI run is about 70 min, and a chain needs one to three runs.

While workers run, keep the heartbeat from the global CLAUDE.md going. A worker that returns
"waiting" has stalled: resume it with SendMessage and tell it to wait in the foreground.

Done when every worker has returned a final state.

## 5. Report

Re-map the chains (step 1). List every PR in the list as a ledger bullet: merged (with the
squash commit), closed as part of a mergetop (with the top PR), auto-merge on and waiting,
or blocked (and on what). Name each listed PR you did not touch, and its reason. Do not
list off-list PRs, except as the block of a landable PR. Write the same ledger to the ledger file.
