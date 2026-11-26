#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""Refuse an RCAPA change whose ticket does not come first (swarm-routing/.github#952).

An ns-3 bug (NS3-NNN) or a process defect (PROC-NNN) gets its RCAPA ticket
*before* the investigation, and the investigation is logged on it (`rcapa.py
log`, swarm-routing/.github `tools/rcapa/rcapa.py`). This check holds a pull
request to that. Against a base ref (default `origin/main`, compared from the
merge base) it finds each ID whose `docs/ns3-rcapa/*.md` (the ID is in the
first heading), `docs/ns3-bugs.md` row or `ns3/patches/<ID>/` the change adds
or changes, and fails when

- no issue titled `[rcapa] <ID> ...` exists in the repository,
- the issue lacks the `rcapa` label (and `ns3-upstream`, for an NS3-NNN),
- the issue was created after the change's first commit (author date), for an
  RCAPA document or a patch directory the change *adds*; documents and
  patches already on the base are grandfathered, or
- a Timeline row of a document the change *adds* has no link
  `https://github.com/swarm-routing/<repo>/issues/<n>#issuecomment-<id>` to a
  comment of that ticket (the comment is looked up).

A Timeline row without such a link in a document already on the base is only
a warning. The GitHub API is read with GITHUB_TOKEN (or GH_TOKEN), read-only.
With no API (no token, or it is unreachable) the check fails closed (exit 2);
`--offline` lists what it would check and passes.

    check-rcapa-tickets.py [--base REF] [--root DIR] [--repo OWNER/NAME] [--offline]

Exits 1 on any finding, 2 on a usage, environment or API error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable

DEFAULT_REPO = "swarm-routing/sim-tools"
BUGS = "docs/ns3-bugs.md"
DOC_DIR = "docs/ns3-rcapa/"
PATCH_DIR = "ns3/patches/"
ID_RE = re.compile(r"(?:NS3|PROC)-\d{3,}")
HEADING_ID = re.compile(r"^#\s+((?:NS3|PROC)-\d{3,})\b")
ROW_ID = re.compile(r"^\|\s*((?:NS3|PROC)-\d{3,})\s*\|")
# sim-tools was ns3-tools until its rename: both spellings link the same issues
COMMENT_LINK = re.compile(
    r"https://github\.com/swarm-routing/(?:sim|ns3)-tools/issues/(\d+)#issuecomment-(\d+)"
)
API = "https://api.github.com"

Api = Callable[[str], object]  # path (with query) -> parsed JSON; None on 404


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout


def show(root: Path, rev: str, path: str) -> str | None:
    try:
        return git(root, "show", f"{rev}:{path}")
    except RuntimeError:
        return None


class Touch:
    """What a change does for one ID."""

    def __init__(self) -> None:
        self.docs_added: list[str] = []
        self.docs_changed: list[str] = []
        self.rows_changed = False
        self.patch_added = False
        self.patch_changed = False

    @property
    def added(self) -> bool:
        return bool(self.docs_added) or self.patch_added


def register_rows(text: str | None) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in (text or "").splitlines():
        m = ROW_ID.match(line)
        if m:
            rows[m.group(1)] = line
    return rows


def touched(root: Path, base: str, head: str) -> dict[str, Touch]:
    """{ID: what the change does} for the RCAPA paths between base and head."""
    found: dict[str, Touch] = {}

    def of(rcapa_id: str) -> Touch:
        return found.setdefault(rcapa_id, Touch())

    out = git(root, "diff", "--name-status", "-M", base, head, "--", DOC_DIR, PATCH_DIR, BUGS)
    for line in out.splitlines():
        parts = line.split("\t")
        status, path = parts[0][0], parts[-1]
        if status == "D":
            continue
        if path.startswith(DOC_DIR) and path.endswith(".md"):
            if path.rsplit("/", 1)[1] in ("README.md", "_template.md"):
                continue
            first = (show(root, head, path) or "").split("\n", 1)[0]
            m = HEADING_ID.match(first)
            if m:
                (
                    of(m.group(1)).docs_added if status == "A" else of(m.group(1)).docs_changed
                ).append(path)
        elif path.startswith(PATCH_DIR):
            m = ID_RE.fullmatch(path[len(PATCH_DIR) :].split("/", 1)[0])
            if m:
                touch = of(m.group(0))
                if git(root, "ls-tree", base, "--", f"{PATCH_DIR}{m.group(0)}/").strip():
                    touch.patch_changed = True
                else:
                    touch.patch_added = True
    old, new = register_rows(show(root, base, BUGS)), register_rows(show(root, head, BUGS))
    for rcapa_id, row in new.items():
        if old.get(rcapa_id) != row:
            of(rcapa_id).rows_changed = True
    return found


def timeline_rows(text: str) -> list[str]:
    """The data rows of the `## Timeline` table."""
    rows: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Timeline"
        elif inside and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and cells[0] != "Date" and not set("".join(cells)) <= set("-: "):
                rows.append(line)
    return rows


def find_ticket(api: Api, repo: str, rcapa_id: str) -> dict | None:
    query = f'repo:{repo} is:issue in:title "[rcapa] {rcapa_id}"'
    found = api(f"/search/issues?q={urllib.parse.quote(query)}&per_page=30")
    for item in (found or {}).get("items", []):
        title = item.get("title", "")
        if "pull_request" not in item and re.match(
            rf"\[rcapa\]\s+{re.escape(rcapa_id)}(?!\d)", title
        ):
            return item
    return None


def check(
    root: Path, base: str, repo: str, api: Api | None, head: str = "HEAD"
) -> tuple[list[str], list[str], list[str]]:
    """(failures, warnings, notes) for the change from base's merge base to head."""
    fails: list[str] = []
    warns: list[str] = []
    notes: list[str] = []
    merge_base = git(root, "merge-base", base, head).strip()
    ids = touched(root, merge_base, head)
    dates = git(root, "log", "--no-merges", "--reverse", "--format=%aI", f"{merge_base}..{head}")
    first_commit = datetime.fromisoformat(dates.split()[0]) if dates.split() else None
    for rcapa_id in sorted(ids):
        touch = ids[rcapa_id]
        what = ", ".join(
            [f"{p} (added)" for p in touch.docs_added]
            + [f"{p} (changed)" for p in touch.docs_changed]
            + (["register row"] if touch.rows_changed else [])
            + (["ns3/patches (added)"] if touch.patch_added else [])
            + (["ns3/patches (changed)"] if touch.patch_changed else [])
        )
        if api is None:
            notes.append(f"{rcapa_id}: would check the ticket for {what}")
            continue
        ticket = find_ticket(api, repo, rcapa_id)
        if ticket is None:
            fails.append(
                f"{rcapa_id}: no issue titled '[rcapa] {rcapa_id} ...' in {repo}; "
                f"open the ticket first, then investigate (changed: {what})"
            )
            continue
        number = ticket["number"]
        have = {label["name"] for label in ticket.get("labels", [])}
        need = {"rcapa"} | ({"ns3-upstream"} if rcapa_id.startswith("NS3-") else set())
        if need - have:
            fails.append(
                f"{rcapa_id}: {repo}#{number} lacks label(s) {', '.join(sorted(need - have))}"
            )
        if touch.added and first_commit is not None:
            created = datetime.fromisoformat(ticket["created_at"])
            if created > first_commit:
                fails.append(
                    f"{rcapa_id}: {repo}#{number} was created {ticket['created_at']}, after the "
                    f"change's first commit ({first_commit.isoformat()}); the ticket comes first"
                )
        for path in touch.docs_added + touch.docs_changed:
            strict = path in touch.docs_added
            for row in timeline_rows(show(root, head, path) or ""):
                problem = bad_timeline_row(api, repo, number, row)
                if problem:
                    (fails if strict else warns).append(
                        f"{rcapa_id}: {path}: {problem}: {row[:80]}"
                    )
    return fails, warns, notes


def bad_timeline_row(api: Api, repo: str, number: int, row: str) -> str | None:
    """Why a Timeline row does not link a comment of ticket `number`, or None."""
    for m in COMMENT_LINK.finditer(row):
        if int(m.group(1)) != number:
            continue
        comment = api(f"/repos/{repo}/issues/comments/{m.group(2)}")
        if comment and str(comment.get("issue_url", "")).endswith(f"/issues/{number}"):
            return None
    return f"no link to a comment on {repo}#{number} (…/issues/{number}#issuecomment-…)"


def github_api(token: str) -> Api:
    def call(path: str) -> object:
        req = urllib.request.Request(
            API + path,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "sim-tools-check-rcapa-tickets",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            raise

    return call


def main(argv: list[str] | None = None, api: Api | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--base", default="origin/main", help="base ref (default origin/main)")
    ap.add_argument("--root", type=Path, default=Path("."), help="repository root")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY") or DEFAULT_REPO)
    ap.add_argument("--offline", action="store_true", help="list what would be checked; no API")
    args = ap.parse_args(argv)
    if not args.offline and api is None:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            print(
                "check-rcapa-tickets: no GITHUB_TOKEN or GH_TOKEN, so the tickets cannot be read "
                "(failing closed); pass --offline to list what would be checked",
                file=sys.stderr,
            )
            return 2
        api = github_api(token)
    try:
        fails, warns, notes = check(args.root, args.base, args.repo, None if args.offline else api)
    except (RuntimeError, urllib.error.URLError, OSError, ValueError, KeyError) as err:
        print(
            f"check-rcapa-tickets: {err} (failing closed); pass --offline to skip the GitHub API",
            file=sys.stderr,
        )
        return 2
    for line in notes:
        print(f"note: {line}")
    for line in warns:
        print(f"warn: {line}")
    for line in fails:
        print(f"FAIL: {line}")
    if fails:
        print(f"check-rcapa-tickets: {len(fails)} finding(s); swarm-routing/.github#952")
        return 1
    print("check-rcapa-tickets: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
