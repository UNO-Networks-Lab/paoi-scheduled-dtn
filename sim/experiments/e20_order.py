#!/usr/bin/env python3
"""E20: how often do deliveries OVERTAKE on a multi-segment path?  (DCN review R1)

The per-update identity E[PAoI^per] = E[Z] + E[Y_min] presumes order-
preserving deliveries (System Model); Y_max - Y_min <= Z_min is sufficient.
This experiment measures, on the paper's heterogeneous chain (sensor ->
UAV mule -> LEO -> gateway, the parameters of tier2/make_hetero_scenario.py),

  * the fraction of deliveries that arrive STALE (a newer update was
    delivered earlier), i.e. the order-inversion probability per update;
  * the mean per-update peak evaluated on the freshness-resetting
    subsequence (the honest PAoI^per) against the naive E[Z] + E[Y];

for single-copy transport at two generation spacings: the Tier-2 cadence
(GEN = 400 s, many updates per LEO pass) and one update per LEO period
(GEN = P_LEO, the paced model of Result 3).  The single-LEO-segment case is
included as the control (deterministic gating is monotone in the arrival
phase, so a single segment never reorders).

Model-exact Monte-Carlo (stdlib): per segment an update generated/arriving
at time t waits until the next window opening (0 if inside a window), then
pays a lumped service T_s; windows within a segment serve in FIFO order.

Run:  python3 experiments/e20_order.py            (seconds)
Outputs: results/e20_order.csv
"""
from __future__ import annotations

import bisect
import csv
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from montecarlo.stats import summarize          # noqa: E402

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

# tier2/make_hetero_scenario.py parameters
G1, W1, CV1 = 3000.0, 300.0, 1.3          # terrestrial: gamma gaps
P2, W2, J2 = 1800.0, 180.0, 240.0         # UAV: periodic + Gaussian jitter
P3, W3 = 5736.0, 430.0                    # LEO: deterministic periodic
T_S = 10.0
HORIZON = 400 * P3                        # ~ 2.3e6 s per seed
SEEDS = list(range(1, 11))


def gamma_gap(rng, mean, cv):
    k = 1.0 / (cv * cv)
    return rng.gammavariate(k, mean * cv * cv)


def seg_terrestrial(rng):
    wins, t = [], 0.0
    while t < HORIZON:
        wins.append((t, t + W1))
        t += W1 + gamma_gap(rng, G1, CV1)
    return wins


def seg_uav(rng):
    wins, last_end, n = [], 0.0, 0
    while n * P2 < HORIZON:
        s = max(last_end, n * P2 + rng.gauss(0, J2))
        wins.append((s, s + W2)); last_end = s + W2
        n += 1
    return wins


def seg_leo(offset=0.0):
    return [(offset + n * P3, offset + n * P3 + W3) for n in range(int(HORIZON / P3) + 2)]


class Segment:
    """Gated FIFO server: an arrival at t departs at max(t, next window open)
    + T_s, never before the previous departure (FIFO within a window)."""

    def __init__(self, wins):
        self.starts = [s for s, _ in wins]
        self.ends = [e for _, e in wins]
        self.last_dep = -1.0

    def depart(self, t):
        i = bisect.bisect_right(self.ends, t)       # first window ending after t
        if i >= len(self.starts):
            return float("inf")
        open_t = max(t, self.starts[i])
        d = max(open_t, self.last_dep) + T_S
        self.last_dep = d
        return d


def run(chain: str, gen: float, seed: int):
    rng = random.Random(seed)
    if chain == "leo":
        segs = [Segment(seg_leo(rng.uniform(0, P3)))]
    else:
        segs = [Segment(seg_terrestrial(rng)), Segment(seg_uav(rng)),
                Segment(seg_leo(rng.uniform(0, P3)))]
    g = rng.uniform(0, gen)
    gens, deliv = [], []
    while g < HORIZON - 20 * P3:
        t = g
        for s in segs:
            t = s.depart(t)
        if t == float("inf"):
            break
        gens.append(g); deliv.append(t)
        g += gen
    n = len(gens)
    # stale = some LATER-generated update was delivered earlier
    order = sorted(range(n), key=lambda i: deliv[i])
    newest = -1.0
    stale = 0
    resets = []                       # (delivery time, generation time)
    for i in order:
        if gens[i] <= newest:
            stale += 1
        else:
            newest = gens[i]
            resets.append((deliv[i], gens[i]))
    # per-update peak on the resetting subsequence: age just before reset j
    # = deliv_j - gen_{j-1}
    peaks = [resets[j][0] - resets[j - 1][1] for j in range(1, len(resets))]
    ys = [deliv[i] - gens[i] for i in range(n)]
    naive = gen + sum(ys) / n
    honest = sum(peaks) / len(peaks)
    spread = max(ys) - min(ys)
    return dict(n=n, stale_frac=stale / n, naive=naive, honest=honest,
                spread=spread, mean_y=sum(ys) / n)


def main():
    os.makedirs(RESULTS, exist_ok=True)
    rows = []
    print(f"{'chain':>6} {'GEN[s]':>7} | {'P(stale)':>9} | {'E[Z]+E[Y]':>10} {'PAoI^per(reset)':>16} {'bias%':>6} | Ymax-Ymin / Z")
    for chain, gen in (("leo", 400.0), ("leo", P3), ("hetero", 400.0), ("hetero", P3)):
        res = [run(chain, gen, 20_000 + s) for s in SEEDS]
        st = summarize([r["stale_frac"] for r in res])
        nv = summarize([r["naive"] for r in res])
        ho = summarize([r["honest"] for r in res])
        sp = max(r["spread"] for r in res)
        bias = 100 * (ho.mean - nv.mean) / nv.mean
        print(f"{chain:>6} {gen:>7.0f} | {st.mean:9.4f} | {nv.mean:10.0f} {ho.mean:16.0f} {bias:6.2f} | {sp/gen:6.2f}")
        rows.append(dict(chain=chain, gen_s=gen, stale_frac=round(st.mean, 5),
                         stale_ci=round(st.ci95, 5), naive_paoi=round(nv.mean, 1),
                         reset_paoi=round(ho.mean, 1), reset_ci=round(ho.ci95, 1),
                         bias_pct=round(bias, 3), max_spread_over_Z=round(sp / gen, 3),
                         mean_y=round(sum(r["mean_y"] for r in res) / len(res), 1)))
    with open(os.path.join(RESULTS, "e20_order.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"-> wrote {os.path.join(RESULTS, 'e20_order.csv')}")


if __name__ == "__main__":
    main()
