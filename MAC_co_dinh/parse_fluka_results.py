"""
Doc flux tu file _usrtrack_sum.lis (ket qua sau khi chay merge_all.sh voi
ustsuw cho USRTRACK cua FLUKA), xuat ra file Excel dang bang doc, moi hang
1 job co mau: Energy | Material | Thickness_cm | Flux | Blank_Flux.

Danh sach job (va ten job) doc tu CHINH bang be day, qua ham
read_thickness_jobs() cua generate_fluka_inputs.py, nen luon khop voi luc sinh
input (ho tro nhieu be day / nang luong, bo qua cot chua khai bao).
Blank_Flux cua moi hang lay tu job blank CUNG nang luong va CUNG be day.

Cau truc thu muc (giong PHITS): moi job FLUKA chay trong MOT thu muc rieng,
vi du:
    outputs_fluka/s1_40keV_t0p5cm/s1_40keV_t0p5cm_usrtrack_sum.lis
    outputs_fluka/blank_40keV_t0p5cm/blank_40keV_t0p5cm_usrtrack_sum.lis

CHI LAY 1 SO DUY NHAT cho moi job: gia tri "Cumul. Flux (Part/cmq/pr)" lay
tu khoi Cumulative Fluxes (khoi nam SAU khoi flux vi phan, la flux da cong
don theo nang luong), bang cach QUET TU DUOI LEN (tu cuoi danh sach cac cap
gia_tri/sai_so, tuc tu bin nang luong THAP NHAT, di nguoc len dan) va lay
GIA TRI KHAC 0 DAU TIEN gap duoc theo huong quet nay. Vi day la khoi cong
don (tang dan khi nang luong giam), gia tri lay duoc chinh la TONG FLUX
cong don cuoi cung trong file.

File Excel xuat ra CHI GOM cot gia tri flux, KHONG gom cot sai so (%).

Vi du thuc te (s1_15keV_usrtrack_sum.lis, quet tu duoi len):
  Cumul. Flux (Part/cmq/pr):
   0.000000     +/-    0.000000     %    0.000000     +/-    0.000000     %
   ... (nhieu dong 0.000000 lien tiep, ung voi cac bin gan E0 nhat) ...
   1.3167179E-05 +/-    99.00000     %   1.3167481E-05 +/-    99.00000     %
   ...
   1.3184806E-05 +/-    99.00000     %   1.3184807E-05 +/-    99.00000     %
   1.3184813E-05 +/-    99.00000     %   1.3184863E-05 +/-    99.00000     %
  -> quet tu cuoi (1.3184863E-05) nguoc len, gap gia tri khac 0 dau tien la
     chinh 1.3184863E-05 (bin cuoi cung, cung la tong flux cong don).

Chay: python parse_fluka_results.py thickness_table.xlsx outputs_fluka/ flux_results_fluka.xlsx
"""
import re
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_fluka_inputs import read_thickness_jobs, sample_job_name, blank_job_name

FLUX_MARKER = "Cumul. Flux (Part/cmq/pr):"
# So khop tung cap "gia_tri +/- sai_so %" bat ke xuong dong / khoang trang,
# vi file .lis in 2 cap tren 1 dong, khong theo cot co dinh.
PAIR_RE = re.compile(r'([-+0-9.]+(?:[Ee][-+]?\d+)?)\s*\+/-\s*([-+0-9.]+(?:[Ee][-+]?\d+)?)\s*%')


def parse_peak_track_flux(filepath: Path) -> tuple[float, float]:
    """
    Doc file _usrtrack_sum.lis, tra ve (flux, sai_so_%) lay tu khoi
    "Cumul. Flux (Part/cmq/pr):" (khoi Cumulative Fluxes), bang cach QUET
    TU DUOI LEN (tu cuoi danh sach cac cap gia_tri/sai_so - tuc bin nang
    luong THAP NHAT - di nguoc len dan ve dau danh sach) va lay GIA TRI
    KHAC 0 DAU TIEN gap duoc theo huong quet nay. Vi day la khoi cong don,
    gia tri nay chinh la TONG FLUX cong don cuoi cung trong file.

    LUU Y: khoi nay khac khoi "Flux (Part/GeV/cmq/pr):" (flux vi phan) o
    phia tren no, nen PHAI dung dung marker FLUX_MARKER, KHONG duoc nham
    voi khoi vi phan.
    """
    text = filepath.read_text()

    start = text.find(FLUX_MARKER)
    if start == -1:
        raise ValueError(f"Khong tim thay '{FLUX_MARKER}' trong {filepath}")
    start += len(FLUX_MARKER)

    # Khoi flux ket thuc truoc khi gap khoi tiep theo (danh dau boi "****",
    # thuong la "**** Cumulative Fluxes ..."). Neu khong co "****" o phia
    # sau (file bi cat/loi), lay het phan con lai cua file.
    end = text.find("****", start)
    segment = text[start:end] if end != -1 else text[start:]

    pairs = PAIR_RE.findall(segment)
    if not pairs:
        raise ValueError(f"Khong doc duoc du lieu flux trong {filepath}")

    # Quet TU DUOI LEN: bat dau tu cap CUOI CUNG trong danh sach (bin
    # nang luong THAP NHAT) va di NGUOC LEN dan ve dau danh sach, lay
    # cap DAU TIEN gap duoc (theo huong quet nay) co flux khac 0.
    for val_str, err_str in reversed(pairs):
        val = float(val_str)
        if val != 0.0:
            return val, float(err_str)

    # Toan bo pho bang 0 (truong hop hiem)
    return 0.0, 0.0


def main(excel_path: str, outputs_dir: str, result_path: str):
    jobs, skipped = read_thickness_jobs(excel_path)
    outputs_dir = Path(outputs_dir)

    if skipped:
        print(f"CANH BAO: bo qua cot {skipped} - chua khai bao trong generate_fluka_inputs.py")

    missing = []
    parse_errors = []

    def read_flux(job_name: str):
        # job_name phai khop CHINH XAC voi thu muc do run_batch_fluka.py /
        # merge_all.sh da tao ra: outputs_fluka/{job_name}/{job_name}_usrtrack_sum.lis
        lis_path = outputs_dir / job_name / f"{job_name}_usrtrack_sum.lis"
        if not lis_path.exists():
            missing.append(str(lis_path))
            return None
        try:
            peak_flux, err_pct = parse_peak_track_flux(lis_path)
        except ValueError as e:
            parse_errors.append(str(e))
            return None
        return peak_flux

    # 1 blank / (nang luong, be day), doc 1 lan roi dung chung cho moi vat lieu
    blank_flux = {}
    for energy_kev, _, thickness in jobs:
        key = (energy_kev, thickness)
        if key not in blank_flux:
            blank_flux[key] = read_flux(blank_job_name(energy_kev, thickness))

    rows = []
    for energy_kev, mat, thickness in jobs:
        rows.append({
            "Energy": energy_kev,
            "Material": mat,
            "Thickness_cm": thickness,
            "Flux": read_flux(sample_job_name(mat, energy_kev, thickness)),
            "Blank_Flux": blank_flux[(energy_kev, thickness)],
        })

    result = pd.DataFrame(rows, columns=["Energy", "Material", "Thickness_cm", "Flux", "Blank_Flux"])
    result = result.sort_values(["Material", "Energy", "Thickness_cm"], kind="stable")
    result.to_excel(result_path, index=False)
    print(f"Da luu ket qua {len(result)} job vao '{result_path}'")

    if missing:
        print(f"\nCANH BAO: {len(missing)} file khong tim thay (bo qua):")
        for m in missing[:20]:
            print(" -", m)
        if len(missing) > 20:
            print(f"   ... va {len(missing) - 20} file khac")

    if parse_errors:
        print(f"\nCANH BAO: {len(parse_errors)} loi khi doc du lieu:")
        for e in parse_errors[:20]:
            print(" -", e)
        if len(parse_errors) > 20:
            print(f"   ... va {len(parse_errors) - 20} loi khac")


if __name__ == "__main__":
    excel_path = sys.argv[1] if len(sys.argv) > 1 else "thickness_table.xlsx"
    outputs_dir = sys.argv[2] if len(sys.argv) > 2 else "outputs_fluka"
    result_path = sys.argv[3] if len(sys.argv) > 3 else "flux_results_fluka.xlsx"
    main(excel_path, outputs_dir, result_path)
