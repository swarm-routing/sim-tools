#!/usr/bin/env python3
# Copyright (c) 2026 Daniel Joppi (https://github.com/swarm-routing)
# SPDX-License-Identifier: MIT OR GPL-2.0-only
"""Self-test for cost.py (ns3-tools#95), offline.

1. The fit recovers known a, b and k from synthetic samples within
   tolerance; one node count fixes k = 1; a negative intercept falls back to
   a fit through the origin.
2. The estimate: runner-minutes and the elapsed time at a cap, reusable cells
   free, an arm without samples bounded by the slowest known arm, and no
   number at all without samples.
3. The samples: ##PERF## rows joined to their ##CONFIG##, their id from
   ##PROV##; the store deduplicates and stays bounded; the seed table comes
   from a benchmarks checkout whose files match their manifest.

Run: python3 test_cost.py   (no pytest; exits non-zero on the first failure)
"""

import contextlib
import hashlib
import io
import json
import os
import random
import sys
import tempfile

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(TESTS), "ns3_tool"))
import cost  # noqa: E402 (after the sys.path insert)


def check(cond, what):
    if not cond:
        sys.exit(f"FAIL: {what}")
    print(f"ok   {what}")


def close(x, y, rel):
    return abs(x - y) <= rel * abs(y)


def test_fit():
    rng = random.Random(95)
    a, b, k = 2.0, 5e-4, 1.5
    pts = []
    for n in (20, 50, 100, 150):
        for t in (100, 300, 600):
            for _seed in range(3):
                w = a + b * n**k * t
                pts.append((n, t, w * (1 + rng.uniform(-0.01, 0.01))))
    f = cost.fit(pts)
    check(abs(f["k"] - k) <= 0.05, f"fit: k {f['k']} within 0.05 of {k}")
    check(close(f["b"], b, 0.15), f"fit: b {f['b']:.3g} within 15% of {b}")
    check(abs(f["a"] - a) <= 1.5, f"fit: a {f['a']:.3g} within 1.5 s of {a}")
    check(f["n"] == len(pts) and f["rmse"] < 0.02 * (a + b * 150**k * 600), "fit: n and rmse")
    exact = cost.fit([(n, t, a + b * n**k * t) for n, t, _w in pts])
    check(exact["k"] == k and close(exact["b"], b, 1e-6), "fit: noiseless samples, exact")

    one = cost.fit([(50, t, 1.0 + 0.01 * t) for t in (100, 200, 300)])
    check(
        one["k"] == 1.0 and close(one["b"], 0.01 / 50, 1e-9) and close(one["a"], 1.0, 1e-9),
        f"fit: one node count, k = 1 ({one})",
    )
    flat = cost.fit([(50, 300, 4.0), (50, 300, 6.0)])
    check(flat["a"] == 0 and close(flat["b"] * 50 * 300, 5.0, 1e-9), "fit: one x, the mean ratio")
    neg = cost.fit([(50, 100, 0.5), (50, 200, 3.0), (50, 300, 5.5)])
    check(neg["a"] == 0 and neg["b"] > 0, f"fit: a < 0 falls back to the origin ({neg})")
    check(cost.fit([(None, 300, 1.0), (50, None, 1.0)]) is None, "fit: no usable point, None")


def samples(arm, wall, n=50, t=300, count=3, program="routing-compare"):
    return [
        {"kind": "perf", "arm": arm, "program": program, "profile": "optimized",
         "nNodes": n, "time": t, "seed": s, "wall_s": wall, "id": f"x-{arm}"}
        for s in range(1, count + 1)
    ]  # fmt: skip


def test_estimate():
    prog = "routing-compare"
    fitted = cost.fits(samples("a", 2.0) + samples("b", 1.0))
    jobs = [("j1", 50, 300, 20, False), ("j2", 50, 300, 10, False), ("j3", 50, 300, 10, True)]
    est = cost.estimate(jobs, ["a", "b"], fitted, 60.0, 2, prog)
    ra, rb, t = est["arms"]["a"], est["arms"]["b"], est["total"]
    check((ra["cells"], ra["reusable"]) == (3, 1), "estimate: cells and reusable per arm")
    check(close(ra["minutes"], 60 / 60, 1e-9), f"estimate: arm a, 30 runs x 2 s ({ra})")
    check(close(rb["minutes"], 30 / 60, 1e-9), "estimate: arm b, 30 runs x 1 s")
    jobs_s = [20 * 3 + 60, 10 * 3 + 60]
    check(close(t["minutes"], sum(jobs_s) / 60, 1e-9), f"estimate: total + overhead ({t})")
    check(close(t["elapsed"], 120 / 60, 1e-9), "estimate: elapsed at cap 2 is the longest job")
    one = cost.estimate(jobs, ["a", "b"], fitted, 60.0, 1, prog)
    check(close(one["total"]["elapsed"], 210 / 60, 1e-9), "estimate: cap 1 runs them in turn")
    check(cost.makespan([3, 5, 3, 4, 3], 2) == 10, "makespan: longest first, to the least loaded")

    bound = cost.estimate(jobs, ["a", "c"], fitted, None, 2, prog)
    rc = bound["arms"]["c"]
    check(rc["basis"] == "bound:a" and close(rc["minutes"], 1.0, 1e-9), f"unknown arm: <= a ({rc})")
    check(bound["total"]["bound"], "unknown arm: the total is an upper bound")
    lines = cost.report(bound, 2, fitted, prog)
    check(
        any(ln.startswith("estimate\tc\t") and "<=1.0 runner-min" in ln and "upper bound" in ln
            for ln in lines),
        f"report: the bound is stated ({lines})",
    )  # fmt: skip
    check(any("no samples: 0 counted" in ln for ln in lines), "report: no overhead samples")
    none = cost.estimate(jobs, ["a"], {}, None, 2, prog)
    check(
        none["total"]["minutes"] is None and none["arms"]["a"]["basis"] is None,
        "no samples: unknown, never a number",
    )
    check(
        any("unknown runner-min" in ln for ln in cost.report(none, 2, {}, prog)),
        "report: unknown",
    )
    nod = cost.estimate([("j", None, 300, 20, False)], ["a"], fitted, None, 2, prog)
    check(nod["total"]["minutes"] is None, "no --nNodes in the args: unknown")


CELL = """##CONFIG## scenario=paper nNodes=50 time=300 runs=2 firstRun=1 flows=20 cbrBps=512
##CONFIG## attr HelloInterval=+1e+09ns
##RUN## 1 aodv 80.0 1 1 1 1 1 1 1 1
##PERF## paper aodv 1 1.100 1.200 5000 -
##PERF## paper aodv 2 1.000 1.300 5000 -
##PERF## paper-mobile all 512.3 734212
##ARGS## routing-compare --nNodes=50 --time=300
##PROV## base=x image=y modules=z run_id=7 key=KEY1
##CONFIG## scenario=paper nNodes=100 time=300 runs=1 firstRun=3
##PERF## paper olsr 3 2.000 2.500 9000 81234
##PROV## base=x image=y modules=z run_id=8
"""


def test_samples():
    got = cost.samples_of_text(CELL, source="src")
    check(len(got) == 3, f"samples: the per-arm rows only ({len(got)})")
    s = got[0]
    check(
        (s["arm"], s["nNodes"], s["time"], s["flows"], s["cbrBps"], s["wall_s"], s["id"])
        == ("aodv", 50, 300, 20, 512, 1.2, "KEY1"),
        f"samples: joined to ##CONFIG##, id from ##PROV## key ({s})",
    )
    check(s["program"] == "routing-compare", "samples: the program from ##ARGS##")
    check(got[2]["nNodes"] == 100 and got[2]["id"] == "run:8", "samples: the next block's own")
    o = cost.overhead_sample(7, 600, CELL)
    check(o["seconds"] == round(600 - 5.0, 3), f"overhead: duration minus ##PERF## walls ({o})")
    check(cost.overhead_sample(7, 1, CELL) is None, "overhead: never negative")

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "perf.jsonl")
        check(cost.append_samples(path, got) == 3, "store: three added")
        check(cost.append_samples(path, got) == 0, "store: a second collect adds nothing")
        more = [dict(s, seed=s["seed"] + 100) for s in got]
        cost.append_samples(path, more, limit=4)
        kept = cost.read_samples(path)
        check(len(kept) == 4 and kept[-1]["seed"] == 103, "store: bounded, the newest kept")
        with open(path, "a") as f:
            f.write("not json\n")
        check(
            len(cost.read_samples(path, os.path.join(d, "none"))) == 4, "store: bad lines skipped"
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cost.main(["fit", path])
        check(
            "routing-compare\taodv\toptimized\tn=2\t" in out.getvalue()
            and "overhead\t-\t(median of 0 run(s))" in out.getvalue(),
            f"fit command: each fit and its error ({out.getvalue()!r})",
        )


def test_seed():
    with tempfile.TemporaryDirectory() as d:
        run = os.path.join(d, "runs", "2026-11-20-x")
        os.makedirs(os.path.join(run, "cells"))
        files = []
        for name, text in (("good", CELL), ("bad", CELL)):
            with open(os.path.join(run, "cells", f"{name}.txt"), "w") as f:
                f.write(f"# x {name}: header\n" + text)
            data = ("# x good: header\n" + CELL).encode()  # bad's sha is good's
            files.append({"path": f"cells/{name}.txt", "sha256": hashlib.sha256(data).hexdigest()})
        with open(os.path.join(run, "cells", "bad.txt"), "a") as f:
            f.write("tampered\n")
        with open(os.path.join(run, "manifest.json"), "w") as f:
            json.dump(
                {"base_image": {"profile": "optimized"},
                 "harness": {"program": "routing-compare"}, "files": files},
                f,
            )  # fmt: skip
        got = cost.seed_samples(d)
        check(len(got) == 3, f"seed: the matching file only ({len(got)})")
        check({s["profile"] for s in got} == {"optimized"}, "seed: the manifest's profile")
        check(cost.seed_samples(os.path.join(d, "empty")) == [], "seed: no runs/, nothing")


if __name__ == "__main__":
    test_fit()
    test_estimate()
    test_samples()
    test_seed()
    print("test_cost: all ok")
