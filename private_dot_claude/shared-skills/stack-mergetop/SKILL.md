---
name: stack-mergetop
description: Merge a whole PR stack as one, now, when its top PR is green — point at any PR in the stack. The lower PRs need not finish CI.
disable-model-invocation: true
allowed-tools: Bash(git:*), Bash(gh:*)
argument-hint: "<PR number | PR URL | branch in the stack>"
---

Arguments: "$ARGUMENTS"

The top PR of a stack holds the commits of every PR below it, so a green run on the top tests the whole stack. GitHub does not see it that way. It checks the rules of the default branch on each PR alone:

- A merge-async call on the top of a native stack only queues. It waits until every PR in the stack passes the rules.
- `bypass_rules=true` is refused on every PR except the bottom-most one ("Rules can only be bypassed when merging the bottom-most unmerged pull request in the stack").
- When the bottom merges alone, GitHub can force-push the upper branches to the merge commit and close them as empty. Their commits then leave the branch.

So this skill takes the top out of the stack, points it at the default branch, merges it there, and closes the PRs below it. Invoking the skill is the user's go-ahead for that merge.

## 1. Map the chain

Resolve the argument to a PR. Walk **down** through base branches (`gh pr list --head <baseRefName> --state all`) until you reach the default branch. Walk **up** through head branches (`gh pr list --base <headRefName> --state open`) until no open PR is above. The **top** is the highest open PR. When more than one open PR sits on the same branch, the chain forks: stop and ask which branch is the top.

For each PR, read `gh api repos/{owner}/{repo}/pulls/<n>`: `.stack` (`.number` is the stack number, null means not stacked), `.head.sha`, `.base.ref`, `.draft`, `.auto_merge`, `.mergeable_state`. Read `gh pr view <n> --json reviewDecision`. Read the repo's allowed merge methods (`allow_squash_merge`, `allow_merge_commit`, `allow_rebase_merge`), and the rules on the default branch (`gh api repos/{owner}/{repo}/rules/branches/<default>`).

Done when you hold the chain bottom → top, with every field above for each PR.

## 2. Check the top covers the stack

Stop and report what is missing, and merge nothing, unless every item is true:

- **Green.** Every required status check of the default branch passed on the top's current head SHA (`gh api repos/{owner}/{repo}/commits/<top-sha>/check-runs` and `/status`). A run on an older SHA does not count.
- **Covers.** Each lower open PR's head is an ancestor of the top's head: `gh api repos/{owner}/{repo}/compare/<lower-sha>...<top-sha> --jq .status` is `ahead` or `identical`. A push to a lower PR after the top's run fails this check.
- **Approved.** Every PR in the chain has `reviewDecision` `APPROVED`. The top's approval does not cover the review of the code in the lower PRs.
- **Ready.** No PR is a draft, and the top is not `dirty`.

When the top is still running, report "waiting" with the checks that are pending. Do not poll.

## 3. Merge the top

1. Turn off auto-merge on every PR in the chain that has it: `gh pr merge <n> --disable-auto`. GitHub refuses a direct merge on a PR with auto-merge set.
2. Unstack each native stack in the chain: `gh stack unstack <stack-number>`. The command has no `-R`, so run it inside a checkout of the repo. Done when `.stack` is null on every open PR.
3. Retarget the top: `gh pr edit <top> --base <default>`. **Warning:** merge only the top. When a lower PR merges first, GitHub can empty and close the top.
4. Merge the top: `gh api -X PUT repos/{owner}/{repo}/pulls/<top>/merge-async -f merge_method=<method> -f sha=<top-sha>`. Use squash when the repo allows it. Add `-F bypass_rules=true` only when the plain call is refused because of the rules and the ruleset shows `current_user_can_bypass`. The `sha` makes GitHub refuse the merge when the head moved since step 2.
5. Wait for the merge: read `gh api repos/{owner}/{repo}/pulls/<top> --jq .merged` every 20 s, for up to 3 min.

Done when `.merged` is true on the top and its merge commit is on the default branch.

## 4. Close the lower PRs

A merge commit keeps the lower heads as ancestors, so GitHub can mark the lower PRs merged by itself. Read each one's state first. Close each lower PR that is still open, with a comment that names where its code went:

`gh pr close <n> -c "Merged into <default> as part of #<top> (<merge-sha>), which held this PR's commits."`

Leave the branches. The user deletes them.

## 5. Report

List every PR in the chain with its link and its end state: merged, closed as part of the top, or not merged and why. Give the merge commit. Say which lower PRs never finished their own CI, so the user knows which checks the default branch did not get.
