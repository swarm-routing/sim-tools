// Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
// SPDX-License-Identifier: GPL-2.0-only

/*
 * Scripted node and link failures (--failures=<file>, ns3-tools#128): the
 * same failure at the same simulated time for every arm, on the harness's own
 * path (stock ns-3 only, no arm named).
 *
 * The file is swarm-routing/ns3-swarm-core#43's `<time> <node> <op>` lines,
 * plus link lines whose target is `a-b`:
 *
 *   # '#' starts a comment; blank lines are skipped
 *   40  2    shutdown     node ops: start | shutdown | crash
 *   60  2    start
 *   40  1-2  down         link ops: down | up (both directions)
 *
 * Mechanisms, the same for every arm:
 *  - a link down cuts the pair on the channel: FailureLossModel, appended to
 *    the tail of the run's YansWifiChannel loss chain, returns -1000 dBm
 *    between the two nodes (as RangePropagationLossModel does beyond its
 *    range), so neither decodes nor carrier-senses the other; while nothing
 *    is cut it returns its input unchanged;
 *  - a node shutdown takes the node's non-loopback IPv4 interfaces down
 *    (Ipv4::SetDown, so the routing protocol gets NotifyInterfaceDown, ns-3's
 *    own path) and cuts every link of the node on the channel, so an arm that
 *    forwards below IP (802.11s) loses it as a relay too;
 *  - a crash is a shutdown that also drops the node's dynamic ARP entries
 *    (neither permanent nor auto-generated) and the packets pending on them;
 *  - a start lifts the cut and brings up exactly the interfaces the shutdown
 *    or crash took down (Ipv4::SetUp, NotifyInterfaceUp).
 * A protocol that keeps state across an interface down keeps it across a
 * crash: wiping a protocol's own state needs its lifecycle (ns3-tools#150).
 *
 * Nothing here draws a random number, and the state is a vector per node and
 * an ordered set of links, read by lookup only, so a schedule is a pure
 * function of the file.
 */
#ifndef ROUTING_BENCH_FAILURE_SCHEDULE_H
#define ROUTING_BENCH_FAILURE_SCHEDULE_H

#include "ns3/ipv4-address.h"
#include "ns3/mobility-model.h"
#include "ns3/node-container.h"
#include "ns3/propagation-loss-model.h"
#include "ns3/ptr.h"
#include "ns3/yans-wifi-channel.h"

#include <cstddef>
#include <cstdint>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace ns3 {
namespace bench {

/// The most events one --failures file may hold (golden rule 7).
constexpr std::size_t kMaxFailureEvents = 10000;

/// One line of a --failures file.
struct FailureEvent {
    enum class Op { kStart, kShutdown, kCrash, kLinkDown, kLinkUp };
    double time = 0.0;  ///< simulated seconds
    uint32_t a = 0;     ///< the node, or the link's lower end
    uint32_t b = 0;     ///< the link's upper end (link ops only)
    Op op = Op::kStart;
    uint32_t line = 0;  ///< in the file, for messages
};

/// A parsed, checked --failures file.
struct FailureSchedule {
    std::string path;
    std::string sha256;  ///< of the file's bytes, 64 lowercase hex digits
    std::vector<FailureEvent> events;  ///< in time order; equal times in file order
};

/// Read and check `path` for a run of `nNodes` nodes and `simTime` seconds.
/// Aborts with `<path>:<line>: <what>` on a malformed line, an unknown op, an
/// id out of range, a time outside [0, simTime), a state violation (a
/// shutdown or crash of a node that is down, a start of one that is up, a
/// link down twice or up while up), or more than kMaxFailureEvents events.
FailureSchedule ReadFailureSchedule(const std::string& path, uint32_t nNodes, double simTime);

/// SHA-256 of `bytes`, as 64 lowercase hex digits.
std::string Sha256Hex(const std::string& bytes);

/// The channel side of a failure: cuts links (and the links of nodes that
/// are down) and passes every other signal through unchanged.
class FailureLossModel : public PropagationLossModel {
public:
    static TypeId GetTypeId();
    FailureLossModel() = default;

    /// The run's nodes: ids firstId .. firstId + n - 1 are indices 0 .. n-1.
    void SetNodes(uint32_t firstId, uint32_t n);
    void SetNodeCut(uint32_t node, bool cut);
    void SetLinkCut(uint32_t a, uint32_t b, bool cut);
    /// Whether nodes `a` and `b` cannot hear each other.
    bool IsCut(uint32_t a, uint32_t b) const;

private:
    double DoCalcRxPower(double txPowerDbm, Ptr<MobilityModel> a,
                         Ptr<MobilityModel> b) const override;
    int64_t DoAssignStreams(int64_t /*stream*/) override { return 0; }

    uint32_t m_firstId = 0;
    std::vector<bool> m_nodeCut;
    std::set<std::pair<uint32_t, uint32_t>> m_linkCut;  ///< (lower, upper)
    uint32_t m_cuts = 0;  ///< nodes plus links cut; 0 = pass everything
};

/// Apply `events` to this run: append a FailureLossModel to `channel`'s loss
/// chain and schedule every event at its time, in order. `addresses` are the
/// run's IPv4 addresses (for a crash's ARP lookups). Call once per run, after
/// the addresses are assigned and before Simulator::Run(); with no events it
/// still installs the (then inert) loss model.
void InstallFailures(const std::vector<FailureEvent>& events, const NodeContainer& nodes,
                     Ptr<YansWifiChannel> channel, const std::vector<Ipv4Address>& addresses);

}  // namespace bench
}  // namespace ns3

#endif  // ROUTING_BENCH_FAILURE_SCHEDULE_H
