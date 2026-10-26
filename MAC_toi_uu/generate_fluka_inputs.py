"""
Sinh tu dong file .inp cho FLUKA (ca 2 truong hop: CO sample va KHONG sample/blank)
tu bang be day (Energy x s1..s6) trong Excel, khop dung format 2 file .inp mau:
    - s1_100keV.inp        (co sample)
    - nosample_662keV.inp  (khong sample / blank, dung de tinh I0)

Chay:
    python generate_fluka_inputs.py thickness_table.xlsx fluka_inputs/

Excel input phai co cot "Energy" (keV) va cac cot s1..s6 (be day mau, DON VI cm).
NHIEU BE DAY cho cung 1 nang luong: dung 1 trong 2 cach (co the ket hop):
  - ghi nhieu so trong 1 o, cach nhau boi dau ";" hoac "," (vd: 0.5; 1; 2)
  - them nhieu hang co cung gia tri Energy
O de trong = bo qua. Cot vat lieu khong co trong COMPOSITION/DENSITY se bi BO
QUA kem canh bao.

Moi job duoc ghi ra 1 thu muc rieng, chua 1 file .inp:
    {mat}_{E}keV_t{be_day}cm    (vd s1_662keV_t0p5cm, dau "." doi thanh "p")
    blank_{E}keV_t{be_day}cm    (blank CUNG be day, xem ben duoi)

Hinh hoc (khop 2 file .inp mau, khong doi):
  - Nguon diem tai z=0 (SPH source, r=1.0), collimator 1 chi (Pb, r_ngoai=1.0,
    lo r=0.25) tu z=2.0 -> z=12.0.
  - Mau (SAMPREG) bat dau tai z=12.0, day = thickness_cm (RCC, ban kinh 2.5).
  - Collimator 2 (Pb) dai 10.0 cm ngay sau mau, cung ban kinh nhu collimator 1.
  - Dau do NaI(Tl) (DETECTOR, RCC ban kinh 5.0) dai 5.0 cm ngay sau collimator 2.
  - outerbnd (SPH r=100.0) va blkbody (SPH r=300.0) bao ngoai cung.
  - Tally: USRBDX (fluence xuyen qua mat truoc dau do, quy USRBDX area = pi*0.25^2)
    + USRTRACK (fluence trong the tich dau do, V = pi*5^2*5 = 392.7 cm^3).

File BLANK (khong sample) dung de tinh I0 (fluence khong suy giam). Vi
collimator 2 va dau do LUI THEO be day mau, blank duoc sinh RIENG cho tung be
day: giu nguyen vi tri collimator 2 / dau do nhu job co mau, cho trong cua mau
de chan khong -> I va I0 cung hinh hoc, chi khac co/khong co mau.
"""
import sys
import math
import pandas as pd
from pathlib import Path

# ----------------------------------------------------------------------------
# Thanh phan khoi luong (wt fraction, am = FLUKA COMPOUND). Dung chung so lieu
# voi ban PHITS (generate_inputs.py), chi doi ten nguyen to sang dang FLUKA.
# Thu tu nguyen to co dinh: BORON, OXYGEN, SILICON, CALCIUM, LANTHANU
# (OXYGEN, SILICON, CALCIUM la vat lieu co san trong FLUKA, khong can dinh nghia
#  MATERIAL rieng; chi BORON va LANTHANU can MATERIAL rieng vi khong phai
#  ten chuan FLUKA don gian).
COMPOSITION = {
    "s1": {"BORON": -0.16287, "OXYGEN": -0.46483, "SILICON": -0.03022, "CALCIUM": -0.04313, "LANTHANU": -0.29896},
    "s2": {"BORON": -0.1329,  "OXYGEN": -0.4086,  "SILICON": -0.0266,  "CALCIUM": -0.0379,  "LANTHANU": -0.3941},
    "s3": {"BORON": -0.1095,  "OXYGEN": -0.3644,  "SILICON": -0.0237,  "CALCIUM": -0.0338,  "LANTHANU": -0.4688},
    "s4": {"BORON": -0.0905,  "OXYGEN": -0.3289,  "SILICON": -0.0214,  "CALCIUM": -0.0305,  "LANTHANU": -0.5288},
    "s5": {"BORON": -0.0750,  "OXYGEN": -0.2996,  "SILICON": -0.0195,  "CALCIUM": -0.0278,  "LANTHANU": -0.5783},
    "s6": {"BORON": -0.0620,  "OXYGEN": -0.2752,  "SILICON": -0.0179,  "CALCIUM": -0.0255,  "LANTHANU": -0.6195},
}
DENSITY = {"s1": 3.0099, "s2": 3.1999, "s3": 3.3899, "s4": 3.5799, "s5": 3.7699, "s6": 3.9599}

# ----------------------------------------------------------------------------
# Hinh hoc co dinh (khop file .inp mau), chi z_sample_back (mat sau mau) va cac
# mat theo sau doi theo be day.
Z_COLLIM1_FRONT = 2.0
Z_COLLIM1_BACK = 12.0     # = mat truoc mau
COLLIM2_LEN = 10.0
DET_LEN = 5.0
COLL_OUTER_R = 1.0
COLL_HOLE_R = 0.25        # cung ban kinh cho ca 2 collimator
SAMPLE_R = 2.5
DET_R = 5.0
SOURCE_R = 1.0
OUTERBND_R = 100.0
BLKBODY_R = 300.0

USRBDX_AREA = round(math.pi * COLL_HOLE_R ** 2, 5)       # 0.19635 cm^2 (mat cat lo chuan truc)
USRTRACK_VOL = round(math.pi * DET_R ** 2 * DET_LEN, 1)  # 392.7 cm^3 (the tich dau do)

MAXCAS = 1000000.0

# ----------------------------------------------------------------------------
# Khoang nang luong (emin/emax) cho USRBDX/USRTRACK: truoc day co dinh tuyet doi
# (1.7E-2 / 4.0E-5 GeV = 40-17000 keV) nen voi nguon nang luong thap (vd 15 keV)
# thi khoang nay nam ngoai vung co du lieu (qua cham/vo nghia), con voi nguon
# nang luong cao (vd 15000 keV) thi lai qua hep so voi dinh nang luong.
# -> Chuyen sang tinh theo % cua nang luong nguon (e0), giong dung logic
#    PEAK_FRACTION da dung ben ban PHITS (T-Track spectrum near peak).
TALLY_LOW_FRACTION = 0.9      # emin = 90% e0 (bat dau ngay duoi dinh)
TALLY_HIGH_FACTOR = 1.05      # emax = 105% e0 (du de bat tron bin chua dinh)
TALLY_EMIN_FLOOR_GEV = 1.0E-7  # san duoi tuyet doi (0.1 keV), tranh emin~0 khi e0 rat nho
TALLY_NE = 100                 # so bin nang luong (USRBDX). USRTRACK dung so bin rieng (xem ne_usrtrack)


def tally_range_gev(energy_kev: float):
    """Tra ve (emax_gev, emin_gev) cho USRBDX/USRTRACK, ti le theo nang luong
    nguon e0 thay vi hang so tuyet doi co dinh."""
    e0_gev = energy_kev * 1e-6
    emin = max(TALLY_EMIN_FLOOR_GEV, TALLY_LOW_FRACTION * e0_gev)
    emax = TALLY_HIGH_FACTOR * e0_gev
    return emax, emin


# ----------------------------------------------------------------------------
def fnum(x):
    """Dinh dang so cho truong 10 ky tu (fixed-field FLUKA WHAT card)."""
    if x == 0:
        return "0.0"
    if isinstance(x, (int, float)) and float(x) == int(x) and abs(x) < 1e7:
        s = f"{float(x):.1f}"
    else:
        s = f"{x:.6g}"
    if len(s) > 10:
        s = f"{x:.3E}"
    return s


def whatline(name, whats, sdum=""):
    """1 dong the (card) FLUKA fixed-format: ten (10) + dung 6 truong WHAT
    (moi truong 10 ky tu, can phai, thieu thi de trong) + SDUM noi tiep tai
    cot 71 (khop dung format 2 file .inp mau)."""
    whats = list(whats) + [None] * (6 - len(whats))
    line = f"{name:<10}"
    for w in whats[:6]:
        if w is None:
            line += " " * 10
        else:
            line += f"{fnum(w) if not isinstance(w, str) else w:>10}"
    line += sdum
    return line if sdum else line.rstrip()


def compound_lines(comp: dict, mat_name: str) -> str:
    """Sinh 2 dong COMPOUND (toi da 3 cap gia-tri/ten moi dong) tu dict
    {ten_nguyen_to: ty_le_trong_luong}, khop dung thu tu B,O,Si,Ca,La."""
    order = ["BORON", "OXYGEN", "SILICON", "CALCIUM", "LANTHANU"]
    pairs = [(comp[e], e) for e in order]
    line1 = whatline("COMPOUND", [pairs[0][0], pairs[0][1], pairs[1][0], pairs[1][1],
                                   pairs[2][0], pairs[2][1]], sdum=mat_name)
    line2 = whatline("COMPOUND", [pairs[3][0], pairs[3][1], pairs[4][0], pairs[4][1],
                                   0, None], sdum=mat_name)
    return line1 + "\n" + line2


def beam_energy_gev(energy_kev: float) -> float:
    """FLUKA BEAM: nang luong am (GeV) = -E(keV) * 1e-6."""
    return -(energy_kev * 1e-6)


# ----------------------------------------------------------------------------
def build_sample_input(mat: str, energy_kev: float, thickness_cm: float) -> str:
    mat_upper = mat.upper()
    mat_name = f"{mat_upper}GLASS"
    energy_kev_int = int(round(energy_kev))
    e0_gev = beam_energy_gev(energy_kev)

    z_sample_front = Z_COLLIM1_BACK
    z_sample_back = z_sample_front + thickness_cm
    z_coll2_front = z_sample_back
    z_det_front = z_coll2_front + COLLIM2_LEN

    lines = []
    lines.append("* ..+....1....+....2....+....3....+....4....+....5....+....6....+....7...")
    lines.append("TITLE")
    lines.append(f"Gamma attenuation - I (WITH {mat_upper} glass sample) - {energy_kev_int} keV")
    lines.append(whatline("DEFAULTS", [], sdum="PRECISIO"))
    lines.append(whatline("BEAM", [e0_gev, 0.0, 0.0, 0.0, 0.0, 1.0], sdum="PHOTON"))
    lines.append(whatline("BEAMPOS", [0.0, 0.0, 0.0]))
    lines.append(whatline("GEOBEGIN", [], sdum="COMBNAME"))
    lines.append(f"    0    0          Attenuation geometry - WITH {mat_upper} sample")
    lines.append(f"SPH blkbody    0.0 0.0 0.0 {BLKBODY_R}")
    lines.append(f"SPH outerbnd   0.0 0.0 0.0 {OUTERBND_R}")
    lines.append(f"SPH source     0.0 0.0 0.0 {SOURCE_R}")
    lines.append(f"RCC coll1o     0.0 0.0 {Z_COLLIM1_FRONT:.6f} 0.0 0.0 {(Z_COLLIM1_BACK - Z_COLLIM1_FRONT):.6f} {COLL_OUTER_R}")
    lines.append(f"RCC coll1i     0.0 0.0 {Z_COLLIM1_FRONT:.6f} 0.0 0.0 {(Z_COLLIM1_BACK - Z_COLLIM1_FRONT):.6f} {COLL_HOLE_R}")
    lines.append(f"RCC sample     0.0 0.0 {z_sample_front:.6f} 0.0 0.0 {thickness_cm:.6f} {SAMPLE_R}")
    lines.append(f"RCC coll2o     0.0 0.0 {z_coll2_front:.6f} 0.0 0.0 {COLLIM2_LEN:.6f} {COLL_OUTER_R}")
    lines.append(f"RCC coll2i     0.0 0.0 {z_coll2_front:.6f} 0.0 0.0 {COLLIM2_LEN:.6f} {COLL_HOLE_R}")
    lines.append(f"RCC detect     0.0 0.0 {z_det_front:.6f} 0.0 0.0 {DET_LEN:.6f} {DET_R}")
    lines.append("END")
    lines.append("BLKHOLE      5 +blkbody -outerbnd")
    lines.append("SOURCE       5 +source")
    lines.append("COLLIM1      5 +coll1o -coll1i -source")
    lines.append("HOLE1        5 +coll1i -source")
    lines.append("SAMPREG      5 +sample")
    lines.append("COLLIM2      5 +coll2o -coll2i")
    lines.append("HOLE2        5 +coll2i")
    lines.append("DETECTOR     5 +detect")
    lines.append("VACUUM       5 +outerbnd -coll1o -sample -coll2o -detect -source")
    lines.append("END")
    lines.append("GEOEND")
    # FLUKA 4-5: DEFAULTS PRECISIO bat neutron pointwise (can data/neutron, khong co trong goi .deb) -> tat
    lines.append("* Tat neutron pointwise (FLUKA 4-5 can data/neutron) -> dung multigroup")
    lines.append(whatline("LOW-PWXS", [-1.0, None, None, "BLCKHOLE", "@LASTMAT"]))
    lines.append(whatline("MATERIAL", [5.0, 0.0, 2.34, 0.0, None, 0.0], sdum="BORON"))
    lines.append(whatline("MATERIAL", [57.0, 0.0, 6.145, 0.0, None, 0.0], sdum="LANTHANU"))
    lines.append(whatline("MATERIAL", [53.0, 0.0, 4.93, 0.0, None, 0.0], sdum="IODINE"))
    lines.append(whatline("MATERIAL", [0.0, 0.0, DENSITY[mat], 0.0, None, 0.0], sdum=mat_name))
    lines.append(compound_lines(COMPOSITION[mat], mat_name))
    lines.append(whatline("MATERIAL", [0.0, 0.0, 3.67, 0.0, None, 0.0], sdum="NAIIOD"))
    lines.append(whatline("COMPOUND", [-0.15337, "SODIUM", -0.84663, "IODINE", 0.0, None], sdum="NAIIOD"))
    lines.append(whatline("ASSIGNMA", ["BLCKHOLE", "BLKHOLE"]))
    lines.append(whatline("ASSIGNMA", ["AIR", "SOURCE"]))
    lines.append(whatline("ASSIGNMA", ["LEAD", "COLLIM1"]))
    lines.append(whatline("ASSIGNMA", ["VACUUM", "HOLE1"]))
    lines.append(whatline("ASSIGNMA", [mat_name, "SAMPREG"]))
    lines.append(whatline("ASSIGNMA", ["LEAD", "COLLIM2"]))
    lines.append(whatline("ASSIGNMA", ["VACUUM", "HOLE2"]))
    lines.append(whatline("ASSIGNMA", ["NAIIOD", "DETECTOR"]))
    lines.append(whatline("ASSIGNMA", ["VACUUM", "VACUUM"]))
    lines.append(whatline("PHOTONUC", [1.0, None, None, "BLCKHOLE", "@LASTMAT"]))
    lines.append(whatline("EMFCUT", [-1.0E-4, 1.0E-6, 1.0, 1.0, "@LASTMAT", 1.0], sdum="PROD-CUT"))
    lines.append(whatline("EMFCUT", [-1.0E-4, 1.0E-6, 0.0, "BLKHOLE", "@LASTREG", 1.0]))
    lines.append(whatline("USRBDX", [99.0, "PHOTON", -22.0, "HOLE2", "DETECTOR", USRBDX_AREA], sdum="I0ph1"))
    emax_gev, emin_gev = tally_range_gev(energy_kev)
    lines.append(whatline("USRBDX", [emax_gev, emin_gev, float(TALLY_NE)], sdum="&"))
    lines.append(whatline("USRTRACK", [-1.0, "PHOTON", -23.0, "DETECTOR", USRTRACK_VOL, 110.0], sdum="Itrk1"))
    lines.append(whatline("USRTRACK", [emax_gev, emin_gev], sdum="&"))
    lines.append(whatline("RANDOMIZ", [1.0]))
    lines.append(whatline("START", [MAXCAS, None, None, None, 0.0]))
    lines.append("STOP")
    return "\n".join(lines) + "\n"


def build_blank_input(energy_kev: float, thickness_cm: float) -> str:
    """File khong sample (blank), dung de xac dinh I0. Collimator 2 va dau do
    dat DUNG vi tri nhu job co mau cung be day (thickness_cm), cho cua mau la
    chan khong (thuoc vung VACUUM)."""
    energy_kev_int = int(round(energy_kev))
    e0_gev = beam_energy_gev(energy_kev)

    z_coll2_front = Z_COLLIM1_BACK + thickness_cm
    z_det_front = z_coll2_front + COLLIM2_LEN

    lines = []
    lines.append("* ..+....1....+....2....+....3....+....4....+....5....+....6....+....7...")
    lines.append("TITLE")
    lines.append(f"Gamma attenuation - I0 (NO sample, gap {thickness_cm:g} cm) - {energy_kev_int}keV")
    lines.append(whatline("DEFAULTS", [], sdum="PRECISIO"))
    lines.append(whatline("BEAM", [e0_gev, 0.0, 0.0, 0.0, 0.0, 1.0], sdum="PHOTON"))
    lines.append(whatline("BEAMPOS", [0.0, 0.0, 0.0]))
    lines.append(whatline("GEOBEGIN", [], sdum="COMBNAME"))
    lines.append("    0    0          Attenuation geometry - NO sample")
    lines.append(f"SPH blkbody    0.0 0.0 0.0 {BLKBODY_R}")
    lines.append(f"SPH outerbnd   0.0 0.0 0.0 {OUTERBND_R}")
    lines.append(f"SPH source     0.0 0.0 0.0 {SOURCE_R}")
    lines.append(f"RCC coll1o     0.0 0.0 {Z_COLLIM1_FRONT} 0.0 0.0 {(Z_COLLIM1_BACK - Z_COLLIM1_FRONT)} {COLL_OUTER_R}")
    lines.append(f"RCC coll1i     0.0 0.0 {Z_COLLIM1_FRONT} 0.0 0.0 {(Z_COLLIM1_BACK - Z_COLLIM1_FRONT)} {COLL_HOLE_R}")
    lines.append(f"RCC coll2o     0.0 0.0 {z_coll2_front:.6f} 0.0 0.0 {COLLIM2_LEN:.6f} {COLL_OUTER_R}")
    lines.append(f"RCC coll2i     0.0 0.0 {z_coll2_front:.6f} 0.0 0.0 {COLLIM2_LEN:.6f} {COLL_HOLE_R}")
    lines.append(f"RCC detect     0.0 0.0 {z_det_front:.6f} 0.0 0.0 {DET_LEN:.6f} {DET_R}")
    lines.append("END")
    lines.append("BLKHOLE      5 +blkbody -outerbnd")
    lines.append("SOURCE       5 +source")
    lines.append("COLLIM1      5 +coll1o -coll1i -source")
    lines.append("HOLE1        5 +coll1i -source")
    lines.append("COLLIM2      5 +coll2o -coll2i")
    lines.append("HOLE2        5 +coll2i")
    lines.append("DETECTOR     5 +detect")
    lines.append("VACUUM       5 +outerbnd -coll1o -coll2o -detect -source")
    lines.append("END")
    lines.append("GEOEND")
    # FLUKA 4-5: DEFAULTS PRECISIO bat neutron pointwise (can data/neutron, khong co trong goi .deb) -> tat
    lines.append("* Tat neutron pointwise (FLUKA 4-5 can data/neutron) -> dung multigroup")
    lines.append(whatline("LOW-PWXS", [-1.0, None, None, "BLCKHOLE", "@LASTMAT"]))
    lines.append(whatline("MATERIAL", [5.0, 0.0, 2.34, 0.0, None, 0.0], sdum="BORON"))
    lines.append(whatline("MATERIAL", [57.0, 0.0, 6.145, 0.0, None, 0.0], sdum="LANTHANU"))
    lines.append(whatline("MATERIAL", [53.0, 0.0, 4.93, 0.0, None, 0.0], sdum="IODINE"))
    lines.append(whatline("MATERIAL", [0.0, 0.0, 3.67, 0.0, None, 0.0], sdum="NAIIOD"))
    lines.append(whatline("COMPOUND", [-0.15337, "SODIUM", -0.84663, "IODINE", 0.0, None], sdum="NAIIOD"))
    lines.append(whatline("ASSIGNMA", ["BLCKHOLE", "BLKHOLE"]))
    lines.append(whatline("ASSIGNMA", ["AIR", "SOURCE"]))
    lines.append(whatline("ASSIGNMA", ["LEAD", "COLLIM1"]))
    lines.append(whatline("ASSIGNMA", ["VACUUM", "HOLE1"]))
    lines.append(whatline("ASSIGNMA", ["LEAD", "COLLIM2"]))
    lines.append(whatline("ASSIGNMA", ["VACUUM", "HOLE2"]))
    lines.append(whatline("ASSIGNMA", ["NAIIOD", "DETECTOR"]))
    lines.append(whatline("ASSIGNMA", ["VACUUM", "VACUUM"]))
    lines.append(whatline("PHOTONUC", [1.0, None, None, "BLCKHOLE", "@LASTMAT"]))
    lines.append(whatline("EMFCUT", [-1.0E-4, 1.0E-6, 1.0, 1.0, "@LASTMAT", 1.0], sdum="PROD-CUT"))
    lines.append(whatline("EMFCUT", [-1.0E-4, 1.0E-6, 0.0, "BLKHOLE", "@LASTREG", 1.0]))
    lines.append(whatline("USRBDX", [99.0, "PHOTON", -22.0, "HOLE2", "DETECTOR", USRBDX_AREA], sdum="I0ph1"))
    emax_gev, emin_gev = tally_range_gev(energy_kev)
    lines.append(whatline("USRBDX", [emax_gev, emin_gev, float(TALLY_NE)], sdum="&"))
    lines.append(whatline("USRTRACK", [-1.0, "PHOTON", -23.0, "DETECTOR", USRTRACK_VOL, 110.0], sdum="Itrk1"))
    lines.append(whatline("USRTRACK", [emax_gev, emin_gev], sdum="&"))
    lines.append(whatline("RANDOMIZ", [1.0]))
    lines.append(whatline("START", [MAXCAS, None, None, None, 0.0]))
    lines.append("STOP")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------
def thickness_tag(thickness_cm: float) -> str:
    """Be day -> chuoi trong ten job: 0.5 -> '0p5', 8.652004 -> '8p652'."""
    return f"{thickness_cm:g}".replace(".", "p")


def sample_job_name(mat: str, energy_kev: float, thickness_cm: float) -> str:
    return f"{mat}_{int(round(energy_kev))}keV_t{thickness_tag(thickness_cm)}cm"


def blank_job_name(energy_kev: float, thickness_cm: float) -> str:
    return f"blank_{int(round(energy_kev))}keV_t{thickness_tag(thickness_cm)}cm"


def parse_thickness_cell(value) -> list:
    """1 o Excel -> danh sach be day (cm). Nhan so, hoac chuoi nhieu so cach
    nhau boi ';' / ','. O trong -> []."""
    if pd.isna(value):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    parts = str(value).replace(",", ";").split(";")
    return [float(p) for p in (s.strip() for s in parts) if p]


def read_thickness_jobs(excel_path: str):
    """Doc bang be day, tra ve (jobs, skipped):
      jobs    : danh sach (energy_kev, mat, thickness_cm) khong trung, giu thu tu
      skipped : cac cot vat lieu bi bo qua vi chua co trong COMPOSITION/DENSITY
    Dung chung cho generate_fluka_inputs.py va parse_fluka_results.py de ten
    job luon khop nhau."""
    df = pd.read_excel(excel_path)
    columns = [c for c in df.columns if str(c).lower() != "energy"]
    materials = [c for c in columns if c in COMPOSITION and c in DENSITY]
    skipped = [c for c in columns if c not in materials]

    jobs, seen = [], set()
    for _, row in df.iterrows():
        if pd.isna(row["Energy"]):
            continue
        energy_kev = float(row["Energy"])
        for mat in materials:
            for thickness in parse_thickness_cell(row[mat]):
                name = sample_job_name(mat, energy_kev, thickness)
                if name not in seen:
                    seen.add(name)
                    jobs.append((energy_kev, mat, thickness))
    return jobs, skipped


def write_input(out_dir: Path, job_name: str, content: str):
    job_dir = out_dir / job_name
    job_dir.mkdir(parents=True, exist_ok=True)
    # Luon ghi LF (tranh CRLF khi chay bang Python tren Windows)
    with open(job_dir / f"{job_name}.inp", "w", newline="\n") as f:
        f.write(content)


def main(excel_path: str, out_dir: str):
    jobs, skipped = read_thickness_jobs(excel_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if skipped:
        print(f"CANH BAO: bo qua cot {skipped} - chua khai bao thanh phan trong "
              f"COMPOSITION/DENSITY (them vao dau file nay neu can chay).")

    blanks = set()
    for energy_kev, mat, thickness in jobs:
        write_input(out_dir, sample_job_name(mat, energy_kev, thickness),
                    build_sample_input(mat, energy_kev, thickness))
        # 1 blank / (nang luong, be day), dung chung cho moi vat lieu co cung be day
        blank_name = blank_job_name(energy_kev, thickness)
        if blank_name not in blanks:
            blanks.add(blank_name)
            write_input(out_dir, blank_name, build_blank_input(energy_kev, thickness))

    print(f"Da sinh {len(jobs) + len(blanks)} job FLUKA (moi job 1 thu muc rieng) "
          f"trong '{out_dir}' ({len(jobs)} job co mau + {len(blanks)} blank)")


if __name__ == "__main__":
    excel_path = sys.argv[1] if len(sys.argv) > 1 else "thickness_table.xlsx"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "fluka_inputs"
    main(excel_path, out_dir)
