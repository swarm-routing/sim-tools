# FANET: configure a UAV swarm with ns-3

A flying ad hoc network: a small swarm of UAVs that moves fast and smoothly in
three dimensions. Against the ground field of the [MANET family](manet.md),
two things change:
- links break more often and more abruptly, because closing speeds reach
  60 m/s;
- the third dimension spreads the same number of nodes over more volume, so
  density is the first thing to get wrong, before routing.

This page shows how to run the family in ns-3 with the harness in this
repository, for any arm. The catalogue entry is
[`scenarios/fanet/`](../../scenarios/fanet/): `preset.toml`,
`preflight.toml` and `anchors.toml`. Each value on this page comes from
those files, and each value there has its source.

> **A family of its own.** A FANET cell is not comparable with the planar
> corpus. Read it against the other FANET cells and against the FANET
> anchors. Never read it against the Broch floor, which holds only for random
> waypoint on the ground.

## 1. What you need

- **The image** `ghcr.io/swarm-routing/ns3-dev:latest-debug`, with ns-3 and
  `ns3-build-contrib`. The steps are in
  [bring-your-own-protocol.md](../bring-your-own-protocol.md#1-install).
- **routing-bench**, the harness module in this repository
  (`ns3/routing-bench/`, or the release tarball). It provides
  `routing-compare` and its `--scenario=fanet` preset.
- **Stock ns-3 modules only.** routing-bench already links `mobility`,
  `propagation`, `wifi`, `internet`, `applications`, `flow-monitor` and
  `energy`. The family uses:
  - `GaussMarkovMobilityModel` in a 3-D box, for the motion;
  - `RangePropagationLossModel` (a disk) with
    `ConstantSpeedPropagationDelayModel`, for the channel;
  - 802.11b ad hoc at a constant 2 Mbit/s, for the radio.

  No FANET substrate module exists or is needed.
- **The oracle arm, for the anchors only.** The anchors read the oracle's
  mean hop count. The `oracle` arm ships in AntHocNet's `oracle` module, not
  here. Without it, run the anchors with the stock arms and read their PDR
  floors alone.

## 2. The preset

`routing-compare --scenario=fanet` resolves to these values. Any flag you
pass overrides the preset's value.

| cell | nodes | field (m) | range (m) | mobility | speed (m/s) | flows | per-flow rate | time (s) | channel |
|---|---|---|---|---|---|---|---|---|---|
| **fanet-main** (`--scenario=fanet`) | 30 | 1000 × 1000 × 300 | 350 | Gauss-Markov | U(10, 30) | 10 | 4 × 64 B/s (2048 bit/s) | 900 | disk |
| **fanet-sparse** (`--scenario=fanet --range=250`) | 30 | 1000 × 1000 × 300 | 250 | Gauss-Markov | U(10, 30) | 10 | 4 × 64 B/s (2048 bit/s) | 900 | disk |

The other settings:
- flows start uniformly in [0, 180] s;
- Gauss-Markov uses α = 0.85, a 1 s time step and a uniform mean direction;
- `--pause` is inert under Gauss-Markov, so the preset sets it to 0.

The two cells have different jobs:
- **fanet-main measures routing.** Its mean degree is 7.2, which clears
  2·ln(30) = 6.8.
- **fanet-sparse measures the partition regime, on purpose.** Its mean degree
  is 3.5, which sits just above ln(30) = 3.4.

**Where the values come from** (`preset.toml` holds each source in full):

| value | kind | source, in short |
|---|---|---|
| Gauss-Markov, 3-D | sourced | The standard FANET entity model. Makkar, Singh & Singh (2018) use it in a 3-D box in ns-3. [Yang et al. 2024](https://doi.org/10.1038/s41598-024-64454-1) use it in 2-D. [Biomo et al. 2015](https://doi.org/10.3390/aerospace2030392) find (enhanced) Gauss-Markov the model best suited to UAV networks. |
| 30 nodes, 1000 × 1000 × 300 m | chosen | Inside the AntHocNet #298 envelope (20–40 UAVs, about 1000 × 1000 × 300 m). Published fields bracket it. |
| range 350 m / 250 m | chosen | For density: see the two degrees above. Published ranges run from 200 m to 1000 m, and air-to-air links are line of sight. |
| speed U(10, 30) m/s | chosen | The #298 envelope. The 10 m/s floor (`--speedMin`) keeps the swarm from idling near hover. |
| 10 flows at 2048 bit/s | chosen / sourced | Low-rate telemetry at the AntHocNet thesis's per-flow rate (Ducatelle 2007 §5.1.3). The load is about 1 % of the channel. |
| disk channel | sourced | Two-ray and Nakagami assume a ground plane, which is meaningless between aircraft, so the harness refuses them in 3-D. |
| Gauss-Markov pitch | **assumption** | No published FANET evaluation states its pitch parameters. The harness uses its planar perturbation, scaled down by ten. |

## 3. Run it

All cells, every stock arm, 20 seeds, from a checkout of this repository:

```bash
docker run --rm --cpus 2 -v "$PWD:/src:ro" ghcr.io/swarm-routing/ns3-dev:latest-debug bash -c \
  'ns3-build-contrib routing-bench=/src/ns3/routing-bench &&
   cd /opt/ns-3 && ./ns3 run "routing-compare --scenario=fanet --runs=20 --protocols=aodv,olsr,dsdv"'
```

Add `--range=250` for fanet-sparse. To add your own arm, install its module
beside routing-bench and name it in `--protocols`
([bring-your-own-protocol.md §4](../bring-your-own-protocol.md#4-build-and-register-it)).

`ns3-tool sweep` runs the family's cells by name, with the command lines the
catalogue gives. Run it, and the `ns3-scenario-check` commands below, from
the root of a checkout of this repository: `--catalogue scenarios` names the
catalogue there. An installed package does not carry the catalogue, so
without `--catalogue DIR` or `$NS3_TOOL_SCENARIOS` it stops with
`no catalogue at ...`. A tool run from the checkout's `python/` finds
`scenarios/` on its own.

```bash
ns3-tool sweep /opt/ns-3 --family fanet --catalogue scenarios --runs 20 --protocols aodv,olsr,dsdv --dry-run
```

```text
[dry-run] cd "/opt/ns-3" && ./ns3 run "routing-compare --csv --scenario=fanet --runs=20 --protocols=aodv,olsr,dsdv"
[dry-run] cd "/opt/ns-3" && ./ns3 run "routing-compare --csv --scenario=fanet --range=250 --runs=20 --protocols=aodv,olsr,dsdv"
```

## 4. Preflight

```bash
ns3-scenario-check preflight --family fanet --cell fanet-main --catalogue scenarios
```

Both cells pass with WARNs only:
- **fanet-main** gives `verdict: WARN (0 fail, 2 warn)`:
  - the 3-D WARN: the cell is a family of its own;
  - the #230 path-diversity WARN: a 350 m link lives about 5.8 s at 30 m/s,
    under the harness's 10 s `--pathWindowS`, so `path_div_*` is unquotable.
    PDR, delay and NRL are not affected.
- **fanet-sparse** gives `verdict: WARN (0 fail, 3 warn)`: the same two
  WARNs, plus the sparse-regime WARN, which is that cell's purpose.

A knob you pass still wins over the cell's value. For example,
`--family fanet --pause 5` FAILs, because Gauss-Markov nodes never stop.

## 5. Anchors

Both anchors are **analytic**: geometry decides the expected answer. Each
runs the preset with only the field shrunk.

| anchor | cell | expected | floors (`anchors.toml`) |
|---|---|---|---|
| **fanet-single-hop-3d** | `--scenario=fanet --nNodes=10 --areaX=100 --areaY=100 --areaZ=100 --range=350 --time=120 --runs=2` | The cube's 173 m diagonal is inside the range, so every flow is one hop: PDR about 100 %, oracle hopsMean exactly 1.00. | `fanet_single_hop_3d_pdr_min = 99.0`, `fanet_single_hop_3d_oracle_hops_max = 1.0` |
| **fanet-vertical-3d** | `--scenario=fanet --nNodes=10 --areaX=10 --areaY=10 --areaZ=1000 --range=350 --time=120 --runs=2` | A 10 × 10 × 1000 m column. Flattened to 2-D, every pair is one hop (1.00). With altitude honoured, the oracle's hopsMean is above 1.2 (1.90 measured). | `fanet_vertical_3d_pdr_min = 90.0`, `fanet_vertical_3d_oracle_hops_min = 1.2` |

To judge a saved anchor cell, pass the anchor to `results`. It checks the
PDR floor on the `--anchor-arms` rows. It also checks the anchor's oracle hop
bounds on the oracle arm's rows, and WARNs that they went unchecked when the
cell has no oracle row:

```bash
ns3-scenario-check results fanet-single-hop-3d.txt \
  --anchors scenarios/fanet/anchors.toml --anchor fanet-single-hop-3d --anchor-arms aodv,oracle
```

A 3-D arm's own paper trend (gpsr3d's face recovery, AntHocNet #710) is that
arm's gate 3 (rule 6), not a family anchor, so it is not in the catalogue.

## 6. Pitfalls

- **The harness refuses what cannot be 3-D, and so does preflight.** With
  `--areaZ > 0`, it refuses:
  - `--propagation=tworay|nakagami`, which assume ground reflection;
  - `--mobility=ssrwp`, because ns-3's steady-state RWP is planar.

  An arm that cannot honour a 3-D field refuses it too, rather than flatten
  it: for example a planar GPSR.
- **`--pause` is inert under Gauss-Markov.** A pause sweep on this family
  would produce identical cells. Preflight FAILs any `--pause` other than 0.
- **Read path diversity from a dedicated cell.** On this family, use
  `--pathWindowS=2`, under the link lifetime, and read diversity there, not
  from fanet-main.
- **AODV on ns-3.49** livelocks unguarded (NS3-001,
  [`docs/ns3-bugs.md`](../ns3-bugs.md)). The `aodv` arm runs it behind the
  ICMP no-route guard, so use that arm, not a hand-built AODV.

## Provenance

This page and `scenarios/fanet/` were adapted from swarm-routing/AntHocNet:
- `docs/benchmarks/scenarios/fanet.md`, the FANET family page (AntHocNet
  #300, #482);
- `ns3/tools/anchors.yml`;
- `tools/checks/check-anchors.sh`.

These files are GPL-2.0-only, like this page. The measured numbers above
are AntHocNet's. This repository has not re-measured them; it checks the
preset values against routing-compare's `##CONFIG##` output
(`tools/checks/check-scenarios.py --configs`).
