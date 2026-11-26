#!/usr/bin/env python3
"""Exact finite-battery optimum from the stationary battery chain.

Deterministic numerical check (no Monte-Carlo): for Poisson harvest with
mean eta copies per period and all-or-nothing firing (fire k copies iff
b >= k), the embedded battery chain

    b_{n+1} = min(B, (b_n - k 1{b_n >= k}) + A_n),   A_n ~ Poisson(eta)

is solved exactly for its stationary law, giving the firing fraction
p_e(k; B) = Pr_pi(b >= k).  The mean per-update peak is then EXACT,

    E[PAoI^per] / P = 1 / p_e(k; B) + g_k / P + T_s / P,
    g_k = P (1 - delta)^{min(k, K_max) + 1} / (min(k, K_max) + 1),

(Palm inversion gives E[J] = 1/p_e for any stationary firing sequence, and
the delivered residual is independent of the battery), so the exact
finite-battery optimum k_B(eta) = argmin_k follows without simulation.

Reported:
  1. cross-check against the simulated E11 points (results/e11_finite_battery.csv);
  2. B_dagger(eta): the smallest battery from which the large-battery
     two-candidate rule k_pol(eta) equals the exact optimum for every
     larger B scanned -- the rule's finite-battery validity boundary;
  3. the "chain rule": argmin over k <= ceil(eta) of the chain-evaluated
     objective, which is the exact optimum whenever that optimum does not
     exceed ceil(eta) (checked on the whole grid).

Run:  python3 experiments/check_finiteB_chain.py        (about a minute)
Outputs: results/finiteB_chain.csv
"""
from __future__ import annotations

import csv
import math
import os

RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

P, T_S = 1.0, 0.005
B_MAX = 96


def stationary(B: int, k: int, eta: float) -> list:
    """Stationary law of the pre-fire battery level on {0..B} (exact solve)."""
    S = B + 1
    pmf = [math.exp(-eta)]
    for a in range(1, S + 1):
        pmf.append(pmf[-1] * eta / a)
    # T[i][j] = Pr(i -> j)
    T = [[0.0] * S for _ in range(S)]
    for i in range(S):
        base = i - k if i >= k else i
        acc = 0.0
        for a in range(0, B - base):
            T[i][base + a] = pmf[a]
            acc += pmf[a]
        T[i][B] += 1.0 - acc
    # solve pi (T - I) = 0 with sum(pi) = 1: rows of M are the balance equations
    M = [[T[i][j] - (1.0 if i == j else 0.0) for i in range(S)] for j in range(S)]
    M[S - 1] = [1.0] * S
    rhs = [0.0] * S
    rhs[S - 1] = 1.0
    for c in range(S):
        piv = max(range(c, S), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        rhs[c], rhs[piv] = rhs[piv], rhs[c]
        pc = M[c][c]
        Mc = M[c]
        for r in range(c + 1, S):
            f = M[r][c] / pc
            if f:
                Mr = M[r]
                for j in range(c, S):
                    Mr[j] -= f * Mc[j]
                rhs[r] -= f * rhs[c]
    pi = [0.0] * S
    for r in range(S - 1, -1, -1):
        s = rhs[r] - sum(M[r][j] * pi[j] for j in range(r + 1, S))
        pi[r] = s / M[r][r]
    return pi


def p_e(B: int, k: int, eta: float) -> float:
    if k > B:
        return 0.0
    return sum(stationary(B, k, eta)[k:])


def gain(k: int, delta: float, k_max: int) -> float:
    kc = min(k, k_max)
    return P * (1 - delta) ** (kc + 1) / (kc + 1)


def objective(B, k, eta, delta, k_max):
    pe = p_e(B, k, eta)
    return float("inf") if pe <= 0 else P / pe + gain(k, delta, k_max) + T_S


def k_opt_chain(B, eta, delta, k_max, k_hi=None):
    ks = range(1, (k_hi or k_max + 1) + 1)
    return min(ks, key=lambda k: objective(B, k, eta, delta, k_max))


def k_policy(eta, delta, k_max):
    """Large-battery two-candidate rule (fluid p_e = min(1, eta/k))."""
    def A(k):
        pe = min(1.0, eta / k)
        return P * (1 - pe) / pe + gain(k, delta, k_max)
    lo = min(k_max, max(1, int(math.floor(eta))))
    hi = min(k_max, max(1, int(math.ceil(eta))))
    return min({lo, hi}, key=A)


def main():
    os.makedirs(RESULTS, exist_ok=True)
    delta, k_max = 0.10, 8

    # ---- 1. cross-check against the simulated E11 points -------------------
    e11 = os.path.join(RESULTS, "e11_finite_battery.csv")
    ok_e11 = True
    if os.path.exists(e11):
        print("== cross-check vs simulated E11 (k*, and p_e at k = floor(eta)) ==")
        for r in csv.DictReader(open(e11)):
            eta, B = float(r["eta"]), int(float(r["B"]))
            kc = k_opt_chain(B, eta, delta, k_max)
            pe = p_e(B, int(eta), eta)
            match = kc == int(float(r["k_star"]))
            ok_e11 &= match
            print(f"  eta={eta:.0f} B={B:3d}: chain k*={kc} (sim {int(float(r['k_star']))})  "
                  f"chain p_e={pe:.4f} (sim {float(r['p_e']):.4f})  {'OK' if match else 'MISMATCH'}")

    # ---- 2. validity boundary of the two-candidate rule --------------------
    rows = []
    ok_ceil = True
    print("\n== finite-battery validity boundary of the two-candidate rule "
          f"(delta={delta}, K_max={k_max}, B <= {B_MAX}) ==")
    print(f"{'eta':>5} {'k_pol':>5} {'B_dagger':>8} {'B_dagger/eta':>12}   exact optimum at B = ceil(eta), 2eta, 4eta")
    # integer eta, mid-interval eta, and ceiling-branch eta just below an integer
    # (where the rule takes ceil(eta) and its large-battery margin is smallest)
    for eta in (2.0, 2.5, 2.9, 3.0, 3.5, 3.9, 4.0, 4.5, 4.9, 5.0, 5.9, 6.0, 6.5, 8.0):
        kp = k_policy(eta, delta, k_max)
        b_lo = int(math.ceil(eta))
        opt = {}
        for B in range(b_lo, B_MAX + 1):
            opt[B] = k_opt_chain(B, eta, delta, k_max)
            # the exact optimum never exceeds ceil(eta): the chain rule is exact
            ok_ceil &= opt[B] <= min(k_max, int(math.ceil(eta)))
        bad = [B for B in opt if opt[B] != kp]
        b_dag = (max(bad) + 1) if bad else b_lo
        probes = [opt[b_lo], opt.get(int(2 * eta)), opt.get(int(4 * eta))]
        print(f"{eta:>5.1f} {kp:>5} {b_dag:>8} {b_dag/eta:>12.1f}   {probes}")
        rows.append(dict(eta=eta, k_policy=kp, B_dagger=b_dag,
                         B_dagger_over_eta=round(b_dag / eta, 2),
                         k_opt_at_ceil_eta=probes[0], k_opt_at_2eta=probes[1],
                         k_opt_at_4eta=probes[2]))
    with open(os.path.join(RESULTS, "finiteB_chain.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\nexact optimum never above ceil(eta) on the grid: {ok_ceil}")
    print(f"chain reproduces every simulated E11 optimum: {ok_e11}")
    print(f"-> wrote {os.path.join(RESULTS, 'finiteB_chain.csv')}")
    print("PASS" if ok_ceil and ok_e11 else "CHECK")


if __name__ == "__main__":
    main()
