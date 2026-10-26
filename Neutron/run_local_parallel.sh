#!/bin/bash
# =============================================================================
# run_local_parallel.sh - chay 6 input Neutron tren INFN FLUKA (may local/WSL),
# toi da MAXJOBS tien trinh cung luc (moi tien trinh FLUKA = 1 thread).
#
# Moi input duoc CHIA thanh n lan chay doc lap (seed RANDOMIZ khac nhau, moi lan
# START/n hat), chay song song, roi GOP USRTRACK bang ustsuw -> <job>_FLUKA_<u>_sum.lis
# (dung dinh dang gop_tot_response.py can).
#
# Cach dung (trong WSL):
#   bash run_local_parallel.sh                 # thu muc lam viec mac dinh ~/neutron_run
#   bash run_local_parallel.sh /duong/dan/work
#   TEST_PRIMARIES=200 bash run_local_parallel.sh ~/neutron_test   # chay thu nhanh
#
# Ket qua gop: <thu muc script>/03_Simulation_Outputs_local/<job>/
# =============================================================================
set -u
export FLUPRO=${FLUPRO:-/usr/local/flukagfor}
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${1:-$HOME/neutron_run}
MAXJOBS=${MAXJOBS:-30}
RESULTS="$HERE/03_Simulation_Outputs_local"

# so lan chia cho moi input (tong = 30); input nang (Flux_b) chia nhieu hon
declare -A SPLIT=( [Flux_b]=9 [Flux_ca]=6 [Flux_si]=6 [Flux_water]=5 [Flux_la]=2 [Flux_o]=2 )
JOBS=(Flux_b Flux_ca Flux_si Flux_water Flux_la Flux_o)

mkdir -p "$WORK/bin" "$RESULTS"

# --- 1. Bien dich nguon Watt (giong huongdan.txt) ---------------------------
EXE="$WORK/bin/flukawatt"
if [ ! -x "$EXE" ]; then
    (cd "$WORK/bin" && cp "$HERE/source_watt_template.f" . \
        && "$FLUPRO/flutil/fff" source_watt_template.f \
        && "$FLUPRO/flutil/lfluka" -m fluka -o flukawatt source_watt_template.o) > "$WORK/bin/build.log" 2>&1
fi
[ -x "$EXE" ] || { echo "LOI: khong bien dich duoc $EXE (xem $WORK/bin/build.log)"; exit 1; }

# --- 2. Tao cac lan chay con -------------------------------------------------
TASKS="$WORK/tasks.txt"; : > "$TASKS"
seed=1000
for job in "${JOBS[@]}"; do
    n=${SPLIT[$job]}
    total=$(awk '/^START/{printf "%d", substr($0,11,10)}' "$HERE/inputs/$job.inp")
    [ -n "${TEST_PRIMARIES:-}" ] && total=$(( TEST_PRIMARIES * n ))
    for k in $(seq 1 "$n"); do
        per=$(( total / n + (k <= total % n ? 1 : 0) ))
        seed=$(( seed + 7919 ))
        d="$WORK/$job/r$k"
        mkdir -p "$d"
        awk -v start="$(printf '%-10s%10.1f' START "$per")" \
            -v rnd="$(printf '%-10s%10.1f%10.1f' RANDOMIZ 1.0 "$seed")" \
            '/^START/{print start; next} /^RANDOMIZ/{print rnd; next} {print}' \
            "$HERE/inputs/$job.inp" > "$d/$job.inp"
        echo "$d $job" >> "$TASKS"
    done
    echo "$job: $total hat -> $n lan chay"
done

# --- 3. Chay song song (toi da MAXJOBS) --------------------------------------
echo "Chay $(wc -l < "$TASKS") tien trinh, toi da $MAXJOBS cung luc ..."
export EXE FLUPRO
xargs -P "$MAXJOBS" -L 1 bash -c 'cd "$0" && nice -n 10 "$FLUPRO/flutil/rfluka" -e "$EXE" -M 1 -N 0 "$1" > run.txt 2>&1; \
    if grep -q "End of FLUKA run" run.txt && ! grep -q "ABORTED" "${1}001.log" 2>/dev/null; then echo "[OK]  $0"; else echo "[LOI] $0"; fi' < "$TASKS"

# --- 4. Gop USRTRACK tung unit bang ustsuw -----------------------------------
for job in "${JOBS[@]}"; do
    out="$RESULTS/$job"; mkdir -p "$out"
    units=$(ls "$WORK/$job"/r1/"${job}"001_fort.* 2>/dev/null | sed 's/.*_fort\.//' | sort -n)
    nmerged=0
    for u in $units; do
        files=$(ls "$WORK/$job"/r*/"${job}"001_fort."$u")
        (cd "$out" && { printf '%s\n' $files; echo; echo "${job}_FLUKA_${u}"; } | "$FLUPRO/flutil/ustsuw" > /dev/null 2>&1)
        [ -f "$out/${job}_FLUKA_${u}_sum.lis" ] && nmerged=$((nmerged + 1))
    done
    cp "$WORK/$job/r1/${job}001.out" "$out/${job}_r1.out" 2>/dev/null
    echo "$job: gop $nmerged unit USRTRACK -> $out"
done
echo "Xong. Loc ket qua: python gop_tot_response.py 03_Simulation_Outputs_local/<job>"
