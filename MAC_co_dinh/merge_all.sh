#!/bin/bash
# =============================================================================
# merge_all.sh
#
# DA SUA LAN 2 (fix loi merge sai): ban truoc dung "find ... | head -n1" de
# lay fort.22/fort.23 -> CHI lay DUY NHAT 1 file cycle dau tien, cac file
# cycle con lai (neu job chay nhieu cycle, FLUKA se sinh nhieu file
# <job>NNNcyc_fort.22, <job>NNNcyc_fort.23 ...) bi ROI, khong duoc dua vao
# usbsuw -> ket qua "merge" thuc chat khong merge gi ca, chi xu ly 1 file.
# Ham run_usbsuw cu cung chi nhan DUNG 1 file input roi gui dong trong ket
# thuc danh sach ngay lap tuc, nen du find co lay du file cung khong gui
# het cho usbsuw duoc.
#
# Da sua: lay TOAN BO file *_fort.22 (va *_fort.23) trong job_dir, sap xep
# theo ten (dung thu tu cycle), roi truyen CA DANH SACH cho run_usbsuw.
# usbsuw se hoi "Type the input file:" nhieu lan (moi lan 1 file), gui lan
# luot tung file, sau khi het danh sach thi gui dong trong de bao ket thuc,
# roi moi tra loi "Type the output file name:". Day moi dung la merge nhieu
# cycle thanh 1 file .bnn.
#
# Duyet qua TUNG THU MUC JOB con nam truc tiep trong outputs_dir (dung cau
# truc do run_batch_fluka.py tao ra: outputs_fluka/<job_name>/<job_name>NNN_fort.22
# va <job_name>NNN_fort.23 - co the co NHIEU file neu job chay nhieu cycle).
#
# Voi moi thu muc job:
#   1. usbsuw : merge TOAN BO <job>*_fort.22 -> <job>_usrbdx_tab.bnn
#               merge TOAN BO <job>*_fort.23 -> <job>_usrtrack_tab.bnn
#   2. usbrea : convert 2 file .bnn tren -> <job>_usrbdx.lis, <job>_usrtrack.lis
#
# CHAY SONG SONG nhieu job cung luc (giong logic ThreadPoolExecutor trong
# run_batch_fluka.py), dung xargs -P de gioi han so tien trinh dong thoi.
#
# CACH DUNG:
#   chmod +x merge_all.sh
#   ./merge_all.sh /home/ht/flukasp/Proton/outputs_fluka [so_song_song]
#   Vi du chay 10 job cung luc:
#   ./merge_all.sh /home/ht/flukasp/Proton/outputs_fluka 10
#
# QUAN TRONG - HAY TEST TREN 1 JOB DUY NHAT TRUOC (vi du s1_100keV) roi
# kiem tra file .lis sinh ra co hop le khong, MOI chay hang loat toan bo grid.
# Neu usbrea/usbsuw hoi khac voi gia dinh trong expect script (vd wording
# khac), no se timeout va bao loi -> paste dung nguyen van cau hoi that su
# ban thay khi chay tay 1 lan, gui lai de sua script cho chinh xac.
# =============================================================================

set -uo pipefail

BASE_DIR="${1:-.}"
WORKERS="${2:-8}"     # so job chay dong thoi, mac dinh 8 - tang/giam tuy may
FLUPRO="${FLUPRO:-$FLUPRO}"   # gia su FLUPRO da duoc export trong ~/.bashrc

if [ -z "${FLUPRO:-}" ]; then
    echo "LOI: bien moi truong \$FLUPRO chua duoc set. Chay: export FLUPRO=/duong/dan/toi/fluka"
    exit 1
fi

export USBSUW="$FLUPRO/flutil/usbsuw"
export USBREA="$FLUPRO/flutil/usbrea"
# USRTRACK PHAI dung ustsuw, KHONG dung usbsuw (usbsuw danh cho USRBIN).
# ustsuw tu no da sinh ra ca _sum.lis lan _tab.lis trong 1 buoc, KHONG can
# buoc "rea" rieng nhu USRBIN (theo tai lieu FLUKA chinh thuc).
export USTSUW="$FLUPRO/flutil/ustsuw"

if [ ! -x "$USTSUW" ]; then
    echo "CANH BAO: khong thay $USTSUW - kiem tra lai \$FLUPRO/flutil/ da co ustsuw chua (ls \$FLUPRO/flutil | grep ust)"
fi

if ! command -v expect &> /dev/null; then
    echo "LOI: chua cai 'expect'. Chay: sudo apt install expect"
    exit 1
fi

if [ ! -d "$BASE_DIR" ]; then
    echo "LOI: khong tim thay thu muc '$BASE_DIR'"
    exit 1
fi

# -----------------------------------------------------------------------
# usbsuw voi NHIEU file input (merge tat ca cac cycle thanh 1 file .bnn):
# usbsuw hoi "Type the input file:" LAP LAI, moi lan dua 1 ten file trong
# danh sach; khi het danh sach thi gui dong TRONG de bao ket thuc, sau do
# moi den prompt "Type the output file name:".
#
# Tham so: bnn_out la ten file .bnn output, cac tham so con lai (${@:2})
# la DANH SACH TOAN BO cac file fort.NN can merge (>=1 file), da duoc sap
# xep dung thu tu cycle boi process_job.
# -----------------------------------------------------------------------
run_usbsuw () {
    local bnn_out="$1"
    shift
    local files=("$@")

    # Build danh sach Tcl (moi phan tu dat trong ngoac kep rieng) de dua
    # vao script expect - dung "set filelist [list ...]" thay vi noi chuoi
    # tho, tranh loi khi ten file co ky tu dac biet.
    local tcl_items=""
    local f
    for f in "${files[@]}"; do
        tcl_items+=" \"$f\""
    done

    # QUAN TRONG: bien dem "idx" phai la bien TCL (\$idx, co backslash) chu
    # KHONG duoc de bash tu thay the truoc khi dua cho expect - neu khong no
    # se bi "dong cung" thanh gia tri hang so, khien usbsuw nhan mai 1 file
    # dau tien lap vo han, khong bao gio chuyen sang file tiep theo hoac gui
    # dong trong de bao het danh sach.
    expect -c "
        set timeout 20
        set filelist [list$tcl_items]
        set idx 0
        spawn \"$USBSUW\"
        expect {
            -re {Type the input file:} {
                if { \$idx < [llength \$filelist] } {
                    send \"[lindex \$filelist \$idx]\r\"
                    incr idx
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

# -----------------------------------------------------------------------
# ustsuw: cong cu DUNG RIENG cho USRTRACK (khac usbsuw!). Nhan NHIEU file
# fort.23 (cac cycle), merge lai va tu no sinh ra ca file _sum.lis lan
# _tab.lis trong 1 BUOC DUY NHAT - KHONG can chay them "rea" nhu USRBIN.
#
# GIA DINH prompt giong usbsuw ("Type the input file:" lap lai cho tung
# file, "Type the output file name:" 1 lan cuoi). NEU BAN CHAY THU MA THAY
# ustsuw hoi khac (vd wording khac, hoi them cau nao do), HAY CHAY TAY
# ustsuw 1 LAN NGOAI DIRECTORY THAT (khong qua script nay) de xem dung
# nguyen van no hoi gi, roi gui lai cho minh de sua ham nay cho chinh xac,
# vi moi ban build FLUKA co the hoi cau chu hoi khac nhau chut it.
# -----------------------------------------------------------------------
run_ustsuw () {
    local out_name="$1"
    shift
    local files=("$@")

    local tcl_items=""
    local f
    for f in "${files[@]}"; do
        tcl_items+=" \"$f\""
    done

    expect -c "
        set timeout 20
        set filelist [list$tcl_items]
        set idx 0
        spawn \"$USTSUW\"
        expect {
            -re {Type the input file:} {
                if { \$idx < [llength \$filelist] } {
                    send \"[lindex \$filelist \$idx]\r\"
                    incr idx
                } else {
                    send \"\r\"
                }
                exp_continue
            }
            -re {Type the output file name:} { send \"$out_name\r\" ; exp_continue }
            eof
        }
    "
}

# -----------------------------------------------------------------------
# Xu ly 1 thu muc job DAY DU (usbsuw x2 + usbrea x2). Nhan job_dir (duong
# dan tuyet doi) lam tham so, KHONG dung `cd` toan cuc (vi chay song song,
# nhieu tien trinh cung doi cwd se dam vao nhau) - thay vao do luon dung
# duong dan day du hoac subshell rieng cho tung job.
# -----------------------------------------------------------------------
process_job () {
    local job_dir="$1"
    local job_name
    job_name=$(basename "$job_dir")

    # Lay TOAN BO file fort.22 / fort.23 trong job_dir (co the co nhieu
    # neu job chay nhieu cycle), sap xep theo ten -> dung thu tu cycle.
    # KHONG con dung "head -n1" nua vi se lam mat cac cycle con lai.
    local fort22_list fort23_list
    mapfile -t fort22_list < <(find "$job_dir" -maxdepth 1 -name "*_fort.22" | sort)
    mapfile -t fort23_list < <(find "$job_dir" -maxdepth 1 -name "*_fort.23" | sort)

    if [ "${#fort22_list[@]}" -eq 0 ] || [ "${#fort23_list[@]}" -eq 0 ]; then
        echo "[BO QUA] $job_name : thieu fort.22 (USRBDX) va/hoac fort.23 (USRTRACK)"
        return
    fi

    if [ "${#fort22_list[@]}" -gt 1 ] || [ "${#fort23_list[@]}" -gt 1 ]; then
        echo "[$job_name] phat hien nhieu cycle: ${#fort22_list[@]} file fort.22, ${#fort23_list[@]} file fort.23 -> se merge het"
    fi

    # Chay trong subshell rieng, cd vao day chi anh huong subshell nay,
    # khong dam vao cwd cua cac job khac chay song song.
    (
        cd "$job_dir" || exit 1

        local bnn_bdx="${job_name}_usrbdx_tab.bnn"
        local lis_bdx="${job_name}_usrbdx.lis"
        # USRTRACK: dat ten output la "${job_name}_usrtrack" (KHONG co duoi),
        # vi ustsuw se TU sinh them duoi (thuong la _sum.lis / _tab.lis) -
        # NEU ban thay ten file thuc te sinh ra khac voi $lis_trk ben duoi,
        # sua lai bien lis_trk cho khop (xem ghi chu o dinh nghia ham run_ustsuw).
        local trk_out_base="${job_name}_usrtrack"
        local lis_trk="${trk_out_base}_sum.lis"

        # Chuyen duong dan tuyet doi -> ten file tuong doi (vi da cd vao job_dir)
        local f22_basenames=() f23_basenames=() f
        for f in "${fort22_list[@]}"; do f22_basenames+=("$(basename "$f")"); done
        for f in "${fort23_list[@]}"; do f23_basenames+=("$(basename "$f")"); done

        echo "[$job_name] -> usbsuw (USRBDX, ${#f22_basenames[@]} file) ..."
        run_usbsuw "$bnn_bdx" "${f22_basenames[@]}"
        if [ -f "$bnn_bdx" ]; then
            echo "[$job_name] [OK] tao duoc $bnn_bdx"
        else
            echo "[$job_name] [LOI] usbsuw KHONG tao duoc $bnn_bdx (xem output usbsuw phia tren de biet no hoi gi ma khong khop pattern)"
        fi

        echo "[$job_name] -> ustsuw (USRTRACK, ${#f23_basenames[@]} file) ..."
        run_ustsuw "$trk_out_base" "${f23_basenames[@]}"
        if ls "${trk_out_base}"*.lis >/dev/null 2>&1; then
            echo "[$job_name] [OK] ustsuw tao ra: $(ls ${trk_out_base}*.lis 2>/dev/null | tr '\n' ' ')"
        else
            echo "[$job_name] [LOI] ustsuw KHONG tao ra file .lis nao cho USRTRACK - CHAY TAY '$USTSUW' 1 lan trong $job_dir de xem no hoi gi thuc su, roi paste nguyen van de sua ham run_ustsuw"
        fi

        if [ -f "$bnn_bdx" ]; then
            echo "[$job_name] -> usbrea (USRBDX) ..."
            run_usbrea "$bnn_bdx" "$lis_bdx"
        fi

        if [ -f "$lis_bdx" ] && [ -f "$lis_trk" ]; then
            echo "[$job_name] [JOB OK] $lis_bdx , $lis_trk"
        else
            local missing=""
            [ -f "$lis_bdx" ] || missing="$missing $lis_bdx"
            [ -f "$lis_trk" ] || missing="$missing $lis_trk"
            echo "[$job_name] [JOB CHECK LAI] thieu file:$missing - xem log usbsuw/usbrea/ustsuw phia tren cua chinh job nay de biet buoc nao that bai"
        fi
    )
}
export -f run_usbsuw run_usbrea run_ustsuw process_job

# Lay danh sach TUNG THU MUC JOB con truc tiep trong BASE_DIR (khong de quy
# sau hon, vi cau truc run_batch_fluka.py tao ra la phang: outputs_dir/<job>/)
mapfile -t job_dirs < <(find "$BASE_DIR" -mindepth 1 -maxdepth 1 -type d | sort)

if [ "${#job_dirs[@]}" -eq 0 ]; then
    echo "Khong tim thay thu muc job nao trong '$BASE_DIR' (kiem tra lai duong dan)."
    exit 1
fi

echo "Tim thay ${#job_dirs[@]} thu muc job -> chay song song $WORKERS tien trinh"

LOG_FILE=$(mktemp)
printf '%s\n' "${job_dirs[@]}" | xargs -P "$WORKERS" -I{} bash -c 'process_job "$@"' _ {} | tee "$LOG_FILE"

ok_count=$(grep -c '\[JOB OK\]' "$LOG_FILE" || true)
skip_count=$(grep -c '\[BO QUA\]' "$LOG_FILE" || true)
fail_count=$(grep -c '\[JOB CHECK LAI\]' "$LOG_FILE" || true)
rm -f "$LOG_FILE"

echo ""
echo "Hoan tat: $ok_count job OK / $skip_count bo qua (thieu file) / $fail_count can kiem tra lai / tong ${#job_dirs[@]} thu muc job"
