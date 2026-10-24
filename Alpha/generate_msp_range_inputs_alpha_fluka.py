"""
Sinh tu dong file .inp FLUKA de tinh MSP(entrance) va Projected Range cho
ALPHA (He-4) trong ca 6 vat lieu (s1..s6). Ban nay la BAN SAO cua
generate_msp_range_inputs_fluka.py (PROTON, DA VERIFY cot bang file chay
THANH CONG proton_s2_1000keV.inp) - moi ham field()/sci()/card_name()/
build_material_block() GIU NGUYEN 100%.

** SUA LON (v2) SAU KHI CHAY THAT BI LOI "Unknown control code: HEAVYION,
   ignored" TREN CA 138/138 JOB **:

  "HEAVYION" KHONG PHAI la ten 1 card doc lap trong FLUKA. Theo dung manual
  FLUKA (card BEAM):
    "For heavy ions, use the name HEAVYION and specify further the ion
     properties by means of option HI-PROPErt." (card that dinh nghia Z/A
     la HI-PROPE, khong phai "HEAVYION")
  VA quy uoc HEAVYION/HI-PROPE do CHI danh cho ion generic co Z > 2 (xem
  bang ma hat FLUKA: "HEAVYION ... Generic heavy ion with Z > 2"). Alpha
  co Z=2, KHONG thuoc dien nay.

  FLUKA co SAN ten hat RIENG cho alpha: "4-HELIUM" (dung y het "PROTON",
  KHONG can khai bao card Z/A nao ca). Theo dung manual:
    "The light nuclei 4He, 3He, triton and deuteron are defined with their
     own names (4-HELIUM, 3-HELIUM, TRITON and DEUTERON) and WHAT(1) will
     be the total kinetic energy or momentum."
  => WHAT(1) cua BEAM la DONG NANG TOAN PHAN (GeV), KHONG chia cho A=4 nhu
  ban v1 tuong nham (do quy tac per-nucleon CHI ap dung cho HEAVYION/
  HI-PROPE generic Z>2, khong ap dung cho "4-HELIUM").

  => XOA HAN card HEAVYION. SDUM dung "4-HELIUM" cho BEAM/PART-THR/USRBIN,
  y het cach dung "PROTON" cua ban goc - logic don gian hon nhieu so voi v1.

CHI CON 2 KHAC BIET THAT SU so voi ban proton (sau khi bo HEAVYION):

  1. THEM lop dem an toan cho RPP "target": be day khoi = BLOCK_SAFETY_FACTOR
     x zmax tally (mac dinh 5x), thay vi RPP = dung zmax tally nhu ban
     proton. Ly do: Bragg peak cua alpha rat nhon, can dam bao alpha dung
     han HOAN TOAN ben trong khoi truoc khi cham bien VACUUM.

  2. NZ_BINS = 200 (thay vi 300 ben proton) - khop mesh da dung khi doi
     chieu voi file PHITS alpha_s6_100keV da confirm truoc do.

  CANH BAO CHUA VERIFY: van CHUA co file .inp alpha nao chay thanh cong
  tren FLUKA that voi cach sua nay ("4-HELIUM"). Van PHAI chay THU 1 job
  qua flair/FLUKA that truoc khi tin va submit hang loat.

** SUA LON (v3) - BO SCALING THEO MAT DO, DUNG THANG RANGE SRIM RIENG CHO
   TUNG VAT LIEU **:

  Ban v2 uoc luong range cho s1..s5 bang cach lay range SRIM cua s6 roi
  nhan ty le mat do (s6/material). Cach nay GIA DINH s1..s6 chi khac nhau
  ve mat do, bo qua khac biet thanh phan (ty le Lanthanum tang manh tu s1
  -> s6, Boron/Oxygen giam dan) - co the gay sai so he thong, dac biet cho
  cac vat lieu cach xa s6 ve thanh phan (nhu s1).

  => v3: CSV dau vao gio co RIENG 1 cot range cho MOI vat lieu (s1..s6),
  lay THANG tu SRIM cho tung vat lieu - KHONG con scale qua mat do nua.
  Ham estimate_range_for_material() va SRIM_TABLE_MATERIAL da bi XOA.

Cach dung (giong het ban proton, nhung can bang SRIM/stopping-range RIENG
cho ALPHA - KHONG duoc dung chung srim_range_table.csv cua proton):
  1. Chuan bi srim_range_table_alpha.csv voi cac cot:
         energy_keV, s1, s2, s3, s4, s5, s6
     moi cot s1..s6 la range (um) CUA ALPHA lay THANG tu SRIM cho DUNG
     vat lieu do (khong suy tu s6 nua).
  2. python generate_msp_range_inputs_alpha_fluka.py srim_range_table_alpha.csv inputs_fluka_alpha/

Sau khi sinh xong, moi job la 1 thu muc rieng chua 1 file .inp - MOI verify
1-2 job dau qua flair (kiem tra bang mat, khong co o do, xem BEAM/PART-THR/
USRBIN dung "4-HELIUM" khong bi lech cot) TRUOC khi chay thu 1 job qua FLUKA
that, va CHI submit toan bo grid 6 vat lieu x N nang luong SAU KHI da doi
chieu duoc it nhat 1 ket qua voi PHITS.
"""
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Thanh phan + mat do - GIONG HET ban proton (generate_msp_range_inputs_fluka.py)
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

PROJECTILE_SDUM = "4-HELIUM"    # ALPHA: ten hat RIENG cua FLUKA cho He-4 (khong phai HEAVYION)

NZ_BINS = 500                   # ALPHA: so bin doc truc z cho 2 USRBIN (dose + flux)
SAFETY_MARGIN = 1.6             # he so mesh zmax = SAFETY_MARGIN x range uoc luong (giong het ban proton)
BLOCK_SAFETY_FACTOR = 5.0       # ALPHA: be day KHOI target = BLOCK_SAFETY_FACTOR x zmax tally (rieng cho alpha)
MIN_ZMAX_CM = 2.0e-7            # san toi thieu 2 nm, giong ban proton/PHITS

# ---------------------------------------------------------------------------
# Helper fixed-column 10-cot - GIONG HET ban proton, KHONG SUA (da verify).
# ---------------------------------------------------------------------------
import re


def sci(value: float, decimals: int = 3) -> str:
    """Dinh dang khoa hoc kieu Fortran/FLUKA: KHONG dem so 0 o exponent
    (vd -1.000E-3, khong phai -1.000E-03)."""
    s = f"{value:.{decimals}E}"
    return re.sub(r"E([+-])0*(\d)", r"E\1\2", s)


def field(value, width=10):
    """So hoac chuoi, right-justify trong o `width` ky tu (dung cho WHAT1..6).
    Neu can dang khoa hoc kieu Fortran, TRUYEN VAO CHUOI DA QUA ham sci()."""
    if isinstance(value, float):
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
    """MATERIAL (density rieng cua vat lieu nay) + 2 dong COMPOUND - GIONG HET
    ban proton, khong lien quan gi den loai particle."""
    matname = f"S{material.upper()[1:]}GLASS"
    mat_line = (
        card_name("MATERIAL") + field(0.0) + field(0.0) + field(DENSITY[material])
        + field(0.0) + blank() + field(0.0) + matname
    )
    items = list(COMPOSITION[material].items())
    lines = [mat_line]
    for i in range(0, len(items), 3):
        chunk = items[i:i + 3]
        line = card_name("COMPOUND")
        for elem, frac in chunk:
            line += field(frac) + field(elem)
        missing = 3 - len(chunk)
        for _ in range(missing):
            line += field(0.0) + blank()
        line += matname
        lines.append(line)
    return "\n".join(lines), matname


def load_srim_range_table(path):
    """Doc CSV co 1 cot energy_keV + 6 cot rieng s1..s6 (range um cua ALPHA,
    lay THANG tu SRIM cho DUNG vat lieu do - KHONG scale qua mat do nua).

    Tra ve: energies (list, da sap xep tang dan) + dict {material: [range_um,...]}
    voi thu tu range_um khop voi thu tu energies.
    """
    import csv
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        missing_cols = [m for m in COMPOSITION if m not in reader.fieldnames]
        if missing_cols:
            raise ValueError(
                f"CSV '{path}' thieu cot cho vat lieu: {missing_cols}. "
                f"Can du 6 cot: energy_keV, {', '.join(COMPOSITION)}"
            )
        for row in reader:
            rows.append(row)

    rows.sort(key=lambda r: float(r["energy_keV"]))
    energies = [float(r["energy_keV"]) for r in rows]
    ranges_by_material = {
        material: [float(r[material]) for r in rows] for material in COMPOSITION
    }
    return energies, ranges_by_material


def build_input(material: str, energy_kev: float, range_um_estimate: float) -> str:
    energy_gev_total = energy_kev / 1.0e6   # ALPHA (v2): TOAN PHAN, KHONG chia cho A
                                             # (quy tac chia A chi ap dung cho HEAVYION/
                                             #  HI-PROPE generic Z>2, khong ap dung "4-HELIUM")

    # zmax cua 2 USRBIN (dose + flux) = 5x range uoc luong tu SRIM, de vung tally
    # du rong chua het duoi Bragg peak (tranh cat cut alpha o bin cuoi).
    TALLY_SAFETY_FACTOR = 7.0
    tally_zmax_cm = max(TALLY_SAFETY_FACTOR * range_um_estimate * 1e-4, MIN_ZMAX_CM)

    # zmax dung de tinh be day KHOI target (RPP) van GIU SAFETY_MARGIN + BLOCK_SAFETY_FACTOR
    # nhu cu, de dam bao alpha dung han HOAN TOAN ben trong khoi truoc khi cham VACUUM,
    # ke ca khi range uoc luong tu SRIM hoi thap hon thuc te.
    block_zmax_cm = max(SAFETY_MARGIN * range_um_estimate * 1e-4, MIN_ZMAX_CM)
    block_cm = block_zmax_cm * BLOCK_SAFETY_FACTOR   # ALPHA: lop dem an toan phia sau vung tally
    z0_offset_cm = -max(0.001 * block_zmax_cm, 1.0e-9)

    material_block, matname = build_material_block(material)
    energy_tag = f"{energy_kev:g}keV".replace(".", "p")
    job_name = f"alpha_{material}_{energy_tag}"

    beam_line = (
        card_name("BEAM") + field(sci(-energy_gev_total, 3)) + field(0.0) + field(0.0)
        + field(0.0) + field(0.0) + field(1.0) + PROJECTILE_SDUM
    )
    beampos_line = (
        card_name("BEAMPOS") + field(0.0) + field(0.0) + field(sci(z0_offset_cm, 3))
    )
    partthr_line = (
        card_name("PART-THR") + field("-1.0E-5") + field(PROJECTILE_SDUM)
    )
    usrbin_dose_1 = (
        card_name("USRBIN") + field(10.0) + field("DOSE") + field(-21.0)
        + field(1.0) + field(1.0) + field(sci(tally_zmax_cm, 3)) + "TDOSE"
    )
    usrbin_dose_2 = (
        card_name("USRBIN") + field(-1.0) + field(-1.0) + field(0.0)
        + field(1.0) + field(1.0) + field(float(NZ_BINS)) + "&"
    )
    usrbin_flux_1 = (
        card_name("USRBIN") + field(10.0) + field(PROJECTILE_SDUM) + field(-22.0)
        + field(1.0) + field(1.0) + field(sci(tally_zmax_cm, 3)) + "TFLUX"
    )
    usrbin_flux_2 = (
        card_name("USRBIN") + field(-1.0) + field(-1.0) + field(0.0)
        + field(1.0) + field(1.0) + field(float(NZ_BINS)) + "&"
    )

    content = f"""* ..+....1....+....2....+....3....+....4....+....5....+....6....+....7...
TITLE
MSP + Projected Range - ALPHA (4-HELIUM) in Glass {material.upper()} @ {energy_kev:g} keV
DEFAULTS                                                              PRECISIO
{beam_line}
{beampos_line}
GEOBEGIN                                                              COMBNAME
    0    0          MSP/Range geometry - 1 khoi {material.upper()} glass (alpha, co lop dem block)
SPH blkbody    0.0 0.0 0.0 300.0
SPH outerbnd   0.0 0.0 0.0 100.0
RPP target     -1.0 1.0 -1.0 1.0 0.0 {sci(block_cm, 4)}
END
BLKHOLE      5 +blkbody -outerbnd
TARGET       5 +target
VACUUM       5 +outerbnd -target
END
GEOEND
MATERIAL         5.0    10.811      2.34       0.0                 0.0BORON
MATERIAL        57.0   138.905     6.145       0.0                 0.0LANTHANU
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
    energies, ranges_by_material = load_srim_range_table(srim_csv)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for material in COMPOSITION:
        for energy_kev, range_um_est in zip(energies, ranges_by_material[material]):
            # range_um_est gio lay THANG tu SRIM cua chinh vat lieu nay,
            # khong con suy tu s6 qua ty le mat do nua.
            content, job_name = build_input(material, energy_kev, range_um_est)
            job_dir = out_dir / job_name
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / f"{job_name}.inp").write_text(content)
            count += 1
            tally_zmax_um = max(5.0 * range_um_est, MIN_ZMAX_CM * 1e4)
            block_zmax_um = max(SAFETY_MARGIN * range_um_est, MIN_ZMAX_CM * 1e4)
            print(f"  [{material}] {energy_kev:>9.2f} keV -> USRBIN zmax~{tally_zmax_um:.4f} um, "
                  f"block~{block_zmax_um*BLOCK_SAFETY_FACTOR:.4f} um, nz={NZ_BINS}")

    print(f"\nDa sinh {count} job trong '{out_dir}'.")
    print("LUU Y: file alpha CHUA duoc xac nhan chay thanh cong tren FLUKA that voi")
    print("  cach sua 'HEAVYION -> 4-HELIUM' nay (v2).")
    print("  1. Mo 1-2 file dau qua flair, kiem tra bang mat (khong co o do,")
    print("     dac biet la BEAM/PART-THR/USRBIN dung '4-HELIUM' khong bi lech cot).")
    print("  2. Chay THU 1 job qua rfluka THAT (khong qua run_batch_fluka.py) de")
    print("     xem log day du truoc khi tin.")
    print("  3. Chay THU 1 job, doi chieu MSP/Range voi ket qua PHITS alpha")
    print("     da confirm truoc khi submit toan bo grid.")


if __name__ == "__main__":
    srim_csv = sys.argv[1] if len(sys.argv) > 1 else "srim_range_table_alpha.csv"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "inputs_fluka_alpha"
    main(srim_csv, out_dir)
