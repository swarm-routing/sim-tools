# ns3/patches/: patches to upstream ns-3

Diffs to **ns-3's own source**, one directory per bug of the register
([`docs/ns3-bugs.md`](../../docs/ns3-bugs.md)), each applied to an ns-3 tree
only when that tree has the bug, decided from the source. This is the
*patch* kind of ADR-0002 decision 3
([`docs/adr/0002-sim-tools-layout-and-packages.md`](../../docs/adr/0002-sim-tools-layout-and-packages.md)).
A *workaround*, our own code that avoids a bug at run time, lives with the
code that needs it instead (NS3-001's `IcmpErrorGuardHelper` and NS3-002's
`--isolateArms` in `ns3/routing-bench/`).

| Patch | Bug | Fix | ns-3.48 | ns-3.49 |
|-------|-----|-----|---------|---------|
| [`NS3-001/`](NS3-001/README.md) | AODV livelocks in a zero-time ICMP "net unreachable" storm | [nsnam/ns-3-dev!3101](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/3101) (upstream, open) | not-affected | applied |
| [`NS3-005/`](NS3-005/README.md) | AODV route lifetime overflows int64 | ours, not yet reported | applied | applied |

## Use

```bash
ns3/patches/apply.sh [--dry-run] [--expect] <ns-3 source dir> [NS3-NNN ...]
```

Run it on an ns-3 source tree before configuring and building it. It runs
each `NS3-NNN/apply.sh` (every one, or the IDs named) in ID order and prints
each one's line:

```text
NS3-001: applied: /opt/ns-3 has the bug; ns3-001-icmp-no-route-mr3101.patch (nsnam/ns-3-dev!3101) applied
NS3-005: applied: /opt/ns-3 has the bug; ns3-005-aodv-lifetime-saturate.patch applied
```

| Outcome | Meaning | Exit |
|---------|---------|------|
| `not-affected` | the tree does not have the code the bug is in (it predates the bug, or lacks the module) | 0 |
| `applied` | the tree has the bug and the patch applied (with `--dry-run`: would apply; nothing changed) | 0 |
| `already-fixed` | the patch applies in reverse (it, or the same upstream fix, is in), or the bug's code is gone | 0 |
| `refused` | the tree has the bug's code but the patch fits neither way: the patch needs a refresh, or upstream changed the code; the build must stop | 1 |

The runner exits 1 when any patch is refused (it still runs the others), 2
on a usage error. `--expect` also compares each outcome with the patch's
README "Outcomes" row for the tree's release (`<tree>/VERSION`) and exits 1 on
a difference; a release with no row is reported, not compared. The four
outcomes are the vcpkg `ns3` port's (swarm-routing/vcpkg-registry
`ports/ns3/portfile.cmake`), held in one place here.

## The convention: one `NS3-NNN/` per bug

A directory is named by its register ID and holds:

| File | What |
|------|------|
| `README.md` | the bug (link to its RCAPA and register row), the fix (upstream merge request or commit and its base, or "ours"), the decision table of `apply.sh`, an **Outcomes** table (`\| ns-3.49 \| applied \| how it was checked \|`, one row per release checked: `--expect` reads it), how to run `test.sh`, and the patch's provenance and licence (the pre-image blobs; where a copied patch came from, byte for byte) |
| `<id>-<what>.patch` | the diff, `git apply`-able from the ns-3 tree's root (`a/src/...`, `b/src/...`) |
| `apply.sh` | `apply.sh [--dry-run] <ns-3 source dir>`: decides from the **source**, never from the version (a release with the fix is not known in advance, and a patched tree has the same version as a stock one), and prints exactly one line `NS3-NNN: <outcome>: <why>` on stdout; exit 0, 1 on `refused`, 2 on a usage error. It runs `git apply --check` forward and `--reverse` on the tree alone (`--git-dir` pointing nowhere) and, before them, a detect rule: the grep that tells whether the tree has the bug's code at all |
| the reproducer | the minimal program on stock ns-3 that shows the bug (a `scratch/` program), when the RCAPA has one |
| `test.sh` | the proof, run by CI in a throwaway `ns3-dev:latest-sanitized` container: `apply.sh`'s outcomes on copies of the touched files (stock, patched, predating, drifted), the reproducer failing on the stock tree and passing once patched, the module's suites passing, and `already-fixed` when run again |

All of it is **GPL-2.0-only** (`LICENSING.md`): a patch is a derived work of
ns-3, the scripts and reproducers are ns-3 code too. Each file we write
carries the org header; a patch carries none (it is a diff of ns-3's files).

### Adding a patch

1. The bug has its RCAPA ticket, RCAPA and register row first
   ([`docs/ns3-bugs.md`](../../docs/ns3-bugs.md) "Adding a bug").
2. Add `NS3-NNN/` as above, copying the closest existing directory; its
   `test.sh` must fail on the stock tree before the patch and pass after.
3. Add a step to `ns3.yml`'s `ns3-patches` job running its `test.sh`, a row to
   the table above, and name the directory in the register's "Workaround"
   column and the RCAPA's corrective actions.

### Retiring a patch

When `latest` prints `already-fixed` for a patch (the release carries the
fix), record that release in its Outcomes table; once no supported or pinned
release needs it, delete the directory and its CI step in one PR, and say so
in the register. Adding or retiring a patch is a minor release of the
`sim-tools-ns3-patches` asset (ADR-0002, #379).

## CI

`ns3.yml`'s `ns3-patches` job (`ns-3 patches apply only where the bug is`), in
`ns3-dev:latest-sanitized`: the runner with `--dry-run --expect` on the stock
tree (every outcome as its README states for `latest`), then each patch's
`test.sh`, then the runner again, which must print `already-fixed` for every
patch it applied. A refused patch fails the job.
