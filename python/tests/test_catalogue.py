#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""Self-test for the network-family catalogue's readers (ns3-tools#55).

- catalogue.py resolves cells on their preset and reads anchors.toml;
- the manet family's cells are sweep's DISCRETE cells, flag for flag, and
  the catalogue's floors are AntHocNet's anchors.yml floors (the fixture);
- `scenario_check preflight --family F --cell C` prints byte for byte what
  the same knobs given by hand print, and an explicit knob still wins;
- `--anchors FILE.toml` gives `results` the same floors as the yml;
- `sweep --family manet --only C` prints the command line `--only C` does.

Run: python3 test_catalogue.py   (no pytest; exits non-zero on the first failure)
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile

TESTS = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(TESTS), "ns3_tool")
REPO = os.path.dirname(os.path.dirname(TESTS))
CATALOGUE = os.path.join(REPO, "scenarios")
FIXTURES = os.path.join(TESTS, "fixtures")
sys.path.insert(0, TOOL)
import catalogue  # noqa: E402 (after the sys.path insert)
import scenario_check  # noqa: E402
import sweep  # noqa: E402


def check(cond, msg):
    if not cond:
        print("FAIL:", msg)
        sys.exit(1)


def run(*args):
    proc = subprocess.run(
        [sys.executable, "-I", *args], capture_output=True, text=True, check=False, cwd=REPO
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_resolve():
    fam = catalogue.load(CATALOGUE, "vanet")
    preset = fam["preset"]
    v = catalogue.resolve(preset, {"scenario": "vanet", "area": 280, "nNodes": 20})
    check(v["areaX"] == v["areaY"] == 280 and v["nNodes"] == 20, f"area shorthand: {v}")
    check(v["propagation"] == "urban", "an unset flag keeps the preset's value")
    for bad in ({"scenario": "fanet"}, {"warp": 9}):
        try:
            catalogue.resolve(preset, bad)
        except catalogue.CatalogueError:
            continue
        check(False, f"resolve accepted {bad}")
    try:
        catalogue.load(CATALOGUE, "nope")
        check(False, "load accepted an unknown family")
    except catalogue.CatalogueError as e:
        check("fanet, manet, vanet" in str(e), f"the error lists the families: {e}")


def test_root():
    check(catalogue.root() == os.path.normpath(CATALOGUE), "the checkout's scenarios/ by default")
    saved = os.environ.get(catalogue.ENV)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ[catalogue.ENV] = tmp
            check(catalogue.root() == os.path.normpath(tmp), "$NS3_TOOL_SCENARIOS")
            check(catalogue.root(CATALOGUE) == os.path.normpath(CATALOGUE), "--catalogue wins")
        try:
            catalogue.root(os.path.join(REPO, "no-such-dir"))
            check(False, "root accepted a missing directory")
        except catalogue.CatalogueError as e:
            check("--catalogue" in str(e), f"the error says how to fix it: {e}")
    finally:
        if saved is None:
            os.environ.pop(catalogue.ENV, None)
        else:
            os.environ[catalogue.ENV] = saved


def test_manet_cells_are_sweeps():
    cells = sweep.family_cells("manet", CATALOGUE)
    for name, (klass, flags) in cells.items():
        check(name in sweep.DISCRETE, f"manet cell {name} is not a sweep DISCRETE cell")
        check(
            sweep.DISCRETE[name] == (klass, flags),
            f"{name}: {sweep.DISCRETE[name]} != {(klass, flags)}",
        )


def test_floors_are_anthocnets():
    yml = scenario_check.load_anchors(os.path.join(FIXTURES, "anchors.yml"))
    for family in catalogue.families(CATALOGUE):
        path = os.path.join(CATALOGUE, family, "anchors.toml")
        floors = scenario_check.load_anchors(path)
        check(floors == catalogue.anchor_floors(path), "load_anchors reads the toml's floors")
        for key, value in floors.items():
            check(yml.get(key) == value, f"{family}: {key} = {value}, AntHocNet's {yml.get(key)}")
    with tempfile.TemporaryDirectory() as tmp:
        bad = os.path.join(tmp, "anchors.toml")
        with open(bad, "w") as fh:
            fh.write('schema = 1\n[anchors.a]\nfloors = { x_pdr_min = "high" }\n')
        try:
            catalogue.anchor_floors(bad)
            check(False, "a non-numeric floor was accepted")
        except catalogue.CatalogueError:
            pass


def preflight_args(knobs):
    out = []
    for k, v in knobs.items():
        out += [f"--{k}", str(v)]
    return out


def test_preflight_family():
    sc = os.path.join(TOOL, "scenario_check.py")
    for family in catalogue.families(CATALOGUE):
        for cell in catalogue.cells(catalogue.load(CATALOGUE, family)):
            knobs = catalogue.preflight_knobs(CATALOGUE, family, cell)
            by_hand = run(sc, "preflight", *preflight_args(knobs))
            by_family = run(sc, "preflight", "--family", family, "--cell", cell)
            check(by_family == by_hand, f"{family}/{cell}: --family differs from its knobs")
    # The first cell is the default, and an explicit knob still wins.
    check(
        run(sc, "preflight", "--family", "fanet")
        == run(sc, "preflight", "--family", "fanet", "--cell", "fanet-main"),
        "--family without --cell is the family's first cell",
    )
    rc, out, _err = run(sc, "preflight", "--family", "fanet", "--pause", "5")
    check(rc == 1 and "FAIL: --pause=5.0s with --mobility=gaussmarkov" in out, out)
    rc, out, _err = run(sc, "preflight", "--family", "nope")
    check(rc == 1 and "no family 'nope'" in _err, _err)
    rc, _out, err = run(sc, "preflight", "--family", "fanet", "--cell", "nope")
    check(rc == 1 and "no preflight cell 'nope'" in err, err)
    rc, _out, err = run(sc, "preflight", "--cell", "fanet-main")
    check(rc == 2 and "--cell needs --family" in err, err)
    # Without --family, preflight's own defaults are untouched.
    rc, out, _err = run(sc, "preflight")
    check(rc == 0 and out.startswith("field 1500x300 m, 50 nodes, range 300 m"), out)


def test_results_toml_anchors():
    sc = os.path.join(TOOL, "scenario_check.py")
    cell = os.path.join(FIXTURES, "cells", "fanet-main-6arm.txt")
    yml = os.path.join(FIXTURES, "anchors.yml")
    toml = os.path.join(CATALOGUE, "fanet", "anchors.toml")
    for anchor in ("fanet-single-hop-3d", "fanet-vertical-3d"):
        want = run(sc, "results", cell, "--anchors", yml, "--anchor", anchor)
        got = run(sc, "results", cell, "--anchors", toml, "--anchor", anchor)
        check(got == want, f"{anchor}: the toml's verdict differs from the yml's")
    rc, _out, err = run(
        sc, "results", cell, "--anchors", toml, "--anchor", "broch-low-mobility-aodv"
    )
    check(rc == 1 and "it offers: fanet-single-hop-3d, fanet-vertical-3d" in err, err)


def dry_run(argv):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        sweep.main(["/opt/ns-3", "--dry-run", *argv])
    return err.getvalue()


def test_sweep_family():
    for cell in ("paper-base", "large-scale"):
        check(
            dry_run(["--family", "manet", "--only", cell, "--catalogue", CATALOGUE])
            == dry_run(["--only", cell]),
            f"sweep --family manet --only {cell} differs from --only {cell}",
        )
    out = dry_run(["--family", "fanet", "--runs", "20", "--catalogue", CATALOGUE])
    want = [
        '[dry-run] cd "/opt/ns-3" && ./ns3 run "routing-compare --csv --scenario=fanet '
        '--runs=20 --protocols=aodv,olsr,dsdv"',
        '[dry-run] cd "/opt/ns-3" && ./ns3 run "routing-compare --csv --scenario=fanet '
        '--range=250 --runs=20 --protocols=aodv,olsr,dsdv"',
    ]
    check(out.splitlines() == want, f"sweep --family fanet: {out}")
    for argv, msg in (
        (["--family", "vanet", "--only", "paper-base"], "is not one of: all, discrete, vanet-main"),
        (["--family", "vanet", "--point", "1"], "--family runs no sweep"),
        (["--catalogue", CATALOGUE], "--catalogue needs --family"),
        (["--family", "nope", "--catalogue", CATALOGUE], "no family 'nope'"),
    ):
        try:
            dry_run(argv)
            check(False, f"sweep accepted {argv}")
        except SystemExit as e:
            check(msg in str(e), f"{argv}: {e}")


for t in (
    test_resolve,
    test_root,
    test_manet_cells_are_sweeps,
    test_floors_are_anthocnets,
    test_preflight_family,
    test_results_toml_anchors,
    test_sweep_family,
):
    t()
print("test_catalogue: ok")
