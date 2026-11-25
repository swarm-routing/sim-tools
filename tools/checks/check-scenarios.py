#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""The network-family catalogue (scenarios/, ns3-tools#55) is complete and
agrees with the tools that read it.

For every family, scenarios/<family>/{preset,preflight,anchors}.toml:

- each file parses at schema 1 and names its family;
- every preset value (and every fixed setting) has a value, a kind
  (sourced | chosen | assumption | harness) and a source;
- every cell resolves on the preset, and cell names are unique across the
  catalogue (ns3-tool sweep --family runs them by name);
- preflight.toml has exactly the preset's cells; every knob is an
  ns3-scenario-check preflight option, and every knob that a preset value
  maps to equals the value the cell resolves to (a knob left out must have
  that value as scenario_check's default);
- every cell's preflight gives its recorded verdict line;
- every anchor has a kind (literature | analytic | regression), flags that
  resolve on the preset, the arms it judges, what it expects, a source (a
  literature anchor cites an https:// link: its DOI, or its publisher's page)
  and numeric floors, whose keys are unique across the catalogue;
- every fixture the preset lists exists;
- the family's page exists, names its catalogue directory, every cell and
  every anchor, and scenarios/README.md links it.

    check-scenarios.py [--catalogue DIR]        the checks above
    check-scenarios.py --commands               each cell's routing-compare arguments
    check-scenarios.py --configs DIR            DIR/<cell>.txt (routing-compare output of
                                                --commands' line) prints the ##CONFIG##
                                                the preset resolves to

Prints one line per finding and a summary; exits 1 on any finding.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "python" / "ns3_tool"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"check_scenarios_{name}", TOOL / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


catalogue = _load("catalogue")
scenario_check = _load("scenario_check")

# The ##CONFIG## fields a resolved preset is compared on, with the value the
# harness leaves out of the line (#480/#482: areaZ and speedMin only when not
# the default). time, runs and firstRun are what the evidence run overrides.
CONFIG_KEYS = {
    "nNodes": None,
    "areaX": None,
    "areaY": None,
    "areaZ": 0,
    "speed": None,
    "speedMin": 1,
    "pause": None,
    "range": None,
    "propagation": None,
    "mobility": None,
    "blocksX": None,
    "blocksY": None,
    "streetWidth": None,
    "transport": None,
    "flows": None,
    "cbrBps": None,
}
# The evidence run: one short seed of one stock arm, enough to print ##CONFIG##.
EVIDENCE_FLAGS = "--time=1 --runs=1 --protocols=dsdv"


def same(a, b):
    """A catalogue value and a knob or ##CONFIG## field: numbers by value."""
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def flag_args(flags):
    return " ".join(f"--{k}={v}" for k, v in flags.items())


class Checker:
    def __init__(self, base):
        self.base = Path(base)
        self.findings = []
        self.counts = {"families": 0, "cells": 0, "anchors": 0}
        _ap, pre = scenario_check.build_parser()
        self.preflight_defaults = vars(pre.parse_args([]))

    def bad(self, where, msg):
        self.findings.append(f"{where}: {msg}")

    def sourced(self, where, entry, kinds):
        if not isinstance(entry, dict):
            self.bad(where, "not a table")
            return False
        if "value" not in entry and kinds is catalogue.VALUE_KINDS:
            self.bad(where, "no value")
        if entry.get("kind") not in kinds:
            self.bad(where, f"kind {entry.get('kind')!r} is not one of {', '.join(kinds)}")
        if not str(entry.get("source", "")).strip():
            self.bad(where, "no source")
        return True

    def run(self):
        try:
            names = catalogue.families(self.base)
        except OSError as e:
            self.bad(self.base, e.strerror)
            return self.findings
        if not names:
            self.bad(self.base, "no family (no <family>/preset.toml)")
        seen_cells, seen_floors = {}, {}
        for family in names:
            self.family(family, seen_cells, seen_floors)
        return self.findings

    def family(self, family, seen_cells, seen_floors):
        where = f"scenarios/{family}"
        try:
            fam = catalogue.load(self.base, family)
        except catalogue.CatalogueError as e:
            self.bad(where, str(e))
            return
        self.counts["families"] += 1
        for stem, data in fam.items():
            if data.get("family") != family:
                self.bad(f"{where}/{stem}.toml", f"family = {data.get('family')!r}")
        preset = fam["preset"]
        for key in ("scenario", "title", "page"):
            if not str(preset.get(key, "")).strip():
                self.bad(f"{where}/preset.toml", f"no {key}")
        values = preset.get("values", {})
        if not values:
            self.bad(f"{where}/preset.toml", "no [values]")
        for table in ("values", "fixed"):
            for k, entry in preset.get(table, {}).items():
                self.sourced(f"{where}/preset.toml {table}.{k}", entry, catalogue.VALUE_KINDS)
        for fixture in preset.get("fixtures", []):
            if not (self.base / family / fixture).is_file():
                self.bad(f"{where}/preset.toml", f"fixture {fixture} does not exist")
        cells = catalogue.cells(fam)
        if not cells:
            self.bad(f"{where}/preset.toml", "no [cells]")
        resolved = {}
        for name, cell in cells.items():
            cw = f"{where}/preset.toml cells.{name}"
            self.counts["cells"] += 1
            if name in seen_cells:
                self.bad(cw, f"cell name also in scenarios/{seen_cells[name]}")
            seen_cells[name] = family
            if not str(cell.get("class", "")).strip():
                self.bad(cw, "no class")
            try:
                resolved[name] = catalogue.resolve(preset, cell.get("flags", {}))
            except (catalogue.CatalogueError, KeyError) as e:
                self.bad(cw, str(e))
        self.preflight(family, fam, resolved)
        anchors = self.anchors(family, fam, seen_floors)
        self.page(family, preset, list(cells), anchors)

    def preflight(self, family, fam, resolved):
        where = f"scenarios/{family}/preflight.toml"
        rows = fam["preflight"].get("cells", {})
        if set(rows) != set(catalogue.cells(fam)):
            self.bad(
                where,
                f"cells {sorted(rows)} are not the preset's {sorted(catalogue.cells(fam))}",
            )
        for name, row in rows.items():
            cw = f"{where} cells.{name}"
            knobs = row.get("knobs", {})
            for key in ("verdict", "why"):
                if not str(row.get(key, "")).strip():
                    self.bad(cw, f"no {key}")
            unknown = sorted(set(knobs) - set(self.preflight_defaults))
            if unknown:
                self.bad(cw, f"unknown preflight knob(s): {', '.join(unknown)}")
            values = resolved.get(name)
            if values is None:
                continue
            for knob, flag in catalogue.PREFLIGHT_FROM_PRESET.items():
                if flag not in values:
                    continue
                got = knobs.get(knob, self.preflight_defaults.get(knob))
                if got is None:
                    self.bad(cw, f"{knob} must be given (the preset resolves it to {values[flag]})")
                elif not same(got, values[flag]):
                    how = "" if knob in knobs else " (scenario_check's default)"
                    self.bad(
                        cw, f"{knob} = {got}{how}, but the cell resolves {flag} = {values[flag]}"
                    )
            self.verdict(family, name, row.get("verdict"), cw)

    def verdict(self, family, cell, want, where):
        cmd = [sys.executable, "-I", str(TOOL / "scenario_check.py"), "preflight"]
        cmd += ["--family", family, "--cell", cell, "--catalogue", str(self.base)]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        lines = proc.stdout.strip().splitlines() or proc.stderr.strip().splitlines() or [""]
        got = lines[-1].removeprefix("verdict: ")
        if got != want:
            self.bad(where, f"preflight gives {got!r}, the catalogue records {want!r}")

    def anchors(self, family, fam, seen_floors):
        where = f"scenarios/{family}/anchors.toml"
        table = fam["anchors"].get("anchors", {})
        if not table:
            self.bad(where, "no [anchors]")
        for name, anchor in table.items():
            aw = f"{where} anchors.{name}"
            self.counts["anchors"] += 1
            if not self.sourced(aw, anchor, catalogue.ANCHOR_KINDS):
                continue
            if anchor.get("kind") == "literature" and "https://" not in anchor.get("source", ""):
                self.bad(aw, "a literature anchor cites its paper by an https:// link")
            if not str(anchor.get("expected", "")).strip():
                self.bad(aw, "no expected")
            arms = anchor.get("arms")
            if not arms or not all(isinstance(a, str) and a for a in arms):
                self.bad(aw, "arms: the arms it judges, a list of names")
            try:
                catalogue.resolve(fam["preset"], anchor.get("flags", {}))
            except catalogue.CatalogueError as e:
                self.bad(aw, f"flags: {e}")
            floors = anchor.get("floors", {})
            if not floors:
                self.bad(aw, "no floors")
            for key, value in floors.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    self.bad(aw, f"floors.{key} is not a number")
                if key in seen_floors:
                    self.bad(aw, f"floor {key} also in {seen_floors[key]}")
                seen_floors[key] = aw
        return list(table)

    def page(self, family, preset, cells, anchors):
        page = REPO / str(preset.get("page", ""))
        where = f"scenarios/{family}/preset.toml page"
        if not preset.get("page") or not page.is_file():
            self.bad(where, f"{preset.get('page')!r} does not exist")
            return
        text = page.read_text(encoding="utf-8")
        for name in [f"scenarios/{family}/", *cells, *anchors]:
            if name not in text:
                self.bad(str(preset["page"]), f"does not name {name}")
        index = self.base / "README.md"
        link = f"../{preset['page']}"
        if not index.is_file() or link not in index.read_text(encoding="utf-8"):
            self.bad("scenarios/README.md", f"does not link {link}")


def all_cells(base):
    """(family, cell, resolved values, routing-compare arguments) of every cell."""
    for family in catalogue.families(base):
        fam = catalogue.load(base, family)
        for name, cell in catalogue.cells(fam).items():
            values = catalogue.resolve(fam["preset"], cell["flags"])
            yield family, name, values, flag_args(cell["flags"])


def check_configs(base, configs):
    """Each cell's ##CONFIG## line in CONFIGS/<cell>.txt against its resolved values."""
    findings = []
    for _family, name, values, _args in all_cells(base):
        path = Path(configs) / f"{name}.txt"
        line = None
        if path.is_file():
            for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if ln.startswith("##CONFIG## scenario="):
                    line = ln
                    break
        if line is None:
            findings.append(f"{path}: no ##CONFIG## scenario= line")
            continue
        fields = dict(t.split("=", 1) for t in line.split()[1:] if "=" in t)
        for key, omitted in CONFIG_KEYS.items():
            if key not in values:
                continue
            got = fields.get(key, omitted)
            if got is None:
                findings.append(f"{path}: ##CONFIG## has no {key}")
            elif not same(got, values[key]):
                findings.append(f"{path}: ##CONFIG## {key}={got}, the catalogue says {values[key]}")
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(prog="check-scenarios.py", description=__doc__.split("\n")[0])
    ap.add_argument("--catalogue", default=str(REPO / "scenarios"))
    ap.add_argument("--commands", action="store_true", help="print each cell's harness arguments")
    ap.add_argument("--configs", metavar="DIR", help="check routing-compare's ##CONFIG## lines")
    args = ap.parse_args(argv)
    if args.commands:
        for _family, name, _values, flags in all_cells(args.catalogue):
            print(f"{name}\t{flags} {EVIDENCE_FLAGS}")
        return 0
    if args.configs:
        findings = check_configs(args.catalogue, args.configs)
        summary = f"check-scenarios: ##CONFIG## of {len(list(all_cells(args.catalogue)))} cells"
    else:
        checker = Checker(args.catalogue)
        findings = checker.run()
        c = checker.counts
        summary = (
            f"check-scenarios: {c['families']} families, {c['cells']} cells, {c['anchors']} anchors"
        )
    for f in findings:
        print(f)
    print(f"{summary}: {len(findings)} finding(s)" if findings else f"{summary}: ok")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
