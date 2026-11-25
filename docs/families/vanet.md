# VANET: configure vehicles on a city street grid with ns-3

A vehicular ad hoc network in a city. Against the open field of the
[MANET family](manet.md), three things change:
- **Mobility follows the streets.** Vehicles drive along the streets and
  turn at intersections (the Manhattan model).
- **Links run along corridors.** Buildings cut line of sight, so a vehicle
  hears its own street much further away than the parallel street 200 m off.
- **Links break at corners.** A vehicle that turns loses line of sight to its
  former street within metres.

This page shows how to run the family in ns-3 with the harness in this
repository, for any arm. The catalogue entry is
[`scenarios/vanet/`](../../scenarios/vanet/): `preset.toml`,
`preflight.toml` and `anchors.toml`. Each value on this page comes from
those files, and each value there has its source.

> **A family of its own.** A VANET cell is not comparable with the MANET
> corpus. Read it against the other VANET cells and against the VANET
> anchors. Never read it against the Broch floor, which holds only for random
> waypoint.

## 1. What you need

- **The image** `ghcr.io/swarm-routing/ns3-dev:latest-debug`, with ns-3 and
  `ns3-build-contrib`. The steps are in
  [bring-your-own-protocol.md](../bring-your-own-protocol.md#1-install).
- **routing-bench**, the harness module in this repository. It provides
  `routing-compare`, its `--scenario=vanet` preset, and the urban channel,
  `UrbanObstacleShadowingLossModel`
  (`ns3/routing-bench/model/urban-obstacle-loss-model.h`).
- **Stock ns-3 modules only.** The family needs neither ns-3's `buildings`
  module, nor SUMO, nor a BonnMotion trace:
  - **motion:** the Manhattan model, built in the harness as
    `WaypointMobilityModel` waypoints from one pinned RNG stream, so every
    arm on a seed sees the same vehicle schedule;
  - **channel:** `TwoRayGroundPropagationLossModel`, with the urban
    obstacle shadowing on top of it;
  - **radio:** 802.11b ad hoc at a constant 2 Mbit/s.
- **The oracle arm, for the anchors only.** The anchors read the oracle's
  mean hop count. The `oracle` arm ships in AntHocNet's `oracle` module, not
  here.

## 2. The preset

`routing-compare --scenario=vanet` resolves to these values. Any flag you
pass overrides the preset's value.

| cell | vehicles | field (m) | grid | mobility | speed (m/s) | flows | per-flow rate | time (s) | channel |
|---|---|---|---|---|---|---|---|---|---|
| **vanet-main** (`--scenario=vanet`) | 100 | 800 × 800 | 4 × 4 blocks of 200 m, 20 m streets | Manhattan | U(10, 20) | 20 | 4 × 64 B/s (2048 bit/s) | 900 | urban |
| **vanet-sparse** (`--scenario=vanet --nNodes=40`) | 40 | 800 × 800 | 4 × 4 blocks of 200 m, 20 m streets | Manhattan | U(10, 20) | 20 | 4 × 64 B/s (2048 bit/s) | 900 | urban |

The other settings:
- flows start uniformly in [0, 180] s;
- `--range` is inert under the urban channel: the two-ray decode radius,
  423.3 m, and the building loss bound every link;
- `--pause` is inert under the Manhattan model, so the preset sets it to 0.

The two cells have different jobs:
- **vanet-main measures routing.** Its road-network degree is 9.6, which
  clears 2·ln(100) = 9.2.
- **vanet-sparse measures the partition regime, on purpose.** Its degree is
  3.8, against ln(40) = 3.7. 40 is Bai & Helmy's vehicle count.

**The mobility model.** This is the Manhattan model of
[Bai, Sadagopan & Helmy (INFOCOM 2003)](https://doi.org/10.1109/infcom.2003.1208920):
- the streets are the block edges, border streets included;
- each vehicle starts at a uniform point of the street network;
- at each intersection a vehicle goes straight with probability 0.5 and
  turns left or right with 0.25 each, the probabilities of
  [Camp, Boleng & Davies 2002](https://doi.org/10.1002/wcm.72);
- each leg is driven at a speed drawn U(10, 20) m/s;
- vehicles never pause.

The model makes two simplifications against BonnMotion, recorded here:
- it draws one speed per leg, where BonnMotion perturbs speed at every update;
- it has no pauses.

**The channel.** Two-ray ground path loss plus the building shadowing of
[Sommer, Eckhoff, German & Dressler (WONS 2011)](https://doi.org/10.1109/wons.2011.5720204),
at Veins' defaults:

    L_obs = 9 dB × (walls cut) + 0.4 dB/m × (metres inside buildings)

The buildings are the blocks, inset by half the street width.

**Where the values come from** (`preset.toml` holds each source in full):

| value | kind | source, in short |
|---|---|---|
| Manhattan, turns 0.5 / 0.25 / 0.25 | sourced | Bai, Sadagopan & Helmy 2003; Camp, Boleng & Davies 2002 |
| field 800 × 800 m | chosen | Shrunk from Bai & Helmy's 1000 × 1000 m. That field needs about 145 vehicles to clear 2·ln(n) under the urban channel; this one needs 95–100. |
| 4 × 4 blocks of 200 m, 20 m streets | **assumption** | Neither source fixes a block length. A block stays shorter than the line-of-sight reach. |
| 100 / 40 vehicles | chosen | For density: see the two degrees above. |
| speed U(10, 20) m/s | chosen | 36–72 km/h urban arterial speeds, inside the AntHocNet #298 urban envelope. |
| 20 flows at 2048 bit/s, 900 s | sourced | Bai, Sadagopan & Helmy 2003: 20 CBR sources, 4 packets/s of 64 bytes, 900 s. |
| building shadowing | sourced | Sommer et al. 2011. **Threat to validity:** its constants were fitted at 5.9 GHz (802.11p). The radio here stays 2.4 GHz 802.11b, because a family changes the scenario, not the stack (AntHocNet ADR-0019). |

## 3. Run it

All cells, every stock arm, 20 seeds, from a checkout of this repository:

```bash
docker run --rm --cpus 2 -v "$PWD:/src:ro" ghcr.io/swarm-routing/ns3-dev:latest-debug bash -c \
  'ns3-build-contrib routing-bench=/src/ns3/routing-bench &&
   cd /opt/ns-3 && ./ns3 run "routing-compare --scenario=vanet --runs=20 --protocols=aodv,olsr,dsdv"'
```

Add `--nNodes=40` for vanet-sparse. `ns3-tool sweep` runs both cells by
name. Run it, and the `ns3-scenario-check` commands below, from the root of
a checkout of this repository: `--catalogue scenarios` names the catalogue
there. An installed package does not carry the catalogue, so without
`--catalogue DIR` or `$NS3_TOOL_SCENARIOS` it stops with `no catalogue at ...`.

```bash
ns3-tool sweep /opt/ns-3 --family vanet --catalogue scenarios --runs 20 --protocols aodv,olsr,dsdv --dry-run
```

```text
[dry-run] cd "/opt/ns-3" && ./ns3 run "routing-compare --csv --scenario=vanet --runs=20 --protocols=aodv,olsr,dsdv"
[dry-run] cd "/opt/ns-3" && ./ns3 run "routing-compare --csv --scenario=vanet --nNodes=40 --runs=20 --protocols=aodv,olsr,dsdv"
```

## 4. Preflight

```bash
ns3-scenario-check preflight --family vanet --cell vanet-main --catalogue scenarios
```

On a road network, nodes live on the 1-D edges of a 2-D grid. So the
preflight computes the degree over street pairs, applying the two-ray margin
against the building loss, instead of the disk rule. Both cells pass with
WARNs only:
- **vanet-main** gives `verdict: WARN (0 fail, 3 warn)`:
  - the family WARN;
  - the corner WARN: a link round a corner lives about 1 s
    (streetWidth / speed), so route churn is corner-dominated;
  - the #230 path-diversity WARN.
- **vanet-sparse** gives `verdict: WARN (0 fail, 4 warn)`: the same three
  WARNs, plus the sparse-regime WARN, which is that cell's purpose.

## 5. Anchors

Both anchors are **analytic**. Each shrinks the preset to one
280 × 280 m block with 20 vehicles and 4 flows, for 120 s and 2 runs.

| anchor | cell | expected | floors (`anchors.toml`) |
|---|---|---|---|
| **vanet-single-hop** | `--scenario=vanet --nNodes=20 --area=280 --blocksX=1 --blocksY=1 --streetWidth=279 --flows=4 --time=120 --runs=2` | A 279 m street leaves a 1 m building. The 396 m block diagonal is inside the 423.3 m decode radius, so every flow is one hop: PDR about 100 %, oracle hopsMean about 1.00. | `vanet_single_hop_pdr_min = 99.0`, `vanet_single_hop_oracle_hops_max = 1.05` |
| **vanet-building** | the same with `--streetWidth=100` | A 180 × 180 m building. Vehicles on opposite streets relay round a corner, so the oracle's hopsMean is above 1.2 (1.36 measured). A channel that ignored the building would read 1.00. | `vanet_building_pdr_min = 70.0`, `vanet_building_oracle_hops_min = 1.2` |

`results --anchor` checks:
- the PDR floor, on the `--anchor-arms` rows;
- the oracle hop bound, on the oracle arm's rows. It WARNs that the bound went
  unchecked when the cell has no oracle row.

```bash
ns3-scenario-check results vanet-building.txt \
  --anchors scenarios/vanet/anchors.toml --anchor vanet-building --anchor-arms aodv,oracle
```

A junction-aware arm's own paper trend is that arm's gate 3, not a family
anchor: for GPCR, delivering at least 2 pp more than GPSR on the
vanet-building block (Lochert et al. 2005, AntHocNet #709).

## 6. Pitfalls

- **The urban channel needs streets.** The harness refuses
  `--propagation=urban` without `--mobility=manhattan`, or a trace that
  drives the same streets: off-street vehicles would sit inside the
  buildings. It also refuses a `--streetWidth` that is not narrower than a
  block. Preflight FAILs both.
- **`--pause` is inert under Manhattan.** Preflight FAILs any `--pause` other
  than 0.
- **The grid is planar.** The harness refuses `--mobility=manhattan` with
  `--areaZ > 0`.
- **`--range` does nothing here.** Do not sweep it. To change the channel's
  reach, change the buildings: `--streetWidth`, `--blocksX`, `--blocksY`.
- **AODV on ns-3.49** livelocks unguarded (NS3-001,
  [`docs/ns3-bugs.md`](../ns3-bugs.md)). Use the `aodv` arm, which runs AODV
  behind the ICMP no-route guard.

## Provenance

This page and `scenarios/vanet/` were adapted from swarm-routing/AntHocNet:
- `docs/benchmarks/scenarios/vanet.md`, the VANET family page (AntHocNet
  #301, #488);
- `ns3/tools/anchors.yml`;
- `tools/checks/check-anchors.sh`.

These files are GPL-2.0-only, like this page. The measured numbers are
AntHocNet's. This repository checks the preset values against
routing-compare's `##CONFIG##` output (`tools/checks/check-scenarios.py
--configs`).
