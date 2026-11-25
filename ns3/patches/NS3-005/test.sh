#!/usr/bin/env bash
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: GPL-2.0-only
#
# NS3-005 (swarm-routing/sim-tools#374): proves the patch and its apply script
# on a built, sanitized ns-3 tree (ns3-dev:latest-sanitized, ns-3 at /opt/ns-3).
# It changes that tree: run it in a throwaway container.
#
#   bash ns3/patches/NS3-005/test.sh [/opt/ns-3]
#
# 1. apply.sh decides from the source: on copies of the tree's AODV routing
#    table it prints applied on the stock source, already-fixed on a patched
#    one and on one fixed another way, not-affected with no AODV, and
#    refused (exit 1) on a source with the bug that the patch does not fit.
# 2. The reproducer (aodv-lifetime-overflow.cc) aborts under UBSan with the
#    signed overflow on the stock tree.
# 3. apply.sh patches the tree; the reproducer then runs clean, and the AODV
#    suite passes.
# 4. apply.sh run again on the patched tree prints already-fixed.
set -euo pipefail

ns3=${1:-/opt/ns-3}
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
apply="$here/apply.sh"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
fail() {
    echo "FAIL: $*" >&2
    exit 1
}

# copies of the tree's AODV routing table, as a minimal source tree
rtable() {
    mkdir -p "$work/$1/src/aodv/model"
    cp "$ns3/src/aodv/model/aodv-rtable.cc" "$ns3/src/aodv/model/aodv-rtable.h" "$work/$1/src/aodv/model/"
}

echo "== 1. apply.sh decides from the source"
grep -q 'm_lifeTime(lifetime + Simulator::Now())' "$ns3/src/aodv/model/aodv-rtable.cc" ||
    fail "$ns3 is not a stock tree with the bug (start from an unpatched image)"
rtable stock
out=$("$apply" "$work/stock") || fail "stock: exit $?"
[[ $out == "NS3-005: applied: "* ]] || fail "stock: $out"
out=$("$apply" "$work/stock") || fail "patched: exit $?"
[[ $out == "NS3-005: already-fixed: "* ]] || fail "patched: $out"
rtable other-fix
# an upstream fix written differently from ours: no unchecked add, no patch fit
sed -i 's/m_lifeTime(lifetime + Simulator::Now())/m_lifeTime(SaturatedLifetime(lifetime))/' \
    "$work/other-fix/src/aodv/model/aodv-rtable.cc"
sed -i 's/m_lifeTime = lt + Simulator::Now();/m_lifeTime = SaturatedLifetime(lt);/' \
    "$work/other-fix/src/aodv/model/aodv-rtable.h"
out=$("$apply" "$work/other-fix") || fail "other-fix: exit $?"
[[ $out == "NS3-005: already-fixed: "*"fixed or rewritten"* ]] || fail "other-fix: $out"
mkdir -p "$work/no-aodv"
out=$("$apply" "$work/no-aodv") || fail "no-aodv: exit $?"
[[ $out == "NS3-005: not-affected: "* ]] || fail "no-aodv: $out"
rtable drifted
# the bug still there, the patch's context gone (as on ns-3.43 and older)
sed -i 's/m_hops(hops),/m_hops(hops), \/\/ drifted/' "$work/drifted/src/aodv/model/aodv-rtable.cc"
if out=$("$apply" "$work/drifted" 2>&1); then
    fail "drifted: exit 0: $out"
fi
[[ $out == "NS3-005: refused: "*"does not apply"* ]] || fail "drifted: $out"
echo "ok"

repro() {
    (cd "$ns3" && ./ns3 build scratch/aodv-lifetime-overflow >"$work/build.log" 2>&1) ||
        { tail -40 "$work/build.log"; fail "build"; }
    (cd "$ns3" && ./ns3 run --no-build scratch/aodv-lifetime-overflow 2>&1)
}

echo "== 2. the reproducer fails on the stock tree"
cp "$here/aodv-lifetime-overflow.cc" "$ns3/scratch/"
if out=$(repro); then
    echo "$out"
    fail "the reproducer passed on the stock tree: is it a sanitized build?"
fi
echo "$out" | grep -F 'runtime error: signed integer overflow: 9223372036854775807 +' ||
    { echo "$out"; fail "stock: no UBSan overflow report"; }
echo "ok"

echo "== 3. apply.sh patches the tree; the reproducer and the AODV suite pass"
"$apply" "$ns3"
out=$(repro) || { echo "$out"; fail "the reproducer failed on the patched tree"; }
echo "$out" | grep -F 'NS3-005 not-reproduced' || { echo "$out"; fail "patched: no verdict line"; }
echo "$out" | grep -E '^10\.0\.0\.255 .* UP ' || { echo "$out"; fail "patched: no live broadcast route"; }
# The AODV suites: an ns3-dev image's tree builds the tests of the modules its
# last configure named only, so configure it again with the image's own flags
# (.swarm-configure.env, as ns3-build-contrib does: no stock library rebuilds
# but AODV's) and AODV's tests. Another tree is taken as configured.
if [[ -f "$ns3/.swarm-configure.env" ]]; then
    # shellcheck source=/dev/null
    . "$ns3/.swarm-configure.env"
    # shellcheck disable=SC2086  # NS3_PROFILE_FLAGS word-splits on purpose
    (cd "$ns3" && ./ns3 configure -G Ninja $NS3_PROFILE_FLAGS --enable-examples --enable-tests \
        --disable-werror --filter-module-examples-and-tests=aodv --enable-modules="$NS3_MODULES" \
        >"$work/configure.log" 2>&1) || { tail -40 "$work/configure.log"; fail "configure"; }
fi
(cd "$ns3" && ./ns3 build >"$work/build.log" 2>&1) || { tail -40 "$work/build.log"; fail "build"; }
for suite in routing-aodv aodv-routing-id-cache routing-aodv-loopback routing-aodv-regression; do
    (cd "$ns3" && ./test.py --no-build --verbose-failed -s "$suite") || fail "AODV suite $suite"
done
echo "ok"

echo "== 4. apply.sh prints already-fixed on the patched tree"
out=$("$apply" "$ns3") || fail "re-apply: exit $?"
[[ $out == "NS3-005: already-fixed: "* ]] || fail "re-apply: $out"
echo "ok"
echo "NS3-005: all checks passed"
