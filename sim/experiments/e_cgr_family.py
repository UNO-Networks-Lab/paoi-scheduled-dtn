#!/usr/bin/env python3
"""CGR-family comparison: E-CGR, RUCoP, and their composition with the
AoI-Energy degree cap (DCN review R2, comment 3).

Same matched-budget harness as e_baselines.py (all-or-nothing firing from a
single source battery B with Poisson harvest eta, cost 1 per copy, K_MAX
candidate routes with independent ensemble phases), but the routes are now
HETEROGENEOUS in reliability: route i succeeds with probability Q[i]
(i.i.d. per period), so timing diversity (which routes arrive first this
period) and failure diversity (which routes are reliable) no longer
coincide.  Schemes implemented with their published decision rules:

  ecgr      E-CGR (Marchese & Patrone, TGCN 2020): CGR computes the
            candidate routes in earliest-arrival order; each route is then
            VALIDATED against the energy state -- the transmission must leave
            the battery at or above a reserve RES -- and the first route that
            passes carries ONE copy; if no route passes the bundle is held
            (deferred) until a later contact.  Under paced generation a held
            update is superseded by the next one, so deferral = skip; the
            reserve is the parameter that distinguishes E-CGR from a bare
            energy gate.  (In our single-bottleneck model all routes draw the
            same source battery, so validation never reorders routes.)
  rucop     RUCoP-style delivery-max replication: the holder-set MDP core of
            montecarlo/rucop.py selects the copy budget K_MAX (energy-blind)
            and, on a diamond, the budget's most reliable routes.
  rucop+cap RUCoP's route set (most reliable routes) under OUR degree cap
            k*(eta): the composition proposed in Sec. policy.
  ours      the two-candidate degree k*(eta) on the k* EARLIEST routes
            (the policy exactly as realized by the CGR-native k-copy router).
  ours_joint k*(eta) with the route SET chosen PER BUNDLE by the
            success-conditioned residual eq:rminsucc evaluated on the
            bundle's plan-determined residuals r_i and the route-success
            estimates q_i, over all subsets of size k* (the phase-aware
            placement procedure).  A planning-time FIXED set cannot do
            better than the reliability ranking under ensemble phases (it
            coincides with RUCoP's set here), which is why the per-bundle
            form is the one evaluated.

Run (on the VM):  python3 experiments/e_cgr_family.py       (~1 min, 24 cores)
Outputs: results/cgr_family.csv
"""
from __future__ import annotations

import csv
import itertools
import math
import os
import random
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from montecarlo.battery import poisson          # noqa: E402
from montecarlo.residual import residual        # noqa: E402
from montecarlo.stats import summarize          # noqa: E402
from montecarlo import rucop as RU              # noqa: E402
from experiments.e_policy import k_policy       # noqa: E402

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

P, W, T_S = 1.0, 0.15, 0.01
B, K_MAX = 12, 4
Q = [0.90, 0.75, 0.60, 0.45]              # per-route success, heterogeneous
ETAS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0]
N_PERIODS, WARMUP, SEEDS = 60_000, 2_000, list(range(1, 11))
RES_ECGR = [0, 1]                         # E-CGR battery reserve (copies)


# ---------------------------------------------------------------- planning
def surv(r):
    G = P - W
    return (G - r) / P if 0 <= r <= G else (1.0 if r < 0 else 0.0)


def rmin_succ(S):
    """E[R^succ_min,S] of eq:rminsucc for independent routes with ensemble
    phases: (1/s_S) int [prod_i (1-q_i + q_i Pr(R>r)) - prod_i (1-q_i)] dr."""
    fail = math.prod(1 - Q[i] for i in S)
    s = 1 - fail
    G = P - W
    n = 4000
    acc = 0.0
    for j in range(n):
        r = (j + 0.5) * G / n
        acc += math.prod(1 - Q[i] + Q[i] * surv(r) for i in S) - fail
    return acc * (G / n) / s, s


def best_set(k, eta):
    """Exhaustive eq:jointopt at fixed |S| = k with ensemble (planning-time)
    residual laws: reduces to the reliability ranking, kept for reference."""
    pe = min(1.0, eta / k)
    best = None
    for S in itertools.combinations(range(K_MAX), k):
        er, s = rmin_succ(S)
        obj = P / (pe * s) + er
        if best is None or obj < best[0]:
            best = (obj, S)
    return best[1]


SUBSETS = {k: list(itertools.combinations(range(K_MAX), k)) for k in range(1, K_MAX + 1)}


def joint_subset(rs, k, pe):
    """Per-bundle phase-aware placement: given this bundle's residuals r_i on
    the K_MAX candidate routes and the success estimates q_i, pick the
    size-k subset minimizing P/(pe s_S) + E[R^succ_min,S | r], where
    E[R^succ|r] = (1/s_S) sum_i r_i q_i prod_{j in S: r_j < r_i} (1-q_j)."""
    best = None
    for S in SUBSETS[k]:
        fail = 1.0
        for i in S:
            fail *= 1 - Q[i]
        s = 1 - fail
        order = sorted(S, key=lambda i: rs[i])
        er, alive = 0.0, 1.0
        for i in order:
            er += rs[i] * Q[i] * alive
            alive *= 1 - Q[i]
        obj = P / (pe * s) + er / s
        if best is None or obj < best[0]:
            best = (obj, S)
    return best[1]


def rucop_set(k):
    """Route set the RUCoP core commits to for budget k on the diamond:
    the DP's delivery-optimal set = the k most reliable routes (verified
    against the MDP value)."""
    contacts = [(0, 1, q) for q in Q]
    v = RU.delivery_prob(contacts, 0, 1, k)
    S = tuple(sorted(range(K_MAX), key=lambda i: -Q[i])[:k])
    cf = 1 - math.prod(1 - Q[i] for i in S)
    assert abs(v - cf) < 1e-9, (v, cf)
    return S


# -------------------------------------------------------------- simulation
def simulate(scheme, k, eta, seed, reserve=0, fixed_set=None):
    rng = random.Random(seed)
    b = 0
    last_n = None
    peak_sum, peak_cnt = 0.0, 0
    for n in range(N_PERIODS):
        if scheme == "ecgr":
            fired = b - 1 >= reserve            # route validation: reserve kept
            kc = 1
        else:
            fired = b >= k
            kc = k
        if fired:
            b -= kc
        b = min(B, b + poisson(rng, eta))
        if not fired:
            continue
        phs = [rng.uniform(0.0, P) for _ in range(K_MAX)]
        rs = [residual(u, P, W) for u in phs]
        if fixed_set is None:                   # CGR order: earliest arrivals
            routes = sorted(range(K_MAX), key=lambda i: rs[i])[:kc]
        elif fixed_set == "joint":              # per-bundle phase-aware set
            routes = list(joint_subset(rs, kc, min(1.0, eta / kc)))
        else:
            routes = list(fixed_set)
        up = [rs[i] for i in routes if rng.random() < Q[i]]
        if up:
            if last_n is not None and n >= WARMUP:
                peak_sum += (n - last_n) * P + min(up) + T_S
                peak_cnt += 1
            last_n = n
    return peak_sum / peak_cnt if peak_cnt else float("nan")


def _job(a):
    name, scheme, k, eta, seed, reserve, fs = a
    return name, eta, simulate(scheme, k, eta, 21_000 + 31 * seed + 5 * k, reserve, fs)


def main():
    os.makedirs(RESULTS, exist_ok=True)
    delta = W / P
    jobs, meta = [], {}
    for eta in ETAS:
        ks = k_policy(eta, delta, P, K_MAX)
        meta[eta] = dict(k_star=ks, rucop_set=rucop_set(ks), joint_set=best_set(ks, eta))
        for s in SEEDS:
            for res in RES_ECGR:
                jobs.append((f"ecgr_res{res}", "ecgr", 1, eta, s, res, None))
            jobs.append(("rucop", "rep", K_MAX, eta, s, 0, rucop_set(K_MAX)))
            jobs.append(("rucop_cap", "rep", ks, eta, s, 0, meta[eta]["rucop_set"]))
            jobs.append(("ours", "rep", ks, eta, s, 0, None))
            jobs.append(("ours_joint", "rep", ks, eta, s, 0, "joint"))
    with Pool() as pool:
        out = pool.map(_job, jobs)
    cells = {}
    for name, eta, v in out:
        cells.setdefault((eta, name), []).append(v)
    names = ["ecgr_res0", "ecgr_res1", "rucop", "rucop_cap", "ours", "ours_joint"]
    print(f"K_max={K_MAX}, Q={Q}, B={B}; mean PAoI^per (P units) ± 95% CI, 10 seeds")
    print(f"{'eta':>4} k* | " + " | ".join(f"{n:>13}" for n in names) + " | rucop set / fixed joint set")
    rows = []
    for eta in ETAS:
        ests = {n: summarize(cells[(eta, n)]) for n in names}
        m = meta[eta]
        print(f"{eta:>4.1f} {m['k_star']:>2} | " +
              " | ".join(f"{ests[n].mean:6.3f}±{ests[n].ci95:5.3f}" for n in names) +
              f" | {m['rucop_set']} / {m['joint_set']}")
        row = dict(eta=eta, k_star=m["k_star"],
                   rucop_set="".join(str(i) for i in m["rucop_set"]),
                   joint_set="".join(str(i) for i in m["joint_set"]))
        for n in names:
            row[f"{n}_mean"] = round(ests[n].mean, 5)
            row[f"{n}_ci"] = round(ests[n].ci95, 5)
        rows.append(row)
    with open(os.path.join(RESULTS, "cgr_family.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"-> wrote {os.path.join(RESULTS, 'cgr_family.csv')}")


if __name__ == "__main__":
    main()
