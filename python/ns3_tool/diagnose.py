#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""ns3-tool diagnose CELL [--proto ARM] [--check [scenario_check results options]]

Where each arm's packets went (ns3-tools#39): the drop book of a cell, per
arm, from the harness's `# drops` lines (PDR plus the drop causes, each a
percentage of offered packets, route / queue / mac / chan / ttl, their sum
and the unbooked rest) and, where the cell has them, the `##DROPID##`
per-seed identity counters, averaged over the seeds. A cell collected from
several seed blocks has one `# drops` line per block and arm; the table shows
their mean, with the number of lines read.

`--check` then runs scenario_check's `results` on the same cell (the
plausibility rules and an anchor floor), passing every option that follows it
(`--anchors FILE --anchor NAME --anchor-arms ...`), and exits with its code.

A protocol's own causes on the `# drops` line (`[route: setup=.. reconv=..]`,
blank `-` for arms without them) are shown as printed, not interpreted: no
protocol is special-cased here (AGENTS.md rule 12). The `##DIAG##` line is
contract v2's (#79); until the harness prints it, the drop book is the
diagnosis. A field that is present but not a number fails the read, as the
readers do (#58).

The drop book assumes unicast forwarding: each data hop is one transmission
received at most once, and `chan` is the residual hopTx - hopRx minus the
other causes. For an arm that forwards data by broadcast (a flood), every
reception counts as a hop received, so hopRx exceeds hopTx, `chan` goes far
negative and `sum` with it (#351). When that shows (the `##DROPID##` mean
hopRx above the mean hopTx, or a cause below -100 %),
the arm's `chan` and `sum` read `n/a` and a warning line under the row gives
the raw values; PDR and the other columns are printed as read.
"""

import argparse
import re
import sys

DROPS = re.compile(r"^\s*#\s+drops\s+([A-Za-z][\w-]*)\s+(.+)$")
DROPID = re.compile(r"^\s*##DROPID##\s+(\d+)\s+([A-Za-z][\w-]*)\s+(.+)$")
CAUSES = ["pdr", "route", "queue", "mac", "chan", "ttl", "sum", "other"]


class Malformed(ValueError):
    """A diagnostic field that is present but not a number."""


def _number(where, field, tok):
    try:
        return float(tok)
    except ValueError:
        raise Malformed(f"{where}: {field}={tok!r} is not a number") from None


def parse(text, where="<text>"):
    """({arm: {cause: [values]}}, {arm: {key: [values]}}, {arm: own}) of a cell.

    own is the last `[...]` group of an arm's `# drops` line, verbatim.
    """
    drops, ids, own = {}, {}, {}
    for lineno, line in enumerate(text.splitlines(), 1):
        m = DROPS.match(line)
        if m:
            arm, rest = m.group(1), m.group(2)
            main, _, extra = rest.partition("[")
            for tok in main.split():
                key, eq, val = tok.partition("=")
                if eq and key in CAUSES:
                    v = _number(f"{where}:{lineno}: # drops {arm}", key, val)
                    drops.setdefault(arm, {}).setdefault(key, []).append(v)
            if extra:
                own[arm] = "[" + extra.strip()
            continue
        m = DROPID.match(line)
        if m:
            arm = m.group(2)
            for tok in m.group(3).split():
                key, eq, val = tok.partition("=")
                if eq and val != "-":
                    v = _number(f"{where}:{lineno}: ##DROPID## {arm}", key, val)
                    ids.setdefault(arm, {}).setdefault(key, []).append(v)
    return drops, ids, own


def mean(xs):
    return sum(xs) / len(xs)


BROKEN = ("chan", "sum")  # the columns a broadcast-forwarding arm makes meaningless


def not_unicast(d, i):
    """Why an arm's drop book breaks the unicast assumption, or None.

    d is the arm's `# drops` values, i its `##DROPID##` values (or None). A
    unicast hop is received at most once, so hopRx never exceeds hopTx, and no
    cause can book less than -100 % of the offered packets.
    """
    if i and "hopRx" in i and "hopTx" in i and mean(i["hopRx"]) > mean(i["hopTx"]):
        return f"hopRx {mean(i['hopRx']):.4g} > hopTx {mean(i['hopTx']):.4g}"
    low = [c for c in CAUSES[1:6] if c in d and mean(d[c]) < -100]
    return ", ".join(f"{c} {mean(d[c]):.2f} %" for c in low) or None


def report(text, where="<text>", proto=None):
    """The diagnosis as lines of text."""
    drops, ids, own = parse(text, where)
    arms = [a for a in dict.fromkeys(list(drops) + list(ids)) if not proto or a == proto]
    if not arms:
        return [f"{where}: no '# drops' or ##DROPID## lines" + (f" for {proto}" if proto else "")]
    out = [f"{'arm':<14}{'lines':>6}" + "".join(f"{c:>8}" for c in CAUSES)]
    for arm in arms:
        d = drops.get(arm)
        if not d:
            continue
        n = max(len(v) for v in d.values())
        why = not_unicast(d, ids.get(arm))
        out.append(
            f"{arm:<14}{n:>6}"
            + "".join(
                f"{'n/a':>8}"
                if why and c in BROKEN
                else f"{mean(d[c]):>8.2f}"
                if c in d
                else f"{'-':>8}"
                for c in CAUSES
            )
        )
        if why:
            raw = "  ".join(f"{c}={mean(d[c]):.2f}" for c in BROKEN if c in d)
            out.append(
                f"{'':<20}warning: {arm} breaks the drop book's unicast assumption ({why}): "
                f"broadcast receptions count as hops, so chan and sum are not loss causes "
                f"(raw {raw}); read PDR, and ##AIR## for its cost"
            )
        if arm in own:
            out.append(f"{'':<20}{own[arm]}")
    for arm in arms:
        if arm in ids:
            seeds = max(len(v) for v in ids[arm].values())
            fields = "  ".join(f"{k}={mean(v):.4g}" for k, v in ids[arm].items())
            out.append(f"##DROPID## {arm} (mean of {seeds} seed(s)): {fields}")
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    has_check, check = "--check" in argv, []
    if has_check:
        i = argv.index("--check")
        argv, check = argv[:i], argv[i + 1 :]
    ap = argparse.ArgumentParser(prog="ns3-tool diagnose", description=__doc__.split("\n")[0])
    ap.add_argument("cell", help="a harness output file (- for stdin)")
    ap.add_argument("--proto", help="only this arm")
    a = ap.parse_args(argv)
    with sys.stdin if a.cell == "-" else open(a.cell) as f:
        text = f.read()
    try:
        print("\n".join(report(text, "<stdin>" if a.cell == "-" else a.cell, a.proto)))
    except Malformed as e:
        print(f"diagnose: {e}", file=sys.stderr)
        return 2
    if not has_check:
        return 0
    if a.cell == "-":
        print("diagnose: --check reads the cell from a file, not stdin", file=sys.stderr)
        return 2
    print()
    return run_check(a.cell, check)


def run_check(cell, options):
    """scenario_check's `results` on the cell; its exit code."""
    try:  # as the ns3_tool package, or as a script beside its siblings
        from . import scenario_check
    except ImportError:
        import scenario_check
    saved = sys.argv
    sys.argv = ["ns3-scenario-check", "results", cell, *options]
    try:
        scenario_check.main()
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        sys.argv = saved
    return 0


if __name__ == "__main__":
    sys.exit(main())
