# 0002. Classify sim-tools by simulator folder and kind, in place; freeze published paths; ship one package per simulator and kind

- **Status:** proposed
- **Date:** 2026-11-25
- **Issue:** #375

## Context

The maintainer asked (2026-11-25) for every file to be classified (1) by
simulator (ns-3 today; OMNeT++ next, swarm-routing/swarm-adapter-omnet;
simulator-agnostic) and (2) by kind (upstream-bug patches and workarounds, the
comparison harness, comparator arms, probes, readers and statistics, the
campaign driver, the scenario catalogue, CI checks, release tooling,
docs and RCAPA), possibly with one separately released package per group.
The full inventory of `main` is [`docs/layout.md`](../layout.md); the forces
that decide the shape are these.

**Other repositories pin paths, not only releases.** The harness is consumed
as `swarm-routing/sim-tools@<ref>:ns3/routing-bench` by swarm-routing/.github
`reusable-ns3-image.yml` and `reusable-benchmark-cell.yml` (`dependencies:`,
so every protocol's CI and benchmark cell), by swarm-routing/sim-containers'
protocol image (`docker/protocol/Dockerfile` `ROUTING_BENCH_SPEC`,
`tools/protocol_images.py`'s `"ns3/routing-bench"`), by every campaign plan's
`modules` (`campaigns/anthocnet-aodv-smoke.toml`) and by sim-containers'
`test/downstream.txt`, which pins **`@main`** and also runs
`tools/checks/check-stock-arms.sh`. AntHocNet names the path in its own
tooling (code search hit; not opened). A pin at a commit survives a later move,
since the path is resolved at that commit; a pin at a moving ref does not, and
neither does a bump (org-bot's pin tasks) that moves the commit and keeps the
subdir. A campaign's `cell_key` (#94) covers each module spec, subdir
included, so a moved path also makes every earlier cell unreusable even when
the code is identical.

**Releases already ship per simulator folder.** One tag `vX.Y.Z` (Commitizen,
`.cz.toml`) publishes `routing-bench-<ver>.tar.gz` (the `ns3/` modules;
the vcpkg port `sim-tools-ns3`, one port per simulator folder, maintainer
2026-11-24, #359, swarm-routing/vcpkg-registry#76) and the Python
distribution `swarm-sim-tools` (PyPI; `ns3_tool`; AntHocNet pins it through
`ns3-tools.lock`, read by `release_lock.py` and bumped by org-bot). Zenodo, the
CITATION and `release_check.py` assume one version per repository.

**Patches and workarounds are different things and already live in different
places.** NS3-001's runtime guard (`IcmpErrorGuardRouting`,
`IcmpErrorGuardHelper`) and NS3-002's `--isolateArms` are our own code inside
`ns3/routing-bench/`, linked by protocol arms through `${librouting-bench}`.
NS3-001's *source* patch (`nsnam/ns-3-dev!3101`) lives in
swarm-routing/vcpkg-registry `ports/ns3/patches/`, applied by self-detection
(not affected / apply / already fixed / refuse) in that portfile. A first
`ns3/patches/NS3-NNN/` (NS3-005, #374) is being added on a branch. The
register and the RCAPAs (`docs/ns3-bugs.md`, `docs/ns3-rcapa/`) live here.
The images stay stock (maintainer, 2026-11-23).

**The marker contract spans the harness and the readers.** `docs/markers.md`
(contract v1, golden rule 11) is printed by `routing-compare` and read by
`ns3_tool` and `benchmarks`' validator (vendored in `python/tests/benchmarks/`).
A change to it moves both in one PR. A second simulator's harness must print
the same contract, so the contract is simulator-agnostic.

**The Python is mostly agnostic already.** Nine of the fifteen `ns3_tool`
modules name no ns-3 path or program; `sweep`, `scaffold`, `catalogue` and the
image side of `campaign` / `change_plan` are ns-3-bound (`docs/layout.md`
"Python modules").

**Work is in flight on the current paths**: #361 and #373 edit
`ns3/routing-bench/`, `tools/checks/` and AGENTS.md; the NS3-005 branch adds
`ns3/patches/`. A restructure now conflicts with all of them.

## Decision

1. **Classify in place; freeze published paths.** Every path keeps its place.
   `docs/layout.md` records each path's simulator, kind, licence, how it ships
   and who consumes it. The paths another repository or a pinned plan reaches
   by name (its "Published paths" table: `ns3/routing-bench/`, `python/`,
   `scenarios/<family>/*.toml`, `campaigns/*.toml`,
   `tools/checks/check-stock-arms.sh`, `docs/markers.md`, `docs/ns3-bugs.md`,
   `docs/ns3-rcapa/`, the release asset names) are never moved or deleted
   except by a new ADR that names each consumer's migration; a check enforces
   it (#376).
2. **New work goes under `<simulator>/<kind>/`.** The top level is the
   simulator axis: `ns3/`, later `omnetpp/` (#383); everything at the top level
   that is not a simulator folder is simulator-agnostic. Inside a simulator
   folder, one directory per kind: the harness module (`ns3/routing-bench/`,
   its name kept), `arms/<name>/` (one contrib module per comparator arm, epic
   #15, golden rule 12), the probe module (`probes/`, #40, golden rule 10),
   `patches/NS3-NNN/` (#378). Where a new file goes is the rule in
   `docs/layout.md` "Where a new file goes".
3. **A workaround lives with the code that needs it; a patch lives in
   `<sim>/patches/<ID>/`.** A workaround is our code avoiding an upstream bug
   at run time (the NS3-001 guard stays in `routing-bench`: protocol arms link
   it there). A patch is a diff to the simulator's source, one directory per
   register ID, with a README (bug, upstream MR or commit, its base), the diff,
   and a self-detection rule run by one runner that prints exactly one of
   `not-affected | applied | already-fixed | refused` (refused fails the
   build): the vcpkg `ns3` portfile's four outcomes, held in one place. The
   patch set is released as its own asset (#379); the vcpkg `ns3` port takes it
   from there instead of keeping its own copy (#380); a patched image is only
   ever an additional variant beside the stock one, and only on a maintainer
   decision (#381).
4. **One Python distribution, with a checked boundary.** `swarm-sim-tools`
   stays one distribution and `ns3_tool` keeps its module paths; the
   agnostic / ns-3 split is recorded per module and checked (an agnostic
   module imports no ns-3-bound one and names no ns-3 path or program, #377).
   A second simulator's Python is the trigger for a new ADR on splitting it.
5. **Packages and their contracts** (one version train: every package is
   released under the repository's single `vX.Y.Z` tag):

   | Package | From | Channel | Contract (SemVer applies to) |
   |---------|------|---------|------------------------------|
   | `sim-tools-ns3` (C++ modules of `ns3/`) | `routing-bench-<ver>.tar.gz` today; `sim-tools-ns3-<ver>.tar.gz` once `ns3/` holds a second module (#382) | release asset, vcpkg port `sim-tools-ns3`, git path `@<commit>:ns3/routing-bench` | `routing-compare` options, marker contract v1, the arm registration API (`routing-bench-arm.h`), the stock arms' names |
   | `sim-tools-ns3-patches` (planned, #379) | `ns3/patches/` | release asset; the vcpkg `ns3` port | each patch's ID and its outcome per ns-3 release; adding or retiring a patch is a minor release |
   | `swarm-sim-tools` (Python) | `python/` | PyPI, release assets | console scripts and options, reader output byte-identical on the fixtures, marker contract v1 |
   | data: `scenarios/`, `campaigns/` | the tree | not packaged; read at a checkout or pinned commit | a preset's meaning (rule 11); a plan, once dispatched, never changes |
   | `sim-tools-omnetpp`, `sim-tools-omnetpp-patches` (planned, #383) | `omnetpp/` | as `ns3/` | as `ns3/`, same marker contract |

6. **The marker contract stays one, simulator-agnostic**, in
   `docs/markers.md`; a harness of any simulator prints it, and a contract
   change still moves the printer, the readers and `benchmarks` together.

### Rejected alternatives

- **A. Restructure to `<sim>/{harness,arms,probes,patches}/` now**, with
  `ns3/routing-bench/` renamed `ns3/harness/` and the ns-3 Python under
  `ns3/python/`. Gains a uniform name; costs a coordinated change in
  swarm-routing/.github, sim-containers (Dockerfile, `protocol_images.py`,
  `downstream.txt` at `@main`, which breaks the same day), every protocol's
  `dependencies:` pin, AntHocNet's tooling and the vcpkg port; invalidates
  every reusable campaign cell (the subdir is in `cell_key`); conflicts with
  #361, #373 and the NS3-005 branch. Nothing a reader of the tree cannot get
  from `docs/layout.md`.
- **B. Separate repositories per package** (an ns-3 repo, a Python repo, a
  patches repo; #277's split). The marker contract would then span
  repositories, and a contract change could no longer land atomically in the
  printer and the readers (rule 11); the register, its RCAPAs and the patches
  would part; three release pipelines, locks and DOIs for one contract.
- **C. Split the PyPI distribution now** (`swarm-sim-tools-core` +
  `swarm-sim-tools-ns3`). The ns-3-bound Python is four modules, stdlib only;
  a split doubles releases and locks and forces a choice of import names that
  AntHocNet's lock would have to follow, for no second simulator yet. The
  boundary check (#377) keeps the later split mechanical.
- **D. Keep ns-3 source patches only in vcpkg-registry** (today's NS3-001).
  The register and the reproducers are here; a patch checked here against
  `latest` and the reproducer is the evidence the port should consume, not a
  second copy that drifts.
- **E. Move the NS3-001 guard out of `routing-bench`** into `ns3/patches/` or
  its own module. It is a run-time workaround, not a source diff; protocol
  arms link it through `${librouting-bench}` (swarm-routing/.github
  `reusable-ns3-image.yml`), so a move breaks their link lines for no gain.
  It is classified as kind *workaround* in `docs/layout.md` and retired when
  `latest` carries the fix, as AGENTS.md says.
- **F. Version each package on its own** (tags such as
  `routing-bench/v1.2.0`). swarm-routing/.github `reusable-release.yml`,
  `release_lock.py`, Zenodo and `CITATION.cff` assume one tag per repository;
  the harness and readers share a contract and move together anyway.

## Consequences

- No consumer changes for this ADR: every pin, lock, port and plan keeps
  working, old campaigns re-run unchanged, and in-flight PRs do not conflict.
- New groups land in a predictable place; a contributor reads
  `docs/layout.md` "Where a new file goes" before adding a directory, and the
  PR that adds one adds its `LICENSING.md` row (golden rule 1) and its
  `docs/layout.md` row.
- The names stay historical in places (`ns3_tool` for an import package that
  is mostly agnostic, `routing-bench` for the ns-3 harness folder);
  `docs/layout.md` is where the classification is read, not the names.
- A published path is moved only by a new ADR listing each consumer and its
  migration, so the cost is paid knowingly.
- The vcpkg `ns3` port gains a dependency on this repository's releases for
  its patches (#380), or keeps verified copies; one of the two is chosen in
  that issue.
- Ruled out: a second marker contract per simulator; patches applied silently
  (every outcome is printed and a mismatch fails); a patched image replacing a
  stock tag.

### Decisions for the maintainer

1. Accept this ADR as written, or amend it (in particular whether rejected
   alternative A, a one-time rename, is worth its cost to you).
2. #380: the `ns3` port downloads the released patch set, or keeps copies that
   `port_bump.py` verifies.
3. #381: whether any image ships patched (this reverses nothing if the answer
   is no: the stock images stay as decided on 2026-11-23).
4. The asset name for the multi-module ns-3 tarball (#382): proposed
   `sim-tools-ns3-<ver>.tar.gz`, with `routing-bench-<ver>.tar.gz` kept until
   no lock names it.
