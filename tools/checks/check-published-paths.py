#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""Refuse a change that moves or deletes a published path (#376, ADR-0002).

`docs/layout.md` "Published paths" lists the paths other repositories, pinned
plans and org documents reach by name; ADR-0002 "Decision" 1 freezes them. The
table's first column is the machine-readable one: a row whose first cell is a
single backticked path (`ns3/routing-bench/`, `tools/checks/check-stock-arms.sh`)
is checked; any other row (the release asset names) is prose and skipped.

Against a base ref (default `origin/main`, compared from the merge base) it
fails when

- a listed file no longer exists, or a listed directory holds no tracked file
  (deleted, or renamed away), or
- a path of the base's table is missing from this table,

and names the path and the consumer the table records. A path may leave the
list only in a change that also edits the table and cites, on an added line
of `docs/layout.md`, an accepted ADR other than ADR-0002 (the one that froze
the list); such a path is then exempt.

    check-published-paths.py [--base REF] [--root DIR]

Exits 1 on any finding, 2 on a usage or environment error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

LAYOUT = "docs/layout.md"
HEADING = re.compile(r"^##\s+Published paths\s*$")
ROW_PATH = re.compile(r"^\|\s*`([^`<>*|\s]+)`\s*\|(.*)\|\s*$")
ADR_REF = re.compile(r"ADR-(\d{4})")
FROZEN_BY = "0002"


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def parse_table(text: str) -> dict[str, str]:
    """{path: consumer} from the "Published paths" section of layout.md."""
    paths: dict[str, str] = {}
    inside = False
    for line in text.splitlines():
        if HEADING.match(line):
            inside = True
        elif inside and line.startswith("## "):
            break
        elif inside and (m := ROW_PATH.match(line)):
            paths[m.group(1)] = m.group(2).strip()
    return paths


def tracked(root: Path, path: str) -> bool:
    """True if HEAD's tree holds the file, or any file under the directory."""
    return bool(git(root, "ls-tree", "-r", "--name-only", "HEAD", "--", path).strip())


def exempt_adrs(root: Path, base: str) -> list[str]:
    """Accepted ADRs, other than the freezing one, that layout.md's added lines cite."""
    diff = git(root, "diff", "-U0", f"{base}...HEAD", "--", LAYOUT)
    added = "\n".join(
        ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")
    )
    found = []
    for num in sorted(set(ADR_REF.findall(added)) - {FROZEN_BY}):
        for adr in (root / "docs" / "adr").glob(f"{num}-*.md"):
            if re.search(r"^- \*\*Status:\*\*\s*Accepted", adr.read_text(), re.M):
                found.append(f"ADR-{num}")
    return found


def check(root: Path, base: str) -> list[str]:
    git(
        root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"
    )  # an unknown base is an error, not a pass
    head_table = parse_table((root / LAYOUT).read_text())
    try:
        base_table = parse_table(git(root, "show", f"{base}:{LAYOUT}"))
    except RuntimeError:
        base_table = {}  # the table's first PR: nothing frozen yet
    if not head_table:
        return [f"{LAYOUT}: no machine-readable rows under '## Published paths'"]
    consumers = {**head_table, **base_table}
    exempt = bool(base_table and exempt_adrs(root, base))
    findings = []
    for path in sorted(set(head_table) | set(base_table)):
        gone = not tracked(root, path)
        unlisted = path in base_table and path not in head_table
        if (gone or unlisted) and not exempt:
            what = (
                "is missing from the Published paths table" if unlisted else "is moved or deleted"
            )
            findings.append(
                f"{path} {what}; consumers: {consumers[path]}. Moving it needs a new, "
                f"accepted ADR naming each consumer's migration, cited in {LAYOUT} "
                "(ADR-0002 Decision 1)."
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", default="origin/main", help="base ref (default origin/main)")
    ap.add_argument("--root", default=".", type=Path, help="repository root")
    args = ap.parse_args(argv)
    try:
        findings = check(args.root, args.base)
    except (RuntimeError, OSError) as err:
        print(f"check-published-paths: {err}", file=sys.stderr)
        return 2
    for finding in findings:
        print(f"check-published-paths: {finding}")
    if not findings:
        print(f"check-published-paths: ok against {args.base}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
