#!/usr/bin/env bash
# Back-test the apply gate on past cloud_services incidents and on known-clean PRs.
# Run from a FULL clone of kinisi-robotics/cloud_services (not shallow).
# Every CAUSE must give a BLOCK. Of CLEAN, only #119 may (a true hit: #120 removed it).
set -uo pipefail
S=$(cd "$(dirname "$0")" && pwd)
git fetch -q origin main
CAUSE="205 113 428 533 541 644 676 733 783 822 928"   # diff scan BLOCKs these
PLAN_CAUSE="615 975"                                   # plan_risks BLOCKs these (PR plan comment)
CLEAN="119 54 97 185"                                  # spot set; the full set was 40 PRs, 1 BLOCK (#119)
landed() {  # print "<head> <base>" of the commit that landed PR $1 on main
  local c
  c=$(git log origin/main --format='%H %P' --grep "(#$1)\$" -n1)
  [ -z "$c" ] && c=$(git log origin/main --merges --format='%H %P' --grep "^Merge pull request #$1 " -n1)
  set -- $c; echo "$1 $2"
}
fail=0
for n in $CAUSE $CLEAN; do
  read -r h b <<<"$(landed "$n")"
  [ -z "$h" ] && { echo "#$n: no landed commit"; fail=1; continue; }
  python3 -I "$S/infra_risks.py" --base "$b" --head "$h" >/dev/null; rc=$?
  want=$([[ " $CAUSE 119 " == *" $n "* ]] && echo 2 || echo "<2")
  echo "#$n diff-scan exit $rc (want $want)"
  if [ "$want" = 2 ] && [ $rc -ne 2 ]; then fail=1; fi
  if [ "$want" != 2 ] && [ $rc -eq 2 ]; then fail=1; fi
done
tmp=$(mktemp -d)
for n in $PLAN_CAUSE; do
  gh api "repos/kinisi-robotics/cloud_services/issues/$n/comments" --paginate \
    --jq '[.[]|select(.body|startswith("<!-- terraform-plan -->"))]|last|.body' > "$tmp/$n.txt"
  python3 -I "$S/plan_risks.py" "$tmp/$n.txt" >/dev/null; rc=$?
  echo "#$n plan-scan exit $rc (want 2)"; [ $rc -ne 2 ] && fail=1
done
rm -rf "$tmp"
[ $fail -eq 0 ] && echo "BACKTEST PASS" || echo "BACKTEST FAIL"
exit $fail
