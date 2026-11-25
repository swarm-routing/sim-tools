// Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
// SPDX-License-Identifier: GPL-2.0-only
//
// NS3-001 reproducer (swarm-routing/ns3-tools#238,
// docs/ns3-rcapa/ns3-rcapa-aodv-icmp-livelock.md): on ns-3.49, stock AODV
// livelocks in a zero-time ICMP "net unreachable" storm raised by
// Ipv4L3Protocol::SendIcmpNoRoute. It is the routing-bench suite's
// partitioned-AODV case run unguarded (ns3/routing-bench/test/
// routing-bench-test-suite.cc, RunPartition(false)), with stock ns-3 only.
//
// Nodes 0 and 1 share one SimpleChannel, node 2 is alone on its own, all in
// 10.1.1.0/24, stock AODV. From t = 1 s node 0 sends 100 packets/s of UDP to
// node 1 (delivered) and as many to node 2 (no route ever): AODV's request
// queue fills, and with the bug each drop raises an ICMP error that AODV
// defers into the same full queue, at one instant. A sink on
// Ipv4L3Protocol's Drop trace stops the simulator once one instant has seen
// 10000 route-error drops (simulated time stands still: a livelock), so the
// program ends either way:
//   NS3-001 reproduced: livelock at +Xs (10000 route-error drops at one instant), delivered N
//   exit 1
// or
//   NS3-001 not-reproduced: ran to +15s, delivered N
//   exit 0 (exit 1 too if node 1 got fewer than 800 of its 900 packets).
//
//   cp icmp-no-route-livelock.cc <ns-3>/scratch/
//   ./ns3 build scratch/icmp-no-route-livelock
//   ./ns3 run --no-build scratch/icmp-no-route-livelock

#include "ns3/aodv-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/network-module.h"

#include <iostream>

using namespace ns3;

namespace {

struct LivelockWatch {
    Time at;
    uint32_t atNow = 0;
    bool fired = false;

    void Drop(const Ipv4Header&, Ptr<const Packet>, Ipv4L3Protocol::DropReason reason,
              Ptr<Ipv4>, uint32_t) {
        if (reason != Ipv4L3Protocol::DROP_ROUTE_ERROR) return;
        if (Simulator::Now() != at) {
            at = Simulator::Now();
            atNow = 0;
        }
        if (++atNow == 10000) {
            fired = true;
            Simulator::Stop();
        }
    }
};

void CountRx(uint32_t* n, Ptr<Socket> s) {
    while (s->Recv()) ++*n;
}

void SendUdp(Ptr<Socket> s, Ipv4Address to, uint32_t left) {
    s->SendTo(Create<Packet>(64), 0, InetSocketAddress(to, 9));
    if (left > 1) Simulator::Schedule(MilliSeconds(10), &SendUdp, s, to, left - 1);
}

}  // namespace

int main(int argc, char* argv[]) {
    CommandLine cmd(__FILE__);
    cmd.Parse(argc, argv);

    NodeContainer nodes;
    nodes.Create(3);
    SimpleNetDeviceHelper link;
    NetDeviceContainer devs = link.Install(NodeContainer(nodes.Get(0), nodes.Get(1)));
    devs.Add(link.Install(nodes.Get(2)));

    AodvHelper aodv;
    InternetStackHelper internet;
    internet.SetRoutingHelper(aodv);
    internet.Install(nodes);
    Ipv4AddressHelper addresses("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer ifs = addresses.Assign(devs);
    for (uint32_t i = 0; i < nodes.GetN(); ++i) {
        nodes.Get(i)->GetObject<aodv::RoutingProtocol>()->AssignStreams(10 * i);
    }

    LivelockWatch watch;
    for (uint32_t i = 0; i < nodes.GetN(); ++i) {
        nodes.Get(i)->GetObject<Ipv4L3Protocol>()->TraceConnectWithoutContext(
            "Drop", MakeCallback(&LivelockWatch::Drop, &watch));
    }
    uint32_t delivered = 0;
    Ptr<Socket> rx = Socket::CreateSocket(nodes.Get(1), UdpSocketFactory::GetTypeId());
    rx->Bind(InetSocketAddress(Ipv4Address::GetAny(), 9));
    rx->SetRecvCallback(MakeBoundCallback(&CountRx, &delivered));
    Ptr<Socket> tx = Socket::CreateSocket(nodes.Get(0), UdpSocketFactory::GetTypeId());
    tx->Bind();
    for (uint32_t dst : {1u, 2u}) {
        Simulator::ScheduleWithContext(nodes.Get(0)->GetId(), Seconds(1), &SendUdp, tx,
                                       ifs.GetAddress(dst), 900u);
    }
    Simulator::Stop(Seconds(15));
    Simulator::Run();
    const Time end = Simulator::Now();
    Simulator::Destroy();

    if (watch.fired) {
        std::cout << "NS3-001 reproduced: livelock at +" << end.GetSeconds()
                  << "s (10000 route-error drops at one instant), delivered " << delivered
                  << '\n';
        return 1;
    }
    std::cout << "NS3-001 not-reproduced: ran to +" << end.GetSeconds() << "s, delivered "
              << delivered << '\n';
    return delivered > 800 ? 0 : 1;
}
