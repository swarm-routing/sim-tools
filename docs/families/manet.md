# MANET: configure the Broch/CMU random-waypoint field with ns-3

The mobile ad hoc network of the literature: nodes moving by random waypoint
in a 1500 × 300 m strip. This is the field of
[Broch et al. (MobiCom 1998)](https://doi.org/10.1145/288235.288256), and the
base scenario of the AntHocNet paper
([Di Caro, Ducatelle & Gambardella 2004](https://doi.org/10.1007/978-3-540-30217-9_47), §4).
The strip is narrow, so routes are long and thin, and mobility breaks them.
Because published results exist on this field, it is also where the harness
is calibrated: stock AODV's delivery on it at low mobility is a published
number.

This page shows how to run the family in ns-3 with the harness in this
repository, for any arm. The catalogue entry is
[`scenarios/manet/`](../../scenarios/manet/): `preset.toml`,
`preflight.toml` and `anchors.toml`. Each value on this page comes from
those files, and each value there has its source.

## 1. What you need

- **The image** `ghcr.io/swarm-routing/ns3-dev:latest-debug`, with ns-3 and
  `ns3-build-contrib`. The steps are in
  [bring-your-own-protocol.md](../bring-your-own-protocol.md#1-install).
- **routing-bench**, the harness module in this repository. It provides
  `routing-compare` and its `--scenario=paper` preset.
- **Stock ns-3 modules only.** The family uses:
  - `RandomWaypointMobilityModel`, for the motion;
  - `RangePropagationLossModel` (a 300 m disk) with
    `ConstantSpeedPropagationDelayModel`, for the channel;
  - 802.11b ad hoc at a constant 2 Mbit/s, for the radio.

  routing-bench already links every module these need.

## 2. The preset

`routing-compare --scenario=paper` resolves to these values. Any flag you
pass overrides the preset's value.

| nodes | field (m) | range (m) | mobility | speed (m/s) | pause (s) | flows | per-flow rate | time (s) | channel |
|---|---|---|---|---|---|---|---|---|---|
| 50 | 1500 × 300 | 300 | random waypoint | U(1, 20) | 30 | 20 | 1 × 64 B/s (512 bit/s) | 900 | disk |

Flows start uniformly in [0, 180] s. The cells are those of `ns3-tool
sweep`'s discrete taxonomy that run on this preset (`test_catalogue.py`
holds them equal):

| cell | flags on top of `--scenario=paper` | class |
|---|---|---|
| **paper-base** | none | sparse / mobile |
| **sparse-static** | `--pause=900` | sparse / static |
| **high-mobility** | `--pause=0` | sparse / high-mobility |
| **large-scale** | `--nNodes=100 --areaX=2100 --areaY=700` | large / mobile |

**Where the values come from** (`preset.toml` holds each source in full):

| value | kind | source, in short |
|---|---|---|
| 50 nodes, 1500 × 300 m, 900 s, random waypoint at 20 m/s | sourced | Broch et al. 1998 |
| pause 30 s, 300 m range, 20 sources of one 64-byte packet/s | sourced | Di Caro et al. 2004 §4. Broch et al. sweep pause from 0 s to 900 s and use 250 m. |
| speed floor 1 m/s, disk channel, UDP | harness | routing-compare's defaults. The disk keeps the calibration free of fading (AntHocNet #24); `--propagation=tworay|nakagami` are the channel arms. |
| 802.11 DCF at 2 Mbit/s | sourced | Broch et al. 1998; Di Caro et al. 2004 §4 |

## 3. Run it

```bash
docker run --rm --cpus 2 -v "$PWD:/src:ro" ghcr.io/swarm-routing/ns3-dev:latest-debug bash -c \
  'ns3-build-contrib routing-bench=/src/ns3/routing-bench &&
   cd /opt/ns-3 && ./ns3 run "routing-compare --scenario=paper --runs=20 --protocols=aodv,olsr,dsdv"'
```

`ns3-tool sweep --family manet` runs the four cells with exactly the command
lines `--only <cell>` gives:

```bash
ns3-tool sweep /opt/ns-3 --family manet --only sparse-static --runs 20 --dry-run
```

```text
[dry-run] cd "/opt/ns-3" && ./ns3 run "routing-compare --csv --scenario=paper --pause=900 --runs=20 --protocols=aodv,olsr,dsdv"
```

The paper's three sweeps (area, pause, scale) stay in `ns3-tool sweep --only
sweeps`. The catalogue describes cells, not sweeps.

## 4. Preflight

```bash
ns3-scenario-check preflight --family manet --cell paper-base
```

Every cell passes with exactly one WARN (`verdict: WARN (0 fail, 1 warn)`):
- **sparse-static** WARNs that pause is at least the run time: the field is
  static, which is that cell's purpose.
- **The other three cells** give the #230 path-diversity WARN. At 20 m/s a
  300 m link lives about 7.5 s, under the harness's 10 s `--pathWindowS`, so
  `path_div_*` from these cells is unquotable. PDR, delay and NRL are not
  affected. Read diversity from a dedicated cell at `--pathWindowS=2`.

## 5. Anchors

| anchor | kind | cell | expected | floor (`anchors.toml`) |
|---|---|---|---|---|
| **broch-low-mobility** | literature | `--scenario=paper --pause=900 --speed=1 --time=300 --runs=2`, arm `aodv` | Stock AODV delivers about 90–100 % on the Broch field at low mobility (Broch et al. 1998). AntHocNet measured 92.5 %. | `broch_low_mobility_aodv_pdr_min = 85.0` |

```bash
ns3-scenario-check results broch-low-mobility.txt \
  --anchors scenarios/manet/anchors.toml --anchor broch-low-mobility-aodv --anchor-arms aodv
```

The floor applies only to this field and random waypoint. The
[FANET](fanet.md) and [VANET](vanet.md) families have anchors of their own.

## 6. Pitfalls

- **`sparse-static` is static by design.** With pause 900 s on a 900 s run,
  no node moves after its first leg. Read the cell as the static regime, not
  as the paper's mobile one.
- **The channel arms are cells of their own.** A two-ray or Nakagami cell
  on this field, made with `--propagation`, is a different cell from
  paper-base. Under those channels `--range` bounds nothing, and preflight's
  degree figures are a disk estimate. The anchor floor above is a disk-field
  floor.
- **`--offTime`.** It defaults to 0, constant bit rate. `--offTime=1`
  reproduces ns-3's 1 s on / 1 s off schedule, which halves the stated
  rate. It exists only for paired A/B runs against older cells.
- **AODV on ns-3.49** livelocks unguarded (NS3-001,
  [`docs/ns3-bugs.md`](../ns3-bugs.md)). Use the `aodv` arm, which runs AODV
  behind the ICMP no-route guard.

## Provenance

This page and `scenarios/manet/` were adapted from swarm-routing/AntHocNet:
- `docs/benchmarks/scenarios/paper-base.md`;
- `ns3/tools/run-scenarios.py`, whose discrete taxonomy is now
  `ns3-tool sweep`'s;
- `ns3/tools/anchors.yml` and `tools/checks/check-anchors.sh`.

These files are GPL-2.0-only, like this page. AntHocNet's other MANET pages,
`dense-small` and `heavy-load`, run on routing-compare's built-in defaults
rather than on a preset. They come into the catalogue with a follow-up
(swarm-routing/sim-tools#55).
