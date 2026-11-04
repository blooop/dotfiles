#!/bin/sh
# One line for herdr's tab_bar_right: CPU %, RAM used/total, root disk used/total,
# and IO pressure.
# herdr strips escape codes from this output, so colour comes from emoji instead:
# a dot before each figure, green below 75%, yellow from 75%, red from 90%.
# dot PCT [YELLOW RED]: thresholds default to 75 and 90.
dot() { if [ "$1" -ge "${3:-90}" ]; then echo 🔴; elif [ "$1" -ge "${2:-75}" ]; then echo 🟡; else echo 🟢; fi; }

set -- $(head -1 /proc/stat); t1=$(($2+$3+$4+$5+$6+$7+$8)); i1=$(($5+$6))
sleep 1
set -- $(head -1 /proc/stat); t2=$(($2+$3+$4+$5+$6+$7+$8)); i2=$(($5+$6))
cpu=$(( 100 * ( (t2-t1) - (i2-i1) ) / (t2-t1) ))

set -- $(awk '/^MemTotal/{t=$2} /^MemAvailable/{a=$2} END{printf "%d %.1f/%.0fG", 100*(t-a)/t, (t-a)/1048576, t/1048576}' /proc/meminfo)
mem_pct=$1 mem=$2

# df's own Use%: used / (used + available), so root's reserved blocks count as full.
set -- $(df -Pk / | awk 'NR==2{printf "%d %.1f/%.1fT", 100*$3/($3+$4)+0.999, $3/1073741824, $2/1073741824}')
disk_pct=$1 disk=$2

# IO pressure: the % of the last 10 s in which some task waited on the disk.
# The cpu figure above counts IO wait as idle, so a disk hang leaves it low;
# this figure catches it. 20% is already felt, 50% hangs container starts.
io=$(awk '/^some/{split($2,a,"="); printf "%d", a[2]}' /proc/pressure/io 2>/dev/null)
io=${io:-0}

echo "cpu$(dot "$cpu")${cpu}% mem$(dot "$mem_pct")${mem} dsk$(dot "$disk_pct")${disk} io$(dot "$io" 20 50)${io}%"
