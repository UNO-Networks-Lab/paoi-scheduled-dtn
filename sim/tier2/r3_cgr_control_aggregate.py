#!/usr/bin/env python3
"""Summarize the controlled two-relay comparison (run_r3_cgr_control.sh).

Reads results/r3_cgr_control_raw.csv (one row per cap, eta_g, strategy,
seed) and writes results/r3_cgr_control.csv with, per battery capacity and
energy level: mean OPAoI of one copy (kc1) and two copies (kc2) in units of
the relay period P, their 95% Student-t CIs over seeds, and the paired
per-seed difference kc2 - kc1 with its 95% CI (positive = two copies staler).
The `recv` column of the raw file counts received copies, so for two copies
it includes duplicates; it is not a delivered-update count.

    python3 r3_cgr_control_aggregate.py
"""
import csv
import math
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "results", "r3_cgr_control_raw.csv")
OUT = os.path.join(HERE, "results", "r3_cgr_control.csv")
P = 5736.0
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
        7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 14: 2.145, 19: 2.093}


def mean_ci(xs):
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, float("nan")
    t = T975.get(n - 1, 1.96)
    return m, t * st.stdev(xs) / math.sqrt(n)


def main():
    cells = {}
    for r in csv.DictReader(open(RAW)):
        key = (int(r["cap"]), float(r["eta_g"]))
        cells.setdefault(key, {}).setdefault(r["strategy"], {})[int(r["seed"])] = float(r["paoi"]) / P
    rows = []
    for (cap, eta), d in sorted(cells.items()):
        seeds = sorted(set(d["kc1"]) & set(d["kc2"]))
        a = [d["kc1"][s] for s in seeds]
        b = [d["kc2"][s] for s in seeds]
        m1, c1 = mean_ci(a)
        m2, c2 = mean_ci(b)
        md, cd = mean_ci([y - x for x, y in zip(a, b)])
        rows.append(dict(cap=cap, eta_g=eta, seeds=len(seeds),
                         kc1_opaoi_P=round(m1, 3), kc1_ci=round(c1, 3),
                         kc2_opaoi_P=round(m2, 3), kc2_ci=round(c2, 3),
                         ratio_kc1_over_kc2=round(m1 / m2, 2),
                         paired_diff_kc2_minus_kc1_P=round(md, 3),
                         paired_diff_ci=round(cd, 3),
                         significant=abs(md) > cd))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{'cap':>3} {'eta_g':>5} | {'1 copy (P)':>12} {'2 copies (P)':>13} | paired 2-1 (P)")
    for r in rows:
        print(f"{r['cap']:>3} {r['eta_g']:5.2f} | {r['kc1_opaoi_P']:6.2f}±{r['kc1_ci']:4.2f}"
              f"  {r['kc2_opaoi_P']:6.2f}±{r['kc2_ci']:4.2f}  | "
              f"{r['paired_diff_kc2_minus_kc1_P']:+6.3f}±{r['paired_diff_ci']:.3f}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
