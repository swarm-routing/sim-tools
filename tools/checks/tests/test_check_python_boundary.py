#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""check-python-boundary.py's self-test (#377): the real tree passes, and each
way of crossing the boundary is a finding. Exits non-zero on any failure."""

import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "check_python_boundary", ROOT / "tools/checks/check-python-boundary.py"
)
cpb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cpb)

LAYOUT = """### Python modules

| Module | Kind | Simulator |
|--------|------|-----------|
| `reader`, `other` | reader | agnostic |
| `cli` | dispatcher | agnostic (dispatches to ns-3-bound commands too) |
| `sweep` | harness front-end | ns-3 |

## Next
"""


def run(files, layout=LAYOUT):
    with tempfile.TemporaryDirectory() as d:
        pkg = Path(d) / "ns3_tool"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        for name, src in files.items():
            (pkg / f"{name}.py").write_text(src)
        lay = Path(d) / "layout.md"
        lay.write_text(layout)
        return cpb.check(lay, pkg)


CLEAN = {
    "reader": "x = 1\n",
    "other": "import json\n",
    "cli": "from . import sweep\n",
    "sweep": "p = '/opt/ns-3'\n",
}
problems = []


def expect(label, got, want_fragment):
    if want_fragment is None:
        ok = got == []
    else:
        ok = any(want_fragment in g for g in got)
    if not ok:
        problems.append(f"{label}: got {got}")


expect("clean tree", run(CLEAN), None)
expect(
    "relative import",
    run({**CLEAN, "reader": "from . import sweep\n"}),
    "reader: agnostic module imports ns-3 module sweep",
)
expect(
    "from-module import",
    run({**CLEAN, "reader": "from .sweep import x\n"}),
    "imports ns-3 module sweep",
)
expect(
    "package import",
    run({**CLEAN, "reader": "import ns3_tool.sweep\n"}),
    "imports ns-3 module sweep",
)
expect(
    "package from-import",
    run({**CLEAN, "reader": "from ns3_tool import sweep\n"}),
    "imports ns-3 module sweep",
)
expect(
    "bare sibling fallback",
    run({**CLEAN, "reader": "try:\n    pass\nexcept ImportError:\n    import sweep\n"}),
    "imports ns-3 module sweep",
)
expect("agnostic sibling import is fine", run({**CLEAN, "reader": "from . import other\n"}), None)
for word in cpb.NS3_NAMES:
    expect(f"names {word}", run({**CLEAN, "reader": f"x = 'run {word} now'\n"}), f"names {word!r}")
expect("comments are not read", run({**CLEAN, "reader": "# routing-compare\n"}), None)
expect("ns-3 module may name them", run({**CLEAN, "sweep": "x = 'ns3-dev'\n"}), None)
expect(
    "allowed exception",
    run(
        {**CLEAN, "scenario_check": "from . import catalogue\n", "catalogue": ""},
        LAYOUT.replace(
            "`cli`",
            "`scenario_check` | plausibility | agnostic |\n| `catalogue` | reader | ns-3 |\n| `cli`",
        ),
    ),
    None,
)
expect("module without a row", run({**CLEAN, "extra": ""}), "extra has no row")
expect(
    "row without a module",
    run({"reader": "", "other": "", "cli": ""}),
    "sweep is in the table but has no",
)

# the real tree
real = cpb.check(ROOT / "docs/layout.md", ROOT / "python/ns3_tool")
if real:
    problems.append(f"real tree: {real}")

if problems:
    raise SystemExit("FAIL:\n" + "\n".join(problems))
print("test_check_python_boundary: ok")
