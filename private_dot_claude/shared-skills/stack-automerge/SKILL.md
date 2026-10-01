---
name: stack-automerge
description: Put auto-merge on the bottom PR of a native GitHub stack — take it out of the stack, turn on auto-merge, relink the rest on top. One layer per run.
disable-model-invocation: true
allowed-tools: Bash(git:*), Bash(gh:*)
argument-hint: "<PR number | PR URL | branch in the stack>"
---

Arguments: "$ARGUMENTS"

GitHub refuses auto-merge on a PR that is in a native stack (`Auto-merge is not supported for stacked pull requests`), and refuses to put a PR with auto-merge back into a stack. So the **bottom** PR — the one whose base is the default branch — leaves the stack, gets auto-merge, and the layers above are relinked on top of its branch. Only the bottom can auto-merge: an upper PR merges into its parent branch, not the default branch, and at once, because a feature branch has no rules to wait for.

After the bottom merges, GitHub usually retargets the next layer to the default branch and deletes the merged branch. It can fail (`automatic_base_change_failed` in the timeline): the next layer's base then stays on the merged branch, which is left undeleted, and the next run cleans that up first. Every run derives its state from GitHub, so a run is safe to repeat.

## 1. Map the chain

Resolve the argument to a PR. Walk **down** through base branches (`gh pr list --head <baseRefName> --state all`), stopping at the default branch, and **up** through head branches (`gh pr list --base <headRefName> --state open`) until the chain ends at both ends. Read the default branch, the allowed merge methods (`allow_squash_merge`, …), and the rules on the default branch (`gh api repos/{owner}/{repo}/rules/branches/<default>`). Read each PR's stack from `gh api repos/{owner}/{repo}/pulls/<n> --jq .stack` (`.number` is the stack number; null means not stacked). Use this field, not `gh stack` output, to tell whether a PR is stacked.

Done when you hold the ordered chain bottom → top, with each PR's number, head, base, head SHA, state, `autoMergeRequest`, `mergeStateStatus`, and stack number.

## 2. Clean up a merged bottom

Skip when the lowest **open** PR's base is the default branch.

Otherwise its base is the branch of a merged PR. Until you retarget it, the GitHub UI offers "Squash and merge" on it at once, with CI still running: its base is a feature branch, which has no rules. That merge goes into the dead branch, not the default branch. Tell the user not to click it.

Merge the default branch up into each layer. Do not rebase: a layer that already holds merge commits replays as the conflicts those merges resolved, and a rebase needs a force-push, which many repos forbid. A merge push costs no approval, even under `dismiss_stale_reviews_on_push`, because the review stays on commits that are still in the branch. CI runs again on each layer.

1. Unstack the open layers (`gh stack unstack <stack-number>`), when they are stacked. See the unstack note in step 3.
2. Retarget the lowest open PR: `gh pr edit <n> --base <default>`. **Warning:** retarget before you delete the merged branch. Deleting a PR's base branch closes the PR.
3. From the bottom layer up, merge the layer below into each layer: `git merge origin/<default>` on the lowest, then `git merge origin/<lower-branch>` on each one above. Use the checkout that already has the branch, or a scratch worktree (`git checkout -B <branch> origin/<branch>`). A branch checked out in another worktree cannot be checked out again, so work in that worktree for it.
4. Check each merge: `git diff --stat origin/<default>...HEAD` on the lowest layer lists only that PR's own files. Run the repo's gate and tests on it before the push.
5. Push each layer with a plain `git push origin <branch>`. On a conflict, run `git merge --abort`, and report the layer and the files that conflict. The layers below it still go on.
6. Delete the merged branch: `git push origin --delete <merged-branch>`, after `gh pr list --base <merged-branch> --state open` is empty.

When a git hook fails on the host, run the git steps in the project's container.

Done when the lowest open PR targets the default branch, every layer holds its parent's tip, and the merged branch is gone. Re-map the chain (step 1) and go on.

## 3. Put auto-merge on the bottom

Skip, and report "waiting", when the bottom already has `autoMergeRequest` set.

1. When the bottom is stacked, unstack its stack: `gh stack unstack <stack-number>`. Merged PRs stay in the old stack, and the command then warns that some PRs "have auto-merge enabled and remain stacked" even when none has. Judge by `.stack`: done when every open PR's `.stack` is null.
2. Turn on auto-merge: `gh pr merge <bottom> --auto --<method>`, squash when allowed. When the bottom is already mergeable (`CLEAN`), GitHub refuses `--auto`; merge it with `gh pr merge <bottom> --<method>` and go back to step 2.
3. Relink the layers above onto the bottom's branch: `gh stack link --base <bottom-head> <second-pr> <third-pr> ...`. Pass PR numbers: `link` pushes any argument that is a branch name, and a stale local branch would overwrite the remote. With only one layer above, there is nothing to stack: leave it, since its base is already the bottom's branch.

Done when `gh pr view <bottom> --json autoMergeRequest` is set, and the layers above form one stack based on the bottom's branch.

## 4. Report

List every PR in the chain: auto-merge on, merged, restacked, rebased, conflicts (`mergeStateStatus` `DIRTY`: its owner rebases it before it can merge), or waiting — with what still blocks the bottom (`gh pr checks`, review state). Tell the user to run `/stack-automerge` again once the bottom merges: that run retargets and rebases the next layer and puts auto-merge on it.
