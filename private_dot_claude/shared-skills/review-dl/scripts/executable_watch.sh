#!/usr/bin/env bash
# review-dl watch mode: keep a query's PRs reviewed, at most MAX reviewers at once.
#
#   watch.sh DIR init --repo R --since YYYY-MM-DD [--author U] [--assignee U] [--max N] [--scratch PATH]
#   watch.sh DIR next          print "START <n>\t<brief>\t<title>" per PR to start now, then
#                              "WAITING <k> running=<r>", or "NONE running=<r>"; marks started PRs
#   watch.sh DIR peek          exit 0 when `next` would start a PR (no side effects)
#   watch.sh DIR wait          block until `peek` is true (for run_in_background; 2 h cap, exit 124)
#   watch.sh DIR done <n> "<REVIEW line>"   free n's slot and record its verdict
#   watch.sh DIR fail <n>      the reviewer died: delete its workspace and put n back in the queue
#   watch.sh DIR summary       verdict counts and one line per recorded review
#
# The brief is cut from ../SKILL.md ("## The brief"), so the watch never drifts from it.
# A PR qualifies when it is open, not a draft, not approved, not from a fork, and made on or
# after --since; it matches --author or --assignee (either, when both are given).
set -euo pipefail

HERE=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
SKILL="$HERE/../SKILL.md"
D=${1:?state dir}; shift
CMD=${1:?command}; shift || true
mkdir -p "$D"; touch "$D/seen.txt" "$D/running.txt" "$D/results.tsv"

cfg() { # shellcheck disable=SC1091
  [ -f "$D/config.env" ] || { echo "run init first" >&2; exit 2; }
  . "$D/config.env"
}

candidates() {
  local who fields='number,isDraft,reviewDecision,isCrossRepository,createdAt'
  local q='.[]|select((.isDraft|not) and .reviewDecision!="APPROVED" and (.isCrossRepository|not) and .createdAt>=$since)|.number'
  {
    for who in ${AUTHOR:+"--author=$AUTHOR"} ${ASSIGNEE:+"--assignee=$ASSIGNEE"}; do
      gh pr list -R "$REPO" "$who" --state open --limit 200 --json "$fields" \
        | jq -r --arg since "$SINCE" "$q"
    done
  } | sort -un
}

new_prs() { comm -23 <(candidates | grep . | sort) <(sort -u "$D/seen.txt"); }
running() { grep -c . "$D/running.txt" || true; }

brief() { # n title branch author
  awk '/^## The brief/{f=1;next} f&&/^```/{if(o)exit;o=1;next} o' "$SKILL" > "$D/brief.raw"
  python3 - "$D/brief.raw" "$D/brief-$1.txt" "$REPO" "$1" "$2" "$3" "$4" "$SCRATCH" <<'PY'
import sys
src, out, repo, n, title, branch, author, scratch = sys.argv[1:]
s = open(src).read()
for k, v in {"<PR URL>": f"https://github.com/{repo}/pull/{n}", "<title>": title,
             "<branch>": branch, "<author>": author, "<owner/repo>": repo,
             "<scratchpad>": scratch, "<number>": n}.items():
    s = s.replace(k, v)
s += "\nWatch mode: return only the REVIEW, TESTS and CLEANUP lines.\n"
open(out, "w").write(s)
PY
  echo "$D/brief-$1.txt"
}

case "$CMD" in
init)
  REPO= SINCE= AUTHOR= ASSIGNEE= MAX=3 SCRATCH=$D/scratch
  while [ $# -gt 0 ]; do case $1 in
    --repo) REPO=$2;; --since) SINCE=$2;; --author) AUTHOR=$2;; --assignee) ASSIGNEE=$2;;
    --max) MAX=$2;; --scratch) SCRATCH=$2;; *) echo "bad arg $1" >&2; exit 2;; esac; shift 2; done
  [ -n "$REPO" ] && [ -n "$SINCE" ] && [ -n "$AUTHOR$ASSIGNEE" ] || { echo "need --repo --since and --author/--assignee" >&2; exit 2; }
  printf 'REPO=%q\nSINCE=%q\nAUTHOR=%q\nASSIGNEE=%q\nMAX=%q\nSCRATCH=%q\n' \
    "$REPO" "$SINCE" "$AUTHOR" "$ASSIGNEE" "$MAX" "$SCRATCH" > "$D/config.env"
  echo "config written: $D/config.env";;
peek)
  cfg; [ "$(running)" -lt "$MAX" ] && [ -n "$(new_prs)" ];;
wait)
  exec ~/.claude/scripts/run-wait --timeout 7200 --every 600 -- "$0" "$D" peek;;
next)
  cfg; new=$(new_prs); r=$(running)
  [ -z "$new" ] && { echo "NONE running=$r"; exit 0; }
  slots=$((MAX - r)); waiting=0
  for n in $new; do
    if [ "$slots" -le 0 ]; then waiting=$((waiting + 1)); continue; fi
    if [ -n "$(~/.claude/hooks/resource-check.sh 2>/dev/null)" ]; then
      echo "HELD resource-check"; slots=0; waiting=$((waiting + 1)); continue; fi
    j=$(gh pr view "$n" -R "$REPO" --json title,headRefName,author)
    f=$(brief "$n" "$(jq -r .title <<<"$j")" "$(jq -r .headRefName <<<"$j")" "$(jq -r .author.login <<<"$j")")
    echo "$n" >> "$D/seen.txt"; echo "$n" >> "$D/running.txt"
    printf 'START %s\t%s\t%s\n' "$n" "$f" "$(jq -r .title <<<"$j")"
    slots=$((slots - 1))
  done
  echo "WAITING $waiting running=$(running)";;
done)
  n=${1:?n}; line=${2:-}
  grep -vx "$n" "$D/running.txt" > "$D/r.tmp" || true; mv "$D/r.tmp" "$D/running.txt"
  [ -n "$line" ] && printf '%s\t%s\t%s\n' "$(date -Is)" "$n" "$line" >> "$D/results.tsv"
  true;;
fail)
  cfg; n=${1:?n}
  branch=$(gh pr view "$n" -R "$REPO" --json headRefName --jq .headRefName)
  # dl names a workspace <repo>-<branch, cut short>-<4 chars>; match the cut name as a prefix.
  slug=$(dl --ls 2>/dev/null | awk -v b="${branch//\//-}" '{s=$1; sub(/^[a-z0-9]+-[a-z0-9]+-/,"",s); sub(/-[a-z0-9]{4}$/,"",s); if (length(s) > 8 && index(b, s) == 1) {print $1; exit}}')
  if [ -n "$slug" ]; then
    c=$(docker ps --format '{{.Names}}' | grep -m1 "^kinisi_jazzy_$slug$" || true)
    [ -n "$c" ] && docker exec -u kinisi "$c" bash -lc 'cd "${KINISI_ROOT:-$HOME/kinisi}" 2>/dev/null && timeout 120 bin/bm shutdown' >/dev/null 2>&1 || true
    clone=$(dl --ls | awk -v s="$slug" '$1 == s {print $3}')
    timeout 300 dl rm "$REPO@$branch" >/dev/null 2>&1 || timeout 300 dl rm --force "$REPO@$branch" >/dev/null 2>&1 || true
    docker ps -a --format '{{.Names}}' | grep -- "$slug" | xargs -r docker rm -f >/dev/null
    [ -n "$clone" ] && rm -rf "$clone"
    echo "workspace $slug: dl=$(dl --ls 2>/dev/null | grep -c -- "$slug" || true) docker=$(docker ps -a --format '{{.Names}}' | grep -c -- "$slug" || true)"
  else echo "no workspace for $branch"; fi
  rm -rf "$SCRATCH/pr-$n"
  grep -vx "$n" "$D/running.txt" > "$D/r.tmp" || true; mv "$D/r.tmp" "$D/running.txt"
  grep -vx "$n" "$D/seen.txt" > "$D/s.tmp" || true; mv "$D/s.tmp" "$D/seen.txt"
  echo "requeued $n";;
summary)
  for v in blocking comments clean; do
    printf '%s %s\n' "$v" "$(cut -f3 "$D/results.tsv" | grep -c "· $v" || true)"; done
  echo "total $(grep -c . "$D/results.tsv" || true)"
  cut -f2,3 "$D/results.tsv";;
*) sed -n '2,15p' "$0"; exit 2;;
esac
