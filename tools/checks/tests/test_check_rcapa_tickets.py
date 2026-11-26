#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""check-rcapa-tickets.py against a temporary git repository and a fake
GitHub API (no network). Exits non-zero on any failure, like python/tests/."""

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check-rcapa-tickets.py"
spec = importlib.util.spec_from_file_location("check_rcapa_tickets", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REPO = "swarm-routing/sim-tools"
LINK = "https://github.com/swarm-routing/sim-tools/issues/{n}#issuecomment-{c}"
DOC = "docs/ns3-rcapa/ns3-rcapa-x.md"
OLD_DOC = "docs/ns3-rcapa/ns3-rcapa-old.md"


def doc(rcapa_id, rows):
    return f"# {rcapa_id}: x\n\n## Timeline\n\n| Date | Event |\n|------|-------|\n" + "".join(
        f"| 2026-11-26 | {r} |\n" for r in rows
    )


def run(root, *args, date="2026-11-20T10:00:00+00:00"):
    env = {
        **os.environ,
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.org",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.org",
    }
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True, env=env)


def write(root, rel, text):
    path = Path(root, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class Fake:
    """Issues by id, comments by id; counts nothing, 404s are None."""

    def __init__(self, issues, comments=None):
        self.issues, self.comments = issues, comments or {}

    def __call__(self, path):
        if path.startswith("/search/issues"):
            return {"items": self.issues}
        if "/issues/comments/" in path:
            return self.comments.get(int(path.rsplit("/", 1)[1]))
        raise AssertionError(path)


def issue(n, rcapa_id, labels=("rcapa", "ns3-upstream"), created="2026-11-19T00:00:00Z"):
    return {
        "number": n,
        "title": f"[rcapa] {rcapa_id} something",
        "created_at": created,
        "labels": [{"name": name} for name in labels],
    }


def comment(n):
    return {"issue_url": f"https://api.github.com/repos/{REPO}/issues/{n}"}


def scenario(branch_files, base_files=None, branch_date="2026-11-20T10:00:00+00:00"):
    """A repo whose main has base_files and whose branch adds/changes branch_files."""
    root = tempfile.mkdtemp()
    run(root, "init", "-q", "-b", "main")
    for rel, text in (base_files or {"README.md": "x\n"}).items():
        write(root, rel, text)
    run(root, "add", "-A")
    run(root, "commit", "-q", "-m", "base", date="2026-11-01T00:00:00+00:00")
    run(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    run(root, "checkout", "-q", "-b", "pr")
    for rel, text in branch_files.items():
        write(root, rel, text)
    run(root, "add", "-A")
    run(root, "commit", "-q", "--allow-empty", "-m", "change", date=branch_date)
    return root


def verdict(root, api, offline=False, argv=()):
    out, err = io.StringIO(), io.StringIO()
    args = ["--root", root, "--repo", REPO, *argv] + (["--offline"] if offline else [])
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mod.main(args, api=api)
    return code, out.getvalue(), err.getvalue()


problems = []


def expect(name, ok, detail=""):
    if not ok:
        problems.append(f"{name}: {detail}")


good_rows = [f"opened [ticket]({LINK.format(n=7, c=100)})"]
good = Fake([issue(7, "NS3-009")], {100: comment(7)})

# 1. a new doc with ticket first, labels, and a ticket comment on every row passes
root = scenario({DOC: doc("NS3-009", good_rows)})
code, out, _ = verdict(root, good)
expect("clean change passes", code == 0 and "ok" in out, out)

# 2. no ticket
code, out, _ = verdict(root, Fake([]))
expect("missing ticket fails", code == 1 and "no issue titled" in out, out)

# 3. a title that only starts like the ID (NS3-0091) is not the ticket
code, out, _ = verdict(root, Fake([issue(7, "NS3-0091")]))
expect("prefix of a longer ID is not a match", code == 1 and "no issue titled" in out, out)

# 4. a pull request with the title is not a ticket
pr_item = {**issue(7, "NS3-009"), "pull_request": {}}
code, out, _ = verdict(root, Fake([pr_item]))
expect("a PR is not a ticket", code == 1, out)

# 5. missing labels (NS3 needs ns3-upstream; PROC does not)
code, out, _ = verdict(root, Fake([issue(7, "NS3-009", labels=("rcapa",))], {100: comment(7)}))
expect("missing ns3-upstream fails", code == 1 and "ns3-upstream" in out, out)
proc_root = scenario({DOC: doc("PROC-002", good_rows)})
code, out, _ = verdict(
    proc_root, Fake([issue(7, "PROC-002", labels=("rcapa",))], {100: comment(7)})
)
expect("PROC needs only rcapa", code == 0, out)
code, out, _ = verdict(proc_root, Fake([issue(7, "PROC-002", labels=())], {100: comment(7)}))
expect("PROC without rcapa fails", code == 1 and "rcapa" in out, out)

# 6. the ticket opened after the first commit
late = Fake([issue(7, "NS3-009", created="2026-11-21T00:00:00Z")], {100: comment(7)})
code, out, _ = verdict(root, late)
expect("late ticket fails", code == 1 and "first commit" in out, out)

# 7. timeline rows: no link, a link to another ticket, a comment that is not the ticket's
for name, rows, comments in (
    ("no link", ["nothing linked"], {}),
    ("another ticket", [f"x {LINK.format(n=8, c=100)}"], {100: comment(8)}),
    ("unknown comment", good_rows, {}),
    ("comment of another issue", good_rows, {100: comment(8)}),
    ("one good row and one bad", good_rows + ["bare"], {100: comment(7)}),
):
    r = scenario({DOC: doc("NS3-009", rows)})
    code, out, _ = verdict(r, Fake([issue(7, "NS3-009")], comments))
    expect(f"timeline: {name}", code == 1 and "no link to a comment" in out, out)

# 8. the old repository name in a link is the same ticket
old_link = good_rows[0].replace("sim-tools", "ns3-tools")
r = scenario({DOC: doc("NS3-009", [old_link])})
code, out, _ = verdict(r, good)
expect("ns3-tools link accepted", code == 0, out)

# 8b. --repo selects the link's repository: links to it pass, the default's links do not
other = "example/other"
other_row = good_rows[0].replace("swarm-routing/sim-tools", other)
r = scenario({DOC: doc("NS3-009", [other_row])})
fake = Fake([issue(7, "NS3-009")], {100: comment(7)})
code, out, _ = verdict(r, fake, argv=["--repo", other])
expect("--repo link accepted", code == 0, out)
r = scenario({DOC: doc("NS3-009", good_rows)})
code, out, _ = verdict(r, fake, argv=["--repo", other])
expect("--repo rejects the default repository's link", code == 1, out)

# 9. grandfathered: a pre-existing doc changed. Late ticket and bare timeline rows only warn,
#    but a missing ticket still fails.
base = {OLD_DOC: doc("NS3-004", ["old row"])}
r = scenario({OLD_DOC: doc("NS3-004", ["old row", "new row"])}, base)
old_api = Fake([issue(7, "NS3-004", created="2026-11-25T00:00:00Z")])
code, out, _ = verdict(r, old_api)
expect(
    "existing doc: warn only",
    code == 0 and out.count("warn:") == 2 and "first commit" not in out,
    out,
)
code, out, _ = verdict(r, Fake([]))
expect("existing doc: missing ticket still fails", code == 1, out)

# 10. a rename of an existing doc is a change, not an add
r = scenario({}, base)
run(r, "mv", OLD_DOC, "docs/ns3-rcapa/ns3-rcapa-renamed.md")
run(r, "commit", "-q", "-m", "rename")
code, out, _ = verdict(r, old_api)
expect("rename is grandfathered", code == 0, out)

# 11. register row: new or changed row needs the ticket; an untouched row does not
bugs = "| ID | Title |\n|----|-------|\n| NS3-004 | a |\n| NS3-005 | b |\n"
BUGS = "docs/ns3-bugs.md"
r = scenario({BUGS: bugs.replace("| b |", "| b2 |")}, {BUGS: bugs})
code, out, _ = verdict(r, Fake([issue(9, "NS3-005")]))
expect("changed row checks only its own ID", code == 0, out)
code, out, _ = verdict(r, Fake([issue(9, "NS3-004")]))
expect("changed row without a ticket fails", code == 1 and "NS3-005" in out, out)

# 12. patch directory: added is strict, changed is not
r = scenario({"ns3/patches/NS3-012/apply.sh": "#!/bin/sh\n"})
code, out, _ = verdict(r, Fake([issue(3, "NS3-012", created="2026-11-21T00:00:00Z")]))
expect("late ticket for an added patch fails", code == 1 and "first commit" in out, out)
r = scenario(
    {"ns3/patches/NS3-012/apply.sh": "#!/bin/sh\n# x\n"},
    {"ns3/patches/NS3-012/apply.sh": "#!/bin/sh\n"},
)
code, out, _ = verdict(r, Fake([issue(3, "NS3-012", created="2026-11-21T00:00:00Z")]))
expect("late ticket for a changed patch passes", code == 0, out)

# 13. unrelated change: nothing to check, the API is never called
r = scenario({"python/x.py": "x = 1\n"})
code, out, _ = verdict(r, lambda path: (_ for _ in ()).throw(AssertionError("API called")))
expect("no RCAPA path: no API call", code == 0, out)

# 14. fail closed: no token, no API; --offline lists and passes; API errors exit 2
saved = {k: os.environ.pop(k, None) for k in ("GITHUB_TOKEN", "GH_TOKEN")}
code, _, err = verdict(root, None)
expect("no token fails closed with the hint", code == 2 and "--offline" in err, err)
for k, v in saved.items():
    if v is not None:
        os.environ[k] = v
code, out, _ = verdict(root, None, offline=True)
expect("offline lists and passes", code == 0 and "NS3-009" in out, out)


def broken(path):
    raise OSError("unreachable")


code, _, err = verdict(root, broken)
expect("unreachable API fails closed", code == 2 and "--offline" in err, err)
code, _, err = verdict(root, good, argv=["--base", "no-such-ref"])
expect("unknown base is an error", code == 2, err)

if problems:
    print("\n".join(f"FAIL {p}" for p in problems), file=sys.stderr)
    sys.exit(1)
print("test_check_rcapa_tickets: ok")
