# Static Wi-Fi mesh: configure a mesh where nothing moves with ns-3

The community-network (Freifunk-class) **static Wi-Fi mesh**: routers on
poles and rooftops that never move. In the harness it is the
[MANET](manet.md) paper field (50 nodes, 1500 × 300 m, 20 CBR flows,
900 s) with mobility switched off (`--pause=900`, so every node holds its
t = 0 position for the whole run), on the 802.11a radio that stock ns-3
802.11s runs on.

With nothing moving, the regime takes away everything a reactive or
adaptive protocol is designed around: there is no link churn to track and
no route to repair, while proactive maintenance pays for a topology that
never changes. Proactive link-state protocols are at home here, and the
family's native comparators are OLSR and IEEE 802.11s HWMP, the standard's
own path selection.

This page shows how to run the family in ns-3 with the harness in this
repository, for any arm. The catalogue entry is
[`scenarios/static-mesh/`](../../scenarios/static-mesh/): `preset.toml`,
`preflight.toml` and `anchors.toml`. Each value on this page comes from
those files, and each value there has its source.

## 1. What you need

- **The image** `ghcr.io/swarm-routing/ns3-dev:latest-debug`, with ns-3 and
  `ns3-build-contrib`. The steps are in
  [bring-your-own-protocol.md](../bring-your-own-protocol.md#1-install).
- **routing-bench**, the harness module in this repository. It provides
  `routing-compare`, its `--scenario=paper` preset, the `--standard` and
  `--rateManager` radio flags, and the stock `hwmp` arm.
- **Stock ns-3 modules only.** The family uses:
  - `RandomWaypointMobilityModel`, which with pause 900 s on a 900 s run
    places the nodes and never moves them;
  - `RangePropagationLossModel` (a 300 m disk) with
    `ConstantSpeedPropagationDelayModel`, for the channel;
  - 802.11a ad hoc (5 GHz OFDM) at a constant 6 Mbit/s, for the radio;
  - for the `hwmp` arm, ns-3's `mesh` module (`MeshHelper`,
    `Dot11sStack`): one 802.11s mesh point per node.

  routing-bench already links every module these need.

## 2. The preset and the cell

The family runs on `--scenario=paper`, whose values are on the
[MANET](manet.md#2-the-preset) page and in `preset.toml`. Two of them are
the radio, which the cell replaces:

| value | preset | cell | kind |
|---|---|---|---|
| `--standard` | `80211b` (2.4 GHz DSSS) | `80211a` (5 GHz OFDM) | harness |
| `--rateManager` | `constant2` (2 Mbit/s) | `constant6` (6 Mbit/s) | harness |

| cell | flags on top of `--scenario=paper` | class |
|---|---|---|
| **static-mesh** | `--pause=900 --standard=80211a --rateManager=constant6` | static / mesh |

**Why that radio.** ns-3 tunes every 802.11s mesh interface to 5 GHz
channel 100, so 802.11s does not run on 802.11b at all. The maintainer's
decision of 2026-10-19 (AntHocNet #708) moved every arm of the cell to
802.11a at a fixed 6 Mbit/s, so the arms stay paired; real 802.11s
deployments are 5 GHz too. The disk channel ignores frequency, so the
topology is the one the 802.11b `sparse-static` cell of the MANET family
draws. The two cells are still **not** paired: the radio differs.

## 3. Run it

```bash
docker run --rm --cpus 2 -v "$PWD:/src:ro" ghcr.io/swarm-routing/ns3-dev:latest-debug bash -c \
  'ns3-build-contrib routing-bench=/src/ns3/routing-bench &&
   cd /opt/ns-3 && ./ns3 run "routing-compare --scenario=paper --pause=900 --standard=80211a --rateManager=constant6 --runs=20 --protocols=olsr,hwmp,oracle"'
```

`ns3-tool sweep --family static-mesh` runs the cell with exactly that
command line. Run it, and the `ns3-scenario-check` commands below, from the
root of a checkout of this repository: `--catalogue scenarios` names the
catalogue there.

```bash
ns3-tool sweep /opt/ns-3 --family static-mesh --catalogue scenarios --runs 20 --protocols olsr,hwmp,oracle --dry-run
```

```text
[dry-run] cd "/opt/ns-3" && ./ns3 run "routing-compare --csv --scenario=paper --pause=900 --standard=80211a --rateManager=constant6 --runs=20 --protocols=olsr,hwmp,oracle"
```

## 4. Preflight

```bash
ns3-scenario-check preflight --family static-mesh --cell static-mesh --catalogue scenarios
```

The cell passes with two WARNs (`verdict: WARN (0 fail, 2 warn)`):
- pause is at least the run time: the field is static, which is the
  family's purpose;
- `--standard 80211a` is not comparable to the 802.11b corpus, so every arm
  of a comparison must run on the same radio.

The cell's knobs include `rateMbps = 6`, the channel rate preflight's
offered-load rule uses for `constant6`. Without it preflight assumes
2 Mbit/s and WARNs.

## 5. Anchors

| anchor | kind | cell | expected | floor (`anchors.toml`) |
|---|---|---|---|---|
| **mesh-hwmp-shortest** | analytic | `--nNodes=16 --areaX=500 --areaY=500 --range=175 --pause=900 --speed=1 --flows=2 --time=120 --runs=2 --standard=80211a --rateManager=constant6` (no `--scenario`), arms `hwmp`, `oracle` | On a static, connected disk field at one fixed rate, every link costs the same airtime, so HWMP converges to a minimum-hop path: its mean hops sit at the oracle's, never below, at most 0.5 above. | `mesh_hwmp_pdr_min = 95.0` |

```bash
ns3-scenario-check results mesh-hwmp-shortest.txt \
  --anchors scenarios/static-mesh/anchors.toml --anchor mesh_hwmp_pdr_min --anchor-arms hwmp,oracle
```

- **The anchor cell passes no `--scenario`.** It runs on the harness's
  built-in defaults (the [legacy](legacy.md) preset) with its flags on top,
  not on the paper preset: it is the per-PR delivery smoke's 16-node field.
- **Seeds 1–2** are the first two consecutive seeds whose field is
  connected (oracle PDR ≥ 99 %) and multi-hop (oracle hopsMean ≥ 2.0) on
  ns-3.48 and ns-3.49, read off the oracle alone (AntHocNet #1222). Pass
  `--diag` to get the hop counts.
- **What the catalogue enforces.** `results --anchor` checks the PDR floor,
  which only catches an arm that stopped routing. The anchor's point is the
  hop bound between two arms (HWMP ≥ oracle, and HWMP − oracle ≤
  `mesh_hwmp_hops_excess_max = 0.5`). `results --anchor` does not compare
  arms, so that bound is enforced by AntHocNet's `check-anchors.sh
  mesh-hwmp-shortest`, not here. The measured excess was 0.00 to 0.42 hops
  over 24 connected multi-hop fields.

## 6. Pitfalls

- **Do not pair it with the 802.11b record.** The cell's rows and the
  MANET family's `sparse-static` rows draw the same topology on different
  radios.
- **`--standard=80211a` has conditions.** The harness refuses it unless
  `--propagation=range` with `--range > 0`, and unless the rate is an OFDM
  one (`constant6`, `arf` or `ideal`). `constant6` on 802.11b is refused
  too.
- **HWMP routes below IP.** How each harness book maps onto layer-2 path
  selection (NRL from PREQ/PREP/PERR/RANN, hops from the mesh's own relays,
  peering and beacons reported apart) is the `hwmp` arm's business, in
  routing-bench.
- **HWMP's beacon loss.** At ns-3's default `PeerLink::MaxBeaconLoss` of 2,
  HWMP collapsed to 56.5 % on this field; AntHocNet's v2.4.0 campaign ran
  every arm at `--ns3::dot11s::PeerLink::MaxBeaconLoss=20`. A published
  cell states which it used.
- **The missing baselines.** Babel (RFC 8966) and BATMAN-adv, the protocols
  real community meshes run, have no maintained ns-3 port. OLSR is the
  closest stand-in.

## Provenance

This page and `scenarios/static-mesh/` were adapted from
swarm-routing/AntHocNet:
- `docs/benchmarks/static-mesh.md` and `docs/benchmarks/v2.4.0-campaign.md`;
- `ns3/tools/anchors.yml` and `tools/checks/check-anchors.sh`.

These files are GPL-2.0-only, like this page.
