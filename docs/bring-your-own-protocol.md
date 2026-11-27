# Bring your own protocol

From "I have a routing idea" to a paired, gated comparison against stock
ns-3 AODV, OLSR and DSDV, with the released packages only: no checkout of
AntHocNet or any other protocol repository, and no CI of this one. Every
command below was run as written, and every output block is a trimmed copy of
what it printed (2026-11-24, release v1.1.4, the `ns3-dev:latest-debug`
image on ns-3.49; "Worked example" at the end says how).

The steps:

1. [Install](#1-install): the image, the harness module, the Python package.
2. [Run the stock arms](#2-run-the-stock-arms).
3. [Scaffold your arm and make it a toy](#3-scaffold-your-arm-and-make-it-a-toy).
4. [Build and register it](#4-build-and-register-it).
5. [A paired comparison over 20 seeds](#5-a-paired-comparison-over-20-seeds).
6. [The three gates](#6-the-three-gates): when a number may count.
7. [Cite](#7-cite).

What the pieces are: `routing-bench` is an ns-3 contrib module holding the
comparison harness, the program `routing-compare`, which builds one scenario
per seed, runs each *arm* (a routing protocol registered with it) on it, and
prints the results as marker lines
([markers.md](https://github.com/swarm-routing/sim-tools/blob/v1.1.4/docs/markers.md)).
Your protocol becomes an arm by living in its own contrib module with one
file, `helper/<module>-bench-arms.cc` (the harness's README, "Registering an
arm": `contrib/routing-bench/README.md` in the tarball, or
[on GitHub](https://github.com/swarm-routing/sim-tools/blob/v1.1.4/ns3/routing-bench/README.md#registering-an-arm)).

Links to this repository's files point at the v1.1.4 tag, the release the
guide was run with. Replace `v1.1.4` in them as in the commands.
The Python package `swarm-sim-tools` holds `ns3-tool`: `scaffold` writes that
module, `compare` reads the marker lines into per-seed confidence intervals
and paired verdicts.

## 1. Install

You need Docker, Python 3.11 or newer and `curl`. Take the newest release from
[Releases](https://github.com/swarm-routing/sim-tools/releases) (v1.1.4 here;
replace the version throughout):

```bash
mkdir -p byo && cd byo
mkdir -p contrib out
curl -fsSLO https://github.com/swarm-routing/sim-tools/releases/download/v1.1.4/routing-bench-1.1.4.tar.gz
curl -fsSLO https://github.com/swarm-routing/sim-tools/releases/download/v1.1.4/SHA256SUMS
sha256sum -c --ignore-missing SHA256SUMS
tar -xzf routing-bench-1.1.4.tar.gz -C contrib
python3 -m venv venv && . venv/bin/activate
pip install swarm-sim-tools==1.1.4
docker pull ghcr.io/swarm-routing/ns3-dev:latest-debug
```

```text
routing-bench-1.1.4.tar.gz: OK
```

- **The image** `ghcr.io/swarm-routing/ns3-dev:latest-debug` is a warm ns-3
  tree (`/opt/ns-3`, the newest ns-3 release, 3.49 here) with
  `ns3-build-contrib`, which links contrib modules into it and builds only
  them. `latest-sanitized` is the same with ASan/UBSan. Without Docker, the
  tarball's `INSTALL.txt` says how to build it in your own ns-3 tree.
- **The harness** is `contrib/routing-bench/`, from the release tarball
  (GPL-2.0-only, it links stock ns-3 only). From source instead: clone
  [swarm-routing/sim-tools](https://github.com/swarm-routing/sim-tools) and
  use its `ns3/routing-bench/` directory.
- **The Python package** is `swarm-sim-tools` on PyPI (it installs the
  `ns3_tool` package and the `ns3-tool` command; from source,
  `pip install ./python`). Up to v1.1.2 the distribution was called
  `ns3-tools`: uninstall that one first
  ([README](https://github.com/swarm-routing/sim-tools/blob/v1.1.4/README.md),
  "Moving from `ns3-tools`").

Keep one container running for the whole guide, with `contrib/` mounted, so
each build is incremental:

```bash
docker run -d --name byo --cpus 3 -v "$PWD/contrib:/src" ghcr.io/swarm-routing/ns3-dev:latest-debug sleep infinity
docker exec byo ns3-build-contrib --test routing-bench=/src/routing-bench
```

```text
ns3-build-contrib: build took 20 s (profile debug, ns-3.49; strict-warnings OFF, coverage OFF)
[1/1] PASS: TestSuite routing-bench
1 of 1 tests passed (1 passed, 0 skipped, 0 failed, 0 crashed, 0 valgrind errors)
```

`--cpus 3` is what the worked example used on a 4-CPU host (it caps the build
and the runs); set it to your machine, or drop it.

## 2. Run the stock arms

One invocation runs every listed arm on the same seeds. The smallest useful
cell: the `paper` scenario (random waypoint in 1500 x 300 m, 20 CBR flows) with
20 nodes for 30 simulated seconds, one seed:

```bash
docker exec -w /opt/ns-3 byo ./ns3 run --no-build \
    "routing-compare --scenario=paper --nNodes=20 --time=30 --runs=1 --protocols=aodv,olsr,dsdv" > out/stock.txt
grep '^##RUN##' out/stock.txt
for a in aodv olsr dsdv; do echo "$a pdr=$(ns3-tool compare --get pdr --proto $a out/stock.txt)"; done
```

```text
##RUN## 1 aodv 100.0 32.1 709.5 4.98 3.97 28.27 2.5 5.5 2.0726
##RUN## 1 olsr 90.6 3.9 25.5 4.51 2.03 1.04 2.5 25.5 2.1654
##RUN## 1 dsdv 81.3 276.2 7715.5 4.05 3.34 82.92 3.5 inf 2.1452
aodv pdr=100.0
olsr pdr=90.6
dsdv pdr=81.3
```

A `##RUN##` row is `<seed> <arm> pdr delay delay99 thrput nrl jitter off50
off90 nrl_bytes` (PDR in %, delays in ms, throughput in kbit/s, NRL = routing
control packets per delivered data packet). Read fields by name through the
reader (`ns3-tool compare --get FIELD --proto ARM FILE`), never by column
position: the marker contract only appends fields
([markers.md](https://github.com/swarm-routing/sim-tools/blob/v1.1.4/docs/markers.md)).
`routing-compare --PrintHelp` lists every option;
the ones used here are `--scenario`, `--nNodes`, `--time`, `--runs`,
`--firstRun` and `--protocols`. The summary table under the marker lines is
titled "AntHocNet protocol comparison", a leftover of the harness's origin; it
holds whichever arms you listed.

The `aodv` arm is stock AODV behind the ICMP no-route guard that keeps it from
livelocking on ns-3.49 (NS3-001,
[ns3-bugs.md](https://github.com/swarm-routing/sim-tools/blob/v1.1.4/docs/ns3-bugs.md)).

## 3. Scaffold your arm and make it a toy

```bash
ns3-tool scaffold toyflood --out contrib --holder "Your Name"
```

```text
contrib/toyflood/CMakeLists.txt
contrib/toyflood/model/toyflood.h
contrib/toyflood/model/toyflood.cc
contrib/toyflood/helper/toyflood-bench-arms.cc
contrib/toyflood/README.md
```

The skeleton already builds, registers and delivers: until you replace it, its
arm installs stock OLSR. The module name must match `[a-z][a-z0-9-]*` and is
also the arm's `--protocols` token.

The toy here is a **duplicate-suppressed broadcast flood**: every data packet
goes out as a link-layer broadcast; a node that sees it for the first time
delivers it if it is the destination, else rebroadcasts it after a random
jitter of up to 10 ms. No control packets, no routing table. It shows the
three things every arm needs: an `Ipv4RoutingProtocol`, an
`Ipv4RoutingHelper` that installs it, and an `AssignStreams` that pins its
randomness to the harness's seed (org rule 5: a fixed seed gives
byte-identical output). Its duplicate cache has a cap (org rule 7: bounded
structures stay bounded).

Replace `contrib/toyflood/model/toyflood.h` with:

```cpp
// Copyright (c) 2026 Your Name
// SPDX-License-Identifier: GPL-2.0-only
//
// toyflood: a duplicate-suppressed broadcast flood, a teaching toy. Every
// data packet goes out as a link-layer broadcast; a node that sees it for
// the first time delivers it (if it is the destination) or rebroadcasts it
// after a small random jitter. No control packets, no routing table.
#ifndef TOYFLOOD_H
#define TOYFLOOD_H

#include "ns3/ipv4-routing-helper.h"
#include "ns3/ipv4-routing-protocol.h"
#include "ns3/node-container.h"
#include "ns3/random-variable-stream.h"

#include <deque>
#include <set>
#include <tuple>

namespace ns3 {
namespace toyflood {

class RoutingProtocol : public Ipv4RoutingProtocol {
public:
    static TypeId GetTypeId();
    RoutingProtocol();

    Ptr<Ipv4Route> RouteOutput(Ptr<Packet> p, const Ipv4Header& header, Ptr<NetDevice> oif,
                               Socket::SocketErrno& sockerr) override;
    bool RouteInput(Ptr<const Packet> p, const Ipv4Header& header, Ptr<const NetDevice> idev,
                    const UnicastForwardCallback& ucb, const MulticastForwardCallback& mcb,
                    const LocalDeliverCallback& lcb, const ErrorCallback& ecb) override;
    void NotifyInterfaceUp(uint32_t) override {}
    void NotifyInterfaceDown(uint32_t) override {}
    void NotifyAddAddress(uint32_t, Ipv4InterfaceAddress) override {}
    void NotifyRemoveAddress(uint32_t, Ipv4InterfaceAddress) override {}
    void SetIpv4(Ptr<Ipv4> ipv4) override { m_ipv4 = ipv4; }
    void PrintRoutingTable(Ptr<OutputStreamWrapper> stream, Time::Unit unit) const override;

    /// Pin the jitter's random stream; returns the number of streams used (1).
    int64_t AssignStreams(int64_t stream);

private:
    using Key = std::tuple<uint32_t, uint32_t, uint8_t, uint16_t>;  // src, dst, proto, id
    bool SeenBefore(const Ipv4Header& h);  // records h; true if it was already there
    Ptr<Ipv4Route> BroadcastRoute(const Ipv4Header& h, uint32_t iface) const;
    uint32_t WirelessInterface() const;  // the first interface that is not loopback

    Ptr<Ipv4> m_ipv4;
    Ptr<UniformRandomVariable> m_jitter;
    Time m_maxJitter;
    uint32_t m_cacheSize;  // golden rule 7: the duplicate cache is bounded
    std::set<Key> m_seen;
    std::deque<Key> m_order;
};

class ToyFloodHelper : public Ipv4RoutingHelper {
public:
    ToyFloodHelper* Copy() const override { return new ToyFloodHelper(*this); }
    Ptr<Ipv4RoutingProtocol> Create(Ptr<Node> node) const override;
    /// Pin every node's protocol streams from `stream`; returns how many were used.
    int64_t AssignStreams(NodeContainer c, int64_t stream);
};

}  // namespace toyflood
}  // namespace ns3

#endif  // TOYFLOOD_H
```

and `contrib/toyflood/model/toyflood.cc` with:

```cpp
// Copyright (c) 2026 Your Name
// SPDX-License-Identifier: GPL-2.0-only

#include "toyflood.h"

#include "ns3/ipv4-route.h"
#include "ns3/ipv4.h"
#include "ns3/node.h"
#include "ns3/simulator.h"
#include "ns3/uinteger.h"

namespace ns3 {
namespace toyflood {

NS_OBJECT_ENSURE_REGISTERED(RoutingProtocol);

TypeId RoutingProtocol::GetTypeId() {
    static TypeId tid =
        TypeId("ns3::toyflood::RoutingProtocol")
            .SetParent<Ipv4RoutingProtocol>()
            .SetGroupName("Toyflood")
            .AddConstructor<RoutingProtocol>()
            .AddAttribute("MaxJitter", "Upper bound of the rebroadcast jitter.",
                          TimeValue(MilliSeconds(10)),
                          MakeTimeAccessor(&RoutingProtocol::m_maxJitter), MakeTimeChecker())
            .AddAttribute("DupCacheSize", "Packets remembered for duplicate suppression.",
                          UintegerValue(1024),
                          MakeUintegerAccessor(&RoutingProtocol::m_cacheSize),
                          MakeUintegerChecker<uint32_t>(1));
    return tid;
}

RoutingProtocol::RoutingProtocol() : m_jitter(CreateObject<UniformRandomVariable>()) {}

int64_t RoutingProtocol::AssignStreams(int64_t stream) {
    m_jitter->SetStream(stream);
    return 1;
}

uint32_t RoutingProtocol::WirelessInterface() const {
    for (uint32_t i = 0; i < m_ipv4->GetNInterfaces(); ++i) {
        if (m_ipv4->GetAddress(i, 0).GetLocal() != Ipv4Address::GetLoopback()) {
            return i;
        }
    }
    return 0;
}

Ptr<Ipv4Route> RoutingProtocol::BroadcastRoute(const Ipv4Header& h, uint32_t iface) const {
    auto route = Create<Ipv4Route>();
    route->SetDestination(h.GetDestination());
    route->SetSource(m_ipv4->GetAddress(iface, 0).GetLocal());
    route->SetGateway(Ipv4Address::GetBroadcast());  // link-layer broadcast, no ARP
    route->SetOutputDevice(m_ipv4->GetNetDevice(iface));
    return route;
}

bool RoutingProtocol::SeenBefore(const Ipv4Header& h) {
    Key k{h.GetSource().Get(), h.GetDestination().Get(), h.GetProtocol(), h.GetIdentification()};
    if (!m_seen.insert(k).second) {
        return true;
    }
    m_order.push_back(k);
    if (m_order.size() > m_cacheSize) {  // evict the oldest: the cache stays bounded
        m_seen.erase(m_order.front());
        m_order.pop_front();
    }
    return false;
}

Ptr<Ipv4Route> RoutingProtocol::RouteOutput(Ptr<Packet>, const Ipv4Header& header,
                                            Ptr<NetDevice>, Socket::SocketErrno& sockerr) {
    sockerr = Socket::ERROR_NOTERROR;
    return BroadcastRoute(header, WirelessInterface());
}

bool RoutingProtocol::RouteInput(Ptr<const Packet> p, const Ipv4Header& header,
                                 Ptr<const NetDevice> idev, const UnicastForwardCallback& ucb,
                                 const MulticastForwardCallback&, const LocalDeliverCallback& lcb,
                                 const ErrorCallback&) {
    const uint32_t iface = m_ipv4->GetInterfaceForDevice(idev);
    if (m_ipv4->GetInterfaceForAddress(header.GetSource()) >= 0) {
        return true;  // our own packet, rebroadcast back to us: consume it
    }
    const Ipv4Address dst = header.GetDestination();
    if (m_ipv4->IsDestinationAddress(dst, iface)) {
        if (dst.IsBroadcast() || !SeenBefore(header)) {
            lcb(p, header, iface);  // deliver each unicast packet once
        }
        return true;
    }
    if (SeenBefore(header)) {
        return true;  // a duplicate: already forwarded, drop it silently
    }
    Ptr<Ipv4Route> route = BroadcastRoute(header, WirelessInterface());
    UnicastForwardCallback forward = ucb;
    Simulator::Schedule(Seconds(m_jitter->GetValue(0, m_maxJitter.GetSeconds())),
                        [forward, route, p, header]() { forward(route, p, header); });
    return true;
}

void RoutingProtocol::PrintRoutingTable(Ptr<OutputStreamWrapper> stream, Time::Unit) const {
    *stream->GetStream() << "toyflood: no routing table (flooding)\n";
}

Ptr<Ipv4RoutingProtocol> ToyFloodHelper::Create(Ptr<Node>) const {
    return CreateObject<RoutingProtocol>();
}

int64_t ToyFloodHelper::AssignStreams(NodeContainer c, int64_t stream) {
    int64_t used = 0;
    for (auto it = c.Begin(); it != c.End(); ++it) {
        auto proto = DynamicCast<RoutingProtocol>((*it)->GetObject<Ipv4>()->GetRoutingProtocol());
        used += proto->AssignStreams(stream + used);
    }
    return used;
}

}  // namespace toyflood
}  // namespace ns3
```

Two notes on `RouteInput`. It returns `true` for every packet it consumes,
duplicates included: `false` means "no route", on which ns-3.49 answers with
an ICMP Destination Unreachable (the trigger of NS3-001). And it never calls
the error callback, for the same reason.

Then point the arm at the new helper instead of the OLSR placeholder, in
`helper/toyflood-bench-arms.cc` (the include, the helper member, the
`TODO` comment, and `RegisterArm`'s description: what the arm is; for a real
protocol, which paper it follows), and drop OLSR from the module's libraries
in `CMakeLists.txt`. As a patch against the fresh scaffold: save this block as
`toyflood-arm.patch` next to `contrib/`,

```diff
--- a/helper/toyflood-bench-arms.cc
+++ b/helper/toyflood-bench-arms.cc
@@ -6,13 +6,12 @@
 // module (CMakeLists.txt). routing-compare finds this file and calls
 // RegisterArms_toyflood() at start-up; `--protocols=toyflood` runs the arm.
 //
-// TODO: replace OlsrHelper, the placeholder, with this module's own helper,
-// and say in RegisterArm's description which paper the arm follows. An arm
-// counts in a comparison only after its three gates (org golden rule 6): a
+// The arm installs ToyFloodHelper (model/toyflood.h), a teaching toy with no
+// paper. An arm counts in a comparison only after its three gates (org golden rule 6): a
 // fidelity sheet from its paper, the per-PR delivery smoke, and an anchor
 // reproducing the paper's own trend.
-#include "ns3/olsr-helper.h"
 #include "ns3/routing-bench-arm.h"
+#include "ns3/toyflood.h"
 
 namespace ns3 {
 namespace toyflood {
@@ -29,7 +28,7 @@
     }
 
 private:
-    OlsrHelper m_helper;  // TODO: this module's helper
+    ToyFloodHelper m_helper;
 };
 
 Ptr<bench::Arm> MakeToyfloodArm() {
@@ -44,7 +43,7 @@
 void RegisterArms_toyflood();
 
 void RegisterArms_toyflood() {
-    RegisterArm("toyflood", "toyflood (placeholder: stock OLSR until the module's own routing replaces it)",
+    RegisterArm("toyflood", "toyflood (a duplicate-suppressed broadcast flood; a teaching toy, no paper)",
                 &toyflood::MakeToyfloodArm);
 }
 
--- a/CMakeLists.txt
+++ b/CMakeLists.txt
@@ -23,6 +23,5 @@
     ${toyflood_bench_sources}
   HEADER_FILES
     model/toyflood.h
-  # olsr: the placeholder routing the arm installs until you replace it.
-  LIBRARIES_TO_LINK ${libcore} ${libinternet} ${libolsr} ${toyflood_bench_libs}
+  LIBRARIES_TO_LINK ${libcore} ${libinternet} ${toyflood_bench_libs}
 )
```

and apply it:

```bash
(cd contrib/toyflood && patch -p1 < ../../toyflood-arm.patch)
```

```text
patching file helper/toyflood-bench-arms.cc
patching file CMakeLists.txt
```

(Checked with `patch --dry-run`, then applied, against a fresh
`ns3-tool scaffold toyflood --holder "Your Name"` of v1.1.4; the result built
and ran as in step 4.)

The rest of the scaffold stays: `CMakeLists.txt` compiles the arm file only
where `routing-bench` is installed and enabled, so the module also builds
alone, and `routing-compare` finds `helper/toyflood-bench-arms.cc` and calls
its `RegisterArms_toyflood()` at start-up.

## 4. Build and register it

List the harness first, then your module (`name=dir`, the name equal to the
`LIBNAME` in `build_lib`). `--strict-warnings --quality-modules toyflood`
compiles your module only with `-Wall -Wextra ... -Werror`, as the org's CI
would:

```bash
docker exec byo ns3-build-contrib --strict-warnings --quality-modules toyflood \
    routing-bench=/src/routing-bench toyflood=/src/toyflood
docker exec -w /opt/ns-3 byo ./ns3 run --no-build "routing-compare --PrintHelp" | grep -- '--protocols'
```

```text
ns3-build-contrib: build took 3 s (profile debug, ns-3.49; strict-warnings ON, coverage OFF)
    --protocols:       Comma-separated list (aodv,dsdv,hwmp,olsr,toyflood). `oracle` is the #296 global-knowledge shortest-path CONTROL (upper bound, zero control traffic), off unless named. [aodv,olsr,dsdv]
```

`toyflood` in that list means the registration ran. Now one seed of the
arm alone, and the delivery verdict (PDR > 0) read through the reader:

```bash
docker exec -w /opt/ns-3 byo ./ns3 run --no-build \
    "routing-compare --scenario=paper --nNodes=20 --time=30 --runs=1 --protocols=toyflood" > out/smoke.txt
ns3-tool compare --get row --proto toyflood out/smoke.txt
pdr=$(ns3-tool compare --get pdr --proto toyflood out/smoke.txt)
awk -v v="$pdr" 'BEGIN { exit !(v > 0) }' && echo "toyflood delivers: pdr=$pdr"
```

```text
1 99.5 13.3 35.5 4.96 0.00 3.33 11.5 26.5 0.0000
toyflood delivers: pdr=99.5
```

And determinism: the same seed twice, `--perf=0` (the `##PERF##` line is
cost, wall time included, so it is the one line that differs between runs;
[markers.md](https://github.com/swarm-routing/sim-tools/blob/v1.1.4/docs/markers.md)),
must be byte-identical:

```bash
for i in a b; do
  docker exec -w /opt/ns-3 byo ./ns3 run --no-build \
      "routing-compare --scenario=paper --nNodes=20 --time=30 --firstRun=3 --runs=1 --protocols=toyflood --perf=0" > out/det-$i.txt
done
cmp out/det-a.txt out/det-b.txt && echo "seed 3: byte-identical"
```

```text
seed 3: byte-identical
```

## 5. A paired comparison over 20 seeds

Org rule 6: comparisons are paired, per-seed deltas over at least 20 seeds.
Every arm in one invocation sees the same scenario for a given seed, so the
pairs are exact. `--firstRun`/`--runs` split the seeds into blocks that can
run in parallel and be read together; here three blocks, 1-7, 8-14 and
15-20:

```bash
for b in "1 7" "8 7" "15 6"; do
  set -- $b
  docker exec -w /opt/ns-3 byo ./ns3 run --no-build \
      "routing-compare --scenario=paper --nNodes=20 --time=30 --firstRun=$1 --runs=$2 --protocols=toyflood,aodv,olsr,dsdv" \
      > out/cell-seeds$1.txt &
done
wait
```

This took 159 s of wall time on 3 CPUs (each arm runs in its own process by
default, `--isolateArms`; one seed of one arm costs 2 to 10 s of CPU here,
`##PERF##`). Then the paired read, the new arm against each baseline, seed by
seed, over all three blocks:

```bash
for base in aodv olsr dsdv; do
  ns3-tool compare --proto toyflood --vs $base out/cell-seeds1.txt out/cell-seeds8.txt out/cell-seeds15.txt
done
```

```text
toyflood - aodv, by seed: paired 95% CI (n=20): dPDR +6.63 [+1.07,+12.20]pp p=0.0372  d_d99 -466.50 [-613.30,-326.45]ms p=9.56e-05  d_NRL -5.29 [-6.55,-4.04] p=1.91e-06 -> PAIRED-IMPROVED
toyflood - olsr, by seed: paired 95% CI (n=20): dPDR +6.83 [+5.04,+8.63]pp p=0.000142  d_d99 +5.90 [+2.50,+9.15]ms p=0.0108  d_NRL -2.01 [-2.14,-1.88] p=9.52e-05 -> PAIRED-MIXED
toyflood - dsdv, by seed: paired 95% CI (n=20): dPDR +8.77 [+4.95,+12.59]pp p=0.000481  d_d99 -4121.75 [-5785.40,-2508.25]ms p=0.000593  d_NRL -3.49 [-3.76,-3.23] p=1.91e-06 -> PAIRED-IMPROVED
```

Each line is the mean of the 20 per-seed differences (new arm minus
baseline) with its 95% CI and the Wilcoxon signed-rank p, for PDR, the 99th
percentile delay and NRL, and a verdict from the CIs, from the new arm's
view: IMPROVED when every metric whose CI excludes zero is better for it
(higher PDR, lower delay99 or NRL), WORSE when every such metric is worse,
MIXED when they disagree (here: more delivered, but a higher tail delay than
OLSR), NOISE when no CI excludes zero. The per-arm 95% CIs come from the blocks
concatenated into one cell:

```bash
cat out/cell-seeds1.txt out/cell-seeds8.txt out/cell-seeds15.txt > out/cell.txt
ns3-tool compare --all out/cell.txt | grep -v '^##PERF##'
```

```text
cell                        proto            pdr    delay  delay99   thrput      nrl
------------------------------------------------------------------------------------
cell.txt                    aodv           90.80    19.70   362.80     4.59     4.49
                            95% CI  n=20: pdr 89.11 ±7.13  delay 21.12 ±5.17  delay99 493.6 boot[351.8,642.0]  thrput 4.52 ±0.41  nrl 5.29 ±1.25
cell.txt                    dsdv           85.00    93.90  3236.50     4.30     3.35
                            95% CI  n=20: pdr 86.98 ±5.01  delay 146.98 ±64.37  delay99 4148.9 boot[2533.6,5814.4]  thrput 4.41 ±0.33  nrl 3.49 ±0.27
cell.txt                    olsr           89.10     2.70    18.80     4.49     1.97
                            95% CI  n=20: pdr 88.91 ±3.80  delay 3.38 ±0.95  delay99 21.2 boot[18.7,23.9]  thrput 4.50 ±0.25  nrl 2.01 ±0.13
cell.txt                    toyflood       95.10     8.20    24.50     4.80     0.00
                            95% CI  n=20: pdr 95.75 ±4.57  delay 9.50 ±1.41  delay99 27.1 boot[24.1,30.2]  thrput 4.86 ±0.32  nrl 0.00 ±0.00
cell.txt: column mapping vs '# stddev' OK (60 checks)
```

Read the `95% CI n=20` lines. The row above each is the harness's own summary
table, and with concatenated blocks the last block's table wins (seeds 15-20
here), so it is not the 20-seed mean. `compare` also passes every `##PERF##`
line through under the table (the `grep -v` drops them here).

**What this does and does not say.** On this light load (20 nodes, 20 flows
of 512 bit/s, 30 s) the flood delivers more than every stock arm, with an NRL
of zero: NRL counts routing *control* packets, and a flood sends none. Its
cost is in the data copies, which NRL does not see; the channel occupancy
(`##AIR## <seed> <arm> txS rxS ccaS busyPct`, the last field the percentage
of node-time the medium was busy) shows it, three times AODV's on seed 1:

```text
##AIR## 1 toyflood 4.666 21.715 4.723 5.1840
##AIR## 1 aodv 1.422 5.212 2.985 1.6032
##AIR## 1 olsr 1.064 4.577 1.891 1.2553
##AIR## 1 dsdv 1.106 3.708 2.297 1.1852
```

A heavier load or a larger network is where a flood should lose; choosing
the cells that test a claim is the pre-registration's job (gate 3), before
any run. And none of these numbers counts yet: the arm has cleared one gate of
three.

The drop book (`ns3-tool diagnose`, the `# drops` lines) assumes unicast hops,
so for a flooding arm it is meaningless, as here (seeds 1-7; the
`[route: ...]` line under each arm trimmed):

```bash
ns3-tool diagnose out/cell-seeds1.txt
```

```text
arm            lines     pdr   route   queue     mac    chan     ttl     sum   other
toyflood           1   93.09    0.00    0.00    0.00-7853.98    0.00-7760.88    0.00
aodv               1   87.04    0.45    5.84    0.00    6.68    0.00  100.00    0.00
```

Every broadcast reception counts as a hop received, so the `chan` loss goes
negative. Trust it for unicast arms only.

To go beyond one machine, `ns3-campaign` runs a plan of cells as GitHub
Actions jobs in one image pinned by digest
([`python/ns3_tool/campaign.py`](https://github.com/swarm-routing/sim-tools/blob/v1.1.4/python/ns3_tool/campaign.py),
a plan in
[`campaigns/`](https://github.com/swarm-routing/sim-tools/tree/v1.1.4/campaigns));
it needs a repository with the org's cell
workflow, which the local loop above does not.

The cell above is a shortened paper field. For a real comparison, run your
arm on a network family's cells. The
[family catalogue](https://github.com/swarm-routing/sim-tools/blob/main/scenarios/README.md)
covers MANET, FANET, VANET, the static Wi-Fi mesh and the legacy-default
cells. For each family it gives the routing-compare
preset, the cells, the preflight verdict each cell must give, and the
family's anchors, with a source for every value. Each family also has a
"configure it with ns-3" page:
[MANET](https://github.com/swarm-routing/sim-tools/blob/main/docs/families/manet.md),
[FANET](https://github.com/swarm-routing/sim-tools/blob/main/docs/families/fanet.md),
[VANET](https://github.com/swarm-routing/sim-tools/blob/main/docs/families/vanet.md),
[static mesh](https://github.com/swarm-routing/sim-tools/blob/main/docs/families/static-mesh.md),
[legacy defaults](https://github.com/swarm-routing/sim-tools/blob/main/docs/families/legacy.md).

The catalogue came after v1.1.4, so these links point at `main`. To use it:
- check out this repository;
- install a release after v1.1.4, or `pip install ./python` from the
  checkout: v1.1.4's `ns3-scenario-check` and `ns3-tool sweep` have no
  `--family`;
- pass the checkout's `scenarios/` with `--catalogue DIR`:

```bash
ns3-scenario-check preflight --family fanet --catalogue DIR
ns3-tool sweep NS3DIR --family fanet --catalogue DIR --protocols ARM,aodv,olsr,dsdv --runs 20
```

## 6. The three gates

An arm's numbers count in a comparison only after three gates (org rule 6,
[CONTRIBUTING](https://github.com/swarm-routing/.github/blob/main/CONTRIBUTING.md)
"Invariants"). The toy above has no paper, so it can never pass gate 1: its
numbers illustrate the tooling and say nothing about flooding.

### Gate 1: a fidelity sheet from the paper

`docs/fidelity.md` in your repository maps every mechanism and parameter of
the arm to the paper's section, table or equation that gives it, or says
`repo choice: <reason>`, or `unknown`. The tool is
[`tools/fidelity/`](https://github.com/swarm-routing/.github/tree/main/tools/fidelity)
in swarm-routing/.github: `fidelity.py` and the sibling module it imports,
`bib.py`; fetch both into one directory. `skeleton` writes the empty sheet,
`check` validates it (exit 1 on a problem):

```bash
mkdir -p fidelity && cd fidelity
curl -fsSLO https://raw.githubusercontent.com/swarm-routing/.github/main/tools/fidelity/fidelity.py
curl -fsSLO https://raw.githubusercontent.com/swarm-routing/.github/main/tools/fidelity/bib.py
python3 fidelity.py skeleton --protocol toyflood > fidelity.md
python3 fidelity.py check fidelity.md
```

```text
fidelity.md: 1 mechanisms, 1 parameters; unknown: TODO, TODO; repo choice: none; open (sourced, status unknown): none
fidelity check: ok
```

`check` passes the untouched skeleton, every row still `TODO`: it checks the
sheet's shape and its Source cells, not that the mechanisms come from the
paper, so passing it is not gate 1. Gate 1 is the sheet filled from the paper
and reviewed. The skeleton (`fidelity.md` above):

```markdown
# toyflood: fidelity sheet

## Sources

| Key | Citation | Access |
|---|---|---|
| P1 | TODO: authors, title, venue, year, DOI | in hand |

## Mechanisms

| Mechanism | Source | Implementation | Status |
|---|---|---|---|
| TODO | unknown | — | unknown |

## Parameters

| Parameter | Value | Source | Notes |
|---|---|---|---|
| TODO | — | unknown | |

## Anchor candidate

| Trend | Scenario | Metric | Comparators | Source |
|---|---|---|---|---|
| TODO | TODO | TODO | TODO | unknown |
```

(The skeleton's introductory paragraph is trimmed here.) A Source cell is
`[KEY] §3.1`, `[KEY] Table 4`, `[KEY] Fig. 2`, `[KEY] eq. 4` and the like.
Take the citation from the paper's DOI record (`fidelity.py bib entry DOI`
prints it from Crossref), never typed. The anchor candidate row is what gate 3
tests.

### Gate 2: the per-PR delivery smoke

Every change to the arm must still deliver: one short run, PDR > 0, read
through the reader. **With the packages only, the smoke of step 4 is gate 2**:
the one-seed run, `ns3-tool compare --get pdr --proto ARM`, and the `awk`
test that fails unless PDR > 0. Run it on every change.

With a checkout of this repository (`git clone
https://github.com/swarm-routing/sim-tools`), the same check is also a
script, which this repository's stock-arm and scaffold CI jobs use. The
scripts are not in the tarball or the wheel, and need the checkout around
them: `arm-delivers.sh` finds the reader at `../../python/ns3_tool/`, so
fetched alone it fails with `cd: ../../python/ns3_tool: No such file or
directory`. From the checkout's root:

```bash
bash tools/checks/arm-delivers.sh toyflood < out/smoke.txt   # exit 0 if pdr > 0
bash tools/checks/check-scaffold-arm.sh /opt/ns-3 toyflood    # in the container, the checkout mounted
```

The second, run in the worked example's container with the checkout's
`tools/` and `python/` copied in, printed:

```text
ok    routing-compare offers toyflood (aodv,dsdv,hwmp,olsr,toyflood)
ok    toyflood delivers: 1 99.5 13.3 35.5 4.96 0.00 3.33 11.5 26.5 0.0000
```

In your repository's CI, the org's
[`reusable-ns3-ci.yml`](https://github.com/swarm-routing/.github/blob/main/.github/workflows/reusable-ns3-ci.yml)
builds your module in the same image with `routing-bench` as a dependency
(`dependencies: routing-bench=swarm-routing/sim-tools@<commit>:ns3/routing-bench`),
runs your test suites and, with `run:`, a smoke program; its header has a
caller to copy. Making the smoke's verdict fail the job (the PDR > 0 test
above) is a step your workflow adds.

### Gate 3: an anchor, pre-registered

An anchor reproduces the paper's own trend (from the fidelity sheet's anchor
candidate) in the harness: the comparator against the baseline the paper used,
on the paper's scenario, read with `ns3-tool compare --proto ARM --vs BASE`.
Pre-register it, in writing, before the first run: an issue or a committed
file stating what is run and what counts as reproduced. A template:

```markdown
## Anchor pre-registration: <arm> (<paper key>)

- **Trend (from the paper):** <e.g. PDR of <arm> above AODV's as speed grows; [KEY] Fig. 5>
- **Cells:** <the routing-compare flags of each cell, verbatim>
- **Arms:** <arm>, <baseline(s)>; **seeds:** 1-20 (or more), the same for every arm
- **Image:** ghcr.io/swarm-routing/ns3-dev@sha256:<digest> (by digest, never a tag);
  **routing-bench:** <release or commit>; **arm:** <commit>
- **Read:** `ns3-tool compare --proto <arm> --vs <baseline> <cell files>`
- **Reproduced if:** <e.g. PAIRED-IMPROVED on PDR in every cell with speed >= 10 m/s>
- **Not reproduced if:** <the opposite, or NOISE>; reported either way
```

With `ns3-campaign` the plan file is that pre-registration: the cells, arms,
seeds, pinned modules and a `reference` arm, committed before any dispatch
(`campaigns/anthocnet-aodv-smoke.toml` is one; the plan format is
`campaign.py`'s docstring). Examples of complete sheets and pre-registrations
are AntHocNet's `ns3/baselines/adaptive/README.md` and
`docs/benchmarks/v2.5.0-comparators.md` in
[swarm-routing/AntHocNet](https://github.com/swarm-routing/AntHocNet), read as
references only; nothing in this guide needs that repository.

## 7. Cite

Cite this tooling from
[CITATION.cff](https://github.com/swarm-routing/sim-tools/blob/v1.1.4/CITATION.cff)
(GitHub's "Cite this repository" button) and the concept DOI in the README's
[Releases & citing](https://github.com/swarm-routing/sim-tools/blob/v1.1.4/README.md#releases--citing),
which always resolves to
the latest release; when you report a number, cite the version DOI of the
release you measured with, listed on that Zenodo record. Copy DOIs from
those records, never type them. The same section lists the works this
tooling builds on (ns-3 among them).

## Known rough edges

Found while writing and following this guide, on v1.1.4; none of them stops
a step, but each can mislead:

- **The drop book is meaningless for a flooding arm** (step 5): every
  broadcast reception counts as a hop, so `chan` goes to about -7800%.
  After v1.1.4, `ns3-tool diagnose` prints `n/a` and a warning for such an
  arm (#351; [markers.md](markers.md) "Reading an arm that is not unicast
  routing").
- **NRL is 0 for an arm that sends no control packets**: a flood's cost
  shows in `##AIR##`, not in NRL (step 5; [markers.md](markers.md) says so
  after v1.1.4).
- **Concatenated seed blocks:** `ns3-tool compare --all`'s top row per arm
  is the last block's summary table; read the `95% CI n=20` line. `compare`
  also echoes every `##PERF##` line.
- **The summary table is titled "AntHocNet protocol comparison"**, whatever
  arms ran. It stays so for now: committed cells carry it, and AntHocNet's
  callers are checked before it changes (#351).
- **`routing-compare --PrintHelp` cites AntHocNet-internal items**: bare
  issue numbers (`#58`, `#296`, `#639` ...) that are AntHocNet's, and paths
  such as `docs/benchmarks/scenarios/fanet.md` that exist in AntHocNet, not
  here or in the tarball. Gone after v1.1.4 (#351).
- **The scaffold's comments and README name `swarm-routing/ns3-tools`**, this
  repository's old name; it is `swarm-routing/sim-tools` now (the scaffold
  says so after v1.1.4, #351, and its `TODO` lines read as placeholder
  notes, so step 3's patch applies to v1.1.4's skeleton only). Its README's
  `docker run` example also mounts a checkout of this repository, which the
  `ns3-build-contrib` call of step 4 does not need.
- **The delivery-smoke scripts are not shipped** (gate 2):
  `tools/checks/arm-delivers.sh` and `check-scaffold-arm.sh` are in neither
  the tarball nor the wheel, and do not run outside a checkout.

## Worked example

Everything above was run on 2026-11-24 on one Linux host (4 CPUs, Docker
limited to 3 with `--cpus 3`), from an empty directory, with v1.1.4's
`routing-bench-1.1.4.tar.gz` (checksum verified), `swarm-sim-tools==1.1.4`
from PyPI in a fresh venv, and `ghcr.io/swarm-routing/ns3-dev:latest-debug`
(ns-3.49). The steps were first run by hand, then again as one script from a
fresh directory and a fresh container; the outputs above are the script's.
The three 20-seed blocks of the two runs are byte-identical apart from
`##PERF##`, and every other output shown matched. Outputs are trimmed to the
lines shown; no number was edited. The fidelity skeleton came from swarm-routing/.github's
`main` on the same day.

## Clean up

```bash
docker rm -f byo
```
