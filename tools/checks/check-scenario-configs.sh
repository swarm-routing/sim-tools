#!/usr/bin/env bash
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
#
# check-scenario-configs.sh NS3DIR
#
# The family catalogue (scenarios/, #55) against the harness it
# describes, on a built ns-3 tree: every cell's routing-compare line
# (check-scenarios.py --commands) runs once, and check-scenarios.py --configs
# compares the ##CONFIG## line each prints with the values the catalogue
# resolves for that cell. A preset that drifts from routing-compare's
# --scenario fails here, before a benchmarks manifest built from the catalogue
# disagrees with its cells' ##CONFIG## (swarm-routing/benchmarks validate_run.py).
set -euo pipefail
ns3=$1
checks="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp=$(cd "$(mktemp -d)" && pwd)  # absolute: the runs below cd into NS3DIR
trap 'rm -rf "$tmp"' EXIT

python3 -I "$checks/check-scenarios.py" --commands > "$tmp/commands.tsv"
[ -s "$tmp/commands.tsv" ] || { echo "FAIL: the catalogue lists no cell" >&2; exit 1; }
n=0
while IFS=$'\t' read -r cell args; do
    (cd "$ns3" && ./ns3 run --no-build "routing-compare $args") > "$tmp/$cell.txt" 2>> "$tmp/stderr.log" \
        || { echo "FAIL: $cell: routing-compare $args" >&2; tail -20 "$tmp/stderr.log" >&2; exit 1; }
    n=$((n + 1))
done < "$tmp/commands.tsv"
echo "ran $n cell(s)"
python3 -I "$checks/check-scenarios.py" --configs "$tmp"
