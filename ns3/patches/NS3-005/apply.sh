#!/usr/bin/env bash
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: GPL-2.0-only
#
# NS3-005 (swarm-routing/sim-tools#374): apply the AODV route-lifetime
# saturation patch to an ns-3 source tree only when that tree has the bug.
#
#   apply.sh [--dry-run] <ns-3 source dir>
#
# The decision comes from the source, never from the version: no ns-3 release
# carries a fix yet, so no version list can say where it starts, and a tree
# built from master or already patched carries the same version number as a
# stock one. In order:
#
#   no src/aodv/model/aodv-rtable.cc     no AODV module: skip
#   the patch applies in reverse         already patched: skip
#   no unsaturated "lifetime + Now()"    the bug is not there (upstream fixed
#     in RoutingTableEntry                 or rewrote it): skip
#   the patch applies                    the bug is there: apply
#   none of these                        the bug is there but the patch does
#                                          not fit (ns-3.43 and older): fail
#
# One "NS3-005: ..." line says which. Exit 0 on apply or skip, 1 on failure,
# 2 on a usage error. --dry-run decides and logs, and changes nothing.
set -euo pipefail

dry_run=0
if [[ "${1:-}" == "--dry-run" ]]; then
    dry_run=1
    shift
fi
if [[ $# -ne 1 || ! -d "$1" ]]; then
    echo "usage: $0 [--dry-run] <ns-3 source dir>" >&2
    exit 2
fi
src=$(cd "$1" && pwd)
patch="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/ns3-005-aodv-lifetime-saturate.patch"
rtable_cc="$src/src/aodv/model/aodv-rtable.cc"
rtable_h="$src/src/aodv/model/aodv-rtable.h"

# git apply on the tree alone: never the repository the tree may sit in
git_apply() {
    git -C "$src" -c core.autocrlf=false --work-tree=. --git-dir=.git-ns3-005-none apply "$@" "$patch"
}

if [[ ! -f "$rtable_cc" || ! -f "$rtable_h" ]]; then
    echo "NS3-005: $src has no AODV routing table (src/aodv/model/aodv-rtable.{cc,h}): skipped"
    exit 0
fi
if git_apply --check --reverse 2>/dev/null; then
    echo "NS3-005: $src already has the lifetime saturation patch: skipped"
    exit 0
fi
# the bug's signature: RoutingTableEntry adds Now() to a lifetime unchecked
if ! grep -Eq 'm_lifeTime *\( *lifetime *\+ *Simulator::Now *\(' "$rtable_cc" &&
    ! grep -Eq 'm_lifeTime *= *lt *\+ *Simulator::Now *\(' "$rtable_h"; then
    echo "NS3-005: $src adds no unchecked Now() to an AODV route lifetime, so no bug: skipped"
    exit 0
fi
if git_apply --check 2>/dev/null; then
    if [[ $dry_run -eq 1 ]]; then
        echo "NS3-005: $src has the bug: the patch would apply (dry run, nothing changed)"
        exit 0
    fi
    git_apply
    echo "NS3-005: $src has the bug: $(basename "$patch") applied"
    exit 0
fi
echo "NS3-005: $src has the bug (unchecked lifetime + Now() in aodv-rtable) but $(basename "$patch") does not apply: refresh the patch for this tree (swarm-routing/sim-tools docs/ns3-bugs.md, NS3-005)" >&2
exit 1
