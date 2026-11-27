#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""Self-test for the disaster family's scene generator (ns3-tools#55).

- `disaster_scene gen --seed 1` writes exactly the committed
  scenarios/disaster/fixtures/ (the scene AntHocNet's disaster cells replayed);
- the scene is the preset's: 47 nodes in the trace, 20 flows, and the
  buildings line is the cell's --buildings value;
- another seed writes another scene.

Run: python3 test_disaster_scene.py   (no pytest; exits non-zero on the first failure)
"""

import contextlib
import io
import os
import sys
import tempfile
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from ns3_tool import disaster_scene  # noqa: E402

FAMILY = os.path.join(HERE, "..", "..", "scenarios", "disaster")
FILES = ("disaster.ns2", "disaster.flows", "disaster.buildings")


def check(cond, msg):
    if not cond:
        sys.exit(f"FAIL: {msg}")


def gen(out, seed):
    with contextlib.redirect_stdout(io.StringIO()):
        disaster_scene.main(["gen", "--out", out, "--seed", str(seed)])
    return {f: open(os.path.join(out, f), "rb").read() for f in FILES}


with tempfile.TemporaryDirectory() as tmp:
    scene = gen(os.path.join(tmp, "s1"), 1)
    for f in FILES:
        with open(os.path.join(FAMILY, "fixtures", f), "rb") as fh:
            check(scene[f] == fh.read(), f"fixtures/{f} differs from `gen --seed 1`; regenerate it")
    with open(os.path.join(FAMILY, "preset.toml"), "rb") as fh:
        preset = tomllib.load(fh)
    values = {k: v["value"] for k, v in preset["values"].items()}
    trace = scene["disaster.ns2"].decode()
    nodes = {line.split(")")[0].split("(")[-1] for line in trace.splitlines() if "set X_" in line}
    check(
        len(nodes) == values["nNodes"],
        f"{len(nodes)} nodes in the trace, preset {values['nNodes']}",
    )
    flows = [
        ln
        for ln in scene["disaster.flows"].decode().splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    check(len(flows) == values["flows"], f"{len(flows)} flows, preset {values['flows']}")
    buildings = scene["disaster.buildings"].decode().strip()
    check(buildings == values["buildings"], f"buildings {buildings!r} != {values['buildings']!r}")
    cell = preset["cells"]["disaster-main"]["flags"]
    check(cell["buildings"] == buildings, "the cell's --buildings is the scene's")
    other = gen(os.path.join(tmp, "s2"), 2)
    check(other["disaster.ns2"] != scene["disaster.ns2"], "seed 2 wrote seed 1's trace")

print("test_disaster_scene: ok")
