#!/usr/bin/env bash
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: GPL-2.0-only
#
# NS3-001 (swarm-routing/ns3-tools#238): proves nsnam/ns-3-dev!3101's patch and
# its apply script on a built ns-3.49 tree (ns3-dev:latest-sanitized, ns-3 at
# /opt/ns-3). It changes that tree: run it in a throwaway container.
#
#   bash ns3/patches/NS3-001/test.sh [/opt/ns-3]
#
# 1. apply.sh decides from the source: on copies of the two files the patch
#    touches it prints applied on the stock source, already-fixed on a
#    patched one (as on a release with !3101 merged), not-affected on one
#    with no SendIcmpNoRoute (as ns-3.48), and refused (exit 1) on one whose
#    SendIcmpNoRoute changed; the runner (../apply.sh) exits 1 on that one.
# 2. The reproducer (icmp-no-route-livelock.cc) livelocks on the stock tree.
# 3. apply.sh patches the tree; the tree builds, the reproducer runs to its
#    end and delivers, and the internet module's ipv4-icmp-no-route suite
#    (!3101's own test) passes.
# 4. apply.sh run again on the patched tree prints already-fixed.
set -euo pipefail

ns3=${1:-/opt/ns-3}
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
apply="$here/apply.sh"
l3=src/internet/model/ipv4-l3-protocol.cc
suite=src/internet/test/ipv4-icmp-no-route-test-suite.cc
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
fail() {
    echo "FAIL: $*" >&2
    exit 1
}

# copies of the files the patch touches, as a minimal source tree
tree() {
    mkdir -p "$work/$1/src/internet/model" "$work/$1/src/internet/test"
    cp "$ns3/$l3" "$work/$1/$l3"
    cp "$ns3/$suite" "$work/$1/$suite"
}

echo "== 1. apply.sh decides from the source"
grep -q 'ipHeader.GetDestination() == Ipv4Address::GetBroadcast())' "$ns3/$l3" ||
    fail "$ns3 is not a stock ns-3.49 tree with the bug (start from an unpatched image)"
tree stock
out=$("$apply" "$work/stock") || fail "stock: exit $?"
[[ $out == "NS3-001: applied: "* ]] || fail "stock: $out"
out=$("$apply" "$work/stock") || fail "fixed: exit $?"
[[ $out == "NS3-001: already-fixed: "* ]] || fail "fixed: $out"
tree old
# ns-3.48 and earlier: no SendIcmpNoRoute at all
sed -i 's/SendIcmpNoRoute/IcmpGone/g' "$work/old/$l3"
out=$("$apply" "$work/old") || fail "old: exit $?"
[[ $out == "NS3-001: not-affected: "* ]] || fail "old: $out"
tree drifted
# upstream changed SendIcmpNoRoute some other way: neither direction applies
sed -i 's/if (!m_ipForward || ipHeader.GetDestination().IsMulticast() ||/if (!m_ipForward || IsDrifted() || ipHeader.GetDestination().IsMulticast() ||/' \
    "$work/drifted/$l3"
if out=$("$apply" "$work/drifted"); then
    fail "drifted: exit 0: $out"
fi
[[ $out == "NS3-001: refused: "* ]] || fail "drifted: $out"
if out=$(bash "$here/../apply.sh" "$work/drifted" NS3-001); then
    fail "runner on drifted: exit 0: $out"
fi
[[ $out == "NS3-001: refused: "* ]] || fail "runner on drifted: $out"
echo "ok"

repro() {
    (cd "$ns3" && ./ns3 build scratch/icmp-no-route-livelock >"$work/build.log" 2>&1) ||
        { tail -40 "$work/build.log"; fail "build"; }
    (cd "$ns3" && timeout 600 ./ns3 run --no-build scratch/icmp-no-route-livelock 2>&1)
}

echo "== 2. the reproducer livelocks on the stock tree"
cp "$here/icmp-no-route-livelock.cc" "$ns3/scratch/"
if out=$(repro); then
    echo "$out"
    fail "the reproducer finished on the stock tree"
fi
echo "$out" | grep -F 'NS3-001 reproduced: livelock' || { echo "$out"; fail "stock: no livelock"; }
echo "ok"

echo "== 3. apply.sh patches the tree; it builds, the reproducer and the suite pass"
"$apply" "$ns3"
out=$(repro) || { echo "$out"; fail "the reproducer failed on the patched tree"; }
echo "$out" | grep -F 'NS3-001 not-reproduced: ran to +15s' || { echo "$out"; fail "patched: no verdict line"; }
# An ns3-dev image's tree builds the tests of the modules its last configure
# named only, so configure it again with the image's own flags
# (.swarm-configure.env, as ns3-build-contrib does) and internet's tests.
# Another tree is taken as configured.
if [[ -f "$ns3/.swarm-configure.env" ]]; then
    # shellcheck source=/dev/null
    . "$ns3/.swarm-configure.env"
    # shellcheck disable=SC2086  # NS3_PROFILE_FLAGS word-splits on purpose
    (cd "$ns3" && ./ns3 configure -G Ninja $NS3_PROFILE_FLAGS --enable-examples --enable-tests \
        --disable-werror --filter-module-examples-and-tests=internet --enable-modules="$NS3_MODULES" \
        >"$work/configure.log" 2>&1) || { tail -40 "$work/configure.log"; fail "configure"; }
fi
(cd "$ns3" && ./ns3 build >"$work/build.log" 2>&1) || { tail -40 "$work/build.log"; fail "build"; }
(cd "$ns3" && ./test.py --no-build --verbose-failed -s ipv4-icmp-no-route) || fail "suite ipv4-icmp-no-route"
echo "ok"

echo "== 4. apply.sh prints already-fixed on the patched tree"
out=$("$apply" "$ns3") || fail "re-apply: exit $?"
[[ $out == "NS3-001: already-fixed: "* ]] || fail "re-apply: $out"
echo "ok"
echo "NS3-001: all checks passed"
