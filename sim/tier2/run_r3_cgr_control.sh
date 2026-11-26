#!/bin/bash
# CONTROL for run_r3_cgr.sh (two-relay plan under faults).
#
# run_r3_cgr.sh compares dtnsim's stock single-copy router (cgrModel350)
# with our k-copy router at k=2, with a source battery of 5 copies. That
# comparison confounds the copy count with the router implementation, and
# both arms are burst-limited (about 19 updates queue per pass). This
# script supplies the controlled comparison:
#   * SAME router (cgrModelKCopies) for both arms: bundlesCopies=1 vs 2;
#   * two battery capacities: 5 (as recorded) and 32 (burst limit removed).
# Emits raw per-seed rows: cap,eta_g,strategy,seed,paoi,recv
#   eta_g = harvestRate * 300 s / e   (adequacy per update interval)
#
# Run (on the OMNeT++ host), about the cost of two run_r3_cgr.sh sweeps:
#   ./run_r3_cgr_control.sh > results/r3_cgr_control_raw.csv
set -eo pipefail  # fail fast; -u is enabled only after setenv (it reads unset vars)
OMNETPP_HOME="${OMNETPP_HOME:-$HOME/omnetpp-5.7.1}"
DTNSIM_ROOT="${DTNSIM_ROOT:-$HOME/dtnsim/dtnsim}"
source "$OMNETPP_HOME/setenv" -f >/dev/null 2>&1 \
  || { echo "error: cannot source $OMNETPP_HOME/setenv (set OMNETPP_HOME)" >&2; exit 1; }
set -u
cd "$(dirname "$0")" || exit 1
BIN="$DTNSIM_ROOT/dtnsim"
NED="$DTNSIM_ROOT/src:$DTNSIM_ROOT"
[ -x "$BIN" ] || { echo "error: dtnsim binary not found at $BIN (set DTNSIM_ROOT)" >&2; exit 1; }
DEST=4
SEEDS="${SEEDS:-1 2 3 4 5 6 7 8 9 10}"
CAPS="${CAPS:-5 32}"
paoi() { python3 aoi_from_vec.py "$1" --dest $DEST --warmup-frac 0.1 --cluster-gap 600 2>/dev/null | awk '/mean PAoI \(per-outage\)/{print $4; exit}'; }
recv() { grep "node\[$DEST\].app appBundleReceived:count" "$1"|awk '{print $NF}'; }

run() {  # $1=tag $2=copies ; uses $RATE $SD $CAP $ETA
  local tag=$1 copies=$2
  local rd="cgc_${tag}_${CAP}_${RATE}_${SD}"; mkdir -p "$rd"
  $BIN -u Cmdenv -n "$NED" -f r3_diamond.ini \
    '--dtnsim.node[*].dtn.routing="cgrModelKCopies"' \
    "--dtnsim.node[*].dtn.bundlesCopies=$copies" \
    "--dtnsim.node[1].energy.harvestRate=$RATE" \
    "--dtnsim.node[1].energy.batteryCapacity=$CAP" \
    "--dtnsim.node[1].energy.batteryInit=$CAP" \
    '--dtnsim.node[2..3].fault.enable=true' '--dtnsim.node[2..3].fault.meanTTF=8000s' \
    '--dtnsim.node[2..3].fault.meanTTR=4000s' \
    "--dtnsim.node[2..3].fault.faultSeed=$SD" "--seed-0-mt=$SD" \
    --result-dir="$rd" >/dev/null 2>&1
  printf '%s,%s,%s,%s,%.0f,%s\n' "$CAP" "$ETA" "$tag" "$SD" "$(paoi $rd/General-#0.vec)" "$(recv $rd/General-#0.sca)"
}

echo "cap,eta_g,strategy,seed,paoi,recv"
for CAP in $CAPS; do
  for RATE in 0.0020 0.0033 0.0050 0.0067 0.0100 0.0200; do
    ETA=$(awk "BEGIN{printf \"%.2f\", $RATE*300}")
    for SD in $SEEDS; do
      run kc1 1
      run kc2 2
    done
  done
done
