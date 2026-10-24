#!/bin/bash
# =============================================================================
# merge_all.sh
#
# Duyet qua TUNG THU MUC JOB con nam truc tiep trong outputs_dir (dung cau
# truc do run_batch_fluka.py tao ra: outputs_fluka/<job_name>/<job_name>NNN_fort.21
# va <job_name>NNN_fort.22 - MOI thu muc CHI co dung 1 file fort.21 va 1 file
# fort.22, khong co chuyen nhieu cycle sinh nhieu file roi trong cung thu muc).
#
# Voi moi thu muc job:
#   1. usbsuw : convert <job>NNN_fort.21 -> <job>_tdose_tab.bnn
#               convert <job>NNN_fort.22 -> <job>_tflux_tab.bnn
#   2. usbrea : convert 2 file .bnn tren -> <job>_tdose.lis, <job>_tflux.lis
#
# CACH DUNG:
#   chmod +x merge_all.sh
#   ./merge_all.sh /home/ht/flukasp/Proton/outputs_fluka
#
# QUAN TRONG - HAY TEST TREN 1 JOB DUY NHAT TRUOC (vi du proton_s1_30keV) roi
# kiem tra file .lis sinh ra co hop le khong, MOI chay hang loat toan bo grid.
# Neu usbrea/usbsuw hoi khac voi gia dinh trong expect script (vd wording
# khac), no se timeout va bao loi -> paste dung nguyen van cau hoi that su
# ban thay khi chay tay 1 lan, gui lai de sua script cho chinh xac.
# =============================================================================

set -uo pipefail

BASE_DIR="${1:-.}"
FLUPRO="${FLUPRO:-$FLUPRO}"   # gia su FLUPRO da duoc export trong ~/.bashrc

if [ -z "${FLUPRO:-}" ]; then
    echo "LOI: bien moi truong \$FLUPRO chua duoc set. Chay: export FLUPRO=/duong/dan/toi/fluka"
    exit 1
fi

USBSUW="$FLUPRO/flutil/usbsuw"
USBREA="$FLUPRO/flutil/usbrea"

if ! command -v expect &> /dev/null; then
    echo "LOI: chua cai 'expect'. Chay: sudo apt install expect"
    exit 1
fi

# -----------------------------------------------------------------------
# usbsuw voi DUNG 1 file input (khong can merge nhieu file):
# hoi "Type the input file:" -> dua ten file, roi Enter trong de bao het
# danh sach, roi den "Type the output file name:".
# -----------------------------------------------------------------------
run_usbsuw () {
    local fort_file="$1"
    local bnn_out="$2"

    # QUAN TRONG: bien dem "sent" phai la bien TCL (\$sent, co backslash) chu
    # KHONG duoc de bash tu thay the truoc khi dua cho expect - neu khong no
    # se bi "dong cung" thanh gia tri hang so (vd "0 == 0" mai mai dung), khien
    # usbsuw nhan cung 1 file input lap vo han, khong bao gio chuyen sang gui
    # dong trong de bao het danh sach.
    expect -c "
        set timeout 20
        set sent 0
        spawn \"$USBSUW\"
        expect {
            -re {Type the input file:} {
                if { \$sent == 0 } {
                    send \"$fort_file\r\"
                    set sent 1
                } else {
                    send \"\r\"
                }
                exp_continue
            }
            -re {Type the output file name:} { send \"$bnn_out\r\" ; exp_continue }
            eof
        }
    "
}

# -----------------------------------------------------------------------
# usbrea: 1 file .bnn -> .lis. Prompt "Type the input file:" chi hoi 1 lan,
# roi den "Type the output file name:".
# -----------------------------------------------------------------------
run_usbrea () {
    local bnn_file="$1"
    local lis_out="$2"

    expect -c "
        set timeout 20
        spawn \"$USBREA\"
        expect {
            -re {Type the input file:} { send \"$bnn_file\r\" ; exp_continue }
            -re {Type the output file name:} { send \"$lis_out\r\" ; exp_continue }
            eof
        }
    "
}

if [ ! -d "$BASE_DIR" ]; then
    echo "LOI: khong tim thay thu muc '$BASE_DIR'"
    exit 1
fi

# Lay danh sach TUNG THU MUC JOB con truc tiep trong BASE_DIR (khong de quy
# sau hon, vi cau truc run_batch_fluka.py tao ra la phang: outputs_dir/<job>/)
mapfile -t job_dirs < <(find "$BASE_DIR" -mindepth 1 -maxdepth 1 -type d | sort)

if [ "${#job_dirs[@]}" -eq 0 ]; then
    echo "Khong tim thay thu muc job nao trong '$BASE_DIR' (kiem tra lai duong dan)."
    exit 1
fi

count=0
for job_dir in "${job_dirs[@]}"; do
    job_name=$(basename "$job_dir")

    # Moi thu muc job chi co DUNG 1 file *_fort.21 va 1 file *_fort.22
    fort21=$(find "$job_dir" -maxdepth 1 -name "*_fort.21" | head -n1)
    fort22=$(find "$job_dir" -maxdepth 1 -name "*_fort.22" | head -n1)

    if [ -z "$fort21" ] || [ -z "$fort22" ]; then
        echo "[BO QUA] $job_name : thieu fort.21 va/hoac fort.22"
        continue
    fi

    echo "=== Xu ly: $job_name ==="
    cd "$job_dir" || continue

    bnn_dose="${job_name}_tdose_tab.bnn"
    bnn_flux="${job_name}_tflux_tab.bnn"
    lis_dose="${job_name}_tdose.lis"
    lis_flux="${job_name}_tflux.lis"

    echo "  -> usbsuw (TDOSE) ..."
    run_usbsuw "$(basename "$fort21")" "$bnn_dose"

    echo "  -> usbsuw (TFLUX) ..."
    run_usbsuw "$(basename "$fort22")" "$bnn_flux"

    if [ -f "$bnn_dose" ]; then
        echo "  -> usbrea (TDOSE) ..."
        run_usbrea "$bnn_dose" "$lis_dose"
    fi
    if [ -f "$bnn_flux" ]; then
        echo "  -> usbrea (TFLUX) ..."
        run_usbrea "$bnn_flux" "$lis_flux"
    fi

    if [ -f "$lis_dose" ] && [ -f "$lis_flux" ]; then
        echo "  [OK] $lis_dose , $lis_flux"
        count=$((count+1))
    else
        echo "  [CHECK LAI] khong thay day du .lis cho $job_name - xem log ben tren"
    fi

    cd - > /dev/null
done

echo ""
echo "Hoan tat: $count job co day du .lis / tong ${#job_dirs[@]} thu muc job"
