# Disaster area: configure an emergency-response network with ns-3

First-responder teams at an incident site. Firefighters work inside two
walled fire compartments of a shopping mall. Medics shuttle casualties
from there to a treatment area outside, and ambulances run between the
treatment area, a transport zone and the hospital. Every team reports to
one command post at the main gate.

Two things make this family hard for routing, and no other family has
them:
- **Structured, role-driven motion.** Who is connected to whom follows the
  rhythm of the operation, not a random walk.
- **Indoor/outdoor shadowing.** Every link out of a fire compartment
  crosses its walls. A team inside may hold only a chain of links back to
  the door, and that chain breaks when a carrier walks away.

MANET comparisons under disaster-area mobility find that connectivity
"varies widely enough to be hard for current routing protocols"
(Raffelsberger & Hellwagner, WISES 2012). The family's cells are **not
comparable** with the [MANET](manet.md) cells: read them against each other
and against this family's anchor, never against the Broch floor, which
holds for random waypoint only.

This page shows how to run the family in ns-3 with the harness in this
repository, for any arm. The catalogue entry is
[`scenarios/disaster/`](../../scenarios/disaster/): `preset.toml`,
`preflight.toml`, `anchors.toml` and the scene in `fixtures/`. Each value
on this page comes from those files, and each value there has its source.

## 1. What you need

- **The image** `ghcr.io/swarm-routing/ns3-dev:latest-debug`, with ns-3 and
  `ns3-build-contrib`. The steps are in
  [bring-your-own-protocol.md](../bring-your-own-protocol.md#1-install).
- **routing-bench**, the harness module in this repository. It provides
  `routing-compare` and its `--scenario=disaster` preset, which replays a
  scene.
- **The scene**, in `scenarios/disaster/fixtures/`: `disaster.ns2` (the
  movement trace), `disaster.flows` (the flows) and `disaster.buildings`
  (the `--buildings` value). `python3 -m ns3_tool.disaster_scene gen --out
  DIR --seed 1` writes them; `python/tests/test_disaster_scene.py` checks
  that the committed files are what it writes, byte for byte.
- **Stock ns-3 modules only.** The family uses:
  - `Ns2MobilityHelper`, which replays the trace;
  - `TwoRayGroundPropagationLossModel` at 2.4 GHz, plus routing-bench's
    `UrbanObstacleShadowingLossModel` over the two compartments (the
    obstacle shadowing of
    [Sommer et al. 2011](https://doi.org/10.1109/WONS.2011.5720204), 9 dB
    per wall cut and 0.4 dB per metre inside), for the channel;
  - 802.11b ad hoc at a constant 2 Mbit/s, the corpus's radio: a family
    changes the scenario, not the stack.

  routing-bench already links every module these need.

## 2. The preset and the scene

`--scenario=disaster` requires `--traceFile`, `--flowsFile` and
`--buildings`; the harness refuses the preset without them. It defaults to
the urban channel, the trace mobility and 900 s, and sets the oracle's
recompute cadence to 100 ms: links open and close at the compartment walls
as people walk through the doors.

| nodes | field (m) | mobility | channel | flows | per-flow rate | time (s) |
|---|---|---|---|---|---|---|
| 47 (from the trace) | 1000 × 500 | trace replay | two-ray + walls | 20 (from the flows file) | 1 × 64 B/s (512 bit/s) | 900 |

The scene follows the disaster-area mobility model of
[Aschenbruck et al. (MSWiM 2007)](https://doi.org/10.1145/1298126.1298131),
laid out as [Ben Arbia et al. (2017)](https://arxiv.org/abs/1711.10838)
apply it to a shopping-mall fire:

| zone (Aschenbruck et al.) | here | who is there, and how they move |
|---|---|---|
| incident site | two walled fire compartments, 200 × 160 m, at the mall's west and east ends (x 120–320 and 680–880, y 170–330) | 10 firefighters per compartment, random waypoint inside it at 0.3–1.5 m/s, pauses 0–60 s |
| (route between them) | the open concourse and the main gate at (500, 150) | 5 medics per compartment, compartment → gate → treatment area at 0.8–1.2 m/s, 30–90 s at the casualty, 60–180 s at the treatment area |
| casualty treatment area | 160 × 90 m outside the gate (x 280–440, y 30–120) | 6 treatment staff, random waypoint inside it at 0.3–1.0 m/s, pauses 10–90 s |
| transport zone | 160 × 70 m (x 620–780, y 30–100) | 4 ambulances: load at the treatment area, stage, leave for the hospital at the field's corner and return, at 10 m/s |
| technical operational command | the command post at (500, 60), static | node 0, the sink |
| (perimeter) | 20 m outside the mall's corners | 6 police officers patrolling at 1–2 m/s |

**Traffic.** 16 uplink flows (8 firefighters, 4 per compartment; 4 medics;
2 treatment staff; 2 police) and 4 downlink flows from the command post,
each CBR at one 64-byte packet per second, starting in [0, 30] s.

**One layout was rejected before any comparison.** A shell over the whole
mall cut every indoor team off from the gate: even the oracle delivered
42 % (seed 1, 300 s). That cell measures the partition, not routing, so
only the burning compartments are walled.

| cell | flags | class |
|---|---|---|
| **disaster-main** | `--scenario=disaster --traceFile=…/disaster.ns2 --flowsFile=…/disaster.flows --buildings=120,170,320,330;680,170,880,330` | disaster / emergency response |

**Where the values come from** (`preset.toml` holds each source in full):

| value | kind | source, in short |
|---|---|---|
| 47 nodes in their roles and zones | sourced | Aschenbruck et al. 2007 |
| 20 flows to and from one sink, one 64-byte packet/s | sourced | Ben Arbia et al. 2017 |
| two-ray plus building shadowing | sourced | Sommer et al. 2011 |
| the scene (seed 1), the two compartments, the 1000 × 500 m field, 900 s | chosen | AntHocNet #580: one scene seed, a disclosed threat |
| speed, pause, range and cbrBps | harness | printed in `##CONFIG##` but inert: the trace moves the nodes, the flows file sets the rates |

## 3. Run it

From the root of a checkout (the image mounts it at `/src`):

```bash
docker run --rm --cpus 2 -v "$PWD:/src:ro" ghcr.io/swarm-routing/ns3-dev:latest-debug bash -c \
  'ns3-build-contrib routing-bench=/src/ns3/routing-bench &&
   F=/src/scenarios/disaster/fixtures &&
   cd /opt/ns-3 && ./ns3 run "routing-compare --scenario=disaster --traceFile=$F/disaster.ns2 --flowsFile=$F/disaster.flows --buildings=$(cat $F/disaster.buildings) --runs=20 --protocols=aodv,olsr,oracle"'
```

`ns3-tool sweep --family disaster` runs the cell with the fixture paths
made absolute under the catalogue, so the command works from any
directory. Run it, and the `ns3-scenario-check` commands below, from the
root of a checkout of this repository: `--catalogue scenarios` names the
catalogue there.

```bash
ns3-tool sweep /opt/ns-3 --family disaster --catalogue scenarios --runs 20 --protocols aodv,olsr,oracle --dry-run
```

## 4. Preflight

```bash
ns3-scenario-check preflight --family disaster --cell disaster-main --catalogue scenarios
```

The cell passes with four WARNs (`verdict: WARN (0 fail, 4 warn)`).
Preflight reads the trace and the flows (47 nodes, 256 legs, 20 flows) and
checks the buildings against the field: 20 of 47 nodes start indoors.
- **The range knob is 423.3 m**, the two-ray decode radius: preflight's
  disk estimate of the urban channel. The cell's own `--range` is inert.
- **The trace WARN.** The degree and link-lifetime rules read
  `--speed`/`--pause`, not the trace's motion, so they are nominal.
- **The urban WARN.** The channel has no hard cutoff.
- **The not-random-waypoint WARN.** The family is its own, validated by
  its anchor below, not by the Broch floor.
- **The path-diversity WARN.** The 10 s `--pathWindowS` is over half the
  nominal 10.6 s link lifetime, so `path_div_*` is inflated by route churn.

## 5. Anchors

| anchor | kind | cell | expected | floor (`anchors.toml`) |
|---|---|---|---|---|
| **disaster-arm** | regression | the scene at `--time=300 --runs=2`, arms `aodv`, `olsr` | Each native stock arm routes on the walled scene. AntHocNet measured AODV 68.7 % and OLSR 63.1 %. | `disaster_arm_pdr_min = 50.0` |

```bash
ns3-scenario-check results disaster-arm.txt \
  --anchors scenarios/disaster/anchors.toml --anchor disaster-arm --anchor-arms aodv,olsr
```

AntHocNet's disaster gate (`tools/checks/check-disaster.sh` there, #580)
also checks that **the walls matter**. The oracle with the walls' loss
zeroed (`--ns3::UrbanObstacleShadowingLossModel::DbPerCut=0` and
`DbPerMeter=0`) must deliver at least 90 %, and with the walls it must lose
at least 8 pp. AntHocNet measured 100.0 % and 25.9 pp. A channel that
ignored `--buildings` would read the same twice. Those two checks compare
two runs, which `results --anchor` does not do, so the catalogue records
them here and in `anchors.toml`'s `margin`, not as floors.

## 6. Pitfalls

- **The oracle loses packets too.** It routes on the true graph, and about
  19 % of the packets have no path when they are sent (AntHocNet, 2 seeds
  at 900 s: oracle 81.4 / 81.5 %). The gap between an arm and the oracle is
  the routing loss. The gap between the oracle and 100 % is the
  partition, which only a store-carry-forward (DTN) arm can close
  (AntHocNet #727).
- **One scene seed.** Every cell replays the same scene (seed 1), so the
  harness seeds vary the radio and the flows' timing, not the motion. A
  second scene is `disaster_scene gen --seed 2`: a new cell, not a seed of
  this one.
- **Pass the buildings exactly.** `--buildings` must name the same
  compartments the trace's teams work in. Preflight checks that the
  buildings sit in the field and WARNs when nobody starts indoors.
- **Fixture paths.** The harness opens `--traceFile` and `--flowsFile`
  from its own working directory (the ns-3 tree under `./ns3 run`), so pass
  absolute paths. `sweep --family` and `check-scenarios.py --commands` do.
- **AODV on ns-3.49** livelocks unguarded (NS3-001,
  [`docs/ns3-bugs.md`](../ns3-bugs.md)). Use the `aodv` arm, which runs AODV
  behind the ICMP no-route guard.

## Provenance

This page, `scenarios/disaster/` and `python/ns3_tool/disaster_scene.py`
were adapted from swarm-routing/AntHocNet:
- `docs/benchmarks/scenarios/disaster.md`;
- `tools/bench/disaster_scene.py` (MIT OR GPL-2.0-only, ported unchanged in
  its output) and `ns3/tools/fixtures/disaster/` (the scene, byte for byte);
- `ns3/tools/anchors.yml` and `tools/checks/check-disaster.sh`.

The data and this page are GPL-2.0-only; the generator stays dual-licensed.
The flows file's first line still names the generator's AntHocNet path, so
the scene is byte-identical to the one AntHocNet's published cells
replayed.
