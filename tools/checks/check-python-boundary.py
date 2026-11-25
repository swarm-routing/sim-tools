#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""The simulator-agnostic / ns-3 boundary inside python/ns3_tool (#377,
ADR-0002 "Decision" 4).

docs/layout.md "Python modules" is the source of truth: each module is
`agnostic` or `ns-3`. This check holds the code to it:

- the table and python/ns3_tool/*.py list the same modules;
- an agnostic module imports no ns-3 module (AST imports, relative, absolute
  and the bare sibling fallback; every import in the file, try/except
  included). A module of kind `dispatcher` (cli) may import them: it only
  routes to the commands. ALLOWED_IMPORTS lists the recorded exceptions;
- an agnostic module has no string constant (docstrings included; comments
  are not read) naming an ns-3 path or program: /opt/ns-3, ns3-dev,
  ns3-build-contrib, ./ns3, routing-compare.

    check-python-boundary.py

Prints one line per finding and a summary; exits 1 on any finding.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NS3_NAMES = ("/opt/ns-3", "ns3-dev", "ns3-build-contrib", "./ns3", "routing-compare")
PACKAGE = "ns3_tool"
# (importer, imported) pairs the table records as exceptions. scenario_check
# loads catalogue lazily, only for `--family` and an anchors.toml path, never on
# the readers' path; moving the catalogue reader out is a split (ADR-0002 C).
ALLOWED_IMPORTS = {("scenario_check", "catalogue")}


def parse_table(text: str) -> dict[str, tuple[str, str]]:
    """module -> (kind, simulator), from the "Python modules" table."""
    m = re.search(r"^### Python modules\n(.*?)(?=^#{1,3} )", text, re.S | re.M)
    if not m:
        raise SystemExit('layout: no "### Python modules" section')
    modules: dict[str, tuple[str, str]] = {}
    for line in m.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if (
            len(cells) != 3
            or not line.startswith("|")
            or cells[0] in ("Module",)
            or set(cells[0]) <= {"-"}
        ):
            continue
        sim = (
            "ns-3"
            if cells[2].startswith("ns-3")
            else "agnostic"
            if cells[2].startswith("agnostic")
            else None
        )
        if sim is None:
            raise SystemExit(f"layout: simulator of {cells[0]!r} is neither agnostic nor ns-3")
        kind = "dispatcher" if cells[1].startswith("dispatcher") else cells[1]
        for name in re.findall(r"`([^`]+)`", cells[0]):
            if name in modules:
                raise SystemExit(f"layout: module {name} listed twice")
            modules[name] = (kind, sim)
    return modules


def imported_modules(tree: ast.AST, siblings: set[str]) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                parts = a.name.split(".")
                if parts[0] == PACKAGE and len(parts) > 1:
                    found.add(parts[1])
                elif parts[0] in siblings:
                    found.add(parts[0])
        elif isinstance(node, ast.ImportFrom):
            mod = (node.module or "").split(".")
            if node.level == 1 or mod[0] == PACKAGE:
                if node.level == 1 and node.module:
                    found.add(mod[0])
                elif node.level == 1 or len(mod) == 1:
                    found.update(a.name for a in node.names)
                else:
                    found.add(mod[1])
            elif mod[0] in siblings:
                found.add(mod[0])
    return found & siblings


def named_ns3(tree: ast.AST) -> list[tuple[int, str]]:
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for name in NS3_NAMES:
                if name in node.value:
                    hits.append((node.lineno, name))
    return sorted(set(hits))


def check(layout: Path, package: Path) -> list[str]:
    table = parse_table(layout.read_text(encoding="utf-8"))
    files = {p.stem: p for p in package.glob("*.py") if p.stem != "__init__"}
    problems = [
        f"layout: {m} is in the table but has no {package.name}/{m}.py"
        for m in sorted(table.keys() - files.keys())
    ]
    problems += [
        f"layout: {m} has no row in the table" for m in sorted(files.keys() - table.keys())
    ]
    ns3_bound = {m for m, (_, sim) in table.items() if sim == "ns-3"}
    for name in sorted(files.keys() & table.keys()):
        kind, sim = table[name]
        if sim != "agnostic":
            continue
        tree = ast.parse(files[name].read_text(encoding="utf-8"), filename=str(files[name]))
        if kind != "dispatcher":
            for dep in sorted(imported_modules(tree, set(files)) & ns3_bound):
                if (name, dep) in ALLOWED_IMPORTS:
                    continue
                problems.append(f"{name}: agnostic module imports ns-3 module {dep}")
        for line, word in named_ns3(tree):
            problems.append(f"{name}:{line}: agnostic module names {word!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    # No path arguments: the repository's own files only (check() takes paths
    # for the self-test).
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args(argv)
    problems = check(ROOT / "docs" / "layout.md", ROOT / "python" / PACKAGE)
    for p in problems:
        print(p)
    print(f"check-python-boundary: {len(problems)} finding(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
