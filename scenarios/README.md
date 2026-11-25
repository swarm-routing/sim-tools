# The network-family catalogue

One directory per network family. Each holds the routing-compare preset
the family runs on, the preflight rules a cell must pass, and the anchors
that check the family's channel and geometry, with a source for every
value. Any arm can use these cells, so the catalogue names a protocol only
where an anchor judges a stock arm. The catalogue lives in this repository
by maintainer decision on swarm-routing/sim-tools#55 (2026-11-24). It is
data and docs, `GPL-2.0-only` ([`LICENSING.md`](../LICENSING.md)).

| family | preset | cells | anchors | page |
|---|---|---|---|---|
| [`manet`](manet/) | `--scenario=paper` | paper-base, sparse-static, high-mobility, large-scale | broch-low-mobility (literature) | [docs/families/manet.md](../docs/families/manet.md) |
| [`fanet`](fanet/) | `--scenario=fanet` | fanet-main, fanet-sparse | fanet-single-hop-3d, fanet-vertical-3d (analytic) | [docs/families/fanet.md](../docs/families/fanet.md) |
| [`vanet`](vanet/) | `--scenario=vanet` | vanet-main, vanet-sparse | vanet-single-hop, vanet-building (analytic) | [docs/families/vanet.md](../docs/families/vanet.md) |

The catalogue describes the presets of routing-bench
(`ns3/routing-bench/model/routing-bench-harness.cc`). It does not configure
them: routing-bench does not read these files, and the presets keep the
meaning marker contract v1 gives them. `tools/checks/check-scenarios.py`
keeps the two in agreement.

## Using it

```bash
ns3-scenario-check preflight --family fanet --cell fanet-sparse      # a cell's preflight
ns3-scenario-check results CELL.txt --anchors scenarios/fanet/anchors.toml --anchor fanet-single-hop-3d
ns3-tool sweep /opt/ns-3 --family vanet --runs 20 --protocols aodv,olsr,dsdv   # the family's cells
python3 tools/checks/check-scenarios.py                              # the catalogue is complete
```

The readers look for the catalogue in this order:
1. `--catalogue DIR`;
2. `$NS3_TOOL_SCENARIOS`;
3. the `scenarios/` of the checkout they run from.

The `swarm-sim-tools` wheel does not carry the catalogue: it is GPL-only data,
and the package is dual-licensed. With a pip install, point `--catalogue` at a
checkout or a release's source archive.

## The format (schema 1)

TOML, read with Python's `tomllib`. Every file starts with `schema = 1` and
`family = "<directory name>"`.

**`preset.toml`**: the preset and its cells.

| key | what |
|---|---|
| `title`, `page` | the family's name and its page (`docs/families/<family>.md`) |
| `scenario` | routing-compare's `--scenario` value |
| `[values.<flag>]` | each routing-compare flag the preset sets, as the value it resolves to: `value`, `kind`, `source` |
| `[fixed.<name>]` | a setting of the preset that no flag changes (the flow start window, the radio): `value`, `kind`, `source` |
| `[cells.<name>]` | a cell: `class` (its difficulty label) and `flags`, the routing-compare flags on top of the preset (`scenario` names the preset; `area` sets areaX and areaY, as the harness's shorthand) |
| `fixtures` | (optional) files the family's cells read, relative to its directory |

A value's `kind` is one of:
- `sourced`: a published setup uses the value or brackets it;
- `chosen`: a decision made for this family, with its reason;
- `assumption`: no source fixes it, and the value is recorded as an assumption;
- `harness`: routing-compare's own default, not specific to the family.

Cell names are unique across the catalogue.

**`preflight.toml`**: `[cells.<name>]` for every cell of the preset.

| key | what |
|---|---|
| `knobs` | the `ns3-scenario-check preflight` options of the cell; each equals the value the cell resolves to |
| `verdict` | the verdict line they give, e.g. `WARN (0 fail, 2 warn)` |
| `why` | which WARNs are expected, and why they do not stop the cell |

**`anchors.toml`**: `[anchors.<name>]`, one per anchor cell.

| key | what |
|---|---|
| `kind` | `literature` (a published trend), `analytic` (geometry or an identity decides the answer) or `regression` (a floor from this org's own measurement) |
| `flags`, `arms` | the anchor cell's routing-compare flags on top of the preset, and the arms its floors judge (`--anchor-arms`) |
| `expected`, `measured`, `margin` | what the anchor expects, what was measured, and why the floor sits where it does |
| `source` | the citation (a literature anchor links its paper: `https://doi.org/<DOI>`, or the publisher's page) or the derivation |
| `floors` | `key = number`: the floors `ns3-scenario-check results --anchors` reads, under the keys of AntHocNet's `ns3/tools/anchors.yml`; unique across the catalogue |

## Adding a family

1. Create `scenarios/<family>/` with the three files and `docs/families/<family>.md`.
   The family needs a routing-compare preset or flags that build it. A
   family that needs a new harness feature adds that feature in its own PR
   first.
2. Add the family to the table above.
3. Run `python3 tools/checks/check-scenarios.py`; it must print `ok`.
4. Check the preset against the harness. `--commands` prints each cell's
   arguments. Run each line through routing-compare into `DIR/<cell>.txt`,
   then run `--configs DIR`, which compares the `##CONFIG##` lines.

## Provenance

The families here were adapted from `swarm-routing/AntHocNet`:
- `docs/benchmarks/scenarios/{paper-base,fanet,vanet}.md`;
- `ns3/tools/anchors.yml` and `tools/checks/check-anchors.sh`;
- `ns3/tools/run-scenarios.py`.

These files are GPL-2.0-only, so they could move into this GPL path. Each
file names its own source.
