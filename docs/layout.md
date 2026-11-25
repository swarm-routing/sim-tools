# Repository layout

Where everything in sim-tools lives, classified by **simulator** and by
**kind**, how each part ships and who consumes it. The decision behind it is
[ADR-0002](adr/0002-sim-tools-layout-and-packages.md) (**accepted** 2026-11-25, epic
#375): classify in place, never move a published path, put new work under
`<simulator>/<kind>/`. Rows marked *(planned)* do not exist yet; the issue
that adds one moves its row to current.

## The two axes

**Simulator.** The top level is the simulator axis: a simulator folder
(`ns3/`; `omnetpp/` planned, #383) holds code that builds against that
simulator. Everything else at the top level is **agnostic**: it reads or
writes marker lines, plans, data or docs, and builds against no simulator,
even where today it names ns-3 programs (the Python column below says which).

**Kind.**

| Kind | What | Lives in |
|------|------|----------|
| harness | the comparison harness: scenario, traffic, measurement (topology oracle, drop book), markers, the arm registry and the stock arms | `<sim>/routing-bench/` (ns-3) |
| workaround | our code avoiding an upstream simulator bug at run time; names its register ID | the module that needs it (NS3-001's guard, NS3-002's arm isolation: `ns3/routing-bench/`) |
| patch | a diff to the simulator's own source, self-detecting, one per register ID | `<sim>/patches/<ID>/` (`ns3/patches/`, its convention in [`ns3/patches/README.md`](../ns3/patches/README.md)) |
| arm | a comparator arm we did not design (secure, learned, DTN), its own contrib module | `<sim>/arms/<name>/` *(planned, epic #15)* |
| probe | non-intrusive trace readers (oracle, drop book) on any program | `<sim>/probes/` *(planned, #40)* |
| reader | marker-line readers, paired statistics, views | `python/ns3_tool/` |
| plausibility | scenario and result checks against anchors | `python/ns3_tool/` (`scenario_check`) |
| campaign | the campaign and change-test driver, cost model | `python/ns3_tool/` (`campaign`, `change_plan`, `cost`), `.github/workflows/campaign-*.yml` |
| catalogue | network families: presets, preflight, anchors | `scenarios/` |
| plan | a campaign's pre-registration | `campaigns/` |
| check | CI and release-gate scripts | `tools/checks/` |
| release | building and checking the release assets | `tools/release/`, `.cz.toml`, `release.yml` |
| contract | the marker-line contract (simulator-agnostic) | `docs/markers.md` |
| register | upstream ns-3 bugs and their RCAPAs; our own regressions | `docs/ns3-bugs.md`, `docs/ns3-rcapa/`; `docs/rcapa/` |
| docs | guides, roadmap, ADRs | `docs/` |

## Inventory (`main`, 2026-11-25)

Licence column: **GPL** is `GPL-2.0-only`, **dual** is `MIT OR GPL-2.0-only`
([`LICENSING.md`](../LICENSING.md)).

| Path | Simulator | Kind | Licence | Ships as | Consumed by |
|------|-----------|------|---------|----------|-------------|
| `ns3/routing-bench/` (`model/routing-bench-{arm,harness,run,internal}`, `source-refusal-counter`, `urban-obstacle-loss-model`, `livelock-watch`; `helper/stock-arms`; `examples/`; `test/`) | ns-3 | harness | GPL | `routing-bench-<ver>.tar.gz` → vcpkg port `sim-tools-ns3`; git path `sim-tools@<ref>:ns3/routing-bench` | sim-containers protocol image (`docker/protocol/Dockerfile` `ROUTING_BENCH_SPEC`, `tools/protocol_images.py`), sim-containers `test/downstream.txt` (`@main`); swarm-routing/.github `reusable-ns3-image.yml` and `reusable-benchmark-cell.yml` `dependencies:` (every protocol's CI and cells); campaign plans' `modules`; arm modules in protocol repos (`helper/<m>-bench-arms.cc`, `${librouting-bench}`); AntHocNet (`ns3-tools.lock`, its tooling) |
| `ns3/routing-bench/{model/icmp-error-guard-routing,helper/icmp-error-guard-helper}.*` | ns-3 | workaround (NS3-001) | GPL | inside the harness tarball | the `aodv` stock arm; AODV-derived protocol arms (`reusable-ns3-image.yml`) |
| `ns3/routing-bench/model/arm-isolation.*` | ns-3 | workaround (NS3-002: `--isolateArms` default on) and harness | GPL | inside the harness tarball | every comparison run |
| `ns3/patches/<ID>/` (NS3-001, NS3-005), `ns3/patches/apply.sh` (the runner: `not-affected \| applied \| already-fixed \| refused`), `ns3/patches/README.md` (the convention) | ns-3 | patch | GPL | `sim-tools-ns3-patches-<ver>.tar.gz` *(planned, #379)* | CI (`ns3.yml` `ns3-patches`); vcpkg `ns3` port, which downloads the released asset and keeps no copies *(#380; until then it carries its own copy of NS3-001's patch, byte-identical to `ns3/patches/NS3-001/`)*; the patched `ns3-dev` image variant beside the stock tags, self-detecting patches only *(#381; first case NS3-005)* |
| `ns3/arms/<name>/` *(planned, epic #15)* | ns-3 | arm | GPL | in the ns-3 tarball (#382) | campaigns, the guide |
| `ns3/probes/` *(planned, #40)* | ns-3 | probe | GPL | in the ns-3 tarball (#382) | any ns-3 program |
| `omnetpp/` *(planned, #383)* | OMNeT++ | as `ns3/` | decided in its PR | `sim-tools-omnetpp` | swarm-routing/swarm-adapter-omnet |
| `python/ns3_tool/` | agnostic (see "Python modules") | reader, plausibility, campaign | dual | PyPI `swarm-sim-tools` (wheel, sdist; also release assets) | AntHocNet (`ns3-tools.lock`), the guide's users, this repository's campaign workflows |
| `python/tests/` | agnostic | tests | dual; `fixtures/` GPL (data) | not shipped | CI (`python.yml`, `ns3.yml` python-quality) |
| `python/tests/benchmarks/` | agnostic | contract (vendored validator of swarm-routing/benchmarks at a pinned commit) | dual | not shipped | the reader tests |
| `scenarios/<family>/{preset,preflight,anchors}.toml`, `scenarios/README.md` | agnostic data (presets are `routing-compare` flags) | catalogue | GPL | not packaged: read from a checkout (`--catalogue`, `$NS3_TOOL_SCENARIOS`) | `ns3-tool sweep --family`, `ns3-scenario-check`, `check-scenarios.py`, `docs/families/` |
| `campaigns/*.toml` | agnostic (pins ns-3 images and modules) | plan | GPL | not packaged; copied into each benchmarks run | `campaign-image.yml`, `campaign-cell.yml`, swarm-routing/benchmarks |
| `tools/checks/check-stock-arms.sh`, `arm-delivers.sh`, `check-scaffold-arm.sh`, `check-perf-markers.sh` | ns-3 | check | dual | not shipped (#350) | `ns3.yml`; sim-containers `test/downstream.txt` (`check-stock-arms.sh` at `@main`); the guide |
| `tools/checks/check-scenarios.py`, `check-refs.py`, `tests/` | agnostic | check | dual | not shipped | `make test`, CI |
| `tools/release/dist.sh`, `tools/requirements/` | agnostic (builds the ns-3 and Python assets) | release | dual | not shipped | `make dist`, `release.yml` |
| `.cz.toml`, `CHANGELOG.md`, `CITATION.cff` | agnostic | release | GPL | the release, Zenodo | swarm-routing/.github `reusable-release.yml` |
| `.github/workflows/ns3.yml` | ns-3 (plus the Python quality job) | check | GPL | — | every PR |
| `.github/workflows/python.yml` | agnostic | check | GPL | — | every PR |
| `.github/workflows/campaign-image.yml`, `campaign-cell.yml` | ns-3 | campaign | GPL | — | `ns3-campaign build` / `dispatch` |
| `.github/workflows/release.yml` | agnostic | release | GPL | — | the release (assets, PyPI, `vcpkg-ports: sim-tools-ns3`) |
| `.github/workflows/` (the rest: org-managed) | agnostic | org | GPL | — | swarm-routing/.github |
| `docs/markers.md` | agnostic | contract | GPL | — | the readers, swarm-routing/benchmarks, every harness |
| `docs/ns3-bugs.md`, `docs/ns3-rcapa/` (incl. the reproducer `aodv-hello-restart.cc`) | ns-3 | register | GPL | — | org CONTRIBUTING, swarm-routing/.github issue templates, sim-containers README, vcpkg `ns3` portfile messages |
| `docs/rcapa/` | agnostic | register (`NST-NNN`, our own regressions) | GPL | — | org CONTRIBUTING |
| `docs/bring-your-own-protocol.md`, `docs/families/`, `docs/profiling.md`, `docs/api/Doxyfile` | ns-3 | docs | GPL | `api-docs.yml` (Doxygen) | users of the released packages |
| `docs/roadmap.md`, `docs/development.md`, `docs/install.md`, `docs/adr/`, `docs/layout.md`, `docs/references.bib` | agnostic | docs | GPL | — | contributors |
| root `README.md`, `AGENTS.md`, `CONTEXT.md`, `LICENSING.md`, `Makefile`, `SECURITY.md`, dotfiles | agnostic | docs / org | GPL | — | contributors, org-sync |

### Python modules

One distribution, `swarm-sim-tools`, import package `ns3_tool` (ADR-0002
"Decision" 4). The column is what #377 checks: an agnostic module imports no
ns-3-bound one and names no ns-3 path or program.

| Module | Kind | Simulator |
|--------|------|-----------|
| `bench_parse`, `stats_util`, `native_view`, `comparator_view`, `pool_runs`, `sweep_summary` | reader | agnostic |
| `diagnose` | reader (drop book, scenario_check results) | agnostic |
| `scenario_check` | plausibility | agnostic |
| `cost` | campaign (runner-minute model) | agnostic |
| `cli` | dispatcher | agnostic (dispatches to ns-3-bound commands too) |
| `catalogue` | catalogue reader; turns presets into `routing-compare` flags | ns-3 |
| `sweep` | harness front-end (runs `routing-compare` in an ns-3 tree) | ns-3 |
| `scaffold` | arm tooling (writes an ns-3 contrib module) | ns-3 |
| `campaign`, `change_plan` | campaign (plan, cell key and reuse are agnostic; image build and dispatch use `ns3-dev`, `ns3-build-contrib`) | ns-3 |

## Packages

Every package is released under the repository's single `vX.Y.Z` tag
(ADR-0002 "Decision" 5, the contract each one keeps).

| Package | Built from | Channel | Status |
|---------|------------|---------|--------|
| `sim-tools-ns3` | `ns3/routing-bench/` as `routing-bench-<ver>.tar.gz` | release asset, vcpkg port, git path | current |
| `sim-tools-ns3` (every `ns3/` module) | `sim-tools-ns3-<ver>.tar.gz` (name decided 2026-11-25; `routing-bench-<ver>.tar.gz` kept until no lock names it) | release asset, vcpkg port | *(planned, #382)* |
| `sim-tools-ns3-patches` | `ns3/patches/` | release asset; vcpkg `ns3` port | *(planned, #379, #380)* |
| `swarm-sim-tools` | `python/` | PyPI, release assets | current |
| `sim-tools-omnetpp`, `sim-tools-omnetpp-patches` | `omnetpp/` | as ns-3 | *(planned, #383)* |

## Published paths

Paths another repository, a pinned plan or an org document reaches by name.
They are never moved or deleted without a new ADR that names each consumer's
migration (ADR-0002 "Decision" 1); #376 makes this a check that reads this
table's first column.

| Path | Consumer |
|------|----------|
| `ns3/routing-bench/` | swarm-routing/.github `reusable-ns3-image.yml`, `reusable-benchmark-cell.yml` (`@<commit>:ns3/routing-bench`); sim-containers `docker/protocol/Dockerfile`, `tools/protocol_images.py`, `test/downstream.txt` (`@main`); campaign plans; AntHocNet tooling |
| `python/` | `pip install ./python` (README, AGENTS.md), `dist.sh`, this repository's workflows (`python/ns3_tool/campaign.py` in `campaign-image.yml`) |
| `scenarios/` | `ns3-tool sweep --family`, `ns3-scenario-check --anchors`, `docs/families/` |
| `campaigns/` | `campaign-image.yml` (refuses any other path), swarm-routing/benchmarks runs |
| `tools/checks/check-stock-arms.sh` | sim-containers `test/downstream.txt` (`@main`) |
| `docs/markers.md` | swarm-routing/benchmarks, org docs |
| `docs/ns3-bugs.md` | swarm-routing/.github CONTRIBUTING and issue templates, sim-containers README, vcpkg `ns3` portfile |
| `docs/ns3-rcapa/` | the same, and each RCAPA ticket |
| release asset names `routing-bench-<ver>.tar.gz`, `swarm_sim_tools-<ver>*` | vcpkg port `sim-tools-ns3`, `*.lock` files read by `release_lock.py` |

A pin at a commit survives a move (the path is resolved at that commit); a pin
at a moving ref (`@main`) or a bump that moves the commit and keeps the subdir
does not, and a changed subdir changes every campaign `cell_key` (#94), so no
earlier cell is reused.

## Where a new file goes

1. **Does it build against a simulator?** Yes: under that simulator's folder
   (`ns3/`, later `omnetpp/`). No: an agnostic top-level path.
2. **In a simulator folder, by kind:** a diff to the simulator's source →
   `<sim>/patches/<ID>/` (the register ID first: an `NS3-NNN` ticket and its
   RCAPA, AGENTS.md "Agent pitfalls"); run-time code avoiding a simulator bug
   → the module that needs it, naming the ID; a comparator arm →
   `<sim>/arms/<name>/`, its own contrib module (golden rule 12); a probe →
   `<sim>/probes/` (golden rule 10); harness code → `<sim>/routing-bench/`.
3. **Agnostic, by kind:** a reader, statistic or driver → `python/ns3_tool/`
   (an agnostic module imports no ns-3-bound one, #377); a family →
   `scenarios/<family>/`; a campaign plan → `campaigns/`; a CI or release
   script → `tools/checks/` or `tools/release/`; a contract or register →
   `docs/`.
4. **A new directory** gets its `LICENSING.md` row and its row here in the
   same PR (golden rule 1).
5. **Never** move or delete a path in "Published paths" without a new ADR.
