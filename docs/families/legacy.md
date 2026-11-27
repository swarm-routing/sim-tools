# Legacy defaults: configure routing-compare's preset-free cells with ns-3

Two cells of the discrete taxonomy run on no preset at all: routing-compare
without `--scenario`, on the harness's built-in defaults, with a handful of
flags on top. They predate the presets and are kept because AntHocNet's
nightly regression signal and its published scenario pages are measured on
them:
- **dense-small**, a small, dense, barely mobile field, cheap enough to
  run every night. It is the fast regression cell, and AntHocNet's hard
  case;
- **heavy-load**, the paper base field's geometry with twice the sources at
  a much higher rate, so the bottleneck moves from route discovery to
  channel contention.

They are not one network family in the sense of [MANET](manet.md),
[FANET](fanet.md) or [VANET](vanet.md): no published setup defines them, and
every value they resolve to is either the harness's default or the cell's
own flag. The catalogue keeps them so that any arm can be measured on the
same cells AntHocNet's history uses.

This page shows how to run them in ns-3 with the harness in this
repository, for any arm. The catalogue entry is
[`scenarios/legacy/`](../../scenarios/legacy/): `preset.toml`,
`preflight.toml` and `anchors.toml`. Each value on this page comes from
those files, and each value there has its source.

## 1. What you need

- **The image** `ghcr.io/swarm-routing/ns3-dev:latest-debug`, with ns-3 and
  `ns3-build-contrib`. The steps are in
  [bring-your-own-protocol.md](../bring-your-own-protocol.md#1-install).
- **routing-bench**, the harness module in this repository. It provides
  `routing-compare`; these cells pass no `--scenario`.
- **Stock ns-3 modules only.** The cells use:
  - `RandomWaypointMobilityModel`, for the motion;
  - for heavy-load, `RangePropagationLossModel` (a 300 m disk) with
    `ConstantSpeedPropagationDelayModel`;
  - for dense-small, `YansWifiChannelHelper::Default()`: ns-3's
    log-distance loss, because the cell passes `--range=0`;
  - 802.11b ad hoc at a constant 2 Mbit/s, for the radio.

  routing-bench already links every module these need.

## 2. The defaults

`routing-compare` without `--scenario` resolves to these values. Any flag
you pass overrides the default.

| nodes | field (m) | range (m) | mobility | speed (m/s) | pause (s) | flows | per-flow rate | time (s) | channel |
|---|---|---|---|---|---|---|---|---|---|
| 20 | 300 × 300 | 0 (ns-3 default channel) | random waypoint | U(1, 5) | 1 | 5 | 8000 bit/s | 40 | log-distance |

Flows start uniformly in [0, 5] s, not the presets' [0, 180] s. The cells
are those of `ns3-tool sweep`'s discrete taxonomy that run on no preset
(`test_catalogue.py` holds them equal):

| cell | flags on top of the defaults | class |
|---|---|---|
| **dense-small** | `--nNodes=16 --area=250 --speed=5 --pause=1 --flows=4 --range=0` | dense / low-mobility |
| **heavy-load** | `--nNodes=50 --areaX=1500 --areaY=300 --speed=20 --pause=30 --range=300 --flows=40 --cbrBps=4096` | dense / heavy-load |

**Where the values come from** (`preset.toml` holds each source in full):
every default is `harness`, routing-compare's own value
(`ns3/routing-bench/model/routing-bench-harness.cc`), not a published
setup. The cells' flags are AntHocNet's taxonomy, unchanged
(`docs/benchmarks/scenarios/{dense-small,heavy-load}.md` there).

## 3. Run it

```bash
docker run --rm --cpus 2 -v "$PWD:/src:ro" ghcr.io/swarm-routing/ns3-dev:latest-debug bash -c \
  'ns3-build-contrib routing-bench=/src/ns3/routing-bench &&
   cd /opt/ns-3 && ./ns3 run "routing-compare --nNodes=16 --area=250 --speed=5 --pause=1 --flows=4 --range=0 --time=120 --runs=20 --protocols=aodv,olsr,dsdv"'
```

`ns3-tool sweep --family legacy` runs the two cells with exactly the command
lines `--only <cell>` gives. Run it, and the `ns3-scenario-check` commands
below, from the root of a checkout of this repository: `--catalogue
scenarios` names the catalogue there.

```bash
ns3-tool sweep /opt/ns-3 --family legacy --catalogue scenarios --only heavy-load --runs 20 --time 120 --dry-run
```

```text
[dry-run] cd "/opt/ns-3" && ./ns3 run "routing-compare --csv --nNodes=50 --areaX=1500 --areaY=300 --speed=20 --pause=30 --range=300 --flows=40 --cbrBps=4096 --runs=20 --time=120 --protocols=aodv,olsr,dsdv"
```

## 4. Preflight

```bash
ns3-scenario-check preflight --family legacy --cell heavy-load --catalogue scenarios
```

- **heavy-load** gives `verdict: WARN (0 fail, 2 warn)`: the 40 s default
  is shorter than the convergence horizon, and the #230 path-diversity WARN
  (at 20 m/s a 300 m link lives about 7.5 s, under the 10 s
  `--pathWindowS`). PDR, delay and NRL are not affected.
- **dense-small** gives `verdict: FAIL (2 fail, 2 warn)`, and the FAILs are
  preflight's, not the cell's. `--range=0` selects ns-3's default
  log-distance channel, which preflight does not model: it reads a 0 m
  disk, so the expected degree and the link lifetime come out as 0. Read
  this cell's connectivity from its oracle rows instead. The time WARN is
  real.

## 5. Anchors

| anchor | kind | cell | expected | floor (`anchors.toml`) |
|---|---|---|---|---|
| **single-hop** | analytic | `--nNodes=2 --areaX=50 --areaY=50 --range=300 --pause=900 --speed=1 --time=60 --runs=1`, arms `aodv`, `dsdv` | Two static nodes always in range: every flow is one hop, so the stack must deliver about everything. AntHocNet measured 100.0 % for both arms. | `single_hop_pdr_min = 99.0` |

```bash
ns3-scenario-check results single-hop.txt \
  --anchors scenarios/legacy/anchors.toml --anchor single-hop --anchor-arms aodv,dsdv
```

OLSR is left out: its multi-second neighbour sensing loses early packets on
a 60 s run, a startup artefact rather than a channel property. A
rate-manager regression of the AntHocNet #51 kind reads about 50 % here.

## 6. Pitfalls

- **Pass `--time`.** The default is 40 s, a quick run. AntHocNet's nightly
  cells run 120 s; a published cell states its time.
- **dense-small is not a disk.** `--range=0` means ns-3's default channel,
  so links have no fixed range, and a `--range` you add turns the cell into
  a different one (a disk).
- **heavy-load is not the paper preset.** It sets the paper field's
  geometry by hand, but runs on the defaults: 40 s and a [0, 5] s start
  window unless you pass `--time`, where `--scenario=paper` gives 900 s and
  [0, 180] s. Its numbers do not pair with the [MANET](manet.md) cells.
- **AODV on ns-3.49** livelocks unguarded (NS3-001,
  [`docs/ns3-bugs.md`](../ns3-bugs.md)). Use the `aodv` arm, which runs AODV
  behind the ICMP no-route guard.

## Provenance

This page and `scenarios/legacy/` were adapted from swarm-routing/AntHocNet:
- `docs/benchmarks/scenarios/{dense-small,heavy-load}.md`;
- `ns3/tools/run-scenarios.py`, whose discrete taxonomy is now
  `ns3-tool sweep`'s;
- `ns3/tools/anchors.yml` and `tools/checks/check-anchors.sh`.

These files are GPL-2.0-only, like this page.
