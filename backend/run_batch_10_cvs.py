#!/usr/bin/env python
"""
Process up to 10 random CVs through the pipeline and generate an XLSX report.
"""
import os
import random
import time
from datetime import datetime
from pathlib import Path

from app.db import SessionLocal
from app.models.models import Candidate
from app.services.cv_queue import queue_cv_from_path
from app.services.excel_exporter import ExcelExporter

_TERMINAL = frozenset({"completed", "completed_with_errors", "failed"})


def _collect_pool() -> list[Path]:
    roots = [
        Path(os.getenv("TALASH_CV_POOL_DIR", "/app/data/tmp_split/random_pool")),
        Path("/app/data/cvs_split"),
        Path("/app/data/cvs"),
    ]
    paths: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        paths.extend(root.glob("pool_cv_*.pdf"))
        paths.extend(p for p in root.glob("*.pdf") if p not in paths)
    # De-duplicate same file
    uniq = list({p.resolve(): p for p in paths}.values())
    return sorted(uniq)


print("=" * 110)
print("[BATCH] Building CV pool and processing up to 10 random CVs...")
print("=" * 110)

pool = _collect_pool()
print(f"\n[POOL] Total available: {len(pool)} PDFs")
if not pool:
    print("[POOL] No PDFs found under /app/data/cvs_split, /app/data/cvs, or TALASH_CV_POOL_DIR — exiting.")
    raise SystemExit(1)

sampled = random.sample(pool, min(10, len(pool)))
print(f"[SAMPLED] {len(sampled)} CVs to process\n")

completed_ok: list[int] = []
completed_partial: list[int] = []
failed: list[int] = []
db = SessionLocal()

for idx, cv_path in enumerate(sampled, start=1):
    print(f"\n[{idx}/{len(sampled)}] Processing {cv_path.name}...")
    try:
        resp = queue_cv_from_path(str(cv_path))
        cid = resp.get("candidate_id")
        print(f"    ├─ Queued: candidate_id={cid}")

        deadline = time.time() + 2400
        final_status = None
        poll_count = 0
        while time.time() < deadline:
            row = db.query(Candidate).filter(Candidate.id == cid).first()
            final_status = row.status if row else "missing"
            poll_count += 1
            if poll_count % 15 == 1:
                print(f"    ├─ Status: {final_status}")
            if final_status in _TERMINAL or final_status == "missing":
                break
            db.expire_all()
            time.sleep(8)

        if final_status == "completed":
            completed_ok.append(cid)
            print("    └─ ✓ COMPLETED")
        elif final_status == "completed_with_errors":
            completed_partial.append(cid)
            print("    └─ ◆ COMPLETED_WITH_ERRORS (partial pipeline)")
        elif final_status == "missing":
            failed.append(cid)
            print("    └─ ✗ MISSING ROW")
        else:
            failed.append(cid)
            print(f"    └─ ✗ FAILED/TIMEOUT: {final_status}")
    except Exception as e:
        print(f"    └─ ✗ ERROR: {e}")

db.close()

print(f"\n{'=' * 110}")
print(
    f"[SUMMARY] completed={len(completed_ok)} partial={len(completed_partial)} "
    f"failed/missing/timeout={len(failed)} of {len(sampled)}"
)
print(f"[SUMMARY] IDs completed: {completed_ok}")
print(f"[SUMMARY] IDs partial: {completed_partial}")
print(f"[SUMMARY] IDs failed: {failed}")
print(f"{'=' * 110}\n")

print("[EXPORT] Generating master XLSX report...")
db = SessionLocal()
try:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"/app/data/exports/Master_CV_Report_batch10_{ts}.xlsx"
    report_path = ExcelExporter(db).generate_master_report(output_path=out_path)
    print(f"[EXPORT] ✓ Report generated: {report_path}\n")
finally:
    db.close()

print("[DONE] Batch processing complete.")
