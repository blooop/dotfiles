#!/usr/bin/env bash
# Push evidence files (PNGs, and the CSVs behind them) to the repo's one orphan branch,
# `pr-evidence`, under <pr-branch>/, and print a SHA-pinned URL for each file.
# The branch never merges into anything, and no push to it is ever forced.
#
# usage: evidence_push.sh <pr-branch> <file>...
set -euo pipefail

[[ $# -ge 2 ]] || { echo "usage: $0 <pr-branch> <file>..." >&2; exit 2; }
pr_branch=$1; shift
for f in "$@"; do [[ -f $f ]] || { echo "not a file: $f" >&2; exit 2; }; done

branch=pr-evidence
slug=$(git remote get-url origin |
  sed -E 's#^(ssh://)?(git@github\.com[:/]|https://github\.com/)##; s#\.git$##')
wt=$(mktemp -d)
tmp_branch="$branch-tmp-$$"  # only exists while the branch is new on the remote
cleanup() {
  git worktree remove --force "$wt" >/dev/null 2>&1 || rm -rf "$wt"
  git branch -D "$tmp_branch" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for attempt in 1 2 3; do
  cleanup
  if git fetch -q origin "$branch" 2>/dev/null; then
    git worktree add -q --detach "$wt" FETCH_HEAD
  else
    git worktree add -q --orphan -b "$tmp_branch" "$wt"
  fi
  mkdir -p "$wt/$pr_branch"
  cp "$@" "$wt/$pr_branch/"
  git -C "$wt" add -- "$pr_branch"
  git -C "$wt" diff --cached --quiet || git -C "$wt" commit -q -m "evidence: $pr_branch"
  if git -C "$wt" push -q origin "HEAD:refs/heads/$branch"; then
    sha=$(git -C "$wt" rev-parse HEAD)
    for f in "$@"; do
      echo "https://github.com/$slug/blob/$sha/$pr_branch/$(basename "$f")?raw=true"
    done
    exit 0
  fi
  echo "push lost a race (attempt $attempt), retrying" >&2
done
echo "could not push to $branch after 3 attempts" >&2
exit 1
