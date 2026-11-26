# Validation matrix (final, as used in the manuscript)

Two-tier plan closed by a reference-implementation cross-check. Every
analytical claim maps to a model-exact Tier-1 experiment; representative
results are corroborated in the DTN-realistic Tier-2 stack (dtnsim:
Bundle Protocol + Contact Graph Routing); the residual-wait anchor is
additionally reproduced in ION. The manuscript's Tier-1 traceability
table mirrors this file.

| Claim (manuscript) | Experiment | Entry point | Pass criterion (coded in the script) | Result |
|---|---|---|---|---|
| Residual law, Thm 1 (KS + mean/peak exponents) | E1–E2 | `experiments/e1_residual.py` | CI covers the closed-form mean and second moment; KS < 0.02; atom within 0.01 of δ; AoI/OPAoI within 6%; fitted slopes within 0.1 of 2 and 1 | KS ≈ 0.002; slopes 1.98/1.00 |
| Phase mixing + failure mode | E3–E6 | `experiments/e3_e6_replication.py` | mixing: KS-to-uniform < 0.03 and |corr| < 0.05; Gini identity within 2×CI; ratio and E[R_min] within 3%; same-bottleneck gain < 10⁻⁹; stagger worst case within 2% of P | KS-to-uniform 0.001 (2×10⁵ phases per seed); locked KS 0.89; Gini gain; ⅔(1−δ) |
| Threshold k\*, unimodality + staircase | E7–E8 | `experiments/e7_e8_threshold.py` | objective unimodal; argmin within ±1 of the closed form; saturation within ±1 of K_max | argmin brackets η; saturates at K_max |
| Work conservation, P–K law | E9–E10 | `experiments/e9_battery.py` | work-conservation residual < 10⁻²; k=1 limit: p_e and P(b=0) within 3% | residual ≤1.2e−4; distribution-free |
| Finite battery downward pressure | E11 | `experiments/e11_finiteB.py` | k\* non-increasing as B shrinks (k\* ≤ ⌊η⌋ printed, informational only) | k\*: 4→2 as B: 64→4 (η=4) |
| Exact finite-battery optimum; validity boundary of the two-candidate rule | — | `experiments/check_finiteB_chain.py` (exact chain solve, no Monte Carlo) | chain reproduces every simulated E11 optimum; exact optimum ≤ ⌈η⌉ on the grid | reproduces every E11 point; B†(η)=5, 9, 15, 22, 31, 56 at η=2, 3, 4, 5, 6, 8; 3, 6, 9, 16 at η=2.5, 3.5, 4.5, 6.5; and 11, 20, 35, 61 just below an integer (η=2.9, 3.9, 4.9, 5.9, ceiling branch); exact optimum never above ⌈η⌉; B† depends on δ, K_max, q and the gain profile (E19's configuration ties at B=12) |
| Renewal laws + AoI/OPAoI inversion | E12–E13 | `experiments/e12_e13_renewal.py` | E[R] within 4% and atom within 0.01; observed inversion = predicted sign of eq. (6) | E[R] within 1%; crossing at CV²=1+2E[U]/E[V] |
| Ceiling branch, eq. (18) test | E14 | `experiments/e_ceiling.py` | simulated degree = analytic degree at ≥ n−1 of n energy levels | flip at η★ = 3.824 (9/9) |
| Bursty (Markov-modulated) harvest, dwell 1–100 | E15 | `experiments/e15_correlated.py` | k\* = 3 for dwell ≤ 10; work-conservation residual < 5×10⁻³ | k\*=3 to dwell 10; k\*=2 from dwell 20 by a 1.2% margin (5.5% at dwell 50, 7.5% at 100; means only); work conservation ≤3.1e−4 |
| Uncertainty objective (Prop. 1) | E18 | `experiments/e18_uncertain.py` | |sim − eq. (21)| < 2%; optimum in the candidate set | ≤0.7%; simulated optimum = rule's choice (integer η: ceiling branch not exercised) |
| Bursty (Markov) route faults, dwell 1.5–75 | E19 | `experiments/e19_bursty_faults.py` | optimum in, or tied within CIs with, the candidate set at every (ρ, η) | means move <1.3%; optimum in / tied with candidate set (the η=3 tie is present at ρ=0: finite-B effect); order-statistic i.i.d. prediction ≤0.5% to ρ=0.9, 1.2% at 0.98 (4% at k=η: finite-B p_e) |
| Order preservation on the S3 chain (two cadences) | E20 | `experiments/e20_order.py` | descriptive (no pass/fail) | zero inversions (structural for FIFO segments); E[Z]+E[Y] exact to 0.03% |
| CGR family: E-CGR / RUCoP / RUCoP set + cap / ours / ours + phase-aware placement | — | `experiments/e_cgr_family.py` | descriptive; the RUCoP reduction is asserted exactly (|DP − closed form| < 10⁻⁹) | E-CGR = ours at k\*=1; RUCoP 2.7× worse at η=0.5; per-bundle placement best or tied at every η (on this one-hop instance E-CGR reduces to a reserve-gated single copy, RUCoP to the most reliable routes) |
| PAoI tail / CCDF closed form, per-seed CIs (20 seeds) | — | `experiments/e_tail.py` | descriptive (compared with eq. (29) in the text) | matches eq. (29) pointwise; 15.0±0.1× at 1.5P; p99 1.895 → 1.589 (half-widths ≤0.0012) |
| Prop.-1 increment condition grid | — | `experiments/check_gainboundq.py` | no violation of eq. (23) on the grid; minimum margin > 0 | min margin 0.067P over 840 (δ,q,η) points |
| Two-candidate policy vs exhaustive | — | `experiments/e_policy.py` | rule = exhaustive optimum (count reported) | matched at all 11 energy levels (B=64, K_max=4); optimum beats runner-up by ≥3.3% |
| Prediction-error robustness (per-copy success q) | — | `experiments/e_robust.py` | descriptive | keep ⌊η⌋; reserve heuristic +50% |
| Matched-budget + adaptive baselines + phase sets | — | `experiments/e_baselines.py` | descriptive | set-point dominates where energy binds; partial-firing rules ahead by 1.4% (floor-greedy, η=2) and 2.7%/2.5% (greedy/earliest-K, η=3); q=1 tie is by construction in this harness |
| RUCoP-style MDP core (illustrative) | — | `experiments/e_rucop.py` | DP = 1−(1−q)^k on the symmetric diamond (< 10⁻⁹) | concave frontier; 94.7%/40% instance |
| Tier-2 atomic all-or-nothing threshold | — | `tier2/run_r3_atomic.sh` | `r3_atomic_aggregate.py`: starvation ordering at low η; ties at η ≥ k; argmin non-decreasing in η | starvation penalty in dtnsim CGR (2.7× at η=1); admitted fractions within 0.7%; ties at η≥k fault-free |
| Tier-2 unified (faults + atomic, both metrics) | E16 | `tier2/run_e16_unified.sh` | `e16_aggregate.py`: starvation ordering at η=1; argmin non-decreasing; check (ii) compares means only and is not significant (paired CIs in the text) | starvation side significant (argmin ≤ ⌊η⌋ at every η); degrees ≤ η tie within paired CIs (−44±131 s, −16±98 s) |
| Tier-2 two-relay plan under faults: stock single-copy CGR vs k-copy router, and the controlled rerun (same router, batteries 5 and 32) | — | `tier2/run_r3_cgr.sh`, `tier2/run_r3_cgr_control.sh` | descriptive; paired per-seed CIs from `r3_cgr_control_aggregate.py` | original ratio 5.9–6.5× is NOT a hedging gain: same-router single copy reproduces it seed for seed at battery 5; with battery 32, two copies are staler at η_g=1.5, 2 (starvation) and one copy ties or wins at η_g=3, 6 (0.71P); bent-pipe relays ⇒ q_eff≈1 (the q→1 limit of eq. (30)); figure removed, reported in text |
| Tier-2 contact-capacity boundary (3 seeds) | E17 | `tier2/run_e17_capacity.sh` | descriptive (per-seed ratios) | per-seed loaded/unloaded delay ratios 1.00–1.03 to ρ=0.5 (one seed 1.12), 1.05–1.38 at ρ=1, 117–124 at ρ=2 |
| Real-ephemeris residual law + pair scan | — | `tier2/make_tle_scenario.py`, `tier2/two_tle_rmin.py` | descriptive | 0.06% on the reference satellite; 40 pairs, residual-min ratio 0.41–0.95 by phase, mean 0.61 |
| Heterogeneous chain composition (10 seeds) | — | `tier2/run_hetero_seeds.sh` | descriptive | per-seed ≤5.9%; mean 0.2% |
| ION residual-law cross-check | — | `ion/run_capture.sh`, `ion/summarize.py` | |slope − 1| ≤ 0.05 | per-bundle slope 1.016 (95% CI 1.013–1.019, R²=0.998); the 1.6% excess is a two-population effect (window lag 0.55 s, gap lag 2.50 s = T_s) |

Seed counts are experiment-dependent (8–20 for Tier-1 sweeps; 10 for
Tier-2 E16, two-relay, and heterogeneous; 5 for the atomic sweep; 3 for
E17). Seeds are fixed in each script; the Tier-2 raw CSVs record the
seed of every run, the Tier-1 CSVs record across-seed aggregates.

Statistical conventions (as stated in the manuscript): across-seed means;
a quoted ± is a 95% Student-t CI unless stated to be a standard
deviation; curves compared across k share the seed set (paired);
"matches to x%" = max over the sweep of |sim − model|/model of the
across-seed mean; pass criteria are in each script. CIs are recorded for
E1–E2, E9, the matched-budget/adaptive/route-set/CGR-family experiments,
E19, and the tail experiment; the policy, threshold, ceiling,
finite-battery, bursty-harvest, renewal, and uncertainty sweeps record
means only.

Reproduced CSVs can be checked against the frozen paper dataset
(`results/reference/`, `tier2/results/reference/`) with
`python3 sim/compare_results.py [tier2/results]`.
