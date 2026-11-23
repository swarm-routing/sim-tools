// SPDX-License-Identifier: GPL-2.0-only
// Copyright (C) 2026 Daniel Henrique Joppi

/**
 * Unit tests for the routing-bench arm registry (ADR-0027, #766):
 * registration, lookup, the rejection of a duplicate or empty name, the
 * optional hooks' defaults, and the stock arms' names and stream-free hwmp
 * arm; that an arm's rows do not depend on the arms run before it
 * (--isolateArms, ns3-tools#198); and the ICMP no-route guard of the aodv arm
 * (NS3-001, #238): nsnam/ns-3-dev!3101's own test, and a partitioned AODV
 * network that livelocks on ns-3.49 without the guard and runs with it.
 */

#include "ns3/aodv-helper.h"
#include "ns3/aodv-routing-protocol.h"
#include "ns3/boolean.h"
#include "ns3/icmp-error-guard-helper.h"
#include "ns3/icmpv4.h"
#include "ns3/inet-socket-address.h"
#include "ns3/internet-stack-helper.h"
#include "ns3/ipv4-address-helper.h"
#include "ns3/ipv4-l3-protocol.h"
#include "ns3/ipv4-raw-socket-factory.h"
#include "ns3/ipv4-static-routing-helper.h"
#include "ns3/ipv4.h"
#include "ns3/routing-bench-arm.h"
#include "ns3/simple-channel.h"
#include "ns3/simple-net-device-helper.h"
#include "ns3/simple-net-device.h"
#include "ns3/simulator.h"
#include "ns3/stock-arms.h"
#include "ns3/test.h"
#include "ns3/udp-socket-factory.h"
#include "ns3/uinteger.h"

#include <fcntl.h>
#include <sys/wait.h>
#include <unistd.h>

#include <array>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

// TestSuite/TestCase enums became scoped (enum class) in ns-3.42 and the
// unscoped aliases were removed in ns-3.47 (the oracle module's pattern).
#ifdef ROUTING_BENCH_NS3_SCOPED_TEST_ENUMS
#define BENCH_TEST_TYPE_UNIT TestSuite::Type::UNIT
#define BENCH_TEST_QUICK TestCase::Duration::QUICK
#else
#define BENCH_TEST_TYPE_UNIT UNIT
#define BENCH_TEST_QUICK TestCase::QUICK
#endif

// Does this ns-3 have Ipv4L3Protocol::SendIcmpNoRoute (new in 3.49, NS3-001)?
// A non-numeric NS3_VER (3-dev) has it.
#if defined(ROUTING_BENCH_NS3_MINOR) && ROUTING_BENCH_NS3_MINOR < 49
constexpr bool kIcmpNoRoute = false;
#else
constexpr bool kIcmpNoRoute = true;
#endif

// A --coverage build's counters, written before the child's _exit (strong, and
// only in a coverage build: see model/arm-isolation.cc).
#ifdef ROUTING_BENCH_GCOV_DUMP
extern "C" void __gcov_dump();
#endif

namespace ns3 {
namespace bench {
namespace {

class FakeArm : public Arm {
public:
    std::string Name() const override { return "fake"; }
    void InstallRouting(InternetStackHelper&, RunContext&) override {}
    int64_t AssignStreams(RunContext&, int64_t) override { return 3; }
};

Ptr<Arm> MakeFakeArm() { return Create<FakeArm>(); }

// ns3-tools#198. Stock AODV, with a second interface on every node: a
// SimpleNetDevice alone on its own channel, so it carries nothing, but AODV
// opens sockets on it, and its RREQ loop draws one jitter per socket in the
// order of std::map<Ptr<Socket>, ...>, which is heap-address order. Which
// draw the Wi-Fi interface gets then depends on the heap: the leo-walker and
// isl-grid shape (swarm-routing/AntHocNet#1039, #362), on the harness's
// one-radio scenario.
class SpareIfAodvArm : public Arm {
public:
    std::string Name() const override { return "aodv-spare-if"; }
    void InstallRouting(InternetStackHelper& internet, RunContext&) override {
        internet.SetRoutingHelper(m_aodv);
    }
    int64_t AssignStreams(RunContext& run, int64_t stream) override {
        return m_aodv.AssignStreams(run.nodes, stream);
    }
    void AfterAddresses(RunContext& run, const Ipv4InterfaceContainer&) override {
        for (uint32_t i = 0; i < run.nodes.GetN(); ++i) {
            Ptr<Node> node = run.nodes.Get(i);
            Ptr<SimpleNetDevice> dev = CreateObject<SimpleNetDevice>();
            dev->SetChannel(CreateObject<SimpleChannel>());
            dev->SetAddress(Mac48Address::ConvertFrom(Mac48Address::Allocate()));
            node->AddDevice(dev);
            Ptr<Ipv4> ipv4 = node->GetObject<Ipv4>();
            const uint32_t ifIndex = ipv4->AddInterface(dev);
            ipv4->AddAddress(ifIndex,
                             Ipv4InterfaceAddress(Ipv4Address(0xac100001u + (i << 8)),
                                                  Ipv4Mask("255.255.255.0")));
            ipv4->SetUp(ifIndex);
        }
    }

private:
    AodvHelper m_aodv;
};

// ns3-tools#198: stock AODV that also leaves the heap in another state, the
// way an earlier arm's own allocations do (AntHocNet#1035's function-local
// static): it allocates blocks of many sizes, frees two in three and keeps
// the rest for the life of the process.
class HeapChurnArm : public Arm {
public:
    std::string Name() const override { return "heap-churn"; }
    void InstallRouting(InternetStackHelper& internet, RunContext&) override {
        static std::vector<char*> kept;
        std::vector<char*> blocks;
        for (uint32_t k = 0; k < 6000; ++k) blocks.push_back(new char[16 + (k % 256) * 8]);
        for (std::size_t k = 0; k < blocks.size(); ++k) {
            if (k % 3 == 0)
                kept.push_back(blocks[k]);
            else
                delete[] blocks[k];
        }
        internet.SetRoutingHelper(m_aodv);
    }
    int64_t AssignStreams(RunContext& run, int64_t stream) override {
        return m_aodv.AssignStreams(run.nodes, stream);
    }

private:
    AodvHelper m_aodv;
};

// NS3-002 for DSDV (#301). Stock DSDV, with the nodes also joined in a ring
// of wired links (SimpleNetDevice pairs, one SimpleChannel per link), so
// every node has three active interfaces. DSDV keeps one socket per
// interface in std::map<Ptr<Socket>, Ipv4InterfaceAddress> and sends each
// update on them in that map's order, heap-address order; it draws no random
// number inside those loops, so what the heap can change is the order of the
// sends, and with it the order of the simultaneous receptions they cause.
class RingDsdvArm : public Arm {
public:
    std::string Name() const override { return "dsdv-ring"; }
    void InstallRouting(InternetStackHelper& internet, RunContext& run) override {
        m_dsdv->InstallRouting(internet, run);
    }
    int64_t AssignStreams(RunContext& run, int64_t stream) override {
        return m_dsdv->AssignStreams(run, stream);
    }
    void AfterAddresses(RunContext& run, const Ipv4InterfaceContainer&) override {
        const uint32_t n = run.nodes.GetN();
        // Buffering off: with it, LookForQueuedPackets() uses the route to a
        // next hop without checking that LookupRoute() found one, and on these
        // nodes a next hop can be an address with no entry of its own, so a
        // queued packet goes out on an empty route (NS_ASSERT "interface >= 0"
        // in Ipv4L3Protocol::SendRealOut). That is NS3-003 (docs/ns3-bugs.md);
        // this test is about the send order.
        for (uint32_t k = 0; k < n; ++k) {
            run.nodes.Get(k)
                ->GetObject<Ipv4>()
                ->GetRoutingProtocol()
                ->SetAttribute("EnableBuffering", BooleanValue(false));
        }
        for (uint32_t k = 0; k < n; ++k) {
            Ptr<SimpleChannel> link = CreateObject<SimpleChannel>();
            for (uint32_t end = 0; end < 2; ++end) {
                Ptr<Node> node = run.nodes.Get((k + end) % n);
                Ptr<SimpleNetDevice> dev = CreateObject<SimpleNetDevice>();
                dev->SetChannel(link);
                dev->SetAddress(Mac48Address::ConvertFrom(Mac48Address::Allocate()));
                node->AddDevice(dev);
                Ptr<Ipv4> ipv4 = node->GetObject<Ipv4>();
                const uint32_t ifIndex = ipv4->AddInterface(dev);
                ipv4->AddAddress(ifIndex,
                                 Ipv4InterfaceAddress(Ipv4Address(0xac110001u + (k << 8) + end),
                                                      Ipv4Mask("255.255.255.0")));
                ipv4->SetUp(ifIndex);
            }
        }
    }

private:
    Ptr<Arm> m_dsdv = Registry().Make("dsdv");
};

Ptr<Arm> MakeSpareIfAodvArm() { return Create<SpareIfAodvArm>(); }
Ptr<Arm> MakeRingDsdvArm() { return Create<RingDsdvArm>(); }
Ptr<Arm> MakeHeapChurnArm() { return Create<HeapChurnArm>(); }

// The harness run once per command line, each in a child process, every
// child forked from this process in the same state (#211). Every argument
// vector, temporary file and status slot is made before the first fork, and
// nothing is allocated between two forks, so each child enters RunHarness
// with the same heap whatever its arguments, as routing-compare does from
// main(), whose argv lives on the stack. --isolateArms forks its workers from
// the state RunHarness is entered with: when the test built one child's argv,
// read its output and only then forked the next, each later child started
// from another heap, and an arm's rows could differ between "alone" and
// "after other arms" for that reason alone (seen under the bare test runner
// and beside AntHocNet's arm modules, not under test.py).
struct ChildRun {
    std::string output;
    int status = -1;
};

std::vector<ChildRun> RunHarnessInChildren(const std::vector<std::vector<std::string>>& runs) {
    const std::size_t n = runs.size();
    std::vector<std::vector<std::string>> words(n);
    std::vector<std::vector<char*>> argvs(n);
    std::vector<std::array<char, 40>> paths(n);
    std::vector<int> fds(n, -1);
    std::vector<int> statuses(n, -1);
    for (std::size_t i = 0; i < n; ++i) {
        words[i].push_back("routing-compare");
        words[i].insert(words[i].end(), runs[i].begin(), runs[i].end());
        for (std::string& w : words[i]) argvs[i].push_back(w.data());
        argvs[i].push_back(nullptr);
        std::snprintf(paths[i].data(), paths[i].size(), "/tmp/routing-bench-isolation-XXXXXX");
        fds[i] = mkstemp(paths[i].data());
        NS_ABORT_MSG_IF(fds[i] < 0, "mkstemp failed");
    }
    std::cout.flush();
    std::fflush(nullptr);
    // From here to the last waitpid: no allocation in this process.
    for (std::size_t i = 0; i < n; ++i) {
        const pid_t pid = fork();
        if (pid < 0) break;  // statuses[i] stays -1
        if (pid == 0) {
            dup2(fds[i], 1);
            const int rc =
                RunHarness(static_cast<int>(words[i].size()), argvs[i].data(), "routing-compare");
            std::cout.flush();
            std::fflush(nullptr);
#ifdef ROUTING_BENCH_GCOV_DUMP
            __gcov_dump();
#endif
            _exit(rc);
        }
        waitpid(pid, &statuses[i], 0);
    }
    std::vector<ChildRun> out(n);
    for (std::size_t i = 0; i < n; ++i) {
        close(fds[i]);
        std::ifstream in(paths[i].data());
        std::stringstream text;
        text << in.rdbuf();
        std::remove(paths[i].data());
        out[i].output = text.str();
        out[i].status = statuses[i];
    }
    return out;
}

// Every line that starts with `marker`.
std::string MarkerLines(const std::string& output, const std::string& marker) {
    std::istringstream in(output);
    std::string line;
    std::string lines;
    while (std::getline(in, line))
        if (line.rfind(marker, 0) == 0) lines += line + "\n";
    return lines;
}

// One arm's per-seed result rows (everything printed per arm and seed except
// ##PERF##, which is cost, not result).
std::string ArmRows(const std::string& output, const std::string& arm) {
    std::istringstream in(output);
    std::string line;
    std::string rows;
    for (const char* marker : {"##RUN## ", "##GOODPUT## ", "##ROUTE## ", "##HOLD## "}) {
        in.clear();
        in.seekg(0);
        while (std::getline(in, line)) {
            if (line.rfind(marker, 0) != 0) continue;
            std::istringstream f(line);
            std::string m, seed, name;
            f >> m >> seed >> name;
            if (name == arm) rows += line + "\n";
        }
    }
    return rows;
}

/// A measurement no hook may touch: every count is zero.
class NullMeasurement : public Measurement {
public:
    uint64_t ControlPackets() const override { return 0; }
    uint64_t ControlBytes() const override { return 0; }
    double DeliveredDataBytes() const override { return 0.0; }
    void TrackReinjectionIdentity() override {}
    void MacReinjectedData(const Ipv4Header&, Ptr<const Packet>) override {}
    void ArpReinjectedData(const Ipv4Header&, Ptr<const Packet>) override {}
    uint64_t ReinjectedData() const override { return 0; }
    void TrackPacketFate() override {}
    void TrackPendingQueue() override {}
    void MeshManagementEnqueue(Ptr<const BENCH_WIFI_MPDU>) override {}
    void MeshDataEnqueue(uint32_t, Ptr<const BENCH_WIFI_MPDU>) override {}
    uint64_t MeshPeeringFrames() const override { return 0; }
    uint64_t MeshBeacons() const override { return 0; }
    void TypedControlTx(uint8_t, uint8_t, bool) override {}
    void TypedControlRx(uint8_t, uint8_t) override {}
    uint64_t TypedControlTxCount(uint8_t) const override { return 0; }
    uint64_t TypedControlRxCount(uint8_t) const override { return 0; }
};

}  // namespace

class RegistryRulesTest : public TestCase {
public:
    RegistryRulesTest() : TestCase("arm registry: add, lookup, duplicate and empty names") {}

private:
    void DoRun() override {
        ArmRegistry r;
        NS_TEST_ASSERT_MSG_EQ(r.Names().empty(), true, "starts empty");
        NS_TEST_ASSERT_MSG_EQ(r.Add("fake", "a test arm", &MakeFakeArm), true, "first add");
        NS_TEST_ASSERT_MSG_EQ(r.Add("fake", "again", &MakeFakeArm), false, "duplicate refused");
        NS_TEST_ASSERT_MSG_EQ(r.Summary("fake"), "a test arm", "duplicate changed nothing");
        NS_TEST_ASSERT_MSG_EQ(r.Add("", "no name", &MakeFakeArm), false, "empty name refused");
        NS_TEST_ASSERT_MSG_EQ(r.Add("null", "no factory", nullptr), false, "null factory refused");
        NS_TEST_ASSERT_MSG_EQ(r.Names().size(), 1u, "one arm");

        NS_TEST_ASSERT_MSG_EQ(r.Has("fake"), true, "found");
        NS_TEST_ASSERT_MSG_EQ(r.Has("aodv"), false, "absent");
        NS_TEST_ASSERT_MSG_EQ(r.Make("aodv"), Ptr<Arm>(), "unknown name gives no arm");
        Ptr<Arm> a = r.Make("fake");
        Ptr<Arm> b = r.Make("fake");
        NS_TEST_ASSERT_MSG_NE(a, Ptr<Arm>(), "known name gives an arm");
        NS_TEST_ASSERT_MSG_NE(a, b, "a fresh arm for every run");
        RunContext run;
        NS_TEST_ASSERT_MSG_EQ(a->AssignStreams(run, 0), 3, "the arm's own hook");
    }
};

class DefaultHooksTest : public TestCase {
public:
    DefaultHooksTest()
        : TestCase("arm hooks: an arm that overrides none of the optional hooks changes nothing") {}

private:
    void DoRun() override {
        Ptr<Arm> arm = MakeFakeArm();
        RunContext run;
        NullMeasurement m;
        std::ostringstream out;
        arm->Configure(run);
        arm->Validate(run);
        arm->EmitConfig(out);
        NS_TEST_ASSERT_MSG_EQ(arm->ProvidesDevices(), false, "ad-hoc Wi-Fi by default");
        NetDeviceContainer radios;
        DeviceRequest req{};
        NS_TEST_ASSERT_MSG_EQ(arm->InstallDevices(run, req, radios).GetN(), 0u, "no devices");
        NS_TEST_ASSERT_MSG_EQ(radios.GetN(), 0u, "no radios");
        NS_TEST_ASSERT_MSG_EQ(arm->AssignDeviceStreams(run, 7), 0, "no device streams");
        arm->AfterStack(run);
        arm->ConnectTraces(run, m);
        arm->AfterAddresses(run, Ipv4InterfaceContainer());
        NS_TEST_ASSERT_MSG_EQ(arm->StartReplay(run, ReplayRequest(), nullptr, nullptr), false,
                              "no replay");
        arm->FinishReplay(1, 1, 100.0);
        RunCounts c;
        c.txPackets = 10;
        c.dropRoute = 2;
        arm->AdjustCounts(run, c);
        NS_TEST_ASSERT_MSG_EQ(c.txPackets, 10u, "counts untouched");
        NS_TEST_ASSERT_MSG_EQ(c.dropRoute, 2u, "counts untouched");
        arm->EmitRunNote(run, m, out);
        DropDetail d;
        arm->FillDropDetail(run, d);
        NS_TEST_ASSERT_MSG_EQ(d.holdCauses, false, "no drop detail");
        std::vector<HoldTime> hold;
        NS_TEST_ASSERT_MSG_EQ(arm->CollectHoldTimes(run, hold), false, "no pending queue");
        NS_TEST_ASSERT_MSG_EQ(hold.empty(), true, "no hold times");
        arm->AppendDiag(run, m, out);
        arm->EmitDiagnostics(run, m, 0.0, out);
        arm->Check(run, m);
        NS_TEST_ASSERT_MSG_EQ(out.str(), "", "the default hooks print nothing");
    }
};

class StockArmsTest : public TestCase {
public:
    StockArmsTest() : TestCase("stock arms: aodv, dsdv, hwmp and olsr register once") {}

private:
    void DoRun() override {
        // The process-wide registry: other suites in this binary may have
        // registered already, so register only if absent.
        if (!Registry().Has("aodv")) RegisterStockArms();
        const std::vector<std::string> want{"aodv", "dsdv", "hwmp", "olsr"};
        for (const auto& name : want) {
            NS_TEST_ASSERT_MSG_EQ(Registry().Has(name), true, name << " registered");
            Ptr<Arm> arm = Registry().Make(name);
            NS_TEST_ASSERT_MSG_EQ(arm->Name(), name, "the arm answers to its token");
        }
        // hwmp's streams are pinned with the mesh devices; static routing
        // takes none (#708).
        RunContext run;
        NS_TEST_ASSERT_MSG_EQ(Registry().Make("hwmp")->AssignStreams(run, 100), 0,
                              "hwmp takes no routing streams");
        // An olsr arm with no refusals leaves the counts alone.
        RunCounts c;
        c.txPackets = 10;
        c.dropRoute = 2;
        Registry().Make("olsr")->AdjustCounts(run, c);
        NS_TEST_ASSERT_MSG_EQ(c.txPackets, 10u, "no refusals, no change");
        NS_TEST_ASSERT_MSG_EQ(c.dropRoute, 2u, "no refusals, no change");
    }
};

class ArmIsolationTest : public TestCase {
public:
    ArmIsolationTest()
        : TestCase("isolateArms: an arm's rows do not depend on the arms run before it (#198)") {}

private:
    void DoRun() override {
        if (!Registry().Has("aodv")) RegisterStockArms();
        if (!Registry().Has("aodv-spare-if")) {
            RegisterArm("aodv-spare-if", "test: AODV with a second, idle interface",
                        &MakeSpareIfAodvArm);
        }
        if (!Registry().Has("heap-churn")) {
            RegisterArm("heap-churn", "test: AODV that reshapes the heap", &MakeHeapChurnArm);
        }
        if (!Registry().Has("dsdv-ring")) {
            RegisterArm("dsdv-ring", "test: DSDV with a wired ring as well", &MakeRingDsdvArm);
        }
        const std::vector<std::string> base{"--scenario=paper", "--nNodes=8", "--time=8",
                                            "--runs=2", "--perf=0"};
        const auto with = [&base](std::vector<std::string> extra) {
            std::vector<std::string> a = base;
            a.insert(a.end(), extra.begin(), extra.end());
            return a;
        };
        const std::vector<std::string> arms{"aodv-spare-if", "aodv", "olsr", "dsdv"};
        // hwmp, the fourth stock arm, brings its own 802.11s devices and needs
        // 802.11a (#708). Its multi-arm run spells -protocols with one dash, a
        // spelling CommandLine reads too: the worker replaces it.
        const std::vector<std::string> mesh{"--standard=80211a", "--rateManager=constant6"};
        auto meshArgs = [&with, &mesh](const std::string& protocols) {
            std::vector<std::string> a = with(mesh);
            a.push_back(protocols);
            return a;
        };
        // Every run is made up front and forked from one state (#211).
        std::vector<std::vector<std::string>> runs;
        // 0: every arm after another arm and after a reshaped heap, in one run.
        runs.push_back(with({"--protocols=heap-churn,olsr,aodv-spare-if,aodv,dsdv"}));
        for (const std::string& arm : arms) runs.push_back(with({"--protocols=" + arm}));  // 1-4
        runs.push_back(meshArgs("--protocols=hwmp"));                                      // 5
        runs.push_back(meshArgs("-protocols=heap-churn,aodv,hwmp"));                       // 6
        // 7, 8: the same comparison with --isolateArms=0, reported below.
        runs.push_back(with({"--isolateArms=0", "--protocols=aodv-spare-if"}));
        runs.push_back(with({"--isolateArms=0", "--protocols=heap-churn,aodv-spare-if"}));
        // 9, 10 (#218): the cross-arm rows of hwmp and olsr, isolated and in one
        // process. The hwmp worker numbers its address types in another order.
        runs.push_back(meshArgs("--protocols=hwmp,olsr"));
        runs.push_back(meshArgs("--protocols=hwmp,olsr"));
        runs.back().push_back("--isolateArms=0");
        // 11-13 (#301): dsdv-ring in one process, alone, after one heap-churn
        // arm and after it and two more arms: three levels of reshaping.
        runs.push_back(with({"--isolateArms=0", "--protocols=dsdv-ring"}));
        runs.push_back(with({"--isolateArms=0", "--protocols=heap-churn,dsdv-ring"}));
        runs.push_back(with({"--isolateArms=0", "--protocols=heap-churn,olsr,aodv,dsdv-ring"}));
        const std::vector<ChildRun> res = RunHarnessInChildren(runs);
        for (std::size_t i = 0; i < res.size(); ++i) {
            NS_TEST_ASSERT_MSG_EQ(res[i].status, 0, "run " << i << " exits cleanly");
        }
        const std::string& after = res[0].output;
        for (std::size_t k = 0; k < arms.size(); ++k) {
            const std::string& arm = arms[k];
            const std::string rows = ArmRows(res[1 + k].output, arm);
            NS_TEST_ASSERT_MSG_NE(rows.find("##RUN## 2 " + arm), std::string::npos,
                                  arm << " printed its rows");
            NS_TEST_ASSERT_MSG_EQ(ArmRows(after, arm), rows,
                                  arm << ": same rows alone and after other arms");
        }
        const std::string hwmpRows = ArmRows(res[5].output, "hwmp");
        NS_TEST_ASSERT_MSG_NE(hwmpRows.find("##RUN## 2 hwmp"), std::string::npos,
                              "hwmp printed its rows");
        NS_TEST_ASSERT_MSG_EQ(ArmRows(res[6].output, "hwmp"), hwmpRows,
                              "hwmp: same rows alone and after other arms");
        // #218: ##MATCH## and ##COMMON## span arms, so the parent compares
        // keys from different workers; they must be what one process prints.
        for (const char* marker : {"##MATCH## ", "##COMMON## "}) {
            const std::string iso = MarkerLines(res[9].output, marker);
            NS_TEST_ASSERT_MSG_NE(iso, "", "hwmp,olsr isolated printed " << marker << "rows");
            NS_TEST_ASSERT_MSG_EQ(iso, MarkerLines(res[10].output, marker),
                                  "hwmp,olsr: " << marker << "rows isolated = in one process");
        }
        // The same with the reshaping in the arm's own process is not this
        // test's business: --isolateArms isolates arms, not code. What it
        // fixes shows with it off: the aodv-spare-if rows after heap-churn
        // differ from the rows alone on glibc's allocator (not under ASan,
        // which does not reuse freed blocks soon), so that half is reported,
        // not asserted.
        const std::string& inAlone = res[7].output;
        const std::string& inAfter = res[8].output;
        std::clog << "isolateArms=0: aodv-spare-if after heap-churn "
                  << (ArmRows(inAlone, "aodv-spare-if") == ArmRows(inAfter, "aodv-spare-if")
                          ? "matches"
                          : "DIFFERS from")
                  << " its rows alone (#198)\n";
        const std::string dsdvAlone = ArmRows(res[11].output, "dsdv-ring");
        NS_TEST_ASSERT_MSG_NE(dsdvAlone.find("##RUN## 2 dsdv-ring"), std::string::npos,
                              "dsdv-ring printed its rows");
        std::clog << "isolateArms=0: dsdv-ring alone (#301):\n"
                  << MarkerLines(dsdvAlone, "##RUN## ");
        for (std::size_t i : {std::size_t{12}, std::size_t{13}}) {
            const std::string rows = ArmRows(res[i].output, "dsdv-ring");
            std::clog << "isolateArms=0: dsdv-ring after "
                      << (i == 12 ? "heap-churn" : "heap-churn,olsr,aodv") << " "
                      << (rows == dsdvAlone ? "matches" : "DIFFERS from")
                      << " its rows alone (#301)\n";
            if (rows != dsdvAlone) std::clog << "alone:\n" << dsdvAlone << "after:\n" << rows;
        }
    }
};

namespace {

// The router's Destination Unreachable messages, as the source's raw ICMP
// socket sees them.
struct IcmpSink {
    uint32_t unreach = 0;
    Ipv4Address from;

    void Receive(Ptr<Socket> s) {
        Address addr;
        while (Ptr<Packet> p = s->RecvFrom(0xffffffff, 0, addr)) {
            Ipv4Header ip;
            if (p->GetSize() < ip.GetSerializedSize()) continue;
            p->RemoveHeader(ip);
            if (ip.GetProtocol() != 1 || p->GetSize() < 4) continue;
            Icmpv4Header icmp;
            p->RemoveHeader(icmp);
            if (icmp.GetType() == Icmpv4Header::ICMPV4_DEST_UNREACH) {
                ++unreach;
                from = ip.GetSource();
            }
        }
    }
};

void SendIcmpOfType(Ptr<Socket> s, uint8_t type) {
    Ptr<Packet> p = Create<Packet>(8);
    Icmpv4Header icmp;
    icmp.SetType(type);
    icmp.SetCode(0);
    p->AddHeader(icmp);
    s->SendTo(p, 0, InetSocketAddress(Ipv4Address("10.9.9.9"), 0));
}

}  // namespace

// NS3-001: nsnam/ns-3-dev!3101's change to ns-3's ipv4-icmp-no-route test,
// with the router's routing (static, so any protocol does) behind the guard.
//   A (10.0.0.1) ---- (10.0.0.2) R (10.0.1.1) ---- (nothing)
// R forwards and has no route to 10.9.9.0/24. A sends one ICMP message of a
// type to 10.9.9.9: an Echo Request (8) is answered with one net unreachable
// from R, an ICMP error (3, 4, 5, 11, 12) with none. Before ns-3.49 there is
// no no-route error at all, so the Echo Request gets none either.
class IcmpNoRouteGuardTest : public TestCase {
public:
    IcmpNoRouteGuardTest()
        : TestCase("icmp guard: ns-3-dev!3101's no-route test, router guarded (NS3-001)") {}

private:
    void DoRun() override {
        for (uint8_t type : {8, 3, 4, 5, 11, 12}) RunType(type);
    }

    void RunType(uint8_t type) {
        Ptr<Node> a = CreateObject<Node>();
        Ptr<Node> r = CreateObject<Node>();
        SimpleNetDeviceHelper link;
        link.SetNetDevicePointToPointMode(true);
        NetDeviceContainer net0 = link.Install(NodeContainer(a, r));
        NetDeviceContainer net1 = link.Install(NodeContainer(r));

        InternetStackHelper plain;
        plain.Install(a);
        IcmpErrorGuardHelper guard{Ipv4StaticRoutingHelper()};
        InternetStackHelper guarded;
        guarded.SetRoutingHelper(guard);
        guarded.Install(r);

        auto addIf = [](Ptr<Node> n, Ptr<NetDevice> d, const char* addr) {
            Ptr<Ipv4> ipv4 = n->GetObject<Ipv4>();
            const uint32_t i = ipv4->AddInterface(d);
            ipv4->AddAddress(i, Ipv4InterfaceAddress(Ipv4Address(addr), Ipv4Mask("255.255.255.0")));
            ipv4->SetUp(i);
        };
        addIf(a, net0.Get(0), "10.0.0.1");
        addIf(r, net0.Get(1), "10.0.0.2");
        addIf(r, net1.Get(0), "10.0.1.1");
        r->GetObject<Ipv4>()->SetAttribute("IpForward", BooleanValue(true));
        Ipv4StaticRoutingHelper().GetStaticRouting(a->GetObject<Ipv4>())->SetDefaultRoute(
            Ipv4Address("10.0.0.2"), 1);

        IcmpSink sink;
        Ptr<SocketFactory> raw = a->GetObject<Ipv4RawSocketFactory>();
        Ptr<Socket> rx = raw->CreateSocket();
        rx->SetAttribute("Protocol", UintegerValue(1));
        rx->Bind(InetSocketAddress(Ipv4Address::GetAny(), 0));
        rx->SetRecvCallback(MakeCallback(&IcmpSink::Receive, &sink));
        Ptr<Socket> tx = raw->CreateSocket();
        tx->SetAttribute("Protocol", UintegerValue(1));
        tx->Bind(InetSocketAddress(Ipv4Address("10.0.0.1"), 0));

        Simulator::ScheduleWithContext(a->GetId(), Seconds(1), &SendIcmpOfType, tx, type);
        Simulator::Stop(Seconds(5));
        Simulator::Run();
        Simulator::Destroy();

        const IcmpErrorGuardCounters& k = guard.Counters();
        const bool echo = type == 8;
        NS_TEST_ASSERT_MSG_EQ(sink.unreach, (echo && kIcmpNoRoute) ? 1u : 0u,
                              "type " << +type << ": net unreachable messages A received");
        if (sink.unreach) {
            NS_TEST_ASSERT_MSG_EQ(sink.from, Ipv4Address("10.0.0.2"), "the error is R's");
        }
        // The guard sees the failure on every release; it has an error to stop
        // only where ns-3 builds one.
        NS_TEST_ASSERT_MSG_EQ(k.noRoute, 1u, "type " << +type << ": one no-route failure");
        NS_TEST_ASSERT_MSG_EQ(k.allowed, echo ? 1u : 0u, "type " << +type << ": allowed");
        NS_TEST_ASSERT_MSG_EQ(k.armed[IcmpErrorGuardCounters::ICMP_ERROR], echo ? 0u : 1u,
                              "type " << +type << ": classified as an ICMP error");
        NS_TEST_ASSERT_MSG_EQ(k.Vetoed(), (!echo && kIcmpNoRoute) ? 1u : 0u,
                              "type " << +type << ": errors the guard stopped");
    }
};

namespace {

// A partitioned AODV network, the NS3-001 trigger in miniature: nodes 0 and 1
// share one channel, node 2 is alone on its own, all in 10.1.1.0/24. Node 0
// sends 100 packets/s of UDP to node 1 (delivered) and as many to node 2 (no
// route ever): AODV's request queue fills, and on ns-3.49 each drop raises
// an ICMP error that AODV defers into the same full queue, at one instant.
// A sink on Ipv4L3Protocol's Drop trace stops the simulator once one
// instant has seen 10000 route-error drops (a livelock, as simulated time
// stands still), so the test ends either way.
struct PartitionRun {
    uint32_t delivered = 0;
    bool livelock = false;
    Time end;
    IcmpErrorGuardCounters counters;
};

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

PartitionRun RunPartition(bool guarded) {
    NodeContainer nodes;
    nodes.Create(3);
    SimpleNetDeviceHelper link;
    NetDeviceContainer devs = link.Install(NodeContainer(nodes.Get(0), nodes.Get(1)));
    devs.Add(link.Install(nodes.Get(2)));

    AodvHelper aodv;
    IcmpErrorGuardHelper guard{aodv};
    InternetStackHelper internet;
    if (guarded) {
        internet.SetRoutingHelper(guard);
    } else {
        internet.SetRoutingHelper(aodv);
    }
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
    PartitionRun out;
    Ptr<Socket> rx = Socket::CreateSocket(nodes.Get(1), UdpSocketFactory::GetTypeId());
    rx->Bind(InetSocketAddress(Ipv4Address::GetAny(), 9));
    rx->SetRecvCallback(MakeBoundCallback(&CountRx, &out.delivered));
    Ptr<Socket> tx = Socket::CreateSocket(nodes.Get(0), UdpSocketFactory::GetTypeId());
    tx->Bind();
    for (uint32_t dst : {1u, 2u}) {
        Simulator::ScheduleWithContext(nodes.Get(0)->GetId(), Seconds(1), &SendUdp, tx,
                                       ifs.GetAddress(dst), 900u);
    }
    Simulator::Stop(Seconds(15));
    Simulator::Run();
    out.livelock = watch.fired;
    out.end = Simulator::Now();
    out.counters = guard.Counters();
    Simulator::Destroy();
    return out;
}

}  // namespace

class AodvPartitionGuardTest : public TestCase {
public:
    AodvPartitionGuardTest()
        : TestCase("icmp guard: partitioned AODV livelocks on ns-3.49 unguarded, runs guarded "
                   "(NS3-001)") {}

private:
    void DoRun() override {
        const PartitionRun bare = RunPartition(false);
        const PartitionRun guarded = RunPartition(true);
        const IcmpErrorGuardCounters& k = guarded.counters;
        std::clog << "NS3-001 partition: unguarded "
                  << (bare.livelock ? "livelocked" : "finished") << " at "
                  << bare.end.GetSeconds() << " s, delivered " << bare.delivered
                  << "; guarded finished at " << guarded.end.GetSeconds() << " s, delivered "
                  << guarded.delivered << ", no-route " << k.noRoute << ", vetoed "
                  << k.Vetoed() << " (source-own " << k.vetoed[IcmpErrorGuardCounters::SOURCE_OWN]
                  << "), unmatched " << k.unmatched << '\n';
#if defined(ROUTING_BENCH_NS3_MINOR) && ROUTING_BENCH_NS3_MINOR == 49
        // Strict, as ns3-containers' XFAIL: if 3.49 stops livelocking, this
        // test no longer proves the guard.
        NS_TEST_ASSERT_MSG_EQ(bare.livelock, true, "unguarded AODV livelocks on ns-3.49");
#elif defined(ROUTING_BENCH_NS3_MINOR) && ROUTING_BENCH_NS3_MINOR < 49
        NS_TEST_ASSERT_MSG_EQ(bare.livelock, false, "no SendIcmpNoRoute, no livelock");
#endif
        // Later releases only report the unguarded run: a release with the
        // fix stops livelocking (then retire the guard, NS3-001).
        NS_TEST_ASSERT_MSG_EQ(guarded.livelock, false, "guarded AODV does not livelock");
        NS_TEST_ASSERT_MSG_EQ(guarded.end, Seconds(15), "guarded AODV runs to the end");
        NS_TEST_ASSERT_MSG_GT(guarded.delivered, 800u, "the reachable flow is delivered");
        NS_TEST_ASSERT_MSG_GT(k.noRoute, 0u, "the unreachable flow met no-route failures");
        NS_TEST_ASSERT_MSG_EQ(k.allowed, 0u, "!3101 sends none of them");
        if (kIcmpNoRoute) {
            NS_TEST_ASSERT_MSG_EQ(k.Vetoed(), k.noRoute, "each error stopped");
            NS_TEST_ASSERT_MSG_EQ(k.unmatched, 0u, "every veto met its error");
        } else {
            NS_TEST_ASSERT_MSG_EQ(k.Vetoed(), 0u, "no error to stop before ns-3.49");
        }
    }
};

class RoutingBenchTestSuite : public TestSuite {
public:
    RoutingBenchTestSuite() : TestSuite("routing-bench", BENCH_TEST_TYPE_UNIT) {
        AddTestCase(new RegistryRulesTest, BENCH_TEST_QUICK);
        AddTestCase(new DefaultHooksTest, BENCH_TEST_QUICK);
        AddTestCase(new StockArmsTest, BENCH_TEST_QUICK);
        AddTestCase(new ArmIsolationTest, BENCH_TEST_QUICK);
        AddTestCase(new IcmpNoRouteGuardTest, BENCH_TEST_QUICK);
        AddTestCase(new AodvPartitionGuardTest, BENCH_TEST_QUICK);
    }
};

static RoutingBenchTestSuite g_routingBenchTestSuite;

}  // namespace bench
}  // namespace ns3
