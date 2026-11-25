# NS3-005: AODV route lifetime saturation patch

A patch to **upstream ns-3** (not to this repository's code) for
[NS3-005](../../../docs/ns3-rcapa/ns3-rcapa-aodv-lifetime-overflow.md)
(RCAPA ticket swarm-routing/sim-tools#374): stock AODV gives a route that
never expires the lifetime `Simulator::GetMaximumSimulationTime()`, and
`aodv::RoutingTableEntry` adds `Simulator::Now()` to every lifetime, so an
interface that comes up after t=0 overflows `int64` (undefined behaviour;
UBSan aborts the run).

| File | What |
|------|------|
| [`ns3-005-aodv-lifetime-saturate.patch`](ns3-005-aodv-lifetime-saturate.patch) | the fix: `RoutingTableEntry::SetLifeTime` saturates at `Simulator::GetMaximumSimulationTime()`, and the constructor sets its lifetime through it |
| [`apply.sh`](apply.sh) | applies the patch to an ns-3 source tree only when that tree has the bug, and logs one `NS3-005: …` line saying what it did |
| [`aodv-lifetime-overflow.cc`](aodv-lifetime-overflow.cc) | the minimal reproducer on stock ns-3 (an AODV interface set down, then up at 35 s) |
| [`test.sh`](test.sh) | the proof, in a sanitized `ns3-dev` image: `apply.sh`'s five decisions, the reproducer failing on the stock tree, then passing with the AODV suites once patched, and `apply.sh` skipping on the patched tree |

## Use

```bash
ns3/patches/NS3-005/apply.sh [--dry-run] <ns-3 source dir>   # before configuring/building ns-3
```

It decides from the source, never from the ns-3 version. No ns-3 release
carries a fix yet, so no version list can say where one starts, and a tree
built from `master`, or one already patched, carries the same version number
as a stock one. The checks, in order:

| The source | Decision | Exit |
|------------|----------|------|
| no `src/aodv/model/aodv-rtable.{cc,h}` | no AODV: skipped | 0 |
| the patch applies in reverse (`git apply --check --reverse`) | already patched: skipped | 0 |
| no unchecked `lifetime + Simulator::Now()` in `RoutingTableEntry` (the bug's signature, in the constructor or `SetLifeTime`) | no bug (fixed or rewritten upstream): skipped | 0 |
| the patch applies (`git apply --check`) | the bug is there: applied | 0 |
| none of these | the bug is there and the patch does not fit (ns-3.43 and older, where the context differs): fails, asking for a refreshed patch | 1 |

The signature check is why a version check is not needed and would not be
enough: it reads the very code that overflows. The patch is the same
mechanism as the vcpkg `ns3` port's NS3-001 patch (swarm-routing/vcpkg-registry
`ports/ns3/portfile.cmake`): forward and reverse `git apply --check` on the
tree alone (`--git-dir` pointing nowhere, so a repository the tree sits in is
never used). It needs `git` and `grep`.

Where it applies cleanly (read: `git apply --check` on each release's
`aodv-rtable.{cc,h}`): ns-3.44 to ns-3.49 and ns-3-dev `master` `d07400ba`
(the two files are identical in all of them). ns-3.7 to ns-3.43 have the bug
too, with different context: `apply.sh` fails there rather than guess.

## Test

```bash
docker run --rm -v "$PWD:/src:ro" ghcr.io/swarm-routing/ns3-dev:latest-sanitized \
    bash /src/ns3/patches/NS3-005/test.sh /opt/ns-3
```

About a minute on 4 cores. CI runs it in `ns3.yml` (`ns-3 patches apply only
where the bug is`).

## Provenance and licence

The patch is ours, written for swarm-routing (2026-11-25), against ns-3.49's
`src/aodv/model/aodv-rtable.cc` (blob `1e6c7e43`) and `aodv-rtable.h` (blob
`cd791727`). It modifies ns-3, so it is a derived work of ns-3 and is
**GPL-2.0-only**, as ns-3 is; the scripts and the reproducer here are
GPL-2.0-only too (`LICENSING.md`, `ns3/patches/`). It is not an upstream merge
request: the upstream report goes through
[swarm-routing/ns3-upstream-report](https://github.com/swarm-routing/ns3-upstream-report),
and once ns-3 merges a fix, `apply.sh` skips by itself on a release that has it.
