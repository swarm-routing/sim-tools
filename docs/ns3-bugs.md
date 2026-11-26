# Upstream ns-3 bugs the org found

The index of defects in **upstream ns-3** (the simulator and its stock modules,
not our code) that swarm-routing found while benchmarking, running CI or
testing the `ns3-dev` images. It lives here because every comparison runs
through this repository's harness (`routing-bench`), where the stock arms
(AODV, DSDV, OLSR, HWMP) meet these defects (maintainer decision 2026-11-16,
[swarm-routing/ns3-tools#233](https://github.com/swarm-routing/ns3-tools/issues/233)).

This page is the index only. Each bug has an **RCAPA** (root cause analysis
with corrective and preventive actions) in [`ns3-rcapa/`](ns3-rcapa/README.md)
and an **RCAPA ticket**, an issue titled `[rcapa] NS3-NNN …` in this
repository. The detail (reproduction, five whys, diagrams, source excerpts,
actions, the upstream text, the timeline) is in the RCAPA, not here. The
one exception: a bug already fixed in the release ns-3 supports is only
recorded, under ["Fixed upstream before we recorded them"](#fixed-upstream-before-we-recorded-them).

A regression in a published release of ns3-tools' own code is not an ns-3
bug: it is an `NST-NNN` RCAPA, in [`rcapa/README.md`](rcapa/README.md).

Upstream reports are filed on the [nsnam GitLab](https://gitlab.com/nsnam/ns-3-dev/-/issues)
by the maintainer, under their own account: a report speaks for the project.
A session drafts the text and records the link once it is filed; it never
posts upstream.

## Index

Status: **open upstream** (no fix upstream), **draft ready** (a report is
written, not filed), **reported** (an upstream issue exists), **worked around**
(our repositories avoid it), **fixed in ns-3.X** (the first release with the
fix). A bug usually has several.

| ID | Title | ns-3 versions | Modules | Status | Workaround in our repositories | Upstream | Investigation and fixes | RCAPA |
|----|-------|---------------|---------|--------|--------------------------------|----------|-------------------------|-------|
| NS3-001 | AODV livelocks in a zero-time ICMP "net unreachable" storm | 3.49 and ns-3-dev `master` `8ec9b4a1` (run); not 3.48 | internet (`Ipv4L3Protocol::SendIcmpNoRoute`, `Icmpv4L4Protocol`), aodv | open upstream; reported, fix proposed (not ours); worked around | AODV-family arms on `ns3-dev:3.48` (AntHocNet CI) until the harness guard reaches them: `routing-bench` wraps the `aodv` arm in a guard ([swarm-routing/sim-tools#322](https://github.com/swarm-routing/sim-tools/pull/322)) applying [nsnam/ns-3-dev!3101](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/3101)'s rules (maintainer decision 2026-11-23, swarm-routing/sim-tools#238); strict XFAIL `3.49 sparse-aodv` in swarm-routing/sim-containers `test/known-failures.txt`; the patch `ns3/patches/NS3-001/` ([nsnam/ns-3-dev!3101](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/3101) at `d3fbcacb`; `apply.sh` applies it only to a source with the bug, [swarm-routing/sim-tools#378](https://github.com/swarm-routing/sim-tools/issues/378)), which the vcpkg `ns3` port applies by the same rule (maintainer decision 2026-11-25, [swarm-routing/vcpkg-registry#81](https://github.com/swarm-routing/vcpkg-registry/pull/81); its own copy until it takes the released asset, [swarm-routing/sim-tools#380](https://github.com/swarm-routing/sim-tools/issues/380)) | [nsnam/ns-3-dev#1408](https://gitlab.com/nsnam/ns-3-dev/-/work_items/1408) (filed 2026-11-18 through swarm-routing/ns3-upstream-report; text: [swarm-routing/sim-containers#55](https://github.com/swarm-routing/sim-containers/issues/55)), fix [nsnam/ns-3-dev!3101](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/3101) (open, not ours) | [swarm-routing/ns3-tools#238](https://github.com/swarm-routing/ns3-tools/issues/238), [swarm-routing/sim-containers#35](https://github.com/swarm-routing/sim-containers/issues/35), [swarm-routing/sim-containers#42](https://github.com/swarm-routing/sim-containers/issues/42), [swarm-routing/sim-containers#48](https://github.com/swarm-routing/sim-containers/pull/48), [swarm-routing/AntHocNet#843](https://github.com/swarm-routing/AntHocNet/issues/843), [swarm-routing/AntHocNet#842](https://github.com/swarm-routing/AntHocNet/pull/842), [swarm-routing/AntHocNet#656](https://github.com/swarm-routing/AntHocNet/issues/656) | [aodv-icmp-livelock](ns3-rcapa/ns3-rcapa-aodv-icmp-livelock.md) |
| NS3-002 | AODV and DSDV order per-interface sockets by heap address | 3.42, 3.48, 3.49 and ns-3-dev `master` `8ec9b4a1`, `a150de8f` (run); 3.42, 3.48, 3.49 (read) | aodv, dsdv (`std::map` keyed by `Ptr<Socket>`; AODV's rows move with it, DSDV's send order does but its rows did not on the topology tried, swarm-routing/ns3-tools#301; DSDV's `NotifyRemoveAddress()` leaves its socket unbound, so the fix keys by interface index) | open upstream; reported; worked around | `--isolateArms` (default since v1.1.0); AntHocNet: its own maps ordered, stock `aodv` in its own process, the order gate on `anthocnet` rows only | [nsnam/ns-3-dev#1409](https://gitlab.com/nsnam/ns-3-dev/-/work_items/1409) (filed 2026-11-19; a volunteer writes the fix; text: [swarm-routing/ns3-tools#206](https://github.com/swarm-routing/ns3-tools/issues/206)) | [swarm-routing/ns3-tools#239](https://github.com/swarm-routing/ns3-tools/issues/239), [swarm-routing/ns3-tools#301](https://github.com/swarm-routing/ns3-tools/issues/301), [swarm-routing/ns3-tools#198](https://github.com/swarm-routing/ns3-tools/issues/198), [swarm-routing/ns3-tools#202](https://github.com/swarm-routing/ns3-tools/pull/202), [swarm-routing/ns3-tools#212](https://github.com/swarm-routing/ns3-tools/pull/212), [swarm-routing/AntHocNet#362](https://github.com/swarm-routing/AntHocNet/issues/362), [swarm-routing/AntHocNet#471](https://github.com/swarm-routing/AntHocNet/pull/471), [swarm-routing/AntHocNet#675](https://github.com/swarm-routing/AntHocNet/issues/675), [swarm-routing/AntHocNet#1039](https://github.com/swarm-routing/AntHocNet/issues/1039), [swarm-routing/AntHocNet#1059](https://github.com/swarm-routing/AntHocNet/pull/1059) | [socket-map-heap-order](ns3-rcapa/ns3-rcapa-socket-map-heap-order.md) |
| NS3-003 | DSDV sends on a route with a null output device (assert, or a silent SIGSEGV when optimized) | 3.36–3.48 and ns-3-dev 2026-08 (run); 3.49 (read) | dsdv (fault seen in internet's `Ipv4L3Protocol::SendRealOut`) | open upstream; reported, fix proposed; worked around | AntHocNet's `isl-grid` refuses `dsdv` on multi-interface topologies, checked by its satellite arm smoke | [nsnam/ns-3-dev#1364](https://gitlab.com/nsnam/ns-3-dev/-/issues/1364), MR [nsnam/ns-3-dev!2985](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/2985) (open; stalled since 2026-09-16: `need_rebase`, no reviewer; the alternative [nsnam/ns-3-dev!3011](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/3011) defers to it; see PROC-001) | [swarm-routing/ns3-tools#240](https://github.com/swarm-routing/ns3-tools/issues/240), [swarm-routing/AntHocNet#281](https://github.com/swarm-routing/AntHocNet/issues/281), [swarm-routing/AntHocNet#420](https://github.com/swarm-routing/AntHocNet/issues/420), [swarm-routing/AntHocNet#422](https://github.com/swarm-routing/AntHocNet/pull/422), [swarm-routing/AntHocNet#434](https://github.com/swarm-routing/AntHocNet/issues/434), [swarm-routing/AntHocNet#445](https://github.com/swarm-routing/AntHocNet/pull/445), [swarm-routing/ns3-tools#247](https://github.com/swarm-routing/ns3-tools/issues/247) | [dsdv-null-route](ns3-rcapa/ns3-rcapa-dsdv-null-route.md) |
| NS3-004 | AODV never restarts its hello timer when an interface comes back up (a restarted node sends no HELLO for the rest of the run) | 3.49 and ns-3-dev `master` `8a06b457` (run); 3.49, `master` (read) | aodv (`RoutingProtocol::NotifyInterfaceDown` cancels `m_htimer` with the last interface; `NotifyInterfaceUp` never re-arms it) | open upstream; draft ready | none: `--failures` is opt-in; `ns3/routing-bench/README.md` "Scripted failures" names the limit ([swarm-routing/sim-tools#361](https://github.com/swarm-routing/sim-tools/pull/361), open) | not yet reported (draft on [swarm-routing/sim-tools#362](https://github.com/swarm-routing/sim-tools/issues/362)) | [swarm-routing/sim-tools#362](https://github.com/swarm-routing/sim-tools/issues/362), [swarm-routing/sim-tools#361](https://github.com/swarm-routing/sim-tools/pull/361), [swarm-routing/sim-tools#128](https://github.com/swarm-routing/sim-tools/issues/128) | [aodv-hello-restart](ns3-rcapa/ns3-rcapa-aodv-hello-restart.md) |
| NS3-005 | AODV route lifetime overflows int64 when an interface comes up after t=0 (`GetMaximumSimulationTime() + Now()`: UBSan aborts; undefined behaviour otherwise) | 3.49 and ns-3-dev `master` `d07400ba` (run); 3.7–3.49, `master` (read) | aodv (`RoutingTableEntry`'s constructor and `SetLifeTime`; callers `NotifyInterfaceUp`, `NotifyAddAddress`, `NotifyRemoveAddress`, `SetIpv4`) | open upstream; reported; patch kept here and in the patched images | the patch `ns3/patches/NS3-005/` (`apply.sh` applies it only to a source with the bug), applied in swarm-routing/sim-containers `ns3-dev:3.49-{debug,sanitized}-patched-5c58dfa` (publish run 45712453689, the patch at sim-tools `1b36c739`); `--failures` AODV restarts ([swarm-routing/sim-tools#361](https://github.com/swarm-routing/sim-tools/pull/361)) abort on sanitized stock builds: the suite leaves them out where the source has the bug and runs them on the patched sanitized image (`ns3.yml` `failures-patched`) | [nsnam/ns-3-dev#1417](https://gitlab.com/nsnam/ns-3-dev/-/work_items/1417) (filed 2026-11-26 through swarm-routing/ns3-upstream-report) | [swarm-routing/sim-tools#374](https://github.com/swarm-routing/sim-tools/issues/374), [swarm-routing/sim-tools#361](https://github.com/swarm-routing/sim-tools/pull/361) | [aodv-lifetime-overflow](ns3-rcapa/ns3-rcapa-aodv-lifetime-overflow.md) |

## Candidates: not yet shown to be ns-3's

A finding whose cause is not yet known stays here, in its own issue, until it
is classified. If it turns out to be ns-3's, it gets the next `NS3-NNN`, an
RCAPA ticket and an RCAPA.

| Finding | ns-3 | Where | Open question |
|---------|------|-------|---------------|
| 3.42 → 3.48 moves AntHocNet's delay tail and overhead (same build recipe, different release) | 3.42 → 3.48 | [swarm-routing/AntHocNet#923](https://github.com/swarm-routing/AntHocNet/issues/923) | an intended upstream change or a regression; bisect pending |

## Fixed upstream before we recorded them

Upstream ns-3 bugs found on an older release whose fix is already in the
release ns-3 supports (the images' `latest`), so nothing is left to report or
fix upstream. They are recorded here for traceability, with the strict
expected failures that keep on-demand builds of those older releases green,
and get no `NS3-NNN`, RCAPA ticket, RCAPA or upstream report (maintainer
decision 2026-11-23). A pinned older release can still carry one: the
"Workaround" column says where, and a result produced on that release is
checked against it.

| Bug | ns-3 | Fixed in | Upstream | Where found | Workaround in our repositories |
|-----|------|----------|----------|-------------|--------------------------------|
| 802.11b HR/DSSS (5.5, 11 Mb/s) frames dropped as an unsupported modulation: `GetModulationClassForStandard(WIFI_STANDARD_80211b)` returns `WIFI_MOD_CLASS_DSSS`, and since 3.41 `WifiPhy::StartReceivePreamble` refuses any class above it | 3.42 (run); 3.41, 3.42 (read); not 3.40 or earlier (no gate, read) | 3.43 (`da9fcebe`) | [nsnam/ns-3-dev#1095](https://gitlab.com/nsnam/ns-3-dev/-/work_items/1095) | [swarm-routing/sim-containers#44](https://github.com/swarm-routing/sim-containers/issues/44) | strict XFAIL `3.41`/`3.42` `dsdv-manet`, `dense-{aodv,olsr,dsdv}` (`no-packets-delivered`) in swarm-routing/sim-containers `test/known-failures.txt` ([swarm-routing/sim-containers#250](https://github.com/swarm-routing/sim-containers/pull/250)); [swarm-routing/AntHocNet#923](https://github.com/swarm-routing/AntHocNet/issues/923) to check for 802.11b above 2 Mb/s on 3.42 |
| Four wifi unit suites (`wifi-txop`, `wifi-mlo`, `wifi-gcr`, `wifi-emlsr-basic-exchanges`) fail when `test-runner` is built without the `test` module: the tests match frames by packet UID, which needs packet metadata on, and 3.48 turns it on only through `src/test`'s `ns3tcp` suites (a test bug; `wifi-txop` then reads past its frame list) | 3.48 (run) | 3.49 (the tests use the MPDU's own UID) | none | [swarm-routing/sim-containers#49](https://github.com/swarm-routing/sim-containers/issues/49) ([root cause](https://github.com/swarm-routing/sim-containers/issues/49#issuecomment-7110484932)) | strict XFAIL `3.48 unit:<suite>` in swarm-routing/sim-containers `test/known-failures.txt` |

## Process RCAPAs (ours)

Defects in how we carry ns-3 reports, not in ns-3. Same format, IDs
`PROC-NNN`, RCAPA ticket titled `[rcapa] PROC-NNN …`.

| ID | Title | Status | RCAPA ticket | RCAPA |
|----|-------|--------|--------------|-------|
| PROC-001 | Upstream reports have no owner after filing: NS3-003's fix ([nsnam/ns-3-dev!2985](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/2985)) stalled two months unnoticed | open; corrective action with the maintainer (swarm-routing/.github#519), tracker planned ([swarm-routing/ns3-tools#246](https://github.com/swarm-routing/ns3-tools/issues/246)) | [swarm-routing/ns3-tools#247](https://github.com/swarm-routing/ns3-tools/issues/247) | [upstream-report-tracking](ns3-rcapa/ns3-rcapa-upstream-report-tracking.md) |

## Not ns-3 bugs (ours)

Listed for traceability, because they were found next to the bugs above:

- [swarm-routing/ns3-tools#211](https://github.com/swarm-routing/ns3-tools/issues/211) (fixed by
  [swarm-routing/ns3-tools#212](https://github.com/swarm-routing/ns3-tools/pull/212)): our isolation
  test forked its runs from different heaps, so NS3-002 showed through it.
- [swarm-routing/ns3-tools#218](https://github.com/swarm-routing/ns3-tools/issues/218) (fixed by
  [swarm-routing/ns3-tools#219](https://github.com/swarm-routing/ns3-tools/pull/219)): our arm workers
  shipped `ns3::Address` bytes between processes; ns-3 assigns address type
  numbers per process by design (`Address::Register`,
  `src/network/model/address.cc:130–139`, ns-3.49), so the keys did not match.

## Important links

- RCAPA guide and template: [`ns3-rcapa/README.md`](ns3-rcapa/README.md),
  [`ns3-rcapa/_template.md`](ns3-rcapa/_template.md)
- RCAPA tickets: [issues titled `[rcapa]`](https://github.com/swarm-routing/ns3-tools/issues?q=is%3Aissue+%5Brcapa%5D+in%3Atitle)
- The images and their expected failures: swarm-routing/sim-containers
  `test/known-failures.txt` and README "Known issues and findings"
- The nightly build against ns-3-dev that catches upstream changes early:
  swarm-routing/AntHocNet `.github/workflows/ns3-dev.yml`
- ns-3's issue tracker: https://gitlab.com/nsnam/ns-3-dev/-/issues
- The upstream bridge, which files and follows every report on ns-3's
  GitLab: [swarm-routing/ns3-upstream-report](https://github.com/swarm-routing/ns3-upstream-report)
  (its design: swarm-routing/ns3-upstream-report#2). Each reported `NS3-NNN`
  has a mirror ticket there, which mirrors the GitLab notes and state every
  6 h and flags stalls: NS3-001 swarm-routing/ns3-upstream-report#3, NS3-002
  swarm-routing/ns3-upstream-report#4, NS3-003 swarm-routing/ns3-upstream-report#5.

## Adding a bug

Anyone who finds or suspects a defect in upstream ns-3 (a session or a
contributor) follows the steps below, unless the defect is already fixed in
the release ns-3 supports (the images' `latest`): then it gets a row under
["Fixed upstream before we recorded them"](#fixed-upstream-before-we-recorded-them)
and the expected failures that keep older builds green, nothing more
(maintainer decision 2026-11-23).

1. **Open the RCAPA ticket first**: an issue in this repository titled
   `[rcapa] NS3-NNN <short description>`, with the next free number (numbers are
   never reused), labels `verification`, `ns3`, `benchmark`, a priority and a
   model suggestion (and `rcapa` once that label reaches this repository).
   Body: Context, Scope, Acceptance criteria (the RCAPA document written, the
   five whys cited, the reproducer verified on the latest image and on
   ns-3-dev `master`, corrective and preventive actions linked, the upstream
   report filed by the maintainer or the decision recorded), links to the
   investigation issues. Every investigation of an ns-3 bug runs under its
   ticket (maintainer rule 2026-11-16).
2. Write the RCAPA from [`ns3-rcapa/_template.md`](ns3-rcapa/_template.md) as
   `ns3-rcapa/ns3-rcapa-<short-description>.md`; its header links the ticket.
3. Add its row to the index above (and to the table in
   [`ns3-rcapa/README.md`](ns3-rcapa/README.md)); the row links the ticket and
   the RCAPA.
4. Every workaround points back at its row: a `test/known-failures.txt` entry in
   swarm-routing/sim-containers, a pinned image in a workflow, a refused arm, a
   gate that skips an arm, a harness option that exists because of it. Write
   the ID next to the existing issue reference (a comment line such as
   `# NS3-001: …` above a `known-failures.txt` entry, a workflow comment, a
   README sentence).
   A diff to ns-3's own source is a **patch**, not a workaround in our code:
   it goes in `ns3/patches/NS3-NNN/` (the bug, the fix and its base, the
   `.patch`, an `apply.sh` that decides from the source and prints
   `not-affected`, `applied`, `already-fixed` or `refused`, the reproducer,
   `test.sh`, a step in `ns3.yml`'s `ns3-patches` job), as
   [`ns3/patches/README.md`](../ns3/patches/README.md) says; the
   "Workaround" column above names that directory. Run-time code that avoids
   the bug stays in the module that needs it (ADR-0002 decision 3).
5. Upstream: draft the report in the ticket (or link the issue that holds it);
   the maintainer files it under their own account, then the link goes into the
   ticket, the RCAPA and this index. Filing is a step, not the end: the RCAPA
   ticket stays open until the fix is in an ns-3 release we run, and the
   upstream thread (new notes, rebase requests, review, competing fixes) is
   followed on it (PROC-001; the tracker, swarm-routing/ns3-tools#246, will
   watch every link here).
6. Write every issue, PR and MR reference fully qualified (maintainer rule
   2026-11-16), since these documents feed upstream reports, where GitLab
   reads a bare `#N` as an ns-3 issue, and GitHub reads it as an item of the
   repository the text is in: an org item as `swarm-routing/<repo>#N`, this
   repository's own included; an ns-3 item as a link whose text is
   `nsnam/ns-3-dev#N` (issue) or `nsnam/ns-3-dev!N` (merge request) to its
   full gitlab.com URL. Never a bare `#N` or `!N`, never `AntHocNet#N`.
   Inside a mermaid block, where `#` cannot go, name the item in words.
   `python3 -I tools/checks/check-refs.py docs/ns3-bugs.md docs/ns3-rcapa/`
   checks it, in CI on every pull request.
7. When a fix reaches a release: set the status to **fixed in ns-3.X**, re-run
   the reproducer on that release, and remove the workarounds in the same
   round. A row and its RCAPA are never deleted.

Only what a source supports goes in: a claim without a link to its evidence
stays in its issue until it has one.
