#!/usr/bin/env bash
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: GPL-2.0-only
#
# The runner of ns3/patches/ (ADR-0002 decision 3, #378): runs each
# NS3-NNN/apply.sh on an ns-3 source tree, in ID order, and passes on the one
# line each prints:
#
#   NS3-NNN: not-affected | applied | already-fixed | refused: <why>
#
#   apply.sh [--dry-run] [--expect] <ns-3 source dir> [NS3-NNN ...]
#
# Every patch runs (or only the IDs named), even after a refusal. Exit 0 when
# none is refused, 1 when one is (or with --expect, when an outcome differs
# from its README's), 2 on a usage error. --dry-run decides and changes
# nothing. --expect compares each outcome with the row for the tree's release
# (<tree>/VERSION, e.g. 3.49) in the patch's README "Outcomes" table
# (`| ns-3.49 | applied | ... |`); a release with no row is reported and not
# compared.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dry=()
expect=0
while [[ $# -gt 0 && $1 == --* ]]; do
    case $1 in
    --dry-run) dry=(--dry-run) ;;
    --expect) expect=1 ;;
    *)
        echo "usage: $0 [--dry-run] [--expect] <ns-3 source dir> [NS3-NNN ...]" >&2
        exit 2
        ;;
    esac
    shift
done
if [[ $# -lt 1 || ! -d "$1" ]]; then
    echo "usage: $0 [--dry-run] [--expect] <ns-3 source dir> [NS3-NNN ...]" >&2
    exit 2
fi
src=$1
shift
if [[ $# -gt 0 ]]; then
    ids=("$@")
else
    ids=()
    for d in "$here"/NS3-*/; do
        ids+=("$(basename "$d")")
    done
fi
release=""
if [[ $expect -eq 1 ]]; then
    [[ -f "$src/VERSION" ]] || {
        echo "--expect: $src has no VERSION file to name its release" >&2
        exit 2
    }
    release=$(tr -d '[:space:]' <"$src/VERSION")
fi

status=0
for id in "${ids[@]}"; do
    if [[ ! -f "$here/$id/apply.sh" ]]; then
        echo "$id: no such patch ($here/$id/apply.sh)" >&2
        exit 2
    fi
    rc=0
    line=$(bash "$here/$id/apply.sh" "${dry[@]}" "$src") || rc=$?
    echo "$line"
    outcome=$(sed -nE "s/^$id: (not-affected|applied|already-fixed|refused):.*/\1/p" <<<"$line" | head -1)
    if [[ -z $outcome || ($rc -ne 0 && $outcome != refused) || ($rc -eq 0 && $outcome == refused) ]]; then
        echo "$id: apply.sh broke the convention (exit $rc, line above)" >&2
        status=1
        continue
    fi
    [[ $outcome == refused ]] && status=1
    if [[ $expect -eq 1 ]]; then
        want=""
        if [[ -f "$here/$id/README.md" ]]; then
            want=$(sed -nE "s/^\| *ns-${release//./\\.} *\| *(not-affected|applied|already-fixed|refused) *\|.*/\1/p" \
                "$here/$id/README.md" | head -1)
        fi
        if [[ -z $want ]]; then
            echo "$id: its README states no outcome for ns-$release: not compared"
        elif [[ $want != "$outcome" ]]; then
            echo "$id: expected $want on ns-$release (its README), got $outcome" >&2
            status=1
        fi
    fi
done
exit $status
