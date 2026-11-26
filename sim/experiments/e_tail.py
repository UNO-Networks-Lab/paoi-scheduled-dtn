#!/usr/bin/env python3
"""PAoI tail / deadline-violation evaluation (mission-critical metric).

For mission-critical traffic the relevant quantity is not mean PAoI but
the tail: P(PAoI > deadline). Replication shrinks the delivered residual
via the order statistic, so it should pull the PAoI tail in. At a fixed
(energy-abundant) eta we collect per-cycle PAoI peaks for k=1..K_max,
form the empirical CCDF P(PAoI > x), and report deadline-violation
probabilities and tail quantiles.

Seed-level statistics (DCN review R1): the CCDF, the tail-reduction ratio
CCDF_1/CCDF_k, and the 99th percentile are computed PER SEED and reported
as the across-seed mean with a 95% CI (20 seeds by default), so the
quantile estimates carry an honest uncertainty.

Run (on the VM):
    python3 experiments/e_tail.py
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from montecarlo import system as S                 # noqa: E402
from montecarlo.stats import summarize             # noqa: E402

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")


def quantile(sorted_vals, q):
    if not sorted_vals:
        return float("nan")
    i = min(len(sorted_vals) - 1, int(q * len(sorted_vals)))
    return sorted_vals[i]


def _job(a):
    k, s, args = a
    pk = S.r3_peaks(args.P, args.W, args.Ts, k, args.eta, args.B, args.Kmax,
                    args.periods, seed=7700 + s, warmup_periods=args.warmup)
    return k, s, sorted(pk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--P", type=float, default=1.0)
    ap.add_argument("--W", type=float, default=0.10)
    ap.add_argument("--Ts", type=float, default=0.005)
    ap.add_argument("--eta", type=float, default=6.0, help="energy-abundant")
    ap.add_argument("--B", type=int, default=64)
    ap.add_argument("--Kmax", type=int, default=4)
    ap.add_argument("--ks", type=int, nargs="*", default=[1, 2, 4])
    ap.add_argument("--periods", type=int, default=120000)
    ap.add_argument("--warmup", type=int, default=1000)
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    if args.quick:
        args.periods, args.seeds = 20000, 3
    os.makedirs(RESULTS, exist_ok=True)

    # grid of deadlines (normalized to P); peaks ~ P + R_min + T_s in [P, P+G]
    grid = [args.P * (1.0 + i / 20.0) for i in range(0, 21)]   # 1.00 .. 2.00 P
    with Pool() as pool:
        out = pool.map(_job, [(k, s, args) for k in args.ks for s in range(args.seeds)])
    per_seed = {}                       # k -> list of sorted peak lists
    for k, s, pk in out:
        per_seed.setdefault(k, []).append(pk)

    def ccdf(pk, x):
        return sum(1 for v in pk if v > x) / len(pk)

    rows = []
    k1 = args.ks[0]
    for x in grid:
        row = {"deadline": round(x, 4)}
        for k in args.ks:
            est = summarize([ccdf(pk, x) for pk in per_seed[k]])
            row[f"ccdf_k{k}"] = round(est.mean, 5)
            row[f"ccdf_k{k}_ci"] = round(est.ci95, 5)
        for k in args.ks[1:]:
            ratios = [ccdf(a, x) / ccdf(b, x) if ccdf(b, x) > 0 else float("nan")
                      for a, b in zip(per_seed[k1], per_seed[k])]
            ratios = [r for r in ratios if r == r]
            if ratios:
                est = summarize(ratios)
                row[f"ratio_k{k1}_over_k{k}"] = round(est.mean, 3)
                row[f"ratio_k{k1}_over_k{k}_ci"] = round(est.ci95, 3)
            else:
                row[f"ratio_k{k1}_over_k{k}"] = ""
                row[f"ratio_k{k1}_over_k{k}_ci"] = ""
        rows.append(row)
    with open(os.path.join(RESULTS, "paoi_ccdf.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    n_pk = sum(len(pk) for pk in per_seed[k1])
    print(f"PAoI tail at eta={args.eta} (normalized to P); {args.seeds} seeds, "
          f"n_peaks/k ~ {n_pk}")
    print("k   mean (±CI)        p90 (±CI)         p99 (±CI)         P(PAoI>1.5P) (±CI)")
    qrows = []
    for k in args.ks:
        mean = summarize([sum(pk) / len(pk) for pk in per_seed[k]])
        p90 = summarize([quantile(pk, 0.90) for pk in per_seed[k]])
        p99 = summarize([quantile(pk, 0.99) for pk in per_seed[k]])
        viol = summarize([ccdf(pk, 1.5 * args.P) for pk in per_seed[k]])
        print(f"{k}  {mean.mean:.4f}±{mean.ci95:.4f}   {p90.mean:.4f}±{p90.ci95:.4f}   "
              f"{p99.mean:.4f}±{p99.ci95:.4f}   {viol.mean:.4f}±{viol.ci95:.4f}")
        qrows.append(dict(k=k, mean=round(mean.mean, 5), mean_ci=round(mean.ci95, 5),
                          p90=round(p90.mean, 5), p90_ci=round(p90.ci95, 5),
                          p99=round(p99.mean, 5), p99_ci=round(p99.ci95, 5),
                          viol_1p5=round(viol.mean, 5), viol_1p5_ci=round(viol.ci95, 5)))
    with open(os.path.join(RESULTS, "paoi_tail_quantiles.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(qrows[0].keys()))
        w.writeheader(); w.writerows(qrows)
    print("tail-reduction ratio CCDF_k1/CCDF_k across deadlines (mean ± CI):")
    for row in rows:
        if 1.05 <= row["deadline"] <= 1.85 and abs((row["deadline"] * 20) % 2) < 1e-9:
            parts = [f"{k}: {row[f'ratio_k{k1}_over_k{k}']}±{row[f'ratio_k{k1}_over_k{k}_ci']}"
                     for k in args.ks[1:]]
            print(f"  deadline {row['deadline']:.2f}P  " + "   ".join(parts))
    print(f"-> wrote {os.path.join(RESULTS, 'paoi_ccdf.csv')} and paoi_tail_quantiles.csv")


if __name__ == "__main__":
    main()
