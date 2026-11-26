# NS3-001: the ICMP no-route fix (nsnam/ns-3-dev!3101)

A patch to **upstream ns-3** (not to this repository's code) for
[NS3-001](../../../docs/ns3-rcapa/ns3-rcapa-aodv-icmp-livelock.md)
(RCAPA ticket swarm-routing/ns3-tools#238, upstream
[nsnam/ns-3-dev#1408](https://gitlab.com/nsnam/ns-3-dev/-/work_items/1408)):
ns-3.49's `Ipv4L3Protocol::SendIcmpNoRoute` makes every router answer a
no-route forwarding failure with an ICMP "net unreachable", and stock AODV
defers each such error into the same full request queue it came from, so a
partitioned AODV network livelocks in a zero-time ICMP storm.

| File | What |
|------|------|
| [`ns3-001-icmp-no-route-mr3101.patch`](ns3-001-icmp-no-route-mr3101.patch) | the fix: [nsnam/ns-3-dev!3101](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/3101)'s diff (`SendIcmpNoRoute` keeps RFC 1122 sec 3.2.2's exceptions: no error for a non-unicast destination, a non-first fragment, an ICMP error, a source that is not a unicast host address, or the router's own address; and the `ipv4-icmp-no-route` suite tests them) |
| [`apply.sh`](apply.sh) | applies the patch to an ns-3 source tree only when that tree has the bug, and prints one `NS3-001: <outcome>: …` line |
| [`icmp-no-route-livelock.cc`](icmp-no-route-livelock.cc) | the minimal reproducer on stock ns-3: three nodes, one of them partitioned away, stock AODV (the `routing-bench` suite's partition case, unguarded) |
| [`test.sh`](test.sh) | the proof, in an `ns3-dev:latest-sanitized` container: `apply.sh`'s four outcomes, the reproducer livelocking on the stock tree, then running to its end once patched, `!3101`'s own suite passing, and `already-fixed` on the patched tree |

## Use

```bash
ns3/patches/NS3-001/apply.sh [--dry-run] <ns-3 source dir>   # or ns3/patches/apply.sh <dir> NS3-001
```

It decides from the source, never from the ns-3 version, with the vcpkg
`ns3` port's rule (swarm-routing/vcpkg-registry `ports/ns3/portfile.cmake`,
NS3-001 block; [swarm-routing/vcpkg-registry#81](https://github.com/swarm-routing/vcpkg-registry/pull/81)),
now held here (ADR-0002 decision 3; the port takes it from this directory's
release asset, #380). The checks, in order:

| The source | Outcome | Exit |
|------------|---------|------|
| no `SendIcmpNoRoute` in `src/internet/model/ipv4-l3-protocol.cc` | `not-affected` (the code predates the bug) | 0 |
| the patch applies in reverse (`git apply --check --reverse`) | `already-fixed` (`!3101` is in the tree) | 0 |
| the patch applies (`git apply --check`) | `applied` | 0 |
| none of these | `refused`: upstream changed `SendIcmpNoRoute` some other way; re-check NS3-001 in the register, then refresh or retire this patch | 1 |

`git apply` runs on the tree alone (`--git-dir` pointing nowhere, so a
repository the tree sits in is never used). It needs `git` and `grep`.

## Outcomes

| ns-3 | Outcome | How it was checked |
|------|---------|--------------------|
| ns-3.48 | not-affected | `apply.sh` on `ns3-dev:3.48-debug` (2026-11-25) |
| ns-3.49 | applied | `test.sh` on `ns3-dev:latest-sanitized` (2026-11-25); CI (`ns3.yml`, `ns3-patches`) on every change |

A release with `!3101` merged prints `already-fixed` (`test.sh` step 1 and 4:
the reverse apply). When `latest` reaches one, retire the patch and the
`routing-bench` guard together (AGENTS.md, NS3-001), and record the release
here.

## Test

```bash
docker run --rm -v "$PWD:/src:ro" ghcr.io/swarm-routing/ns3-dev:latest-sanitized \
    bash /src/ns3/patches/NS3-001/test.sh /opt/ns-3
```

A few minutes on 4 cores (the internet module and everything linking it
rebuild). CI runs it in `ns3.yml` (`ns-3 patches apply only where the bug
is`).

## Provenance and licence

The patch is **not ours**: it is [nsnam/ns-3-dev!3101](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/3101)'s
diff (open upstream, by its author, not swarm-routing), at the merge
request's head `d3fbcacb25d5a1e3ac314089f3e39fc6ec8531f6` against its base
`a150de8f`. Its pre-image of `src/internet/model/ipv4-l3-protocol.cc` is
ns-3.49's (blob `993e0a99`), of `src/internet/test/ipv4-icmp-no-route-test-suite.cc`
blob `22da18e3`. It was copied byte for byte from swarm-routing/vcpkg-registry
`ports/ns3/patches/ns3-001-icmp-no-route-mr3101.patch` (git blob `e400cf67`,
added by [swarm-routing/vcpkg-registry#81](https://github.com/swarm-routing/vcpkg-registry/pull/81)).
It is ns-3 code, so **GPL-2.0-only**, as ns-3 is; the scripts and the
reproducer here are ours and GPL-2.0-only too (`LICENSING.md`, `ns3/patches/`).

This patch is the source-level fix; it does not replace the run-time
workaround: `routing-bench`'s `aodv` arm keeps `IcmpErrorGuardHelper`
(`ns3/routing-bench/model/icmp-error-guard-routing.h`) on stock images
(ADR-0002 rejected alternative E).
