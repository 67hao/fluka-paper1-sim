"""
Sinh tu dong file .inp FLUKA de tinh MSP(entrance) va Projected Range cho
PROTON trong ca 6 vat lieu (s1..s6), tuong duong logic cua
generate_msp_range_inputs.py (ban PHITS), nhung dung dung cu phap fixed-column
cua FLUKA (moi truong 10 ky tu, ten field cuoi 8 ky tu) - DA VERIFY cot bang
cach do lai chinh xac tung dong trong file .inp da chay THANH CONG cua ban
(proton_s2_1000keV.inp, sau khi sua BEAMPOS/PART-THR).

QUAN TRONG - BAI HOC TU LOI TRUOC (PART-THR, BEAMPOS):
  KHONG gõ khoang trang bang tay. Moi field PHAI qua ham field()/name_field()
  o duoi de dam bao dung 10 cot, neu khong text se bi lech sang field ke ben
  (vi du "PROTON" bi hieu nham la gia tri "Step" thay vi "Part").

Cach dung (giong PHITS):
  1. Chuan bi srim_range_table.csv (cot energy_keV, range_um) - CHI dung cho
     vat lieu SRIM_TABLE_MATERIAL (s6) de scale mesh, KHONG phai gia tri cuoi.
  2. python generate_msp_range_inputs_fluka.py srim_range_table.csv inputs_fluka/

Sau khi sinh xong, moi job la 1 thu muc rieng chua 1 file .inp - chay FLUKA
(hoac qua flair) cho tung job, roi convert USRBIN binary -> ASCII (.lis) bang
usbrea/flair truoc khi dung parse_msp_range_fluka.py.

KHUYEN NGHI: chay THU 1-2 job dau tien qua flair (kiem tra bang mat, khong co
o do) truoc khi sinh & submit toan bo grid 6 vat lieu x N nang luong.
"""
import math
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Thanh phan (wt fraction, am = %-khoi-luong) va mat do cho 6 vat lieu s1..s6.
# Giong het COMPOSITION/DENSITY ben generate_msp_range_inputs.py (PHITS), chi
# doi ma ZA-code (vd "5000.00c") sang ten nguyen to FLUKA (vd "BORON").
# ---------------------------------------------------------------------------
COMPOSITION = {
    "s1": {"BORON": -0.1629, "OXYGEN": -0.4648, "SILICON": -0.0302, "CALCIUM": -0.0431, "LANTHANU": -0.2990},
    "s2": {"BORON": -0.1329, "OXYGEN": -0.4086, "SILICON": -0.0266, "CALCIUM": -0.0379, "LANTHANU": -0.3941},
    "s3": {"BORON": -0.1095, "OXYGEN": -0.3644, "SILICON": -0.0237, "CALCIUM": -0.0338, "LANTHANU": -0.4688},
    "s4": {"BORON": -0.0905, "OXYGEN": -0.3289, "SILICON": -0.0214, "CALCIUM": -0.0305, "LANTHANU": -0.5288},
    "s5": {"BORON": -0.0750, "OXYGEN": -0.2996, "SILICON": -0.0195, "CALCIUM": -0.0278, "LANTHANU": -0.5783},
    "s6": {"BORON": -0.0620, "OXYGEN": -0.2752, "SILICON": -0.0179, "CALCIUM": -0.0255, "LANTHANU": -0.6195},
}
DENSITY = {"s1": 3.0099, "s2": 3.1999, "s3": 3.3899, "s4": 3.5799, "s5": 3.7699, "s6": 3.9599}  # g/cm3

SRIM_TABLE_MATERIAL = "s6"   # vat lieu co bang SRIM that, 5 vat lieu con lai scale theo mat do (chi de chon mesh)
PROJECTILE = "PROTON"
NZ_BINS = 300
SAFETY_MARGIN = 2.5          # zmax tally = SAFETY_MARGIN x range SRIM. 1.6 la KHONG DU: range
                             # PHITS/FLUKA o 15 keV ~1.4x SRIM projected range (+ multiple scattering)
BLOCK_SAFETY_FACTOR = 3.0    # be day KHOI target = BLOCK_SAFETY_FACTOR x zmax tally (truoc day = 1x,
                             # proton xuyen qua bien target -> Range bi cat cut tai zmax)
PART_THR_GEV = "-1.0E-6"     # nguong transport 1 keV (truoc day -1.0E-5 = 10 keV: proton 15 keV chi
                             # duoc theo doi tu 15 -> 10 keV, Range o 15-50 keV hut nang)
MIN_ZMAX_CM = 2.0e-7   # san toi thieu 2 nm, giong ban PHITS

# ---------------------------------------------------------------------------
# Helper dam bao dung field 10-cot fixed-format - THAY THE HOAN TOAN viec go
# tay khoang trang (nguyen nhan loi PART-THR/BEAMPOS truoc do).
# ---------------------------------------------------------------------------
import re


def sci(value: float, decimals: int = 3) -> str:
    """Dinh dang khoa hoc kieu Fortran/FLUKA: KHONG dem so 0 o exponent
    (vd -1.000E-3, khong phai -1.000E-03), de khop dung cach file mau da
    chay thanh cong dang dung (BEAM -1.000E-3 ...)."""
    s = f"{value:.{decimals}E}"
    return re.sub(r"E([+-])0*(\d)", r"E\1\2", s)


def field(value, width=10):
    """So hoac chuoi, right-justify trong o `width` ky tu (dung cho WHAT1..6).
    Neu la float thi dung %.6g; neu can dang khoa hoc kieu Fortran, TRUYEN VAO
    CHUOI DA QUA ham sci() truoc, khong de field() tu format."""
    if isinstance(value, float):
        # giu dang "0.0"/"1.0" (khong phai "0"/"1") de nhat quan voi file mau
        # da chay thanh cong, tranh gay nghi ngo khi doi chieu bang mat
        s = f"{value:.1f}" if value == int(value) else f"{value:.6g}"
    else:
        s = str(value)
    if len(s) > width:
        raise ValueError(f"Gia tri '{s}' dai hon {width} cot - se lam lech dong")
    return s.rjust(width)


def blank(width=10):
    return " " * width


def card_name(name, width=10):
    return name.ljust(width)


def build_material_block(material: str) -> str:
    """MATERIAL (density rieng cua vat lieu nay) + 2 dong COMPOUND, dung dung
    field-width da do duoc tu file mau da chay thanh cong."""
    matname = f"S{material.upper()[1:]}GLASS"  # vd s1 -> S1GLASS (7 ky tu, vua SDUM 8 ky tu)
    mat_line = (
        card_name("MATERIAL") + field(0.0) + field(0.0) + field(DENSITY[material])
        + field(0.0) + blank() + field(0.0) + matname
    )
    items = list(COMPOSITION[material].items())
    lines = [mat_line]
    # COMPOUND: toi da 3 cap (element, fraction) moi dong, giong dung mau goc
    for i in range(0, len(items), 3):
        chunk = items[i:i + 3]
        line = card_name("COMPOUND")
        for elem, frac in chunk:
            line += field(frac) + field(elem)
        # neu dong cuoi thieu du 3 cap, dien 0 cho du field (giong dong 2 cua mau goc)
        missing = 3 - len(chunk)
        for _ in range(missing):
            line += field(0.0) + blank()
        line += matname
        lines.append(line)
    return "\n".join(lines), matname


def estimate_range_for_material(material: str, range_um_srim_table: float) -> float:
    if material == SRIM_TABLE_MATERIAL:
        return range_um_srim_table
    return range_um_srim_table * DENSITY[SRIM_TABLE_MATERIAL] / DENSITY[material]


def load_srim_range_table(path):
    import csv
    xs, ys = [], []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            xs.append(float(row["energy_keV"]))
            ys.append(float(row["range_um"]))
    pairs = sorted(zip(xs, ys))
    xs, ys = zip(*pairs)
    return list(xs), list(ys)


def build_input(material: str, energy_kev: float, range_um_estimate: float) -> str:
    energy_gev = energy_kev / 1.0e6
    zmax_cm = max(SAFETY_MARGIN * range_um_estimate * 1e-4, MIN_ZMAX_CM)
    block_cm = zmax_cm * BLOCK_SAFETY_FACTOR   # lop dem phia sau vung tally
    # BEAMPOS: lui vao VACUUM mot doan TY LE voi zmax (khong dung fixed -1e-4
    # nhu ban sua tay, vi zmax co the rat nho o nang luong thap -> offset co
    # dinh se lon hon ca target). San toi thieu 1e-9 cm de tranh trung bien.
    z0_offset_cm = -max(0.001 * zmax_cm, 1.0e-9)

    material_block, matname = build_material_block(material)
    energy_tag = f"{energy_kev:g}keV".replace(".", "p")
    job_name = f"proton_{material}_{energy_tag}"

    beam_line = (
        card_name("BEAM") + field(sci(-energy_gev, 3)) + field(0.0) + field(0.0)
        + field(0.0) + field(0.0) + field(1.0) + PROJECTILE
    )
    beampos_line = (
        card_name("BEAMPOS") + field(0.0) + field(0.0) + field(sci(z0_offset_cm, 3))
    )
    partthr_line = (
        card_name("PART-THR") + field(PART_THR_GEV) + field(PROJECTILE)
    )
    usrbin_dose_1 = (
        card_name("USRBIN") + field(10.0) + field("DOSE") + field(-21.0)
        + field(1.0) + field(1.0) + field(sci(zmax_cm, 3)) + "TDOSE"
    )
    usrbin_dose_2 = (
        card_name("USRBIN") + field(-1.0) + field(-1.0) + field(0.0)
        + field(1.0) + field(1.0) + field(float(NZ_BINS)) + "&"
    )
    usrbin_flux_1 = (
        card_name("USRBIN") + field(10.0) + field(PROJECTILE) + field(-22.0)
        + field(1.0) + field(1.0) + field(sci(zmax_cm, 3)) + "TFLUX"
    )
    usrbin_flux_2 = (
        card_name("USRBIN") + field(-1.0) + field(-1.0) + field(0.0)
        + field(1.0) + field(1.0) + field(float(NZ_BINS)) + "&"
    )

    content = f"""* ..+....1....+....2....+....3....+....4....+....5....+....6....+....7...
TITLE
MSP + Projected Range - {PROJECTILE} in Glass {material.upper()} @ {energy_kev:g} keV
DEFAULTS                                                              PRECISIO
{beam_line}
{beampos_line}
GEOBEGIN                                                              COMBNAME
    0    0          MSP/Range geometry - 1 khoi {material.upper()} glass
SPH blkbody    0.0 0.0 0.0 300.0
SPH outerbnd   0.0 0.0 0.0 100.0
RPP target     -1.0 1.0 -1.0 1.0 0.0 {sci(block_cm, 4)}
END
BLKHOLE      5 +blkbody -outerbnd
TARGET       5 +target
VACUUM       5 +outerbnd -target
END
GEOEND
* FLUKA 4-5: DEFAULTS PRECISIO bat neutron pointwise (can data/neutron, khong co trong goi .deb) -> tat
LOW-PWXS        -1.0                      BLCKHOLE  @LASTMAT
MATERIAL         5.0       0.0      2.34       0.0                 0.0BORON
MATERIAL        57.0       0.0     6.145       0.0                 0.0LANTHANU
{material_block}
ASSIGNMA    BLCKHOLE   BLKHOLE
{card_name("ASSIGNMA")}{field(matname)}{field("TARGET")}
ASSIGNMA      VACUUM    VACUUM
{partthr_line}
{usrbin_dose_1}
{usrbin_dose_2}
{usrbin_flux_1}
{usrbin_flux_2}
RANDOMIZ         1.0
START      1000000.0                                     0.0
STOP
"""
    return content, job_name


def main(srim_csv: str, out_dir: str):
    xs, ys = load_srim_range_table(srim_csv)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for material in COMPOSITION:
        for energy_kev, range_um_srim in zip(xs, ys):
            range_um_est = estimate_range_for_material(material, range_um_srim)
            content, job_name = build_input(material, energy_kev, range_um_est)
            job_dir = out_dir / job_name
            job_dir.mkdir(parents=True, exist_ok=True)
            # Luon ghi LF (khong de Windows tu doi sang CRLF)
            with open(job_dir / f"{job_name}.inp", "w", newline="\n") as f:
                f.write(content)
            count += 1
            print(f"  [{material}] {energy_kev:>9.2f} keV -> zmax~{SAFETY_MARGIN*range_um_est:.4f} um, "
                  f"block~{SAFETY_MARGIN*BLOCK_SAFETY_FACTOR*range_um_est:.4f} um, nz={NZ_BINS}")

    print(f"\nDa sinh {count} job trong '{out_dir}'.")
    print("LUU Y: MOI verify 1-2 file dau qua flair truoc khi chay hang loat "
          "(kiem tra cot khong bi do/canh bao).")


if __name__ == "__main__":
    srim_csv = sys.argv[1] if len(sys.argv) > 1 else "srim_range_table.csv"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "inputs_fluka"
    main(srim_csv, out_dir)
