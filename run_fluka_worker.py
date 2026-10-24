"""
run_fluka_worker.py - Parallel worker for FLUKA Simulation (2026.23.10_Paper1_Fluka)
Runs across 13 GitHub Actions Swarm accounts (130 concurrent runners).
Uploads 1-to-1 CSV results to 02_Flux_Data/<sub_project>/
Uploads simulation output files (.lis, .out, *fort*, .log) to 03_Simulation_Outputs/<sub_project>/<job_name>/
NO ZIP ARCHIVING - Direct folder storage.
"""

import os
import sys
import time
import json
import random
import shutil
import subprocess
from pathlib import Path
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

import gdrive_helper
from googleapiclient.http import MediaFileUpload

def get_or_create_subfolder(service, parent_id: str, name: str) -> str:
    q = f"'{parent_id}' in parents and name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    for attempt in range(5):
        try:
            res = service.files().list(
                q=q, supportsAllDrives=True, includeItemsFromAllDrives=True, fields="files(id, name)"
            ).execute().get("files", [])
            if res:
                return res[0]["id"]
            body = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
            f = service.files().create(body=body, supportsAllDrives=True, fields="id").execute()
            return f["id"]
        except Exception:
            time.sleep(1.0 + random.uniform(0.5, 2.0))
    raise RuntimeError(f"Failed to get_or_create_subfolder: {name}")

def upload_file_to_drive(service, file_path: Path, parent_folder_id: str) -> str:
    q = f"'{parent_folder_id}' in parents and name = '{file_path.name}' and trashed = false"
    for attempt in range(5):
        try:
            res = service.files().list(
                q=q, supportsAllDrives=True, includeItemsFromAllDrives=True, fields="files(id)"
            ).execute().get("files", [])
            media = MediaFileUpload(str(file_path), resumable=True)
            if res:
                f_id = res[0]["id"]
                service.files().update(fileId=f_id, media_body=media, supportsAllDrives=True).execute()
                return f_id
            body = {"name": file_path.name, "parents": [parent_folder_id]}
            new_f = service.files().create(body=body, media_body=media, supportsAllDrives=True, fields="id").execute()
            return new_f["id"]
        except Exception:
            time.sleep(1.0 + random.uniform(0.5, 2.0))
    raise RuntimeError(f"Failed to upload {file_path.name}")

def ensure_fluka_environment():
    # Verify or setup rfluka path
    fluka_paths = [
        "/usr/local/flukagfor/bin",
        "/usr/local/fluka/bin",
        "/usr/local/bin"
    ]
    cur_path = os.environ.get("PATH", "")
    for fp in fluka_paths:
        if os.path.exists(fp) and fp not in cur_path:
            os.environ["PATH"] = f"{fp}:{cur_path}"
            cur_path = os.environ["PATH"]

    os.environ["FLUFOR"] = "gfortran"
    if "FLUPRO" not in os.environ:
        for p in ["/usr/local/flukagfor", "/usr/local/fluka"]:
            if os.path.exists(p):
                os.environ["FLUPRO"] = p
                break

    # Compile custom routine for Neutron if present
    flupro = os.environ.get("FLUPRO", "/usr/local/flukagfor")
    fff_bin = Path(flupro) / "flutil" / "fff"
    lfluka_bin = Path(flupro) / "flutil" / "lfluka"
    source_f = Path("Neutron") / "source_watt_template.f"
    custom_exe = Path("phits_ca_watt")

    if source_f.exists() and not custom_exe.exists() and fff_bin.exists() and lfluka_bin.exists():
        print(">>> [BUILD] Compiling custom FLUKA routine for Neutron: source_watt_template.f...")
        try:
            subprocess.run([str(fff_bin), str(source_f)], check=True)
            subprocess.run([str(lfluka_bin), "-m", "fluka", "-o", "phits_ca_watt", "source_watt_template.o"], check=True)
            subprocess.run(["chmod", "+x", "phits_ca_watt"], check=True)
            print(">>> [BUILD] phits_ca_watt compiled successfully!")
        except Exception as e:
            print(f">>> [BUILD ERROR] Failed to compile phits_ca_watt: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="FLUKA Swarm Worker")
    parser.add_argument("--runner-id", type=int, required=True)
    parser.add_argument("--num-runners", type=int, default=10)
    parser.add_argument("--gdrive-folder", type=str, required=True)
    parser.add_argument("--plan-file", type=str, default="plan_swarm.json")
    parser.add_argument("--github-user", type=str, default=None)
    args = parser.parse_args()

    acc_name = args.github_user or os.environ.get("GITHUB_REPOSITORY_OWNER") or "runner"
    print("=" * 80)
    print(f"STARTING FLUKA RUNNER #{args.runner_id} (Account: {acc_name})")
    print(f"Plan file: {args.plan_file} | Drive Folder: {args.gdrive_folder}")
    print("=" * 80)

    ensure_fluka_environment()

    # Connect Google Drive
    service = gdrive_helper.get_drive_service()

    with open("drive_folders.json", "r", encoding="utf-8") as f:
        drive_tree = json.load(f)
    subprojects_cfg = drive_tree.get("subprojects", {})

    with open(args.plan_file, "r", encoding="utf-8") as f:
        full_plan = json.load(f)

    my_jobs = full_plan.get(acc_name, {}).get(str(args.runner_id), [])
    if not my_jobs:
        # Fallback round robin
        all_jobs = []
        for a_k, r_dict in full_plan.items():
            for r_k, j_list in r_dict.items():
                all_jobs.extend(j_list)
        my_jobs = [j for i, j in enumerate(all_jobs) if i % args.num_runners == (args.runner_id - 1)]

    print(f"Assigned {len(my_jobs)} jobs to runner #{args.runner_id}:")
    for j in my_jobs[:5]:
        print(f"  * {j['job_name']} ({j['sub_project']})")
    if len(my_jobs) > 5:
        print(f"  ... and {len(my_jobs) - 5} more jobs.")

    if not my_jobs:
        print("No jobs for this runner. Exiting cleanly.")
        return

    # Check Drive for already completed files to resume cleanly
    existing_by_sub = {}
    for sp_name, sp_tiers in subprojects_cfg.items():
        flux_fid = sp_tiers.get("02_Flux_Data")
        completed_set = set()
        if flux_fid:
            pt = None
            while True:
                try:
                    q = f"'{flux_fid}' in parents and trashed = false"
                    res = service.files().list(
                        q=q, supportsAllDrives=True, includeItemsFromAllDrives=True,
                        fields="nextPageToken, files(name)", pageSize=1000, pageToken=pt
                    ).execute()
                    for it in res.get("files", []):
                        fn = it["name"]
                        if fn.endswith(".csv"):
                            completed_set.add(fn.replace(".csv", "").lower().strip())
                    pt = res.get("nextPageToken")
                    if not pt: break
                except Exception:
                    time.sleep(2)
                    break
        existing_by_sub[sp_name] = completed_set

    # Run jobs
    completed_cnt = 0
    total_jobs = len(my_jobs)
    rfluka_cmd = shutil.which("rfluka") or "rfluka"
    custom_exe = Path("phits_ca_watt").resolve()

    for idx, job in enumerate(my_jobs, 1):
        jname = job["job_name"]
        sp = job["sub_project"]
        rel_p = Path(job["rel_path"])
        inp_name = job["inp_name"]
        job_stem = Path(inp_name).stem

        dest_flux_fid = subprojects_cfg[sp]["02_Flux_Data"]
        dest_outputs_fid = subprojects_cfg[sp]["03_Simulation_Outputs"]

        # Check if already completed
        if jname.lower().strip() in existing_by_sub.get(sp, set()):
            print(f"[{idx}/{total_jobs}] SKIP: {jname} ({sp}) already on Drive.")
            completed_cnt += 1
            continue

        if not rel_p.exists():
            print(f"[{idx}/{total_jobs}] [ERROR] Input file not found: {rel_p}")
            continue

        job_dir = rel_p.parent.resolve()
        print(f"\n[{idx}/{total_jobs}] Running FLUKA: {jname} ({sp}) in {job_dir.name}...")

        # Select executable
        if sp == "Neutron" and custom_exe.exists():
            cmd = [rfluka_cmd, "-e", str(custom_exe), "-M", "1", "-N", "0", job_stem]
        else:
            cmd = [rfluka_cmd, "-M", "1", "-N", "0", job_stem]

        t0 = time.time()
        res_run = subprocess.run(cmd, cwd=str(job_dir), capture_output=True, text=True, timeout=900)
        t_elapsed = time.time() - t0

        if res_run.returncode != 0:
            print(f"  [ERROR] FLUKA execution failed (code {res_run.returncode})")
            tail = (res_run.stderr or res_run.stdout)[-300:]
            print(f"  {tail}")

        print(f"  * Sim completed in {t_elapsed:.1f} s")

        # 1. Write 1-to-1 CSV
        local_csv = Path(f"{jname}.csv")
        df_csv = pd.DataFrame([{
            "job_name": jname,
            "sub_project": sp,
            "inp_name": inp_name,
            "elapsed_seconds": round(t_elapsed, 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }])
        df_csv.to_csv(local_csv, index=False)
        upload_file_to_drive(service, local_csv, dest_flux_fid)
        print(f"  * Uploaded CSV -> 02_Flux_Data/{sp}/{local_csv.name}")
        local_csv.unlink()

        # 2. Upload outputs directly into 03_Simulation_Outputs/<sp>/<jname>/
        out_exts = [".lis", ".out", ".log"]
        out_files = [f for f in job_dir.iterdir() if f.is_file() and (f.suffix in out_exts or "fort." in f.name or "fort" in f.name)]
        if out_files:
            job_out_folder_id = get_or_create_subfolder(service, dest_outputs_fid, jname)
            for of in out_files:
                upload_file_to_drive(service, of, job_out_folder_id)
                of.unlink()
            print(f"  * Uploaded {len(out_files)} output files -> 03_Simulation_Outputs/{sp}/{jname}/")

        completed_cnt += 1

    print("\n" + "=" * 80)
    print(f"RUNNER #{args.runner_id} FINISHED: {completed_cnt}/{total_jobs} JOBS COMPLETED!")
    print("=" * 80)

if __name__ == "__main__":
    main()
