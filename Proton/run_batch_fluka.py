"""
Chay hang loat cac job FLUKA - CHAY SONG SONG, moi job trong 1 thu muc rieng,
tuong duong logic cua run_batch.py (ban PHITS).

KHAC BIET QUAN TRONG SO VOI PHITS (doc ky truoc khi dung):

1. LENH CHAY: FLUKA dung script "rfluka" (thuong o $FLUPRO/flutil/rfluka),
   KHONG phai goi truc tiep executable nhu PHITS. Cu phap:
       rfluka -M <so_cycle> -N <seed_bat_dau> <ten_job_KHONG_duoi_.inp>
   rfluka tu tim file "<ten_job>.inp" trong thu muc hien tai.

2. TEN FILE OUTPUT: PHITS cho ten file co dinh (dose_profile_xxx.out...),
   nhung FLUKA dat ten output THEO SO HIEU UNIT FORTRAN da khai bao trong
   card USRBIN (o day la unit -21.0 cho TDOSE, -22.0 cho TFLUX), thuong
   dang "<ten_job><so_run>_fort.21" / "..._fort.22" - NHUNG ten chinh xac
   co the khac tuy phien ban FLUKA/rfluka, va TOI CHUA THE VERIFY 100% vi
   chua thay output that tu may ban. => Script nay DO TIM file bang PATTERN
   (glob "*_fort.21*", "*_fort.22*") thay vi hard-code ten, de tranh bao
   sai "that bai" chi vi doan sai ten file.

3. SO CYCLE (-M): mac dinh script nay dat cycles=1 giong file .inp ban da
   chay OK, NHUNG nho lai canh bao truoc do - voi 1 cycle, FLUKA khong tinh
   duoc sai so thong ke that (file .lis se hien 99% o moi o). Neu muon so
   lieu co sai so dang tin, tang tham so --cycles len (vd 5-10) khi goi
   script nay.

4. SAU KHI CHAY: van la file .lis dang FORMATTED (ASCII) vi unit am
   (-21/-22) da chon tu dau (KHONG can chay usbrea rieng, khac voi truong
   hop dung unit duong/binary). Script se copy nguyen file tim duoc (giu ten
   goc FLUKA sinh ra) vao outputs_dir/{job_name}/ de khop cau truc ma
   parse_msp_range_fluka.py dang doc (script do nhan dien TDOSE/TFLUX qua
   NOI DUNG header, khong dua vao ten file, nen giu nguyen ten cung duoc).

KHUYEN NGHI: chay THU voi 1-2 job (workers nho, --cycles 1) truoc, mo file
outputs_dir/{job}/*.txt in ra de xac nhan dung glob co bat dung file khong,
truoc khi chay full batch.

Chay: python3 run_batch_fluka.py inputs_fluka/ outputs_fluka/ [rfluka_cmd] [so_song_song] [--cycles N]
Vi du: python3 run_batch_fluka.py inputs_fluka/ outputs_fluka/ rfluka 20 --cycles 5
"""
import sys
import subprocess
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def find_unit_outputs(job_dir: Path, unit: int):
    """Do tim file output tuong ung unit Fortran (vd 21, 22) bang nhieu
    pattern co the co, vi ten chinh xac FLUKA sinh ra tuy phien ban/cau hinh."""
    patterns = [
        f"*_fort.{unit}",
        f"*_fort.{unit}_*",
        f"fort.{unit}",
        f"*fort{unit}*",
    ]
    found = []
    for p in patterns:
        found.extend(job_dir.glob(p))
    # loai trung, giu thu tu
    seen = set()
    uniq = []
    for f in found:
        if f not in seen:
            uniq.append(f)
            seen.add(f)
    return uniq


def run_one(job_dir: Path, fluka_cmd: str, outputs_dir: Path, cycles: int):
    """Chay 1 job FLUKA, tra ve (ten_job, thanh_cong, thong_bao_loi)."""
    inp_files = list(job_dir.glob("*.inp"))
    if not inp_files:
        return job_dir.name, False, "khong tim thay file .inp trong thu muc job"
    inp_file = inp_files[0]
    job_stem = inp_file.stem  # ten job KHONG duoi .inp - rfluka can dang nay

    try:
        result = subprocess.run(
            [fluka_cmd, "-M", str(cycles), "-N", "0", job_stem],
            cwd=str(job_dir),
            capture_output=True, text=True, timeout=1800,
        )

        dose_files = find_unit_outputs(job_dir, 21)
        flux_files = find_unit_outputs(job_dir, 22)

        if result.returncode != 0 or not dose_files or not flux_files:
            tail = (result.stderr or result.stdout)[-400:]
            missing_note = []
            if not dose_files:
                missing_note.append("khong tim thay file unit 21 (TDOSE)")
            if not flux_files:
                missing_note.append("khong tim thay file unit 22 (TFLUX)")
            if missing_note:
                tail = " | ".join(missing_note) + " | " + tail
            return job_stem, False, tail

        # Copy nguyen ten file goc (khong doi ten) vao outputs_dir/{job}/,
        # de parse_msp_range_fluka.py tu nhan dien TDOSE/TFLUX qua header.
        job_out_dir = outputs_dir / job_stem
        job_out_dir.mkdir(parents=True, exist_ok=True)
        for f in dose_files + flux_files:
            shutil.copy(str(f), str(job_out_dir / f.name))
        # Copy them log chinh (*.out) neu co, de debug khi can
        for logf in job_dir.glob(f"{job_stem}*.out"):
            shutil.copy(str(logf), str(job_out_dir / logf.name))

        return job_stem, True, ""
    except FileNotFoundError:
        return job_stem, False, (
            f"Khong tim thay lenh '{fluka_cmd}'. Kiem tra $FLUPRO/flutil/rfluka "
            f"co trong PATH khong, hoac truyen duong dan day du qua argv[3]."
        )
    except Exception as e:
        return job_stem, False, str(e)


def main(inputs_dir: str, outputs_dir: str, fluka_cmd: str = "rfluka",
         workers: int = 20, cycles: int = 1):
    inputs_dir = Path(inputs_dir)
    outputs_dir = Path(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    job_dirs = sorted(d for d in inputs_dir.iterdir() if d.is_dir())
    print(f"Tim thay {len(job_dirs)} job -> chay song song {workers} tien trinh, "
          f"{cycles} cycle/job")
    if cycles == 1:
        print("LUU Y: cycles=1 -> file .lis se hien sai so 99% (placeholder, "
              "khong phai sai so that). Tang --cycles neu can so lieu co sai so.")

    done, failed = 0, []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(run_one, d, fluka_cmd, outputs_dir, cycles): d
            for d in job_dirs
        }
        for fut in as_completed(futures):
            name, ok, err = fut.result()
            done += 1
            status = "OK" if ok else f"LOI: {err}"
            print(f"[{done}/{len(job_dirs)}] {name} -> {status}")
            if not ok:
                failed.append(name)

    print(f"\nHoan tat. {len(job_dirs) - len(failed)}/{len(job_dirs)} thanh cong.")
    if failed:
        print("Cac job bi loi (co the chay lai rieng cac job nay):")
        for f in failed:
            print(" -", f)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Chay hang loat job FLUKA song song")
    parser.add_argument("inputs_dir", nargs="?", default="inputs_fluka")
    parser.add_argument("outputs_dir", nargs="?", default="outputs_fluka")
    parser.add_argument("fluka_cmd", nargs="?", default="rfluka")
    parser.add_argument("workers", nargs="?", type=int, default=20)
    parser.add_argument("--cycles", type=int, default=1,
                         help="So cycle (-M) truyen cho rfluka, mac dinh 1")
    args = parser.parse_args()

    main(args.inputs_dir, args.outputs_dir, args.fluka_cmd, args.workers, args.cycles)
