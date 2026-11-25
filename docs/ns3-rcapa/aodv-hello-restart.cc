// Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
// SPDX-License-Identifier: GPL-2.0-only
//
// NS3-004 reproducer (swarm-routing/sim-tools#362, ns3-rcapa-aodv-hello-restart.md):
// stock AODV never restarts its hello timer once all of a node's AODV
// interfaces have gone down and come back up.
//
// Three static nodes in a line, 50 m apart, 802.11 ad hoc (stock defaults),
// stock AODV with EnableHello=true (HelloInterval 1 s). At --downAt (10 s)
// every non-loopback IPv4 interface of node 1 is set down, at --upAt (15 s)
// up again; the run ends at --time (30 s). The loopback stays up: it is not
// an AODV interface (AODV's NotifyInterfaceUp skips 127.0.0.1).
//
// A HELLO is counted on Ipv4L3Protocol's "Tx" trace: an IPv4 packet with
// TTL 1 to UDP port 654 whose AODV message is an RREP with hop count 0 and
// dst == origin (RFC 3561 6.9; aodv::RoutingProtocol::SendHello). The
// program prints one line per node and window, then a verdict:
//
//   HELLO node=N before=B down=D after=A
//   VERDICT reproduced|not-reproduced
//
// "reproduced" means node 1 sent no HELLO after --upAt while every other
// node did; the exit status is 0 either way.
//
// Stock ns-3 only (core, network, internet, wifi, mobility, aodv):
//   cp aodv-hello-restart.cc <ns-3>/scratch/
//   ./ns3 build scratch/aodv-hello-restart
//   ./ns3 run scratch/aodv-hello-restart

#include "ns3/aodv-module.h"
#include "ns3/aodv-packet.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/wifi-module.h"

#include <array>
#include <iostream>
#include <vector>

using namespace ns3;

namespace
{

constexpr uint16_t kAodvPort = 654;
constexpr uint32_t kNodes = 3;
constexpr uint32_t kRestartedNode = 1;

Time g_downAt;
Time g_upAt;
// per node: before down, while down, after up
std::vector<std::array<uint32_t, 3>> g_hellos(kNodes, {0, 0, 0});

bool
IsHello(Ptr<const Packet> p)
{
    Ptr<Packet> q = p->Copy();
    Ipv4Header ip;
    if (q->RemoveHeader(ip) == 0 || ip.GetProtocol() != UdpL4Protocol::PROT_NUMBER ||
        ip.GetTtl() != 1)
    {
        return false;
    }
    UdpHeader udp;
    q->RemoveHeader(udp);
    if (udp.GetDestinationPort() != kAodvPort)
    {
        return false;
    }
    aodv::TypeHeader type;
    q->RemoveHeader(type);
    if (!type.IsValid() || type.Get() != aodv::AODVTYPE_RREP)
    {
        return false;
    }
    aodv::RrepHeader rrep;
    q->RemoveHeader(rrep);
    return rrep.GetHopCount() == 0 && rrep.GetDst() == rrep.GetOrigin();
}

void
OnTx(uint32_t node, Ptr<const Packet> p, Ptr<Ipv4> /*ipv4*/, uint32_t /*interface*/)
{
    if (!IsHello(p))
    {
        return;
    }
    Time now = Simulator::Now();
    size_t window = now < g_downAt ? 0 : (now < g_upAt ? 1 : 2);
    g_hellos[node][window]++;
}

void
SetInterfaces(Ptr<Node> node, bool up)
{
    Ptr<Ipv4> ipv4 = node->GetObject<Ipv4>();
    for (uint32_t i = 1; i < ipv4->GetNInterfaces(); ++i) // 0 is the loopback
    {
        if (up)
        {
            ipv4->SetUp(i);
        }
        else
        {
            ipv4->SetDown(i);
        }
    }
}

} // namespace

int
main(int argc, char* argv[])
{
    double downAt = 10;
    double upAt = 15;
    double stop = 30;
    CommandLine cmd(__FILE__);
    cmd.AddValue("downAt", "time (s) node 1's interfaces go down", downAt);
    cmd.AddValue("upAt", "time (s) they come back up", upAt);
    cmd.AddValue("time", "simulated time (s)", stop);
    cmd.Parse(argc, argv);
    g_downAt = Seconds(downAt);
    g_upAt = Seconds(upAt);

    NodeContainer nodes;
    nodes.Create(kNodes);

    MobilityHelper mobility;
    mobility.SetPositionAllocator("ns3::GridPositionAllocator",
                                  "MinX",
                                  DoubleValue(0),
                                  "MinY",
                                  DoubleValue(0),
                                  "DeltaX",
                                  DoubleValue(50),
                                  "GridWidth",
                                  UintegerValue(kNodes),
                                  "LayoutType",
                                  StringValue("RowFirst"));
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(nodes);

    WifiHelper wifi;
    YansWifiPhyHelper phy;
    YansWifiChannelHelper channel = YansWifiChannelHelper::Default();
    phy.SetChannel(channel.Create());
    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");
    NetDeviceContainer devices = wifi.Install(phy, mac, nodes);

    AodvHelper aodv;
    aodv.Set("EnableHello", BooleanValue(true));
    InternetStackHelper internet;
    internet.SetRoutingHelper(aodv);
    internet.Install(nodes);
    Ipv4AddressHelper addresses;
    addresses.SetBase("10.0.0.0", "255.255.255.0");
    addresses.Assign(devices);

    for (uint32_t n = 0; n < kNodes; ++n)
    {
        nodes.Get(n)->GetObject<Ipv4L3Protocol>()->TraceConnectWithoutContext(
            "Tx",
            MakeBoundCallback(&OnTx, n));
    }

    Ptr<Node> restarted = nodes.Get(kRestartedNode);
    Simulator::Schedule(g_downAt, &SetInterfaces, restarted, false);
    Simulator::Schedule(g_upAt, &SetInterfaces, restarted, true);

    Simulator::Stop(Seconds(stop));
    Simulator::Run();
    Simulator::Destroy();

    bool othersSend = true;
    for (uint32_t n = 0; n < kNodes; ++n)
    {
        std::cout << "HELLO node=" << n << " before=" << g_hellos[n][0]
                  << " down=" << g_hellos[n][1] << " after=" << g_hellos[n][2] << "\n";
        if (n != kRestartedNode && g_hellos[n][2] == 0)
        {
            othersSend = false;
        }
    }
    bool reproduced =
        g_hellos[kRestartedNode][0] > 0 && g_hellos[kRestartedNode][2] == 0 && othersSend;
    std::cout << "VERDICT " << (reproduced ? "reproduced" : "not-reproduced") << "\n";
    return 0;
}
