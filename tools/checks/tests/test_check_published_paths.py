#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""check-published-paths.py on scratch repositories. Exits non-zero on any
failure, like python/tests/."""

import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check-published-paths.py"
spec = importlib.util.spec_from_file_location("check_published_paths", SCRIPT)
cpp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cpp)

LAYOUT = """# Layout

## Published paths

| Path | Consumer |
|------|----------|
| `ns3/routing-bench/` | the org image workflows |
| `tools/checks/check-stock-arms.sh` | sim-containers `test/downstream.txt` |
| release asset names `routing-bench-<ver>.tar.gz` | vcpkg port |

## Where a new file goes
"""
ADR = "# 0003. Move it\n\n- **Status:** Accepted (2026-12-01)\n"


def run(root, *cmd):
    subprocess.run(["git", "-C", str(root), *cmd], check=True, capture_output=True)


def write(root, rel, text="x\n"):
    p = Path(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def scratch():
    root = tempfile.mkdtemp()
    run(root, "init", "-q", "-b", "main")
    run(root, "config", "user.email", "t@example.org")
    run(root, "config", "user.name", "t")
    write(root, "docs/layout.md", LAYOUT)
    write(root, "docs/adr/0002-layout.md", "- **Status:** Accepted\n")
    write(root, "ns3/routing-bench/model/a.cc")
    write(root, "tools/checks/check-stock-arms.sh")
    run(root, "add", ".")
    run(root, "commit", "-qm", "base")
    run(root, "branch", "base")
    run(root, "checkout", "-qb", "work")
    return root


def verdict(root):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cpp.main(["--root", str(root), "--base", "base"])
    return code, out.getvalue()


def commit(root):
    run(root, "add", "-A")
    run(root, "commit", "-qm", "change")


problems = []


def expect(name, ok):
    if not ok:
        problems.append(name)


# the table parses: two path rows, the release-asset row is prose
expect(
    "table rows",
    set(cpp.parse_table(LAYOUT)) == {"ns3/routing-bench/", "tools/checks/check-stock-arms.sh"},
)

# an additive change passes
root = scratch()
write(root, "ns3/patches/NS3-005/README.md")
commit(root)
code, _ = verdict(root)
expect("additive change failed", code == 0)

# a file moved inside a published directory passes
root = scratch()
run(root, "mv", "ns3/routing-bench/model/a.cc", "ns3/routing-bench/model/b.cc")
commit(root)
expect("move inside a directory failed", verdict(root)[0] == 0)

# renaming the directory fails, naming the path and the consumer
root = scratch()
run(root, "mv", "ns3/routing-bench", "ns3/harness")
commit(root)
code, out = verdict(root)
expect(
    "directory rename passed",
    code == 1 and "ns3/routing-bench/" in out and "org image workflows" in out,
)

# deleting the file fails, naming the consumer
root = scratch()
run(root, "rm", "-q", "tools/checks/check-stock-arms.sh")
commit(root)
code, out = verdict(root)
expect("file delete passed", code == 1 and "check-stock-arms.sh" in out and "sim-containers" in out)

# dropping the row without an ADR fails
root = scratch()
write(
    root,
    "docs/layout.md",
    LAYOUT.replace(
        "| `tools/checks/check-stock-arms.sh` | sim-containers `test/downstream.txt` |\n", ""
    ),
)
commit(root)
expect("row removal passed", verdict(root)[0] == 1)

# row removal + delete + an accepted ADR other than 0002 cited passes
root = scratch()
run(root, "rm", "-q", "tools/checks/check-stock-arms.sh")
write(
    root,
    "docs/layout.md",
    LAYOUT.replace(
        "| `tools/checks/check-stock-arms.sh` | sim-containers `test/downstream.txt` |\n", ""
    )
    + "Retired by ADR-0003.\n",
)
write(root, "docs/adr/0003-move.md", ADR)
commit(root)
expect("ADR exemption failed", verdict(root)[0] == 0)

# citing ADR-0002 (the freezing one) or an unaccepted ADR does not exempt
for cited, adr in (("ADR-0002", None), ("ADR-0003", "- **Status:** Proposed\n")):
    root = scratch()
    run(root, "rm", "-q", "tools/checks/check-stock-arms.sh")
    write(root, "docs/layout.md", LAYOUT + f"Retired by {cited}.\n")
    if adr:
        write(root, "docs/adr/0003-move.md", adr)
    commit(root)
    expect(f"{cited} exempted", verdict(root)[0] == 1)

# a table with no rows, and an unknown base, are refused
root = scratch()
write(root, "docs/layout.md", "# Layout\n")
commit(root)
expect("empty table passed", verdict(root)[0] == 1)
with contextlib.redirect_stderr(io.StringIO()):
    expect("bad base", cpp.main(["--root", str(root), "--base", "nope"]) == 2)

sys.exit("FAIL: " + "; ".join(problems) if problems else 0)
