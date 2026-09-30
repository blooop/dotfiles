#!/usr/bin/env bash
# Print every loose end in the given git repos (default: the current one).
# Read-only: it changes nothing. A repo with no loose ends prints one "clean" line.
# Usage: sweep.sh [repo-path ...]
set -u

sweep_repo() {
  local repo=$1 top gitdir found=0
  if ! top=$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null); then
    echo "== $repo: not a git repo (work here is not durable)"
    return
  fi
  gitdir=$(git -C "$top" rev-parse --absolute-git-dir)
  echo "== $top"

  say() { found=1; echo "  $*"; }

  # In-progress operations: porcelain status does not report these.
  for state in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
    [ -e "$gitdir/$state" ] && say "in-progress: $state"
  done

  local head
  head=$(git -C "$top" status --porcelain=v2 --branch | sed -n 's/^# branch.head //p')
  [ "$head" = "(detached)" ] && say "detached HEAD at $(git -C "$top" rev-parse --short HEAD)"

  local dirty
  dirty=$(git -C "$top" status --porcelain --untracked-files=all)
  if [ -n "$dirty" ]; then
    say "uncommitted ($(printf '%s\n' "$dirty" | wc -l) paths):"
    printf '%s\n' "$dirty" | head -20 | sed 's/^/      /'
  fi

  local stashes
  stashes=$(git -C "$top" stash list)
  [ -n "$stashes" ] && { say "stashes:"; printf '%s\n' "$stashes" | sed 's/^/      /'; }

  # Every local branch: no upstream, ahead of upstream, or upstream gone.
  local default
  default=$(git -C "$top" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')
  while read -r br up track; do
    if [ -z "$up" ]; then
      # A branch with no upstream is a loose end only if it holds commits no remote has.
      local n
      n=$(git -C "$top" rev-list --count "$br" --not --remotes 2>/dev/null || echo 0)
      [ "$n" -gt 0 ] && say "branch $br: no upstream, $n commit(s) on no remote"
    else
      case "$track" in
        *gone*) say "branch $br: upstream $up is gone (merged or deleted?)" ;;
        *ahead*) say "branch $br: $track vs $up (unpushed)" ;;
      esac
    fi
  done < <(git -C "$top" for-each-ref --format='%(refname:short) %(upstream:short) %(upstream:track)' refs/heads/)
  [ -n "$default" ] && [ -n "$(git -C "$top" rev-list "origin/$default..$default" 2>/dev/null)" ] \
    && say "default branch $default is ahead of origin/$default"

  # Linked worktrees, and whether each holds work.
  local wt
  while read -r wt; do
    [ "$wt" = "$top" ] && continue
    local st
    st=$(git -C "$wt" status --porcelain 2>/dev/null | wc -l)
    say "worktree $wt ($(git -C "$wt" branch --show-current 2>/dev/null || echo '?'), $st uncommitted)"
  done < <(git -C "$top" worktree list --porcelain | sed -n 's/^worktree //p')
  git -C "$top" worktree list --porcelain | grep -q '^prunable' && say "prunable worktree entries (git worktree prune)"

  # Open PRs from this repo's branches, with CI state.
  if command -v gh >/dev/null && git -C "$top" remote get-url origin 2>/dev/null | grep -q github.com; then
    local prs
    prs=$(cd "$top" && gh pr list --author @me --state open \
      --json number,headRefName,url,statusCheckRollup,isDraft \
      --jq '.[] | "#\(.number) \(.headRefName) \(if .isDraft then "draft " else "" end)ci=\([.statusCheckRollup[]? | (.conclusion // .status)] | unique | join(",")) \(.url)"' 2>/dev/null)
    [ -n "$prs" ] && { say "open PRs by you:"; printf '%s\n' "$prs" | sed 's/^/      /'; }
  fi

  [ "$found" = 0 ] && echo "  clean"
}

if [ $# -eq 0 ]; then set -- .; fi
for r in "$@"; do sweep_repo "$r"; done

# Host-wide leftovers. The agent decides which of these it started.
echo "== host"
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  docker ps --format '{{.Names}} ({{.Image}}, {{.Status}})' | sed 's/^/  container /'
fi
# ss names the owning process only for this user's processes, so system daemons drop out.
command -v ss >/dev/null && ss -ltnpH 2>/dev/null | awk '$6 ~ /users:/ {print "  listening " $4 " " $6}' | head -20
