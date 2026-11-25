#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""check-scenarios.py's self-test: the committed catalogue passes, and each
kind of defect in a copy of it is found (ns3-tools#55). Exits non-zero on
any failure, like python/tests/."""

import contextlib
import importlib.util
import io
import shutil
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check-scenarios.py"
REPO = SCRIPT.parents[2]
spec = importlib.util.spec_from_file_location("check_scenarios", SCRIPT)
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

problems = []


def expect(name, ok):
    if not ok:
        problems.append(name)


def findings(base):
    return cs.Checker(base).run()


def main_out(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cs.main(argv)
    return code, out.getvalue()


code, out = main_out([])
expect(f"the committed catalogue fails: {out}", code == 0 and out.endswith(": ok\n"))

# Each defect, alone, in a fresh copy of the catalogue: (file, old, new, finding).
DEFECTS = [
    ("fanet/preset.toml", 'kind = "assumption"', 'kind = "guess"', "is not one of sourced"),
    ("vanet/preset.toml", 'source = "as blocksX"', 'source = ""', "values.blocksY: no source"),
    ("fanet/preset.toml", "range = 250 }", "range = 250, warp = 9 }", "'warp' is not a value"),
    ("vanet/preset.toml", "[cells.vanet-sparse]", "[cells.fanet-main]", "also in scenarios/"),
    ("manet/preflight.toml", "nodes = 100,", "nodes = 99,", "nodes = 99, but the cell resolves"),
    ("fanet/preflight.toml", "range = 250,", "", "range = 300 (scenario_check's default)"),
    ("fanet/preflight.toml", "(0 fail, 3 warn)", "(0 fail, 9 warn)", "preflight gives"),
    ("manet/preflight.toml", "pause = 900,", "pause = 900, hover = 1,", "unknown preflight knob"),
    (
        "manet/anchors.toml",
        "(https://doi.org/10.1145/288235.288256)",
        "",
        "cites its paper by an https:// link",
    ),
    ("vanet/anchors.toml", 'arms = ["aodv", "oracle"]', "arms = []", "arms: the arms it judges"),
    (
        "fanet/anchors.toml",
        "= 1.2 }",
        "= 1.2, fanet_single_hop_3d_pdr_min = 1 }",
        "floor fanet_single_hop_3d_pdr_min also in",
    ),
    (
        "fanet/anchors.toml",
        "= 1.2 }",
        '= "high" }',
        "floors.fanet_vertical_3d_oracle_hops_min is not",
    ),
    ("manet/preset.toml", 'page = "docs/families/manet.md"', 'page = "x.md"', "does not exist"),
    ("README.md", "](../docs/families/vanet.md)", "]", "does not link ../docs/families/vanet.md"),
    ("vanet/preset.toml", "schema = 1", "schema = 2", "this reader reads 1"),
    ("fanet/anchors.toml", 'family = "fanet"', 'family = "vanet"', "family = 'vanet'"),
]
for path, old, new, want in DEFECTS:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "scenarios"
        shutil.copytree(REPO / "scenarios", base)
        f = base / path
        text = f.read_text(encoding="utf-8")
        if old not in text:
            problems.append(f"{path}: the defect's text {old!r} is gone; update the test")
            continue
        f.write_text(text.replace(old, new, 1), encoding="utf-8")
        got = findings(base)
        expect(f"{path}: {new!r} not found ({want!r}; got {got})", any(want in g for g in got))

# A missing fixture is a finding.
with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp) / "scenarios"
    shutil.copytree(REPO / "scenarios", base)
    preset = base / "vanet" / "preset.toml"
    preset.write_text(
        preset.read_text(encoding="utf-8").replace(
            'page = "docs/families/vanet.md"',
            'page = "docs/families/vanet.md"\nfixtures = ["fixtures/none.ns2"]',
        ),
        encoding="utf-8",
    )
    expect("a missing fixture", any("fixtures/none.ns2" in g for g in findings(base)))

# --commands and --configs: a ##CONFIG## line that matches, and one that does not.
code, out = main_out(["--commands"])
lines = out.splitlines()
expect(
    f"--commands: {lines[:2]}", code == 0 and lines[0].startswith("fanet-main\t--scenario=fanet")
)
GOOD = {
    "fanet-main": "scenario=fanet nNodes=30 time=1 runs=1 firstRun=1 areaX=1000 areaY=1000 "
    "areaZ=300 speed=30 speedMin=10 pause=0 range=350 propagation=range mobility=gaussmarkov "
    "transport=udp flows=10 cbrBps=2048",
    "fanet-sparse": "scenario=fanet nNodes=30 areaX=1000 areaY=1000 areaZ=300 speed=30 "
    "speedMin=10 pause=0 range=250 propagation=range mobility=gaussmarkov transport=udp "
    "flows=10 cbrBps=2048",
    "paper-base": "scenario=paper nNodes=50 areaX=1500 areaY=300 speed=20 pause=30 range=300 "
    "propagation=range mobility=rwp transport=udp flows=20 cbrBps=512",
    "sparse-static": "scenario=paper nNodes=50 areaX=1500 areaY=300 speed=20 pause=900 "
    "range=300 propagation=range mobility=rwp transport=udp flows=20 cbrBps=512",
    "high-mobility": "scenario=paper nNodes=50 areaX=1500 areaY=300 speed=20 pause=0 range=300 "
    "propagation=range mobility=rwp transport=udp flows=20 cbrBps=512",
    "large-scale": "scenario=paper nNodes=100 areaX=2100 areaY=700 speed=20 pause=30 range=300 "
    "propagation=range mobility=rwp transport=udp flows=20 cbrBps=512",
    "vanet-main": "scenario=vanet nNodes=100 areaX=800 areaY=800 speed=20 speedMin=10 pause=0 "
    "range=0 propagation=urban mobility=manhattan blocksX=4 blocksY=4 streetWidth=20 "
    "transport=udp flows=20 cbrBps=2048",
    "vanet-sparse": "scenario=vanet nNodes=40 areaX=800 areaY=800 speed=20 speedMin=10 pause=0 "
    "range=0 propagation=urban mobility=manhattan blocksX=4 blocksY=4 streetWidth=20 "
    "transport=udp flows=20 cbrBps=2048",
}
with tempfile.TemporaryDirectory() as tmp:
    for cell, fields in GOOD.items():
        (Path(tmp) / f"{cell}.txt").write_text(f"noise\n##CONFIG## {fields}\n", encoding="utf-8")
    code, out = main_out(["--configs", tmp])
    expect(f"--configs on matching lines: {out}", code == 0 and out.endswith(": ok\n"))
    bad = GOOD["vanet-sparse"].replace("nNodes=40", "nNodes=41").replace(" speedMin=10", "")
    (Path(tmp) / "vanet-sparse.txt").write_text(f"##CONFIG## {bad}\n", encoding="utf-8")
    (Path(tmp) / "paper-base.txt").unlink()
    code, out = main_out(["--configs", tmp])
    for want in (
        "nNodes=41, the catalogue says 40",
        "speedMin=1, the catalogue says 10",
        "no ##CONFIG##",
    ):
        expect(f"--configs: {want!r} not in {out}", code == 1 and want in out)

sys.exit("FAIL: " + "; ".join(problems) if problems else 0)
