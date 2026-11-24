#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""What a campaign costs, from ##PERF## samples (ns3-tools#95).

A sample is one ##PERF## row of the per-arm form (docs/markers.md) joined to
the ##CONFIG## line before it: arm, harness program, profile, scenario,
nNodes, time and the traffic load (flows, cbrBps; recorded, not fitted), with
its wall seconds. An overhead sample is what one cell run cost beyond its
##PERF## wall times (image pull, setup, upload), from the run's own timings.
`ns3-campaign collect` appends both to a local store (store_path(), bounded);
`seed` writes the same JSON lines from a swarm-routing/benchmarks checkout,
and a `perf-seed.jsonl` beside this file, when present, is read with the
store (the seed table).

The fit, per (program, arm, profile): wall_s ~ a + b * (nNodes^k * time).
k is a least-squares grid search over 0.50..3.00 when the samples have two
node counts or more, else 1. a and b are ordinary least squares; one distinct
x, a < 0 or b <= 0 gives a fit through the origin (a = 0, b = sum wall /
sum x). The error reported is n and the RMSE in seconds. An arm without
samples is unknown: it gets the slowest fitted arm's prediction as a stated
upper bound, and with no fitted arm at all there is no number.

    python3 cost.py fit [FILE...]       # every fit and its error (default: the store)
    python3 cost.py seed BENCHMARKS     # samples of runs/*/cells/*.txt, as JSON lines

Statistics stay scripted (org rule 13): this is the only place a cost is
estimated, and ##PERF## never feeds a verdict. `ns3-campaign verdicts` prints
each arm's CPU s per simulated s and events/s per cell on stderr after its
verdicts (verdict_cost_lines, ns3-tools#91): median and min..max across the
seeds, descriptive and unpaired, and nothing at all without ##PERF## rows.
"""

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys

try:  # as the ns3_tool package, or as a script beside its siblings
    from . import bench_parse
except ImportError:
    import bench_parse

SEED_TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "perf-seed.jsonl")
STORE_MAX = int(os.environ.get("NS3_CAMPAIGN_PERF_MAX", "20000"))  # lines kept, newest
K_GRID = [round(0.5 + 0.05 * i, 2) for i in range(51)]  # 0.50 .. 3.00
CONFIG = re.compile(r"^\s*##CONFIG##\s+(\S+=.*)$")


def store_path(cache):
    """The sample store: NS3_CAMPAIGN_PERF, else <cache>/perf.jsonl."""
    return os.environ.get("NS3_CAMPAIGN_PERF") or os.path.join(cache, "perf.jsonl")


# --- samples ------------------------------------------------------------------


def _num(v):
    for conv in (int, float):
        try:
            return conv(v)
        except (TypeError, ValueError):
            pass
    return None


def samples_of_text(text, profile="optimized", program=None, source=None):
    """The per-arm ##PERF## rows of a cell's text as sample dicts.

    Each row takes nNodes, time, flows and cbrBps from the last ##CONFIG##
    key=value line before it, and its id from the ##PROV## line closing its
    block (key=, else run_id=, else `source`). Rows without a seed, an arm
    or a wall time (AntHocNet's per-process 'all' form) are skipped."""
    out, block, config, prog = [], [], {}, program
    for line in text.splitlines() + ["##PROV## (end)"]:
        m = CONFIG.match(line)
        if m:  # the scenario's key=value line, not a '##CONFIG## attr ...' one
            config = dict(t.split("=", 1) for t in m[1].split() if "=" in t)
            continue
        if line.startswith("##ARGS## "):
            prog = line.split()[1] if len(line.split()) > 1 else prog
            continue
        if line.startswith("##PROV##"):
            prov = dict(t.split("=", 1) for t in line.split()[1:] if "=" in t)
            sid = prov.get("key") or (f"run:{prov['run_id']}" if "run_id" in prov else source)
            for row in block:
                row["id"] = sid
                row["program"] = row["program"] or prog
                out.append(row)
            block = []
            continue
        for p in bench_parse.parse_perf(line):
            if p["seed"] is None or p["wall_s"] is None or p["arm"] in (None, "all"):
                continue
            block.append(
                {
                    "kind": "perf",
                    "arm": p["arm"],
                    "program": prog,
                    "profile": profile,
                    "scenario": config.get("scenario", p["scenario"]),
                    "nNodes": _num(config.get("nNodes")),
                    "time": _num(config.get("time")),
                    "flows": _num(config.get("flows")),
                    "cbrBps": _num(config.get("cbrBps")),
                    "seed": p["seed"],
                    "wall_s": p["wall_s"],
                    "cpu_s": p["cpu_s"],
                    "events": p["events"],
                }
            )
    return out


def overhead_sample(run_id, seconds, text):
    """One run's overhead: its duration minus its ##PERF## wall times (None if < 0)."""
    walls = sum(r["wall_s"] or 0 for r in bench_parse.parse_perf(text) if r["arm"] != "all")
    over = seconds - walls
    if over < 0:
        return None
    return {"kind": "overhead", "id": f"run:{run_id}", "seconds": round(over, 3)}


# --- per-arm cost under the verdicts (ns3-tools#91) ---------------------------

VERDICT_NOTE = "(##PERF##: descriptive, unpaired, noisy; never a verdict or a gate)"


def _spread(xs):
    """'median [min..max]' of the values, '-' with none."""
    xs = sorted(xs)
    if not xs:
        return "-"
    return f"{statistics.median(xs):.4g} [{xs[0]:.4g}..{xs[-1]:.4g}]"


def arm_cost(text, arms):
    """{arm: (n, cpu_s/sim_s spread, events/s spread)} of a cell's per-arm
    ##PERF## rows, for the arms in `arms` that have one, in that order. Simulated
    seconds are the `time=` of the ##CONFIG## before each row; a value the row
    cannot give (no CPU, events or time) is left out, '-' when none is left."""
    by = {}
    for s in samples_of_text(text):
        by.setdefault(s["arm"], []).append(s)
    out = {}
    for arm in arms:
        rows = by.get(arm)
        if not rows:
            continue
        cpu = [s["cpu_s"] / s["time"] for s in rows if s["cpu_s"] is not None and s["time"]]
        eps = [s["events"] / s["wall_s"] for s in rows if s["events"] is not None and s["wall_s"]]
        out[arm] = (len(rows), _spread(cpu), _spread(eps))
    return out


def verdict_cost_lines(head, cells):
    """The cost lines `ns3-campaign verdicts` prints on stderr after its verdicts.

    `head` names every label column, the arm's last (["cell", "arm"]); `cells`
    is [(labels, text, arms)], labels the columns before the arm. One row per (labels, arm) with ##PERF## rows, under
    one header; no row at all gives [] (nothing printed). Descriptive only:
    median and min..max across the cell's seeds, never paired, never a gate."""
    rows = []
    for labels, text, arms in cells:
        for arm, (n, cpu, eps) in arm_cost(text, arms).items():
            rows.append("\t".join(["cost", *labels, arm, str(n), cpu, eps]))
    if not rows:
        return []
    cols = ["cost", *head, "n", "cpu_s/sim_s median [min..max]", "events/s median [min..max]"]
    return ["\t".join([*cols, VERDICT_NOTE]), *rows]


def _sample_id(s):
    return json.dumps([s.get("kind"), s.get("id"), s.get("scenario"), s.get("arm"), s.get("seed")])


def read_samples(*paths):
    """Every sample of the JSON-line files that exist, in order (bad lines skipped)."""
    out = []
    for path in paths:
        try:
            with open(path) as f:
                lines = f.readlines()
        except OSError:
            continue
        for line in lines:
            try:
                s = json.loads(line)
            except ValueError:
                continue
            if isinstance(s, dict):
                out.append(s)
    return out


def append_samples(path, new, limit=None):
    """Add the samples not yet stored (same kind, id, scenario, arm, seed), then
    keep the newest `limit` lines (STORE_MAX). Returns how many were added."""
    limit = STORE_MAX if limit is None else limit
    old = read_samples(path)
    seen = {_sample_id(s) for s in old}
    added = []
    for s in new:
        sid = _sample_id(s)
        if s.get("id") is not None and sid not in seen:
            seen.add(sid)
            added.append(s)
    if not added and len(old) <= limit:
        return 0
    kept = (old + added)[-limit:] if limit > 0 else []
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        for s in kept:
            f.write(json.dumps(s, sort_keys=True) + "\n")
    os.replace(tmp, path)
    return len(added)


# --- the fit ------------------------------------------------------------------


def _ols(xs, ys):
    """(a, b) of y = a + b x, or a fit through the origin when OLS cannot hold."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx > 0:
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        a = my - b * mx
        if a >= 0 and b > 0:
            return a, b
    sx = sum(xs)
    return 0.0, (sum(ys) / sx if sx > 0 else 0.0)


def _sse(a, b, xs, ys):
    return sum((y - a - b * x) ** 2 for x, y in zip(xs, ys))


def fit(points):
    """{a, b, k, n, rmse} of wall ~ a + b * (nNodes^k * time) over
    [(nNodes, time, wall)]; None without a usable point."""
    pts = [(n, t, w) for n, t, w in points if n and t and n > 0 and t > 0 and w is not None]
    if not pts:
        return None
    grid = K_GRID if len({n for n, _t, _w in pts}) > 1 else [1.0]
    best = None
    ys = [w for _n, _t, w in pts]
    for k in grid:
        xs = [n**k * t for n, t, _w in pts]
        a, b = _ols(xs, ys)
        sse = _sse(a, b, xs, ys)
        if best is None or sse < best[0] - 1e-12:
            best = (sse, a, b, k)
    sse, a, b, k = best
    return {"a": a, "b": b, "k": k, "n": len(pts), "rmse": math.sqrt(sse / len(pts))}


def predict(f, nodes, time):
    return max(0.0, f["a"] + f["b"] * nodes ** f["k"] * time)


def fits(samples):
    """{(program, arm, profile): fit} of the perf samples."""
    groups = {}
    for s in samples:
        if s.get("kind", "perf") != "perf":
            continue
        key = (s.get("program"), s.get("arm"), s.get("profile"))
        groups.setdefault(key, []).append((s.get("nNodes"), s.get("time"), s.get("wall_s")))
    out = {}
    for key, pts in groups.items():
        f = fit(pts)
        if f:
            out[key] = f
    return out


def overhead(samples):
    """(median overhead seconds per run, how many runs), or (None, 0)."""
    xs = sorted(s["seconds"] for s in samples if s.get("kind") == "overhead")
    if not xs:
        return None, 0
    mid = len(xs) // 2
    return (xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2), len(xs)


def arm_wall(fitted, program, arm, profile, nodes, time):
    """(seconds per run, basis): basis is 'fit', 'bound:<arm>' (the slowest
    fitted arm, an upper bound) or None with seconds None (unknown)."""
    if not nodes or not time:
        return None, None
    f = fitted.get((program, arm, profile))
    if f:
        return predict(f, nodes, time), "fit"
    for same in (True, False):  # the slowest fitted arm, same program and profile first
        cands = [
            (predict(g, nodes, time), a)
            for (p, a, pr), g in fitted.items()
            if not same or (p == program and pr == profile)
        ]
        if cands:
            secs, slow = max(cands)
            return secs, f"bound:{slow}"
    return None, None


def makespan(durations, slots):
    """Longest-processing-time-first schedule of `durations` on `slots` runners."""
    loads = [0.0] * max(1, slots)
    for d in sorted(durations, reverse=True):
        i = loads.index(min(loads))
        loads[i] += d
    return max(loads) if durations else 0.0


def estimate(jobs, arms, fitted, over, cap, program, profile="optimized"):
    """The cost of `jobs` [(label, nNodes, time, seeds_in_block, reusable)].

    Returns {arms: {arm: {cells, reusable, minutes, elapsed, basis}},
    total: {...}, overhead: seconds or None}; minutes/elapsed are None when
    unknown. A job runs its arms and seeds one after another; reusable jobs
    are free; elapsed is the makespan at `cap` with the runners free."""
    per_arm, durations, unknown = {}, [], False
    run = [j for j in jobs if not j[4]]
    for arm in arms:
        row = {"cells": len(jobs), "reusable": len(jobs) - len(run), "basis": "fit"}
        secs = []
        for _label, nodes, time, n, _r in run:
            w, basis = arm_wall(fitted, program, arm, profile, nodes, time)
            if w is None:
                row["basis"] = None
                break
            if basis != "fit":
                row["basis"] = basis
            secs.append(w * n)
        if row["basis"] is None:
            row.update(minutes=None, elapsed=None)
            unknown = True
        else:
            row.update(minutes=sum(secs) / 60, elapsed=makespan(secs, cap) / 60)
        per_arm[arm] = row
        durations.append(secs)
    total = {"cells": len(jobs), "reusable": len(jobs) - len(run)}
    if unknown:
        total.update(minutes=None, elapsed=None)
    else:
        jobs_s = [sum(d[i] for d in durations) + (over or 0) for i in range(len(run))]
        total.update(minutes=sum(jobs_s) / 60, elapsed=makespan(jobs_s, cap) / 60)
    total["bound"] = any(r["basis"] not in ("fit", None) for r in per_arm.values())
    return {"arms": per_arm, "total": total, "overhead": over}


def _mins(x, bound):
    if x is None:
        return "unknown"
    return f"{'<=' if bound else '~'}{x:.1f}"


def report(est, cap, fitted, program, profile="optimized", nover=0):
    """The estimate as tab-separated `estimate` lines."""
    lines = []
    for arm, r in est["arms"].items():
        if r["basis"] == "fit":
            f = fitted[(program, arm, profile)]
            why = f"fit: n={f['n']}, k={f['k']:.2f}, rmse {f['rmse']:.2f} s"
        elif r["basis"]:
            why = f"no samples: upper bound from the slowest known arm, {r['basis'][6:]}"
        else:
            why = "unknown: no samples (or no --nNodes/--time in the cell args)"
        b = r["basis"] not in ("fit", None)
        lines.append(
            f"estimate\t{arm}\t{r['cells']} cells, {r['reusable']} reusable\t"
            f"{_mins(r['minutes'], b)} runner-min\t{_mins(r['elapsed'], b)} min elapsed "
            f"at cap {cap}\t({why})"
        )
    over = est["overhead"]
    lines.append(
        "estimate\toverhead\t"
        + (
            f"{over / 60:.1f} min per run (median of {nover} run(s))"
            if over is not None
            else "no samples: 0 counted"
        )
    )
    t = est["total"]
    lines.append(
        f"estimate\ttotal\t{t['cells']} cells, {t['reusable']} reusable\t"
        f"{_mins(t['minutes'], t['bound'])} runner-min\t"
        f"{_mins(t['elapsed'], t['bound'])} min elapsed at cap {cap}"
    )
    return lines


# --- the seed table -----------------------------------------------------------


def seed_samples(root):
    """Samples of every runs/*/cells/*.txt of a benchmarks checkout whose
    sha256 matches its manifest entry (others are skipped, on stderr)."""
    out, runs = [], os.path.join(root, "runs")
    for run in sorted(os.listdir(runs)) if os.path.isdir(runs) else []:
        mpath = os.path.join(runs, run, "manifest.json")
        if not os.path.isfile(mpath):
            continue
        with open(mpath) as f:
            man = json.load(f)
        profile = (man.get("base_image") or {}).get("profile", "optimized")
        program = (man.get("harness") or {}).get("program")
        for entry in man.get("files", []):
            rel = entry.get("path", "")
            path = os.path.join(runs, run, rel)
            if not rel.startswith("cells/") or not os.path.isfile(path):
                continue
            with open(path, "rb") as f:
                data = f.read()
            if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                print(f"{path}: sha256 is not its manifest entry's; skipped", file=sys.stderr)
                continue
            out += samples_of_text(data.decode(), profile, program, f"{run}/{rel}")
    return out


def main(argv=None):
    p = argparse.ArgumentParser(prog="cost.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("fit", help="every fit and its error")
    s.add_argument("files", nargs="*", help="sample files (default: the store and seed table)")
    s = sub.add_parser("seed", help="samples of a benchmarks checkout, as JSON lines")
    s.add_argument("benchmarks")
    a = p.parse_args(argv)
    if a.cmd == "seed":
        for s in seed_samples(a.benchmarks):
            print(json.dumps(s, sort_keys=True))
        return
    cache = os.environ.get("NS3_CAMPAIGN_CACHE") or os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "ns3-campaign"
    )
    samples = read_samples(*(a.files or [store_path(cache), SEED_TABLE]))
    for (program, arm, profile), f in sorted(fits(samples).items(), key=str):
        print(
            f"{program}\t{arm}\t{profile}\tn={f['n']}\ta={f['a']:.4g}\tb={f['b']:.4g}\t"
            f"k={f['k']:.2f}\trmse={f['rmse']:.3g} s"
        )
    over, n = overhead(samples)
    print(f"overhead\t{'-' if over is None else f'{over:.1f} s'}\t(median of {n} run(s))")


if __name__ == "__main__":
    main()
