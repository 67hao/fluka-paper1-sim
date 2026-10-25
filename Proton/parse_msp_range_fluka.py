"""
Doc ket qua USRBIN (.lis, dang ASCII sau khi convert bang usbrea/flair) cua
FLUKA, tinh MSP(entrance) va Projected Range cho tung vat lieu (s1..s6) x
tung nang luong, xuat Excel theo layout Energy x s1..s6 - tuong duong
parse_msp_range.py (ban PHITS).

DA VERIFY dinh dang file that (proton_s2_1000keV_tdose.lis /
proton_s2_1000keV_tflux.lis ban gui):

    Cartesian binning n.   1  "TDOSE     " , generalized particle n.  228
      X coordinate: from -1.0000E+00 to  1.0000E+00 cm,     1 bins ( ... cm wide)
      Y coordinate: from -1.0000E+00 to  1.0000E+00 cm,     1 bins ( ... cm wide)
      Z coordinate: from  0.0000E+00 to  1.5000E-03 cm,   300 bins ( ... cm wide)
      Data follow in a matrix A(ix,iy,iz), format (...)

      accurate deposition along the tracks requested
      this is a track-length binning
       <10 gia tri moi dong> ...
      (blank line)
      Percentage errors follow in a matrix A(ix,iy,iz), ...

CONG THUC (suy tu chinh don vi FLUKA, khac PHITS):
  - USRBIN quantity "DOSE" tra ve GeV/g/primary (da TU CHIA density va the
    tich o), nen:
        dE/dx (o lop dau) = Dose_bin0 * density * Area
        MSP = dE/dx / density = Dose_bin0 * Area        <-- density TRIET TIEU
    => KHONG can bang density rieng cho tung vat lieu nhu ban PHITS.
    Doi don vi GeV -> MeV (x1000) de ra MeV.cm2/g.

  - USRBIN quantity "PROTON" (hoac ten hat khac) tra ve fluence track-length
    (1/cm2/primary) - CHINH LA S(z) (xac suat con "song", tuc chua dung) khi
    nhan voi Area:
        R = tich phan [flux(z) * Area] dz  (0 -> zmax), cong don Riemann
    voi dz = (zmax-zmin)/nz (deu nhau, KHAC PHITS - FLUKA Cartesian luon
    deu, khong can doc z_lower/z_upper tung o).

  MSP entrance van la GAN DUNG tu 1 o dau tien (khong ngoai suy ve z=0),
  giong han che da neu o ban PHITS.

Cau truc thu muc ky vong (khop dung ten job cua generate_msp_range_inputs_fluka.py):
    outputs_fluka/proton_s1_1000keV/  (chua .lis da convert, ten file bat ky,
                                        script tu nhan dien TDOSE/TFLUX qua
                                        NOI DUNG header, khong dua vao ten file)

Chay:
  python parse_msp_range_fluka.py thickness_table.xlsx outputs_fluka/ msp_range_fluka_results.xlsx
"""
import re
import sys
from pathlib import Path

import pandas as pd

PROJECTILE = "proton"


def energy_tag_for(energy_kev: float) -> str:
    return f"{energy_kev:g}keV".replace(".", "p")


def job_name_for(material: str, energy_kev: float) -> str:
    return f"{PROJECTILE}_{material}_{energy_tag_for(energy_kev)}"


HEADER_RE = re.compile(
    r'Cartesian binning n\.\s*\d+\s*"(\w+)', re.IGNORECASE
)
AXIS_RE = re.compile(
    r"(\w) coordinate:\s*from\s*([\d.Ee+-]+)\s*to\s*([\d.Ee+-]+)\s*cm,\s*(\d+)\s*bins"
)


def parse_lis(filepath: Path):
    """Tra ve dict {'name':..., 'axes':{'X':(min,max,n),...}, 'values':[...]}"""
    text = filepath.read_text()
    lines = text.splitlines()

    name = None
    axes = {}
    for line in lines:
        m = HEADER_RE.search(line)
        if m:
            name = m.group(1).strip()
        m2 = AXIS_RE.search(line)
        if m2:
            axis, lo, hi, n = m2.groups()
            axes[axis.upper()] = (float(lo), float(hi), int(n))

    if name is None or "Z" not in axes:
        raise ValueError(f"Khong doc duoc header binning trong {filepath}")

    # Tim vi tri bat dau khoi du lieu chinh (truoc khoi "Percentage errors")
    try:
        data_start = next(i for i, l in enumerate(lines) if "Data follow" in l)
    except StopIteration:
        raise ValueError(f"Khong tim thay 'Data follow' trong {filepath}")

    values = []
    started_numbers = False
    for line in lines[data_start + 1:]:
        stripped = line.strip()
        if "Percentage errors" in line:
            break
        if not stripped:
            if started_numbers:
                break
            continue
        parts = stripped.split()
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            # dong text nhu "accurate deposition along the tracks requested"
            continue
        values.extend(nums)
        started_numbers = True

    nx = axes.get("X", (0, 0, 1))[2]
    ny = axes.get("Y", (0, 0, 1))[2]
    nz = axes["Z"][2]
    expected = nx * ny * nz
    if len(values) != expected:
        raise ValueError(
            f"{filepath}: doc duoc {len(values)} gia tri, ky vong {expected} "
            f"(nx={nx},ny={ny},nz={nz}) - kiem tra lai file .lis"
        )

    return {"name": name, "axes": axes, "values": values}


def find_lis_pair(job_dir: Path):
    """Tim 2 file ket qua USRBIN trong job_dir, phan biet TDOSE/TFLUX qua
    NOI DUNG header (khong dua vao duoi file). QUET MOI FILE trong thu muc
    (khong chi *.lis) vi run_batch_fluka.py giu nguyen ten goc FLUKA sinh ra
    (thuong dang "..._fort.21", KHONG co duoi .lis) - chi khi ban tu tay
    convert/doi ten qua usbrea/flair thi moi co duoi .lis that su."""
    dose_file = flux_file = None
    for f in job_dir.iterdir():
        if not f.is_file():
            continue
        if f.suffix in (".inp",) or f.name.endswith(".err"):
            continue
        try:
            parsed = parse_lis(f)
        except (ValueError, UnicodeDecodeError):
            continue  # file khong phai USRBIN output dang doc duoc (vd .out log, .inp)
        if "DOSE" in parsed["name"].upper():
            dose_file = (f, parsed)
        else:
            flux_file = (f, parsed)
    return dose_file, flux_file


def compute_msp_entrance(dose_parsed: dict) -> float:
    """MSP(entrance, MeV.cm2/g) = Dose_o_dau_tien(GeV/g) * Area(cm2) * 1000.
    Density TU TRIET TIEU (xem giai thich o dau file), khong can bang density
    rieng nhu ban PHITS."""
    xmin, xmax, _ = dose_parsed["axes"]["X"]
    ymin, ymax, _ = dose_parsed["axes"]["Y"]
    area_cm2 = (xmax - xmin) * (ymax - ymin)
    dose_bin0_gev_per_g = dose_parsed["values"][0]
    return dose_bin0_gev_per_g * area_cm2 * 1000.0  # GeV -> MeV


def compute_range(flux_parsed: dict) -> float:
    """Projected Range (um) = tich phan flux(z)*Area dz, dz deu nhau."""
    xmin, xmax, _ = flux_parsed["axes"]["X"]
    ymin, ymax, _ = flux_parsed["axes"]["Y"]
    area_cm2 = (xmax - xmin) * (ymax - ymin)
    zmin, zmax, nz = flux_parsed["axes"]["Z"]
    dz_cm = (zmax - zmin) / nz

    R_cm = sum(v * area_cm2 * dz_cm for v in flux_parsed["values"])
    return R_cm * 1e4


def check_truncation(flux_parsed: dict) -> str:
    """Hat van con 'song' o bin z cuoi (S = flux*Area > 0.1%) -> zmax tally qua
    nho, Range bi CAT CUT tai zmax (MSP van dung). Tra ve chuoi mo ta, rong neu OK.
    LUU Y: FLUKA co multiple scattering nen flux*Area la quang duong di (path
    length) trong bin, co the hoi > 1 o dau duong di - chi dung bin CUOI de kiem tra."""
    xmin, xmax, _ = flux_parsed["axes"]["X"]
    ymin, ymax, _ = flux_parsed["axes"]["Y"]
    area_cm2 = (xmax - xmin) * (ymax - ymin)
    s_last = flux_parsed["values"][-1] * area_cm2
    if s_last > 1e-3:
        zmax_um = flux_parsed["axes"]["Z"][1] * 1e4
        return (f"S(zmax)={s_last:.3f}, zmax={zmax_um:.4g} um -> Range bi CAT CUT, "
                f"can chay lai voi SAFETY_MARGIN lon hon")
    return ""


def find_energy_column(df: pd.DataFrame) -> str:
    for c in df.columns:
        if "energy" in c.lower():
            return c
    raise ValueError("Khong tim thay cot nang luong (ten cot phai chua 'energy')")


def main(excel_path: str, outputs_dir: str, result_path: str):
    if excel_path.lower().endswith(".csv"):
        df = pd.read_csv(excel_path)
    else:
        df = pd.read_excel(excel_path)

    energy_col = find_energy_column(df)
    materials = [c for c in df.columns if c != energy_col]
    outputs_dir = Path(outputs_dir)

    msp_result = df[[energy_col]].copy().rename(columns={energy_col: "Energy_keV"})
    range_result = df[[energy_col]].copy().rename(columns={energy_col: "Energy_keV"})
    for mat in materials:
        msp_result[mat] = None
        range_result[mat] = None

    missing, parse_errors, truncated = [], [], []

    for idx, row in df.iterrows():
        energy_kev = float(row[energy_col])
        for mat in materials:
            job_name = job_name_for(mat, energy_kev)
            job_dir = outputs_dir / job_name
            if not job_dir.exists():
                missing.append(str(job_dir))
                continue

            dose_pair, flux_pair = find_lis_pair(job_dir)
            if dose_pair is None or flux_pair is None:
                missing.append(f"{job_dir} (thieu file TDOSE hoac TFLUX .lis)")
                continue

            try:
                msp = compute_msp_entrance(dose_pair[1])
                rng = compute_range(flux_pair[1])
                trunc_msg = check_truncation(flux_pair[1])
            except Exception as e:
                parse_errors.append(f"{job_name}: {e}")
                continue
            if trunc_msg:
                truncated.append(f"{job_name}: {trunc_msg}")

            msp_result.loc[idx, mat] = msp
            range_result.loc[idx, mat] = rng

    with pd.ExcelWriter(result_path) as writer:
        msp_result.to_excel(writer, sheet_name="MSP_MeV_cm2_per_g", index=False)
        range_result.to_excel(writer, sheet_name="Projected_Range_um", index=False)

    print(f"Da luu ket qua vao '{result_path}'")
    if missing:
        print(f"\nCANH BAO: {len(missing)} job thieu du lieu:")
        for m in missing[:20]:
            print(" -", m)
    if parse_errors:
        print(f"\nCANH BAO: {len(parse_errors)} loi khi doc/tinh:")
        for e in parse_errors[:20]:
            print(" -", e)
    if truncated:
        print(f"\nCANH BAO: {len(truncated)} job co Range bi CAT CUT (gia tri Range SAI, MSP van dung):")
        for t in truncated:
            print(" -", t)


if __name__ == "__main__":
    excel_path = sys.argv[1] if len(sys.argv) > 1 else "thickness_table.xlsx"
    outputs_dir = sys.argv[2] if len(sys.argv) > 2 else "outputs_fluka"
    result_path = sys.argv[3] if len(sys.argv) > 3 else "msp_range_fluka_results.xlsx"
    main(excel_path, outputs_dir, result_path)
