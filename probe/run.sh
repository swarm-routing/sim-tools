#!/usr/bin/env bash
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
# Scratch probe for swarm-routing/sim-tools#301 (validation branch, no PR):
# ArmIsolationTest's DSDV comparison three times, on ns-3.49 (the image's
# tree) or ns-3-dev master, with stock DSDV or with a print of the order of
# DSDV's per-interface sockets (probe/order.patch).
#   probe/run.sh <release|master> <stock|order>
set -euo pipefail
tree=$1 variant=$2
src=$GITHUB_WORKSPACE
if [ "$tree" = master ]; then
    git clone -q --depth 1 https://gitlab.com/nsnam/ns-3-dev.git /tmp/ns-3-dev
    ns3=/tmp/ns-3-dev
    echo "ns-3-dev master $(git -C "$ns3" rev-parse HEAD)"
else
    ns3=/opt/ns-3
    echo "ns-3 $(cat "$ns3/VERSION")"
fi
cd "$ns3"
if [ "$variant" = order ]; then git apply "$src/probe/order.patch"; fi
if [ "$tree" = master ]; then
    cp -r "$src/ns3/routing-bench" contrib/
    ./ns3 configure -d debug --enable-examples --enable-tests --disable-werror \
        --enable-modules='core;network;internet;wifi;mobility;applications;aodv;olsr;dsdv;mesh;flow-monitor;energy;propagation;routing-bench' >/tmp/configure.log
    ./ns3 build >/tmp/build.log 2>&1 || { tail -50 /tmp/build.log; exit 1; }
else
    ns3-build-contrib "routing-bench=$src/ns3/routing-bench" >/tmp/build.log 2>&1 || { tail -50 /tmp/build.log; exit 1; }
fi
runner=$(find build/utils -name 'ns3*-test-runner-*' -type f | head -1)
for t in 1 2 3; do
    echo "=== try $t"
    "$runner" --suite=routing-bench >/tmp/out.txt 2>&1 || { tail -40 /tmp/out.txt; exit 1; }
    grep -E '^(isolateArms=0|##RUN## |ORDER )' /tmp/out.txt || true
done
