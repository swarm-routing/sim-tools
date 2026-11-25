#!/usr/bin/env bash
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: GPL-2.0-only
#
# NS3-001 (swarm-routing/ns3-tools#238): apply nsnam/ns-3-dev!3101 (the
# upstream fix, at its head d3fbcacb) to an ns-3 source tree only when that
# tree has the bug. The rule is the vcpkg ns3 port's (swarm-routing/vcpkg-registry
# ports/ns3/portfile.cmake, NS3-001 block), held here (ADR-0002, #378).
#
#   apply.sh [--dry-run] <ns-3 source dir>
#
# The decision comes from the source, never from the version: no ns-3 release
# carries the fix yet, so no version list can say where it starts. In order:
#
#   no SendIcmpNoRoute in              the code predates the bug (ns-3.48 and
#     ipv4-l3-protocol.cc                earlier): not-affected
#   the patch applies in reverse       !3101 is in the tree: already-fixed
#   the patch applies                  the bug is there (ns-3.49): applied
#   none of these                      upstream changed that code: refused
#
# One "NS3-001: <outcome>: ..." line on stdout says which, the outcome one of
# not-affected, applied, already-fixed, refused. Exit 0 on the first three,
# 1 on refused, 2 on a usage error. --dry-run decides and logs, and changes
# nothing.
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
patch="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/ns3-001-icmp-no-route-mr3101.patch"
l3="$src/src/internet/model/ipv4-l3-protocol.cc"

# git apply on the tree alone: never the repository the tree may sit in
git_apply() {
    git -C "$src" -c core.autocrlf=false --work-tree=. --git-dir=.git-ns3-001-none apply "$@" "$patch"
}

if [[ ! -f "$l3" ]] || ! grep -q 'SendIcmpNoRoute' "$l3"; then
    echo "NS3-001: not-affected: $src has no Ipv4L3Protocol::SendIcmpNoRoute (ns-3.48 and earlier)"
    exit 0
fi
if git_apply --check --reverse 2>/dev/null; then
    echo "NS3-001: already-fixed: $src has nsnam/ns-3-dev!3101"
    exit 0
fi
if git_apply --check 2>/dev/null; then
    if [[ $dry_run -eq 1 ]]; then
        echo "NS3-001: applied: $src has the bug; dry run, nothing changed"
        exit 0
    fi
    git_apply
    echo "NS3-001: applied: $src has the bug; $(basename "$patch") (nsnam/ns-3-dev!3101) applied"
    exit 0
fi
echo "NS3-001: refused: $src changed SendIcmpNoRoute and neither has nsnam/ns-3-dev!3101 nor takes it: re-check NS3-001 (swarm-routing/sim-tools docs/ns3-bugs.md) and refresh or retire ns3/patches/NS3-001/"
exit 1
