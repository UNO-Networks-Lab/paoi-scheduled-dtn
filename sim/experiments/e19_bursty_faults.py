#!/usr/bin/env python3
"""E19: replication under CORRELATED (bursty) route faults (DCN review R1).

The uncertainty-aware objective (Prop. 1, eq:objq) assumes i.i.d. per-copy
route success q across copies and periods.  Here each route's availability
is a 2-state Markov chain with the SAME stationary up-probability q but a
tunable persistence rho (lag-1 autocorrelation of the up/down indicator):

    P(up -> up)     = q + (1-q) rho,      P(down -> down) = (1-q) + q rho,
    mean down-dwell = 1/(q (1-rho)) periods  (rho = 0 recovers i.i.d.).

Everything else is the matched-budget harness of e_baselines.py: all-or-
nothing firing (battery B, Poisson harvest eta, cost 1/copy), K_max plan
routes with independent (ensemble) phases, CGR commits the k copies to the
k earliest-arriving routes, each copy delivers iff its route is UP in that
period.  Questions answered:
  1. does the freshness-optimal degree leave the two-candidate set
     {floor(eta), ceil(eta)} as faults become bursty?
  2. how does the replication hedge (k=1 vs k=k*) move with persistence?
  3. how far does the i.i.d. prediction eq:objq drift from the bursty truth?

Run (on the VM):
    python3 experiments/e19_bursty_faults.py          # ~2 min, 24 cores
Outputs: results/e19_bursty_faults.csv
"""
from __future__ import annotations

import csv
import math
import os
import random
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from montecarlo.battery import poisson          # noqa: E402
from montecarlo.residual import residual        # noqa: E402
from montecarlo.stats import summarize          # noqa: E402

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

P, W, T_S = 1.0, 0.15, 0.01
B, K_MAX = 12, 3
Q = 2.0 / 3.0
RHOS = [0.0, 0.5, 0.9, 0.98]            # down-dwell 1.5, 3, 15, 75 periods
ETAS = [2.0, 3.0, 6.0]
KS = [1, 2, 3]
N_PERIODS, WARMUP, SEEDS = 60_000, 2_000, list(range(1, 11))


def order_stat_means(K: int, delta: float, n: int = 4000) -> list:
    """E[R_(i)], i=1..K, for the i-th smallest of K i.i.d. mixed residuals
    (atom delta at 0, uniform slab; survival (G-r)/P on [0,G])."""
    G = P * (1 - delta)
    out = []
    for i in range(1, K + 1):
        acc = 0.0
        for j in range(n):
            r = (j + 0.5) * G / n
            S = (G - r) / P
            acc += sum(math.comb(K, m) * (1 - S) ** m * S ** (K - m) for m in range(i))
        out.append(acc * G / n)
    return out


def paoi_iid_pred(eta: float, q: float, k: int, delta: float) -> float:
    """E[PAoI^per] under i.i.d. (memoryless) route success for CGR-ORDER
    placement: the k copies ride the k earliest of the K_MAX candidate
    routes, so the delivered residual is R_(m) with m the smallest index
    among the survivors; eq:objq's cadence term is unchanged."""
    pe = min(1.0, eta / k)
    s = 1 - (1 - q) ** k
    ros = order_stat_means(K_MAX, delta)
    h = sum(ros[i - 1] * q * (1 - q) ** (i - 1) for i in range(1, k + 1)) / s
    return P / (pe * s) + h + T_S


def simulate(k: int, eta: float, rho: float, seed: int):
    rng = random.Random(seed)
    up = [rng.random() < Q for _ in range(K_MAX)]
    p_uu = Q + (1 - Q) * rho
    p_dd = (1 - Q) + Q * rho
    b = 0
    last_n = None
    peak_sum, peak_cnt = 0.0, 0
    for n in range(N_PERIODS):
        # route availability evolves once per period
        for i in range(K_MAX):
            r = rng.random()
            up[i] = (r < p_uu) if up[i] else (r >= p_dd)
        fired = b >= k
        if fired:
            b -= k
        b = min(B, b + poisson(rng, eta))
        if not fired:
            continue
        phs = [rng.uniform(0.0, P) for _ in range(K_MAX)]
        order = sorted(range(K_MAX), key=lambda i: residual(phs[i], P, W))[:k]
        rs_up = [residual(phs[i], P, W) for i in order if up[i]]
        if rs_up:
            if last_n is not None and n >= WARMUP:
                peak_sum += (n - last_n) * P + min(rs_up) + T_S
                peak_cnt += 1
            last_n = n
    return peak_sum / peak_cnt if peak_cnt else float("nan")


def _job(args):
    k, eta, rho, seed = args
    return (k, eta, rho, seed, simulate(k, eta, rho, 19000 + 101 * seed + 7 * k))


def main():
    os.makedirs(RESULTS, exist_ok=True)
    delta = W / P
    jobs = [(k, eta, rho, s) for rho in RHOS for eta in ETAS for k in KS for s in SEEDS]
    with Pool() as pool:
        out = pool.map(_job, jobs)
    cells = {}
    for k, eta, rho, s, v in out:
        cells.setdefault((rho, eta, k), []).append(v)
    rows = []
    print(f"q={Q:.3f}, K_max={K_MAX}, B={B}; mean PAoI^per (units of P), 95% CI")
    print(f"{'rho':>5} {'dwell':>6} {'eta':>4} | " + " | ".join(f"k={k:<12}" for k in KS)
          + " | argmin  cand  pred(iid) argmin")
    ok_all = True
    for rho in RHOS:
        dwell = 1.0 / (Q * (1 - rho)) if rho < 1 else float("inf")
        for eta in ETAS:
            ests = {k: summarize(cells[(rho, eta, k)]) for k in KS}
            preds = {k: paoi_iid_pred(eta, Q, k, delta) for k in KS}
            kopt = min(KS, key=lambda k: ests[k].mean)
            kpred = min(KS, key=lambda k: preds[k])
            cand = {max(1, min(K_MAX, int(math.floor(eta)))),
                    max(1, min(K_MAX, int(math.ceil(eta))))}
            in_cand = kopt in cand
            # an argmin not separated from a candidate by the CIs is a tie,
            # not a displaced optimum: report it as such
            tie = (not in_cand) and any(
                abs(ests[kopt].mean - ests[c].mean) <= ests[kopt].ci95 + ests[c].ci95
                for c in cand)
            ok_all = ok_all and (in_cand or tie)
            gain = ests[1].mean / ests[kopt].mean
            line = " | ".join(f"{ests[k].mean:6.3f}±{ests[k].ci95:5.3f}" for k in KS)
            print(f"{rho:>5.2f} {dwell:>6.1f} {eta:>4.1f} | {line} |   {kopt}    "
                  f"{sorted(cand)}  {kpred}  "
                  f"{'ok' if in_cand else ('tie' if tie else 'OUT')}")
            row = dict(rho=rho, down_dwell=round(dwell, 2), eta=eta, k_opt=kopt,
                       k_opt_iid_pred=kpred, in_candidate_set=in_cand,
                       tie_with_candidate=tie,
                       gain_k1_over_kopt=round(gain, 4))
            for k in KS:
                row[f"paoi_k{k}"] = round(ests[k].mean, 5)
                row[f"ci_k{k}"] = round(ests[k].ci95, 5)
                row[f"pred_iid_k{k}"] = round(preds[k], 5)
                row[f"drift_pct_k{k}"] = round(100 * (ests[k].mean - preds[k]) / preds[k], 2)
            rows.append(row)
    with open(os.path.join(RESULTS, "e19_bursty_faults.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\noptimum in (or tied with) the two-candidate set at every (rho, eta): {ok_all}")
    print(f"-> wrote {os.path.join(RESULTS, 'e19_bursty_faults.csv')}")
    print("PASS" if ok_all else "CHECK")


if __name__ == "__main__":
    main()
