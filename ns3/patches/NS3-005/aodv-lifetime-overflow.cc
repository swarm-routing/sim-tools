// Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
// SPDX-License-Identifier: GPL-2.0-only
//
// NS3-005 reproducer (swarm-routing/sim-tools#374, docs/ns3-rcapa/ns3-rcapa-aodv-lifetime-overflow.md):
// stock AODV adds the local broadcast route of an interface that comes up with
// lifetime Simulator::GetMaximumSimulationTime(), and aodv::RoutingTableEntry's
// constructor adds Simulator::Now() to it: a signed 64-bit overflow for any
// interface brought up after t=0.
//
// Two nodes on a CSMA link, stock AODV. At --downAt (1 s) node 1's CSMA
// interface is set down (Ipv4::SetDown), at --upAt (35 s) up again
// (Ipv4::SetUp -> aodv::RoutingProtocol::NotifyInterfaceUp); at --upAt + 1 s
// node 1's AODV routing table is printed and the run ends.
//
// Build ns-3 with its sanitizers (NS3_SANITIZE=ON, which adds
// -fno-sanitize-recover=all; the ns3-dev:*-sanitized images): with the bug,
// UBSan aborts the run inside NotifyInterfaceUp with
//   nstime.h:...: runtime error: signed integer overflow: 9223372036854775807 + 35000000000 ...
// and the exit status is non-zero; without it the program prints
//   NS3-005 not-reproduced: interface up at +35s, no overflow
// and exits 0. On a build without sanitizers the overflow is silent undefined
// behaviour, so this program cannot tell there; the printed table shows the
// broadcast route's expiry as computed by the build.
//
// Stock ns-3 only (core, network, internet, csma, aodv):
//   cp aodv-lifetime-overflow.cc <ns-3>/scratch/
//   ./ns3 build scratch/aodv-lifetime-overflow
//   ./ns3 run --no-build scratch/aodv-lifetime-overflow

#include "ns3/aodv-module.h"
#include "ns3/core-module.h"
#include "ns3/csma-module.h"
#include "ns3/internet-module.h"
#include "ns3/network-module.h"

#include <iostream>

using namespace ns3;

int
main(int argc, char* argv[])
{
    double downAt = 1.0;
    double upAt = 35.0;
    CommandLine cmd(__FILE__);
    cmd.AddValue("downAt", "when node 1's CSMA interface goes down (s)", downAt);
    cmd.AddValue("upAt", "when it comes up again (s)", upAt);
    cmd.Parse(argc, argv);

    NodeContainer nodes;
    nodes.Create(2);
    CsmaHelper csma;
    NetDeviceContainer devices = csma.Install(nodes);

    AodvHelper aodv;
    InternetStackHelper stack;
    stack.SetRoutingHelper(aodv);
    stack.Install(nodes);
    Ipv4AddressHelper addresses;
    addresses.SetBase("10.0.0.0", "255.255.255.0");
    addresses.Assign(devices);

    Ptr<Ipv4> ipv4 = nodes.Get(1)->GetObject<Ipv4>();
    const uint32_t iface = ipv4->GetInterfaceForDevice(devices.Get(1));
    Simulator::Schedule(Seconds(downAt), &Ipv4::SetDown, ipv4, iface);
    Simulator::Schedule(Seconds(upAt), &Ipv4::SetUp, ipv4, iface);

    Ptr<OutputStreamWrapper> out = Create<OutputStreamWrapper>(&std::cout);
    Ipv4RoutingHelper::PrintRoutingTableAt(Seconds(upAt + 1), nodes.Get(1), out);
    Simulator::Stop(Seconds(upAt + 2));
    Simulator::Run();
    Simulator::Destroy();

    std::cout << "NS3-005 not-reproduced: interface up at " << Seconds(upAt).As(Time::S)
              << ", no overflow" << std::endl;
    return 0;
}
