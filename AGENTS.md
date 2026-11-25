# AGENTS.md — guide for AI coding agents

Operational guide for LLM agents working in `swarm-routing/ns3-tools`. Read this
before changing anything. Org-wide conventions:
[`swarm-routing/.github` CONTRIBUTING.md](https://github.com/swarm-routing/.github/blob/main/CONTRIBUTING.md). Shape and rules mirror
[AntHocNet's AGENTS.md](https://github.com/swarm-routing/AntHocNet/blob/main/AGENTS.md), the source repository.

## What this repo is

**Status: v1.1.0 released (2026-11-15): per-arm process isolation (`--isolateArms`, #198) and `ns3-tools` on PyPI (#196), on the CLI and marker contract v1 (`docs/markers.md`) frozen since v1.0.0 (2026-11-13; `docs/roadmap.md`); v1.2.0 next (families and metrics, additive; re-plan 2026-11-15); contract v2 is v2.0.0.** On `main`, moved from AntHocNet: the `routing-bench` comparison harness (`ns3/routing-bench/`, #2) and the result readers (`python/`, #3), behind the `ns3-tool` CLI (`compare`, `sweep`, `diagnose`, `scaffold`, #39), plus the campaign driver `ns3-campaign` (#66, #81). Probes as their own module are planned (#40); update this file in the PR that adds each part.

Protocol-agnostic diagnostics and comparison tooling: the comparison harness
(`routing-compare`), which today holds the measurement itself (the topology
oracle for BFS-reachable PDR and path stretch, the drop book for
PHY/MAC/ARP/TTL/loop root causes, both in
`ns3/routing-bench/model/routing-bench-run.cc`) and prints the
`##RUN##`/`##PROV##`/`##PERF##` lines; non-intrusive C++20 probes as their own
module (planned, #40: the oracle and the drop book extracted); and the
`ns3-tool` Python CLI (`sweep`, `compare`, `diagnose`, `scaffold`) ported
from AntHocNet's `run-scenarios.py` / `bench_parse.py`. "Universal arenas"
were the original plan; no issue schedules them, and whether they stay (or
the harness, the family catalogue #55 and the satellite harnesses #5 replace
them) is the maintainer's open decision in #161.

```
ns3/routing-bench/  the comparison harness module `routing-bench` (moved from AntHocNet as-is; routing-compare + the anthocnet-compare alias; each arm in its own process by default, `--isolateArms`, #198; a run whose simulated time stops advancing fails fast, `--livelockEvents`, NS3-001) — GPL-2.0-only
ns3/arms/<name>/    (planned) non-swarm comparator arms, one contrib module each (epic #15) — GPL-2.0-only
ns3/                (planned) the probe module (#40), the satellite harnesses on the arm registry (#5) — GPL-2.0-only
tools/checks/       CI scripts (check-scenarios.py, the family catalogue complete and agreeing with scenario_check, #55; check-stock-arms.sh; arm-delivers.sh, its verdict read through the reader, #6; check-perf-markers.sh, the ##PERF## line, #91; check-scaffold-arm.sh, the arm `ns3-tool scaffold` writes, #39; check-refs.py, every reference in the ns-3 bug register fully qualified, #247; tests/: their Python tests, measured with python/'s by ns3.yml's python-quality for SonarQube Cloud) — MIT OR GPL-2.0-only
tools/release/      dist.sh: the release assets (routing-bench tarball, ns3-tool wheel + sdist), each checked; `make dist` — MIT OR GPL-2.0-only
.cz.toml            Commitizen config; releases run through .github/workflows/release.yml (the org reusable-release.yml, #26)
python/ns3_tool/    `ns3-tool` (cli: compare = bench_parse, sweep = a port of AntHocNet's run-scenarios.py, diagnose = the drop book + scenario_check results, scaffold = an arm module skeleton; #39), the readers and statistics (bench_parse, stats_util, native/comparator views, pool_runs, sweep_summary), the plausibility checker (scenario_check: ns3-scenario-check, anchors from an --anchors file) and the campaign driver (campaign: ns3-campaign; change_plan: the change-test plans it routes, #81), stdlib only (PyYAML only to read a .yaml plan) — MIT OR GPL-2.0-only
python/tests/       their self-tests (MIT OR GPL-2.0-only); fixtures/cells/: 14 AntHocNet cells (data, GPL-2.0-only); benchmarks/: swarm-routing/benchmarks' run validator, vendored at a pinned commit
campaigns/          campaign plans (TOML), the pre-registration of each multi-protocol campaign — GPL-2.0-only
scenarios/          the network-family catalogue (#55): <family>/{preset,preflight,anchors}.toml, each value sourced; manet, fanet, vanet; README.md is the format; read by ns3-scenario-check preflight --family / results --anchors <family>/anchors.toml and ns3-tool sweep --family (python/ns3_tool/catalogue.py), never by routing-bench; tools/checks/check-scenarios.py holds it complete — GPL-2.0-only
.github/workflows/  campaign-image.yml (one image per plan, through reusable-ns3-image.yml), campaign-cell.yml (one cell in it by digest)
docs/               markers.md (the marker-line contract, ##PERF## included, #91), profiling.md (perf / heaptrack / massif on one cell), roadmap.md (the release ladder), ns3-bugs.md (the index of upstream ns-3 bugs the org found, NS3-NNN, #233), ns3-rcapa/ (one RCAPA per bug: root cause, corrective and preventive actions; README.md, _template.md), references.bib; bring-your-own-protocol.md (the user guide, #4); families/<family>.md ("configure it with ns-3", one per catalogue family, #55)
```

## Build & verify

The step-by-step version for people (prerequisites, every command, the CI
map, troubleshooting) is [`docs/development.md`](docs/development.md).

CI is [`reusable-ns3-ci.yml`](https://github.com/swarm-routing/.github/blob/main/.github/workflows/reusable-ns3-ci.yml):
the module builds inside `ghcr.io/swarm-routing/ns3-dev:latest-{debug,sanitized}`
(warm ns-3 tree; only the module compiles) and runs its test.py suites.
`latest` is the release ns-3 supports (it maintains its latest only), so
automatic CI follows ns-3 with no edit; an older ns-3 release runs only on
demand, through a manual `workflow_dispatch` passing `ns3-versions`, a JSON list such as `["3.48"]` (org
CONTRIBUTING invariant 7). The
same locally:

```bash
docker run --rm -v "$PWD:/src:ro" ghcr.io/swarm-routing/ns3-dev:latest-debug bash -c \
    'ns3-build-contrib --strict-warnings --test routing-bench=/src/ns3/routing-bench &&
     bash /src/tools/checks/check-stock-arms.sh /opt/ns-3 "aodv olsr dsdv hwmp"'
```

The module is named `routing-bench`, as in AntHocNet: every arm module that
ships `helper/<module>-bench-arms.cc` keeps registering against it. CI
(`.github/workflows/ns3.yml`) also checks that each stock arm delivers.
**NS3-001 (#238):** ns-3.49's stock AODV livelocks, so the `aodv` arm installs
AODV behind the ICMP no-route guard (`model/icmp-error-guard-routing.h`,
`helper/icmp-error-guard-helper.h`: [nsnam/ns-3-dev!3101](https://gitlab.com/nsnam/ns-3-dev/-/merge_requests/3101)'s suppression rules,
generic over any routing helper; maintainer decision 2026-11-23, the images
stay stock) and its check runs on `latest` with the others; the 3.48-only leg
of option A is gone. Retire the guard once an ns-3 release with the fix is
`latest` (the suite's NS3-001 test then reports that unguarded AODV no longer
livelocks). C++ formatting is not checked
yet, in CI (`format: false` in `ns3.yml`) or by `make`: the harness keeps
AntHocNet's style until a restyle PR adopts the org `.clang-format` and adds
clang-format back to `make lint` and `make format`. Never run clang-format on
`ns3/` before that PR.

Before pushing, run `make check` (needs `ruff`, and network for the org
tooling). It runs four targets: `lint` (`ruff check` and `ruff format
--check` on `python/` with the org ruff configuration, as CI's
`python-quality / python`), `test` (the Python self-tests), `headers` and
`org-sync-check`. `make format` runs
`ruff format python` only. The ns-3 build, its suites and the stock-arm
checks need the docker line above and run in CI.

Python (no pytest dependency; each test exits non-zero on its first failure):

```bash
for t in python/tests/test_*.py; do python3 "$t"; done
NS3_TOOL_CELLS=/path/to/AntHocNet/results/cells python3 python/tests/test_bench_parse_query.py  # the full corpus, as CI
NS3_TOOL_CELLS=/path/to/AntHocNet/results/cells NS3_TOOL_SCENARIO_CHECK=/path/to/AntHocNet/tools/bench/scenario_check.py \
    python3 python/tests/test_scenario_check_corpus.py   # scenario_check's verdicts = AntHocNet's, as CI
NS3_TOOL_ANTHOCNET=/path/to/AntHocNet python3 python/tests/test_change_plan.py   # change-plan verdicts = AntHocNet's campaign.py on every plan (PyYAML), as CI
pip install ./python   # (or `pip install swarm-sim-tools` from PyPI, published by release.yml's pypi job, #196; `ns3-tools` up to v1.1.2: `pip uninstall ns3-tools` first, README "Moving from ns3-tools") ns3-tool {compare,sweep,diagnose,scaffold}; the older scripts stay: ns3-bench-parse, ns3-native-view, ns3-comparator-view, ns3-pool-runs, ns3-sweep-summary, ns3-scenario-check, ns3-campaign
ns3-tool sweep /opt/ns-3 --only discrete --runs 10 --time 120 --dry-run   # the harness command lines, nothing run
ns3-campaign plan campaigns/anthocnet-aodv-smoke.toml   # offline: the image and every cell; validate checks a plan alone
```

Releases (#26; `swarm-routing/.github` CONTRIBUTING "Cutting a release"):
the `release` environment is ungated for now (`[settings]
release_environment = false`, maintainer decision 2026-11-11, written when
`swarm-routing/.github`'s `repo-settings` runs in `apply` mode; `true`
would make the maintainer approve each publish). Dispatch `release.yml`
with `dry-run`, then `bump`; merging the bot's
`chore(release): bump version A to B` PR tags and publishes with no
approval step; its `vcpkg-ports: sim-tools-ns3` then opens the port bump in
swarm-routing/vcpkg-registry (one vcpkg port per simulator folder: `ns3/` is
`sim-tools-ns3`, on the `ns3` port, from `routing-bench-<ver>.tar.gz`;
swarm-routing/vcpkg-registry#76). `make dist`
builds the assets locally (`DIST_CHECK=0` skips the docker suite and the
wheel check).

A reader change must keep its output byte-identical on the fixtures unless the
change is the point (then say so in the PR and update AntHocNet's callers).

## Golden rules (invariants — do not break)

Org-wide (1–9), then this repo's own.

<!-- org-sync:begin org-rules -->
1. **Licensing per directory, as AntHocNet** ([`LICENSING.md`](LICENSING.md);
   AntHocNet [LICENSING.md](https://github.com/swarm-routing/AntHocNet/blob/main/LICENSING.md),
   [ADR-0028](https://github.com/swarm-routing/AntHocNet/blob/main/docs/adr/0028-core-is-dual-licensed.md)). A
   simulator-free `core/` and the standalone tooling are `MIT OR GPL-2.0-only`;
   ns-3 modules, the site, docs and data are `GPL-2.0-only`. Every original
   `.h`/`.hpp`/`.cc`/`.cpp`/`.go`/`.py`/`.sh` starts with
   `// Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)` +
   `// SPDX-License-Identifier: <MIT OR GPL-2.0-only | GPL-2.0-only>` (`#`
   comments where needed), matching its directory in `LICENSING.md`; an
   outside contributor may add their own `Copyright (c) <year> <Name>` line
   beneath the org line, never replace it, and signs off every commit (DCO,
   CONTRIBUTING "Outside contributions"). CI (`reusable-licence-check.yml`)
   checks the SPDX line, and the org line's place when a header names more
   than one holder; a header with a single, other holder (a replaced org line,
   or third-party code) passes it, so review catches that. A new directory
   gets its row in `LICENSING.md` in the same PR.
2. **The licence boundary only goes one way.** GPL code may use the dual
   parts; dual code never pulls GPL-only code in: a `core/` file includes only
   the C++ standard library, other `core/` files and the dual-licensed `core/`
   of a dependency pinned by commit and declared as the `core-deps` input of
   every workflow that runs the licence check (one calling
   `reusable-licence-check.yml`, or one calling `reusable-ns3-ci.yml`, which
   forwards it; workflow file names differ per repo), each with the same pin,
   with `core-roots` naming the repo's own `core/`
   (without it the check skips core includes; a protocol's `core/` on
   swarm-core's; CI checks it, `check-headers --core-dep`), and a dual script imports no GPL-only code. Code coming from AntHocNet keeps its
   licence: its `core/`/`tools/` (dual) may land in dual or GPL paths here; its
   `ns3/` modules and `web/` (GPL-2.0-only) only in GPL paths. Third-party code
   (AntHocNet's vendored `aomdv`/`gpsr`, IITP RAS) lands only in GPL paths with
   its provenance recorded. Write clean implementations against public ns-3
   interfaces rather than copying ns-3's `src/aodv`/`src/olsr`.
3. **Wire formats are POD + versioned.** Control headers are
   simulator-independent POD structs with bounds-checked little-endian
   readers/writers, a leading version byte, and deterministic roundtrip + fuzz
   tests. Changing a field or its units bumps the version byte.
4. **No contrib module named `core`** (collides with ns-3's `src/core`). The
   shared module is `swarm-core` (`#include "ns3/swarm-core-module.h"`), and
   every protocol builds on it, AntHocNet included: `core/` on its `core/`, the
   ns-3 adapter on `SwarmRoutingBase` (swarm-routing/swarm-adapter-ns3#14).
5. **Determinism.** A fixed `--seed=<N>` gives byte-identical output. All
   randomness through the simulator's seeded streams or an injected RNG port;
   never libc `rand()`, wall-clock time, or unordered-container iteration order
   in anything that reaches an output.
6. **Comparisons are paired.** Per-seed deltas across >= 20 seeds, emitting the
   canonical `##CONFIG##`, `##RUN##`, `##BENCH##`, `##DIAG##` lines. A
   comparator arm (a protocol we did not design) counts only after its three
   gates: a fidelity sheet from its paper, the per-PR delivery smoke, and an
   anchor reproducing the paper's own trend.
7. **Keep bounded structures bounded** (visited paths, dedup histories, queues
   carry a configured cap).
8. **CI hygiene.** Actions pinned by full commit SHA with a `# vX.Y.Z` comment;
   buildx caches scoped per profile; transient artifacts `retention-days` <= 7.
   Every job that runs steps has a `timeout-minutes` cap (a job that only
   calls a reusable workflow cannot take one: the called workflow's jobs carry it), and every apt, npm or installer step
   its own, sized from recent green runs; `apt-get update` runs with
   `--error-on=any` inside a shell retry. Ubuntu mirror outages are the usual
   cause of a red run.
9. **Nothing shipped depends on `.claude/`.** Skills hold procedures; scripts
   that anything shipped needs live in `tools/` (AntHocNet ADR-0014).
<!-- org-sync:end org-rules -->
10. **Probes are non-intrusive.** They read trace sources and callbacks only; attaching a probe never changes a simulation's output (same seed, byte-identical `##RUN##` with and without it — test it).
11. **The marker lines are a versioned contract.** `##CONFIG##`/`##RUN##`/`##BENCH##`/`##DIAG##` fields are only appended; a removal or meaning change bumps the schema version and updates the reader and `benchmarks`' parsers in the same change (AntHocNet #128, #771).
12. **Protocol-agnostic.** No protocol is special-cased in an arena or the harness; protocols register as arms (AntHocNet ADR-0027). The comparator arms that are not swarm protocols (secure, learned, DTN: epic #15) live here by maintainer decision (2026-11-02), each as its **own** contrib module under `ns3/arms/<name>/` that registers through `helper/<name>-bench-arms.cc` exactly as an out-of-repo arm does; no code outside its directory hard-codes a reference to it or branches on its name (registration and docs may name it). Swarm-based variants live with their protocol (ARA, BeeAdHoc). Every arm clears the three gates (rule 6) before a number counts.
13. **Statistics stay scripted.** Noise verdicts and paired tests come from the CLI, never from eyeballing numbers (AntHocNet ADR-0014).

## Conventions

<!-- org-sync:begin conventions -->
- Issues follow the org taxonomy ([CONTRIBUTING.md](https://github.com/swarm-routing/.github/blob/main/CONTRIBUTING.md#issues), from
  [AntHocNet ADR-0013](https://github.com/swarm-routing/AntHocNet/blob/main/docs/adr/0013-track-bugs-and-findings-as-issues.md)): one type label
  (`bug`/`enhancement`/`chore`/`documentation`/`verification`, plus `epic` for
  umbrellas), area label(s) (`protocol`/`adapter`/`ns3`/`benchmark`/
  `observability`/`packaging`/`ci`/`learn-site`/`literature`), one `model:*`
  suggestion (a model on the Claude Pro plan), one `priority:P1|P2|P3` on
  non-epic issues (none on an epic), and a `release:vX.Y.Z` label only when
  a release in the repository's ladder (`docs/roadmap.md`, else the org
  ROADMAP's release train) gates the issue: that label set is the version's
  scope, released when its issues are done (CONTRIBUTING "Cutting a
  release"). Labels come from `.github`'s `labels.json`, applied to every
  repository as soon as it changes (never deleting one); a release version
  it lacks is added there (and to CONTRIBUTING's label table), or, in a
  repository that keeps its own release labels (AntHocNet), created with
  `gh label create release:vX.Y.Z`.
- Issue bodies: **Context** (evidence, numbers, links) · **Scope** ·
  **Acceptance criteria** (checkboxes) · **Depends on** (cross-repo form
  `swarm-routing/<repo>#N`) · **References**. Children of an epic say "Part of
  #N" and are linked as sub-issues. Comments you post end with the Claude Code
  footer.
- Issues migrated from AntHocNet carry `migrated` and start with *Migrated from
  `danieljoppi/AntHocNet#N`*.
- Epics are listed in a public repository's README `## Epics` and the org
  [ROADMAP](https://github.com/swarm-routing/.github/blob/main/ROADMAP.md#epics),
  generated from the `epic` issues by `.github`'s `tools/epics/epics.py`. An
  open epic is Planned (no sub-issue closed) or In progress (some closed); it
  is Done or Dropped only once the epic itself is closed (completed or not
  planned). The lists follow the issues with no hand step: an issue change
  that can move them makes the org-managed `epics-changed.yml` run org-bot's
  `epics` task, which opens the refresh PRs. Never edit a generated section
  by hand; private repositories keep none.
<!-- org-sync:end conventions -->

## Git workflow

<!-- org-sync:begin git-workflow -->
- Branch from `main` (`claude/<short-topic>`), one focused change per PR.
- **Always open a PR to `main`** once the branch is pushed — every change is
  tracked through one.
- **PRs are squash-merged** (the only merge method enabled). The PR title is
  the commit on `main`: a lowercase Conventional Commit, `type(scope)!:
  subject`, type one of `feat fix docs style refactor perf test build ci
  chore revert`, subject starting lowercase.
- Push with `git push -u origin <branch>`; merge when CI is green.
- **`main` takes no direct push**, in any repo: its ruleset requires a PR and
  the required checks, not an up-to-date branch. Bots push `bot/<name>`
  branches and open PRs; a release is the bump PR from `bot/release`, tagged
  after it merges (CONTRIBUTING "Cutting a release").
- A PR behind `main` may merge as it is. Update it
  (`gh api -X PUT "repos/<owner>/<repo>/pulls/<n>/update-branch"`, the PR's
  base repository) only when `main` changed what it touches (a template, a
  workflow, a required check), then merge after its CI. Never update a
  merge-queue PR by hand: enable auto-merge and the queue tests it on the
  latest `main` (CONTRIBUTING "Merge when CI is green"). Never force-push a
  branch someone else pushed. A behind `bot/release` PR: dispatch the release
  `bump` again.
- **Settings are code.** Settings, rulesets, required checks and the Actions
  allowlist change only by a PR to the repo's `[settings]` in
  `.github/org-sync.toml` or to `templates/rulesets/` in
  `swarm-routing/.github`, never in the UI or by a direct API write. A
  rulesets change applies on merge, a `[settings]` change on its push through
  the org-managed `settings-apply.yml` (swarm-routing/.github#569). A required
  check runs on every PR (no `paths:` filter; skip work inside a gate job) and
  is named exactly as its check run. A new third-party action goes into
  `defaults.json` `selected_actions` (`templates/rulesets/`) in swarm-routing/.github
  before or with the workflow that uses it, or `repo-settings` refuses the repo.
<!-- org-sync:end git-workflow -->

<!-- org-sync:begin skills -->
## Agent skills

The org's procedures ship as the Claude Code plugin **`swarm-routing`**
([`swarm-routing/skills`](https://github.com/swarm-routing/skills)), which this
repository's `.claude/settings.json` enables; other agents install the same
skills with `npx skills add swarm-routing/skills` ([skills.sh](https://skills.sh)).
A skill is the procedure; its script does the work without it (golden rule 9),
so an agent without the skill, or a session that does not read this
repository's settings, starts from the script. Plugin missing (it was
`org-repo` before 2026-11-09)? Run `claude plugin marketplace update
swarm-routing` and start a new session.

| Task | Script (any agent) | Skill |
|------|--------------------|-------|
| Bring this repository onto the org templates, or fix their drift | `swarm-routing/.github` `tools/org-sync/org_sync.py` | `org-repo` |
| Write or review a protocol's paper-fidelity sheet (`docs/fidelity.md`) | `swarm-routing/.github` `tools/fidelity/fidelity.py` | `fidelity-sheet` |
| Check a diff against the org golden rules before a PR or a review | `swarm-routing/.github` `tools/protocol-review/check_invariants.py` | `protocol-review` |
| Bring the README, AGENTS/CLAUDE/CONTEXT and docs/ to the org standard | `swarm-routing/.github` `tools/docs-review/check_docs.py` | `docs-review` |
| Find new papers on a topic, or confirm a reference (free sources only) | `swarm-routing/.github` `tools/lit-search/lit_search.py` | `lit-search` |
| Give a repository its docs/references.bib, or review it (every paper and org release it relies on, confirmed from its record) | `swarm-routing/.github` `tools/fidelity/fidelity.py` (bib), `tools/zenodo/zenodo.py` | `references` |
| Take open pull requests from review to merge (CI, review threads, merge) | `swarm-routing/.github` `tools/pr-status/pr_status.py` | `pr-shepherd` |
| Measure what a session loads from the agent files, or where a finished session's tokens went | `swarm-routing/skills` `tools/token-audit/token_audit.py` | `token-audit` |
| Register a repository for the OpenSSF Best Practices badge, or check its answers | `swarm-routing/.github` `cmd/bestpractices` (Go) | `bestpractices` |
| Check or bump the release a repository builds on (`swarm-core.lock`, `ns3-tools.lock`) | `swarm-routing/.github` `tools/checks/release_lock.py`, `tools/checks/check-swarm-core-pin.py` | `dependency-bump` |
| Cut a release on the maintainer's request, and its aftercare | `swarm-routing/.github` `tools/release/release_check.py`, `tools/zenodo/zenodo.py` | `release` |
| Record a reviewed SonarQube Cloud false positive or accepted finding | `swarm-routing/.github` `tools/sonar-triage/sonar_triage.py` | `sonar-triage` |

A skill only this repository uses lives in its own `.claude/skills/`; one two
repositories need moves to the plugin. Skills that file, cite and extract
papers stay in the maintainer's private library; a public skill may point to
them, never carry their content.
<!-- org-sync:end skills -->

<!-- org-sync:begin agent-defaults -->
## Working defaults

Condensed from [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills).

- **Assumptions:** state the ones that matter. Ask only when the choice
  belongs to the maintainer (a default, a published number, a cell, the
  scope), with your recommendation and its reason, never the options alone.
  Otherwise pick the sensible option, say which, and keep going: long
  unattended runs, like campaigns, depend on that.
- **Simplicity:** the least code that solves the task. No speculative
  features, configurability or abstractions for one use.
- **Surgical diffs:** every changed line traces to the request. Match the
  surrounding style. Mention unrelated dead code rather than deleting it, and
  remove only the orphans your own change created. Update the doc or ADR of a
  documented decision you change.
- **Verifiable goals:** a bug gets a reproducing test first; a refactor passes
  before and after. Finish when the check passes, not when the code looks right.

## Session habits

- **Handoffs are always a ticket**: work in flight at a session's end, or a
  handoff asked for, is an issue from the *Handoff* template (label
  `handoff`), never a file in the repo; a session continuing a handoff
  updates that issue. Continued work starts from the newest open `handoff`
  issue for it, a new task from the request; close the issue, and any older
  one it superseded, when its work is done ([AntHocNet ADR-0013](https://github.com/swarm-routing/AntHocNet/blob/main/docs/adr/0013-track-bugs-and-findings-as-issues.md) item 5).
- **Attach only the repositories the task needs**: every request loads each
  attached repository's agent files.
- **Start from the record, not from memory:** the matching `handoff` issue,
  then the issue's acceptance criteria, then `main`. Check a claim against its
  source before it goes into an issue or a PR.
- **Script what repeats**: a check or lookup run more than a few times
  becomes a script in `tools/` that prints a summary; read the verdict, not
  the raw data (AntHocNet ADR-0014).
- **Automate what can be automated** (org CONTRIBUTING invariant 8): a step
  stays manual only when no API or permission exists for it, or the
  maintainer reserves the decision; list it in swarm-routing/.github#568.
- **Measure before cutting or adding agent text** with the `token-audit`
  skill (`swarm-routing/skills` `tools/token-audit/token_audit.py`). MCP
  servers, plugins, token habits and the long form of each pitfall below:
  [`docs/agents.md`](https://github.com/swarm-routing/.github/blob/main/docs/agents.md)
  in swarm-routing/.github (ADR-0005).

## Response style — caveman (token economy)

Answer in tight, low-filler prose: no hedging, pleasantries or preamble; same
information, fewer output tokens. **The record stays full:** code, commands,
paths, error text and benchmark numbers byte-for-byte, and commit messages,
PR bodies, ADRs, `docs/` and issue threads detailed (AntHocNet's AC_BE_NQOS /
A2 investigation was recoverable only from thorough threads). Caveman the
chat, not the record.

## Agent pitfalls

- **Before every push, run `make check`** (none: the "Build & verify"
  commands; `make pre-push TITLE='…'` where it exists) **and check the PR
  title** (Git workflow): a skipped step costs a CI round
  (swarm-routing/.github#586).
- `gh api … -F body=@file` reads the file; `-f body=@file` posts the literal
  text `@file`.
- When the permission system refuses a command (a merge, say), stop and report
  it. Never retry it another way, and never ask another agent to run it.
- Edit files with the editor tools, never a shell heredoc or `sed -i`, and
  touch one repository per command (swarm-routing/.github#578).
- Stage files by name, never `git add -A`; keep build output in `.gitignore`
  (swarm-routing/.github#644).
- A Go test reads only files under `cmd/` or `internal/` (`testdata/`)
  (swarm-routing/.github#587).
- Clean up only your own directory, never a shared one
  (swarm-routing/.github#644).
- Search an output the harness saved to a file (`grep`, `head`, `sed -n`),
  never read it whole; wait on a PR with `pr_status.py wait` or `wait
  --merged`, not by subscribing to its activity (swarm-routing/.github#794).
- A PR body's `Closes #N` closes the issue on merge; write `Part of #N` while
  acceptance criteria remain open.
- Before saying a tool or check is missing, look at `main` (`git fetch`,
  `origin/main`), not a stale local checkout.
- Write another repository's issue in full, `swarm-routing/<repo>#N`, also in
  a list or range: a bare `#N` links to the repository the text is in
  (swarm-routing/.github#277). An ns-3 item is its GitLab URL (or link text
  `nsnam/ns-3-dev#N`); text bound for ns-3's GitLab names ours by full GitHub
  URL (CONTRIBUTING "ns-3 bugs (RCAPA)").
- An issue called done in `ROADMAP.md` or an AGENTS.md is not evidence: read
  its acceptance criteria (swarm-routing/.github#274).
- Change text inside `org-sync:begin/end` markers only through
  `swarm-routing/.github` `templates/`, then org-bot's refresh PRs; never add
  such commits to an unrelated PR (swarm-routing/.github#236).
- With a merge queue, merge by enabling auto-merge (squash); a direct merge is
  refused (HTTP 405). Only the required checks (`gh api
  'repos/{owner}/{repo}/rules/branches/main'`) gate a merge; a report-only
  check (`codecov/patch`, Sonar) is triaged, not waited on. Merge an outside
  contributor's PR only after `dco` passed on its head, and never push to it
  (swarm-routing/.github#288; CONTRIBUTING "Merge when CI is green").
- `review / coderabbit` is required (swarm-routing/.github#294), so
  auto-merge may be enabled at once; still fix or answer every CodeRabbit
  thread before resolving it, and call a PR thread-free only after
  `pulls/N/comments` and the reviews show none. Where the gate is not
  required yet, wait with `pr_status.py gate REPO#N`
  (swarm-routing/.github#238).
- Never add a `Signed-off-by` trailer, for the maintainer or anyone else
  (CONTRIBUTING "Outside contributions").
- Never delete a stale branch or ask the maintainer to: org-bot's daily
  `branch-sweep` does (swarm-routing/.github#595).
- Releases are cut on request only, once the version's `release:vX.Y.Z`
  issues and its ladder exit criteria are done; never approve a gated publish;
  recover a failed publish with "Re-run all jobs"; read a DOI from Zenodo,
  never type it; never dispatch the site's `release-sync.yml` by hand
  (swarm-routing/.github#571; CONTRIBUTING "Cutting a release").
- Cite a paper by its `https://doi.org/<DOI>` link, read from its record
  (`lit-search`), or a DOI-less work by its publisher's page; never point into
  or name the private paper library.
- Never dismiss a security alert or handle a leaked secret: both are the
  maintainer's; review `security-autofix.yml`'s PRs like any other
  (swarm-routing/.github#629; CONTRIBUTING "Security alerts").
- An ns-3 bug, or its investigation, gets an RCAPA ticket in
  swarm-routing/sim-tools first (`NS3-NNN`), then its doc and register row;
  every workaround links the ID, and upstream reports go out only through
  swarm-routing/ns3-upstream-report. A regression in a published library
  version gets one in that library's repository (`<PREFIX>-NNN`), open until a
  release carries the fix; the pins and `git tag --contains` decide, never
  memory (CONTRIBUTING "RCAPA", "ns-3 bugs (RCAPA)").
<!-- org-sync:end agent-defaults -->

## Where to look

| You want to… | Go to |
|--------------|-------|
| Where the Python came from (ported, MIT OR GPL-2.0-only → `python/`) | AntHocNet `tools/bench/` (`bench_parse.py`, `stats_util.py`; `scenario_check.py`, #28; `campaign.py` as `change_plan.py`, #81), `ns3/tools/run-scenarios.py` (`ns3-tool sweep`, #39); AntHocNet runs them from here since #29 |
| Where the harness came from (moved, GPL-2.0-only), and its design | `ns3/routing-bench/` (README there); AntHocNet `docs/comparison-harness.md`, ADR-0027 |
| Run or add a network family (MANET, FANET, VANET: the preset, its cells, preflight, anchors, sources) | [`scenarios/README.md`](scenarios/README.md) (the format, "Adding a family"), the family's page in [`docs/families/`](docs/families/), `python3 tools/checks/check-scenarios.py` (`--commands` / `--configs DIR`: the presets against routing-compare's `##CONFIG##`); #55. The catalogue describes routing-bench's presets; changing a preset's meaning is a contract change (rule 11) |
| Add a protocol as an arm and compare it, from the released packages (the user guide: install, stock arms, `ns3-tool scaffold`, a 20-seed paired comparison, the three gates, citing) | [`docs/bring-your-own-protocol.md`](docs/bring-your-own-protocol.md) (#4), its worked example run for real |
| Run a multi-protocol campaign (one image, cells by digest, a benchmarks manifest) | `python/ns3_tool/campaign.py` (`ns3-campaign`: `validate`, `plan`, `build`, `dispatch`, `status`, `collect`, `verdicts`; its docstring is the plan format), a plan in `campaigns/`, `campaign-image.yml` + `campaign-cell.yml`; #66, swarm-routing/.github#107. Every cell has a key over every pinned input (`cell_key`; in `##PROV##` and the artifact name): `dispatch` reuses a cell already run, from the local cache (`~/.cache/ns3-campaign/`), a benchmarks checkout (`--benchmarks DIR`) or this repository's artifacts, and stops on any mismatch; `--no-reuse` runs everything (#94). Cost (#95, `python/ns3_tool/cost.py`): `collect` appends each cell's `##PERF##` rows and each run's overhead to `~/.cache/ns3-campaign/perf.jsonl` (bounded); `plan` prints on stderr, only when a sample exists, per arm and in total the cells, reusable cells, estimated runner-minutes and elapsed time at `cap` (fit `wall ≈ a + b·(nNodes^k·time)` per arm; an arm without samples bounded by the slowest known one); `dispatch --budget-minutes N` (or the plan's `budget_minutes`) refuses an estimate over budget or unknown unless `--yes-over-budget`, and without a budget there is no guard; `python3 python/ns3_tool/cost.py fit` prints the fits, `cost.py seed BENCHMARKS` the seed samples of a benchmarks checkout. The campaign image is `ns3-tools-dev` (`ns3-tools-ns3-campaign` before #169, frozen): `ns3.yml`'s `dev-images` job, on `main`, deletes its versions older than 2 days that no committed file pins (swarm-routing/.github#370) |
| Run a protocol repository's change tests (AntHocNet's plans: cells x arms) | `python/ns3_tool/change_plan.py`, reached through `ns3-campaign` for any plan with a `generation` key (`plan`, `dispatch`, `status`, `collect [--redispatch]`, `verdicts`; `--repo`, `--workflow`; its docstring is the plan format): every cell goes to the repository's caller of swarm-routing/.github's `reusable-benchmark-cell.yml` pinned to the plan's `source_sha` and image (swarm-routing/.github#157); verdicts byte for byte AntHocNet's (`NS3_TOOL_ANTHOCNET=<checkout> python3 python/tests/test_change_plan.py`, as CI); `verdicts` pairs arms; a plan's `reference: <protocol>` (or a list) also pairs every other protocol of a cell against it by seed, an anchor's read (#152); when the caller forwards `key`, `dispatch` passes each job's cell key and reuses a cell an earlier run with that key produced (`--dry-run` shows which, `--no-reuse` runs all; #155); `plan` shows each arm's ns-3 release, image and commit and flags a control whose arms differ in more than it `isolates` (#89); `collect` rejects a cell whose `##PROV## modules=` dependency commits are not the campaign's one set, recorded in `state.json` (#148); with `freeze: true` (opt-in; it needs a token that may create tags) the first `dispatch` tags the commit the plan's `ref` names as `campaign/<generation>` and dispatches every cell of the campaign at that tag, so a dependency bump merged on the branch mid-campaign cannot reach its later cells (swarm-routing/ARA#288); a never-published change test (a protocol's smoke plan) may name `image` by tag with `rolling_image: true`: the first `dispatch` records the tag's digest in `state.json` and the campaign keeps it whatever the tag does later (anchors, pilots and anything published pin a digest); #81, epic swarm-routing/.github#156 |
| Comparator arms (SAODV, SEAD, TAODV, DRL, DTN) and their gates | epic #15; the arm contract: AntHocNet `docs/comparison-harness.md`, ADR-0027 |
| Found or suspect an ns-3 bug (a stock arm hangs, crashes or moves with unrelated changes) | open the `[rcapa] NS3-NNN` ticket first, then [`docs/ns3-rcapa/`](docs/ns3-rcapa/README.md) (the RCAPA from `_template.md`) and its row in [`docs/ns3-bugs.md`](docs/ns3-bugs.md) ("Adding a bug"); known bugs, their workarounds and upstream status are in that index; the maintainer files upstream (#233) |
| Measure what an arm costs, or read a protocol's internals | `##PERF##` (CPU, wall time and events per arm and seed; peak RSS only when the process runs one arm, and then the process peak up to that seed, `-` otherwise; `--perf`, default on; never compared between cells): `docs/markers.md`, `tools/checks/check-perf-markers.sh`, `bench_parse --from perf`, `docs/profiling.md` (#91, #97); a protocol's own counters come from swarm-core's router observer (`SwarmRoutingHelper::CollectStats`, swarm-routing/ns3-swarm-core#42), state footprint in the harness still open in #91 |
| Issues migrated from AntHocNet (2026-11-01) | the issues labelled `migrated`, each starting with *Migrated from*; #2 to #8 here came from AntHocNet #764, #771, #772, #773, #791, #294, #431 |
| The org's invariants, labels, issue shape | [`swarm-routing/.github` CONTRIBUTING.md](https://github.com/swarm-routing/.github/blob/main/CONTRIBUTING.md) |
| The reference implementation and its history | [`swarm-routing/AntHocNet`](https://github.com/swarm-routing/AntHocNet) (`AGENTS.md`, `CONTEXT.md`, `docs/adr/`) |
| Know which release a piece of work serves, or why something is not planned | [`docs/roadmap.md`](docs/roadmap.md): the ladder v0.1.0 → v0.2.0 → v1.0.0 (contract v1 frozen) → v1.1.0 → v2.0.0 (contract v2), per-release exit criteria, the non-goals; issues carry `release:` labels |
| Pick up open work | this repo's issues — highest open `priority:P*` first; newest open `handoff` issue for work in flight |
