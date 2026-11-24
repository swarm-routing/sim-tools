# The marker-line contract

`routing-compare` (and its alias `anthocnet-compare`) prints its results as
marker lines on stdout: a line that starts with `##NAME##`, then fields. The
readers in [`python/ns3_tool/`](../python/ns3_tool/) and
[swarm-routing/benchmarks](https://github.com/swarm-routing/benchmarks)'
validator consume them, so their shape is a contract (golden rule 11): fields
are only appended; removing a field or changing its meaning bumps the contract
version and updates the readers and `benchmarks`' parsers in the same change.

The machine-readable contract is `benchmarks`'
[`schemas/markers/v<N>.json`](https://github.com/swarm-routing/benchmarks/tree/main/schemas/markers)
(vendored here under `python/tests/benchmarks/`). This page is the human
description of what the harness prints and which lines are results.

## Version

Today's output is **contract v1**: there is no `##HARNESS## version=<n>` line
yet (#3), and v1 does not require one. Version 2 (#79) adds that line, makes
the harness print `##BENCH##` and `##DIAG##` itself, and records the positional
fields of `##PERF##` below.

## Stability

From ns3-tools **v1.0.0** (maintainer decision 2026-11-13, `docs/roadmap.md`),
contract v1 as this page describes it and the `ns3-tool` CLI (`compare`,
`sweep`, `diagnose`, `scaffold`, and the console scripts kept as aliases) are
**frozen**: marker fields, marker lines, commands and options are only
appended. Removing one, or changing what one means or its units, is a
breaking change: it waits for the next major release (v2.0.0, contract v2,
#79), which says what changed and how to migrate, and moves `benchmarks`'
schema in step. Until then a replacement is added beside the old field or
option, and the old one keeps working.

## Results and cost

Every line below except `##PERF##` is a **result**: for a fixed seed it is
byte-identical run to run (org rule 5), and comparisons pair it by seed (org
rule 6). `##PERF##` is **cost**: CPU and wall time differ between two runs of
the same seed by nature. So:

- the determinism gate (`.github/workflows/ns3.yml`, `determinism:`) runs with
  `--perf=0`, and `tools/checks/check-perf-markers.sh` proves that `--perf`
  adds `##PERF##` lines and changes no other byte (two same-seed runs minus
  `##PERF##` are identical, and equal to the `--perf=0` run);
- no reader compares `##PERF##` between cells: `bench_parse` passes it through
  verbatim under the compare table and `--control` reads `##RUN##` only
  (`python/tests/test_perf.py` checks every fixture cell with `##PERF##` lines
  added); the one reader that pools it across cells is the campaign cost
  estimate (`python/ns3_tool/cost.py`, ns3-tools#95), which predicts
  runner-minutes for `ns3-campaign plan` and its `dispatch` budget guard and
  never feeds a verdict; `ns3-campaign verdicts` reads it within each cell
  only, printing per arm the CPU s per simulated s (`cpu_s` over the
  `##CONFIG##` `time=`) and events/s as median [min..max] across seeds, on
  stderr after the verdicts, labelled descriptive, unpaired and noisy, never a
  verdict or an exit code, and nothing at all for a cell without `##PERF##`
  (ns3-tools#91);
- the workflow-written lines `##ARGS##` and `##PROV##` are not harness output
  either: they describe how a cell was run, not what it measured.
- the livelock watch (`--livelockEvents`, NS3-001) adds no marker and no
  `##CONFIG##` field: a run it does not stop prints the same bytes as with it
  off, and a run it stops prints no row, only one `routing-bench: livelock:`
  line on stderr, and fails (exit 70; `ns3/routing-bench/README.md`
  "Failing fast on a livelock").

Across ns-3 releases a seed draws the same scenario: node placement, movement
and the flows' start times are pinned to streams that do not depend on how
many streams the release's devices take (swarm-routing/AntHocNet#1222; the
layout is in [`ns3/routing-bench/README.md`](../ns3/routing-bench/README.md)
"The same field on every ns-3 release"). Result lines can still differ between
releases wherever ns-3 itself behaves differently, so a cell pins its image
and two releases are compared by seed, never row for row.

## The lines, per seed and arm

For each arm (in `--protocols` order) and each seed `firstRun..firstRun+runs-1`
the harness runs one simulation and prints, in this order (some only under a
flag or a condition, absent rather than zero when they do not apply):

| Marker | Fields | When |
|--------|--------|------|
| `##DROPID##` | `<seed> <arm> key=value ...` | UDP runs |
| `##REINJ##` | `<seed> <arm> key=value ...` | arms whose measurement keeps the re-injection books |
| `##RUN##` | `<seed> <arm> pdr delay delay99 thrput nrl jitter off50 off90 nrl_bytes` | always; positional, the row pairing uses |
| `##HOLD##` | `<seed> <arm> (count mean_ms max_ms)...` | arms with pending-queue instrumentation |
| `##AIR##`, `##ENERGY##` | `<seed> <arm> ...` | the energy model on (`--energyJ` > 0) |
| `##GOODPUT##` | `<seed> <arm> goodput_kbps` | always |
| `##ROUTE##` | `<seed> <arm> ...` | UDP runs |
| `##PERF##` | `<scenario> <arm> <seed> <cpu_s> <wall_s> <events> <maxrss_kb>` | `--perf` (default on) |

After every arm and seed: `##MATCH##` and `##COMMON##` (per seed, across arms),
the summary table and `# stddev` lines. Before the runs: `##CONFIG##`
(`key=value`).

### Reading an arm that is not unicast routing

Two readings assume an arm that forwards data hop by hop over unicast and
spends control packets to find its routes (#351):

- **NRL** (`##RUN##` `nrl`, and `nrl_bytes`) counts routing *control*
  packets (bytes) per delivered data packet (byte). An arm that sends no
  control traffic, a flood for instance, reads 0 by definition, however
  many data copies it sends. Its cost is the channel occupancy: `##AIR##`
  `<seed> <arm> txS rxS ccaS busyPct`, the last field the percentage of
  node-time the medium was busy, compared between arms by seed.
- **The drop book** (`##DROPID##` and the `# drops` line: pdr + route +
  queue + mac + chan + ttl = 100 % of offered packets) counts one data
  transmission received at most once per hop; `chan` is the residual of
  `hopTx - hopRx` after the other causes. Under broadcast forwarding every
  reception counts as a hop received, so `hopRx` exceeds `hopTx` and `chan`
  and the sum go far negative (about -7800 % for a toy flood). The bytes
  stay as they are (contract v1); `ns3-tool diagnose` prints `n/a` for that
  arm's `chan` and `sum` and a warning line with the raw values whenever
  `hopRx` exceeds `hopTx` or a cause is below -100 %. PDR still reads as
  for any arm; the other causes count events on every copy, so read them
  with care.

## `##PERF##`: what one run cost

```
##PERF## <scenario> <arm> <seed> <cpu_s> <wall_s> <events> <maxrss_kb>
##PERF## paper olsr 3 0.404 0.409 4302 -
```

| Field | Meaning |
|-------|---------|
| `scenario` | `--scenario` (`-` when none was given) |
| `arm`, `seed` | the run, as in its `##RUN##` row |
| `cpu_s` | user + system CPU seconds of the process during this run (`getrusage(RUSAGE_SELF)` delta), 3 decimals |
| `wall_s` | wall seconds of this run (steady clock delta), 3 decimals |
| `events` | events the ns-3 simulator executed in this run (`Simulator::GetEventCount()`, read before `Simulator::Destroy()`); events/s is `events / wall_s` |
| `maxrss_kb` | the process's peak resident set in kB (`ru_maxrss`), **only when the process runs a single arm**; `-` otherwise |

`maxrss` is a process-lifetime peak, so with two arms in one process the second
arm's number would include the first's. It is printed only when the arm has
its process to itself: one arm in `--protocols`, or every arm under
`--isolateArms` (the default since ns3-tools#198, each arm in its own worker
process); with several seeds of that arm it is the peak up to that seed. With
`--isolateArms=0` and several arms it is `-`.

Read it through the reader, never by column position:

```bash
python3 python/ns3_tool/bench_parse.py --get row --from perf --proto olsr CELL     # scenario seed cpu_s wall_s events maxrss_kb
python3 python/ns3_tool/bench_parse.py --get maxrss_kb --from perf --proto olsr CELL
```

`bench_parse.parse_perf()` returns each line as a dict (plus `events_per_s`).
It also reads AntHocNet's older per-process form,
`##PERF## <scenario> all <wall_s> <maxrss_kb>` (swarm-routing/AntHocNet#131,
written by its `run-scenarios.py` around one process that ran every arm): the
arm is `all` and seed, CPU and events are absent. The two forms differ in field
count (7 against 4), which is how the reader tells them apart.

These numbers are descriptive and noisy: they depend on the runner's CPU and
load. Compare them only between cells run on the same kind of runner, and never
gate on them. To see *where* the time or memory goes, profile one cell
([profiling.md](profiling.md)).

### Why this is not a version bump

`routing-bench` never printed `##PERF##` before, and contract v1 lists `PERF` as
free-form, so the new line is an addition that every v1 reader and `benchmarks`'
v1 validator accept. Its positional fields enter the machine-readable contract
with v2 (#79; the matching `schemas/markers/v2.json` entry is
swarm-routing/benchmarks#33).
