#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""The network-family catalogue (`scenarios/`, ns3-tools#55): its reader.

A family is a directory `scenarios/<family>/` with three TOML files (schema 1;
the format is `scenarios/README.md`):

- `preset.toml`: the routing-compare preset (`--scenario=<name>`), every value
  it resolves to with its `kind` and `source`, and the family's cells (named
  flag sets on top of it);
- `preflight.toml`: per cell, the `ns3-scenario-check preflight` knobs and the
  verdict line they must give;
- `anchors.toml`: the family's anchors, each an anchor cell (flags, the arms
  it judges) with its floors (`key = number`, the keys of AntHocNet's
  `ns3/tools/anchors.yml`).

The catalogue is data (GPL-2.0-only); this reader is dual-licensed and reads
it, never imports it. The wheel does not carry the catalogue: it is found at
--catalogue DIR, else $NS3_TOOL_SCENARIOS, else the `scenarios/` of the
checkout this file runs from. Standard library only (tomllib).
"""

import os
import tomllib

SCHEMA = 1
VALUE_KINDS = ("sourced", "chosen", "assumption", "harness")
ANCHOR_KINDS = ("literature", "analytic", "regression")
ENV = "NS3_TOOL_SCENARIOS"
FILES = ("preset.toml", "preflight.toml", "anchors.toml")

# The preflight knob each preset value is checked against (scenario_check's
# preflight option -> routing-compare's flag).
PREFLIGHT_FROM_PRESET = {
    "nodes": "nNodes",
    "areaX": "areaX",
    "areaY": "areaY",
    "areaZ": "areaZ",
    "range": "range",
    "time": "time",
    "pause": "pause",
    "speed": "speed",
    "flows": "flows",
    "cbrBps": "cbrBps",
    "mobility": "mobility",
    "propagation": "propagation",
    "blocksX": "blocksX",
    "blocksY": "blocksY",
    "streetWidth": "streetWidth",
    "transport": "transport",
    "standard": "standard",
    "rateManager": "rateManager",
    "buildings": "buildings",
    "traceFile": "traceFile",
    "flowsFile": "flowsFile",
}
# Flags whose value is a fixture: a path relative to the family's directory,
# made absolute (with_fixtures) wherever a cell is run or preflighted.
FIXTURE_FLAGS = ("traceFile", "flowsFile")


class CatalogueError(Exception):
    """A catalogue file that is missing, unreadable or malformed."""


def root(path=None):
    """The catalogue directory: PATH, else $NS3_TOOL_SCENARIOS, else the
    checkout's `scenarios/`. Raises CatalogueError when it does not exist."""
    here = os.path.dirname(os.path.abspath(__file__))
    found = path or os.environ.get(ENV) or os.path.join(here, "..", "..", "scenarios")
    found = os.path.normpath(found)
    if not os.path.isdir(found):
        raise CatalogueError(
            f"no catalogue at {found}: pass --catalogue DIR (a checkout's scenarios/) or set {ENV}"
        )
    return found


def families(base):
    """The family names of the catalogue at BASE, sorted."""
    return sorted(
        d for d in os.listdir(base) if os.path.isfile(os.path.join(base, d, "preset.toml"))
    )


def read_toml(path):
    """One catalogue file, parsed, at schema 1."""
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except OSError as e:
        raise CatalogueError(f"{path}: {e.strerror}") from e
    except tomllib.TOMLDecodeError as e:
        raise CatalogueError(f"{path}: {e}") from e
    if data.get("schema") != SCHEMA:
        raise CatalogueError(f"{path}: schema = {data.get('schema')!r}, this reader reads {SCHEMA}")
    return data


def load(base, family):
    """{file stem: parsed data} of one family (preset, preflight, anchors)."""
    if family not in families(base):
        raise CatalogueError(
            f"no family {family!r} in {base}; it has: {', '.join(families(base)) or 'none'}"
        )
    return {f.removesuffix(".toml"): read_toml(os.path.join(base, family, f)) for f in FILES}


def resolve(preset, flags):
    """The values routing-compare runs with for FLAGS on top of PRESET:
    `scenario` must name the preset, `area` sets areaX and areaY (the
    harness's shorthand), any other flag replaces that value."""
    values = {k: v["value"] for k, v in preset["values"].items()}
    for key, value in flags.items():
        if key == "scenario":
            if value != preset["scenario"]:
                raise CatalogueError(
                    f"scenario={value!r} on the {preset['scenario']!r} preset's family"
                )
        elif key == "area":
            values["areaX"] = values["areaY"] = value
        elif key in values:
            values[key] = value
        else:
            raise CatalogueError(f"flag {key!r} is not a value of the preset")
    return values


def with_fixtures(base, family, mapping):
    """MAPPING (flags, values or knobs) with each FIXTURE_FLAGS value made an
    absolute path under BASE/FAMILY, as the harness and preflight open it."""
    return {
        k: os.path.abspath(os.path.join(base, family, v)) if k in FIXTURE_FLAGS else v
        for k, v in mapping.items()
    }


def cells(fam):
    """{cell name: {"class": label, "flags": {...}}} of a loaded family."""
    return fam["preset"].get("cells", {})


def preflight_knobs(base, family, cell=None):
    """The preflight knobs of FAMILY's CELL (default: its first cell)."""
    fam = load(base, family)
    names = list(cells(fam))
    cell = cell or (names[0] if names else None)
    rows = fam["preflight"].get("cells", {})
    if cell not in rows:
        raise CatalogueError(
            f"family {family!r} has no preflight cell {cell!r}; it has: {', '.join(rows)}"
        )
    return with_fixtures(base, family, rows[cell]["knobs"])


def anchor_floors(path):
    """{floor key: number} of an anchors.toml: every anchor's floors."""
    floors = {}
    for name, anchor in read_toml(path).get("anchors", {}).items():
        for key, value in anchor.get("floors", {}).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise CatalogueError(f"{path}: anchors.{name}.floors.{key} is not a number")
            floors[key] = float(value)
    return floors
