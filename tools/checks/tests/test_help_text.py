#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""routing-compare's --PrintHelp text is protocol-agnostic (golden rule 12, #351).

Reads the help strings of every `cmd.AddValue` in
ns3/routing-bench/model/routing-bench-harness.cc (the string literals between
`CommandLine cmd(program);` and `cmd.Parse(argc, argv);`, comments left out)
and fails on a bare issue number (an AntHocNet one; this repository's are
written `sim-tools#N`), the repository's old name, the name AntHocNet, or a
path that exists only in AntHocNet. Exits non-zero on any failure, like
python/tests/.
"""

import re
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[3] / "ns3/routing-bench/model/routing-bench-harness.cc"
LITERAL = re.compile(r'"((?:[^"\\]|\\.)*)"')
FORBIDDEN = [
    (re.compile(r"(?<![\w-])#\d+"), "a bare issue number"),
    (re.compile(r"ns3-tools"), "the old repository name"),
    (re.compile(r"AntHocNet", re.IGNORECASE), "a protocol's name"),
    (re.compile(r"docs/benchmarks/|tools/bench/"), "an AntHocNet-only path"),
]


def help_text(source):
    """The help strings' literals, one per line, from the CommandLine block."""
    start = source.index("CommandLine cmd(program);")
    end = source.index("cmd.Parse(argc, argv);", start)
    lines = []
    for line in source[start:end].splitlines():
        if not line.lstrip().startswith("//"):
            lines += LITERAL.findall(line)
    return lines


def problems(lines):
    return [f"{why}: {text!r}" for text in lines for rx, why in FORBIDDEN if rx.search(text)]


def main():
    lines = help_text(HARNESS.read_text())
    selftest = problems(["see #58", "AntHocNet's field", "docs/benchmarks/x.md", "ns3-tools#91"])
    found = problems(lines)
    if len(selftest) != 4:
        print(f"FAIL: the patterns missed a planted reference ({selftest})")
        return 1
    if problems(["sim-tools#91", "NS3-001 (docs/ns3-bugs.md)", "a '#' comment"]):
        print("FAIL: an allowed reference was refused")
        return 1
    if len(lines) < 40:
        print(f"FAIL: only {len(lines)} help literals read; the block moved?")
        return 1
    if found:
        print("FAIL: --PrintHelp text is not protocol-agnostic:\n  " + "\n  ".join(found))
        return 1
    print(f"ok   --PrintHelp: {len(lines)} help literals, no AntHocNet reference")
    return 0


if __name__ == "__main__":
    sys.exit(main())
