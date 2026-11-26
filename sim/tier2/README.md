# Tier-2 — DTN-realistic validation (OMNeT++ + dtnsim, Bundle Protocol/CGR)

Corroborates the analytical results in a real Bundle-Protocol / Contact
Graph Routing stack, complementing the model-exact Tier-1 Monte-Carlo
(`../montecarlo`, `../experiments`). The recorded outputs in `results/`
were produced on a stock Ubuntu VM; the scripts are host-agnostic (see
*Portability* below). Experiment→claim mapping: `../VALIDATION.md`.

## Toolchain

- **OMNeT++ 5.7.1** core, built headless:
  `./configure WITH_QTENV=no WITH_OSG=no && make MODE=release`.
  Installed at `$OMNETPP_HOME` (default `~/omnetpp-5.7.1`).
- **dtnsim** (Fraire/CGR lineage), upstream
  `https://github.com/lggaray/dtnsim.git`, **pinned commit
  `a9cf3fc655308a95884260a53878fbecb5d09708`**
  (`git clone https://github.com/lggaray/dtnsim.git && git -C dtnsim
  checkout a9cf3fc655308a95884260a53878fbecb5d09708`). Checked out at
  `$DTNSIM_ROOT` (default `~/dtnsim/dtnsim`) and built with
  `opp_makemake -f --deep -o dtnsim -O out -I. && make MODE=release`
  (the `-I.` is required — sources use root-relative includes).
- **Vector instrumentation (one-line patch):** in
  `src/node/app/App.ned`, add `,vector` to the `record=` list of
  `@statistic[appBundleReceivedDelay]` so per-bundle delivery delay is
  recorded as a vector `(time=delivery, value=latency Y)`, enabling
  AoI/PAoI reconstruction by `aoi_from_vec.py`.
- **Energy module:** `dtnsim_patch/` adds an `Energy` submodule
  (battery `B`, harvest rate `lambda_e`, per-copy cost `e`) and gates
  `Dtn.cc` forwarding (`consume()` per transmitted copy; skip while
  `battery < e`). `atomic=true` switches to all-or-nothing per-update
  admission (fire k copies only if `battery >= k e`, charged once at
  the firing point) — used by the atomic and E16 experiments. Install:
  `python3 dtnsim_patch/apply_patch.py $DTNSIM_ROOT/src`, rebuild.
  Idempotent; `enable=false` restores unlimited energy. NED-path note:
  run with `-n "$SRC:$DTNSIM_ROOT"` (do **not** add `.`, or the loader
  rejects the patch dir's package).
- **k-copy CGR router:** `dtnsim_patch/install_kcopies.py` adds
  `RoutingCgrModelKCopies` — source-only replication committing one
  copy to each of the top-k decorrelated CGR routes (unique per-copy
  bundle IDs; delivery uses the freshest-arriving copy).
- **Relay faults:** dtnsim's native per-node fault process
  (`fault.meanTTF` / `fault.meanTTR`, exponential ON/OFF) provides the
  route-uncertainty knob; the energy gate composes with the existing
  `onFault` forwarding check.

## Portability

Every `run_*.sh` reads two environment variables and otherwise runs
from its own directory:

```bash
OMNETPP_HOME=${OMNETPP_HOME:-$HOME/omnetpp-5.7.1}   # sourced setenv
DTNSIM_ROOT=${DTNSIM_ROOT:-$HOME/dtnsim/dtnsim}     # binary + NED roots
```

Override them if your checkouts live elsewhere; no script edits needed.
All scripts are fail-fast (`set -eo pipefail`, `-u` after OMNeT++'s
`setenv`): a missing toolchain or a simulator failure aborts loudly
instead of producing partial CSVs. Seed counts are env-overridable
where applicable (`SEEDS`); **defaults reproduce the paper's recorded
datasets exactly** (e.g. E16 runs seeds 1–10). For a quick pass, lower
the seed count explicitly, e.g. `SEEDS="1 2 3" ./run_e16_unified.sh`.
Scripts write into `results/`; the committed paper dataset is frozen
under `results/reference/` and never written by scripts — compare a
reproduction with `python3 ../compare_results.py tier2/results`.

## Scenario generators and analysis

- `make_leo_scenario.py` — periodic single-segment LEO plan
  (P=5736 s, W=430 s, δ=0.075, 60 periods; ION contact-plan format).
- `make_relay_scenario.py {incomm,comm}` — 2-segment relay
  (sensor→sat→gateway), incommensurate vs commensurate periods.
- `make_renewal_scenario.py {gamma cv|exp|pareto cv}` — random contact
  gaps (renewal law / inversion).
- `make_r3_scenario.py` — 2-relay diamond with relay faults + source
  energy gate (threshold experiments).
- `make_r3_atomic_scenario.py`, `make_policy_scenario.py`,
  `make_e17_scenario.py`, `make_hetero_scenario.py` — atomic-admission,
  policy, capacity, and heterogeneous-chain variants.
- `make_tle_scenario.py` — real Iridium-NEXT contact plan from
  `iridium.tle` over a Svalbard station via Skyfield
  (provenance: `TLE_PROVENANCE.md`).
- `two_tle_rmin.py` — 40-pair residual-min scan over real satellite
  pairs.
- `aoi_from_vec.py` — reconstruct AoI/PAoI (per-reset and per-update)
  from the delivery vector; `*_collect.py` / `*_aggregate.py` — CSV
  summarization with 95% CIs.

## Running

Single R1 cross-check by hand:

```bash
source "$OMNETPP_HOME/setenv" -f
python3 make_leo_scenario.py
"$DTNSIM_ROOT/dtnsim" -u Cmdenv -n "$DTNSIM_ROOT/src:.:$DTNSIM_ROOT" -f leo.ini
python3 aoi_from_vec.py results/General-#0.vec --P 5736 --W 430 --periods 60
```

Sweeps (each writes its CSV under `results/`):

```bash
./run_r3_sweep.sh        # k=1 vs k=2 delivery vs harvest (spray variant)
./run_r3_cgr.sh          # CGR-native k=2 vs single-copy, 10 seeds
./run_r3_atomic.sh       # all-or-nothing admission threshold sweep
./run_e16_unified.sh     # unified faults+atomic experiment (10 seeds)
./run_e17_capacity.sh    # contact-capacity boundary (3 seeds)
./run_hetero_seeds.sh    # heterogeneous 3-segment chain (10 seeds)
./run_policy_sweep.sh    # k in {1..4} policy comparison
```

## Recorded results

### R1 — residual law in real CGR (`results/results_leo_summary.txt`)

1129/1147 delivered over the periodic plan; **mean delivery delay
2453.92 s vs closed form E[R]=(P−W)²/2P=2454.1 s** (within 0.01%); delay histogram = the full mixed residual law (atom ≈δ at 0 +
uniform slab on (0,G]); mean per-reset PAoI 5450 s ≈ G + finite-horizon
offset, mean AoI 2554 s ≈ E[R] + same offset.

### Phase mixing — support for the fixed-plan approximation (`results/relay_summary.txt`)

End-to-end latency variance over the 2-segment relay discriminates
mixing from locking:

| Mode | mean Y | sd Y (sim) | sd if independent | verdict |
|---|---|---|---|---|
| incommensurate (P1=5736, P2=4500) | 4425 | 2086 | 2072 | variance adds — supports the fixed-plan mixing **approximation** |
| commensurate (P2=P1, offset P/2) | 5306 | 1657 | 1630 | phases locked — no added variance (predicted failure mode) |

Scoping (matches the manuscript): the mixing lemma is *exact* for
random-offset ensembles; for a single fixed co-period plan, downstream
independence is an engineering approximation whose validity this
experiment measures in a real CGR stack — and whose failure the
commensurate row reproduces.

### Renewal law + AoI/PAoI inversion (`results/renewal_summary.txt`)

Gamma gaps, CV ∈ {0.5, 1, 2}: residual law E[V²]/2E[C] matches to
<0.5%; mean AoI and mean per-reset PAoI invert at high CV (10402 vs
7704 at CV=1.88), the manuscript's inversion regime, in real CGR.

### Energy–replication threshold, spray variant (`results/r3_sweep.txt`) — preliminary

A preliminary mechanism check predating the CGR-native router (not
used in the manuscript; retained for provenance). Delivery count k=1
vs k=2 (sprayAndWait) vs harvest: k=2 starves below
η≈2 and wins from η≈3 — the crossover sits at η≈k, per the threshold
k\*=min(K_max,⌊η⌋). (dtnsim's `cgrModel350_2Copies` does not replicate
on a symmetric diamond — its diversity metric is arrival-time-vs-hops —
and `epidemic` misbehaved here; `sprayAndWait` is the clean k knob.)

### Two-relay plan under faults (`results/r3_cgr_raw.csv`) — read with caution

`run_r3_cgr.sh` + `r3_aggregate.py`, 10 seeds, 95% CIs, relay faults
on, per-transmission energy gate, one update every 300 s (about 19 per
period), source battery of 5 copies. The energy axis of this experiment
is the adequacy **per update interval**, η_g = λ_e·300 s/e, not the
per-period η of the manuscript's Section 6. Our k-copy router with two
copies keeps mean OPAoI 5.9–6.5× below dtnsim's stock single-copy CGR
(8.9P → 1.39P at η_g=0.6; 7.0P → 1.19P at η_g=6).

This is **not** a controlled measurement of hedging: (i) both arms are
burst-limited — a 5-copy battery cannot clear the updates queued for a
pass, so delivery is 34% (lowest energy) to 73–76% (highest) of the
generated updates, nearly equal in the two arms, and the single-copy
arm carries a standing backlog; (ii) the arms differ in router
implementation (`cgrModel350` vs `cgrModelKCopies`) as well as in copy
count.

**Controlled rerun (2026-11-22, `run_r3_cgr_control.sh`,
`results/r3_cgr_control_raw.csv`; 10 seeds, the k-copy router in both
arms at one and two copies, source batteries of 5 and 32 copies).**
The router is not the cause: at battery 5 the single-copy arm reproduces
the stock-router results identically, seed for seed (8.89P at η_g=0.6,
7.01P at η_g=6). Summary with paired CIs: `python3
r3_cgr_control_aggregate.py` → `results/r3_cgr_control.csv`. The relays
are bent pipes (uplink and downlink contacts share windows), so a
faulted relay almost never holds a committed bundle and CGR re-routes it
from the source: the effective per-pass success is ≈1, the q→1 limit of
the manuscript's eq. (30). With battery 32 and η_g ≥ 1.5 a single copy is as fresh as two
or fresher: mean OPAoI 0.71P for one copy; two copies are staler by
0.49 ± 0.06P (η_g=1.5), 0.46 ± 0.07P (2.0), 0.15 ± 0.14P (3.0), and tie at
6.0 (0.05 ± 0.11P; paired per-seed differences, 95% CIs). The large ratio
survives only where the source cannot keep up with its own updates
(battery 5, or η_g < 1). Under these stall-type faults, which CGR routes
around, the outcome is the oracle tie of the manuscript's Remark 8, so
the manuscript reports the controlled result in text and no longer shows
the two-relay figure; the hedge is established model-exactly
(`e_baselines.py`, `e19_bursty_faults.py`). The `recv` column counts
received copies, so for two copies it includes duplicates.

### Atomic all-or-nothing threshold (`results/r3_atomic.csv`)

With atomic admission (fire k copies only if battery ≥ ke), the
starvation penalty appears in real CGR: at η=1, k=3 is 2.7× worse than
k=1; admitted fraction matches the theory to within 0.7%; at η≥k under a
fault-free deterministic plan the degrees tie — the replication benefit
requires route uncertainty, exactly the manuscript's framing.

### E16 — unified experiment (`results/e16_unified.csv`)

One topology, atomic admission, relay faults, both metrics, 10 seeds,
six-copy source battery. The starvation side is significant (every
degree above η is penalized: +144%, +71%, +33%), so the argmin is at
most ⌊η⌋. Among affordable degrees the means are ordered as predicted
(−0.6%/−0.8% for the second copy in OPAoI/PAoI^per, a further −0.2 to
−0.3% for the third) but the paired per-seed differences are within
noise (−44 ± 131 s, −16 ± 98 s): consistent with, not resolving,
min(K_max, ⌊η⌋). dtnsim's faults are stall-type, so the effective
per-pass success is close to one here.

### E17 — contact-capacity boundary (`results/e17_capacity.csv`)

Window capacity fixed at m bundles, offered rate swept ~1→16 per
period, 3 seeds, M=64 as the unloaded control on the same seeds.
Per-seed loaded/unloaded delay ratios for one copy: 1.00–1.03 up to
ρ=0.5 (one seed 1.12 at the lowest load), 1.05–1.38 at ρ=1, and
117–124 at ρ=2, where the delivered fraction drops to the capacity
ratio: a step, not a knee. Two copies double the offered contact volume:
only mildly affected at 8 updates/period (ρ=0.67, ratios 1.05–1.13),
past the wall at 16 (ρ=1.33, ratios 95–101). This is the manuscript's
low-load scope boundary, measured.

### Real Iridium-NEXT ephemeris (`results/tle_summary.txt`, `results/two_tle_scan.log`)

Single satellite over Svalbard (101 passes / 7 days): 2015/2015
delivered; mean delay 2490.9 s vs renewal law 2492.4 s (**0.06%**).
40-pair scan: pairwise residual-min ratio spans 0.41–0.95 with phase
alignment — the route-set latency-diversity *potential* on real orbits;
the near-independent pair matches the product formula to 4.3%.

### Heterogeneous chain (`results/hetero_summary.txt`, `results/hetero_seeds.csv`)

3-segment LEO+UAV+terrestrial chain, 10 seeds: end-to-end mean delay
vs the composed per-segment laws — per-seed deviation ≤5.9%, mean 0.2%.
