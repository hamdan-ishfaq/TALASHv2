#!/usr/bin/env python
"""
Process 10 random CVs through the pipeline and generate XLSX report.
"""
import random
import time
from pathlib import Path
from datetime import datetime
from app.services.cv_queue import queue_cv_from_path
from app.db import SessionLocal
from app.models.models import Candidate
from app.services.excel_exporter import ExcelExporter

print("=" * 110)
print("[BATCH] Building CV pool and processing 10 random CVs...")
print("=" * 110)

# Step 1: Get random pool
pool = sorted(Path('/app/data/tmp_split/random_pool').glob('pool_cv_*.pdf'))
print(f"\n[POOL] Total available: {len(pool)} files")

# Step 2: Sample 10 random CVs
sampled = random.sample(list(pool), min(10, len(pool)))
print(f"[SAMPLED] {len(sampled)} CVs to process\n")

completed_ids = []
db = SessionLocal()

for idx, cv_path in enumerate(sampled, start=1):
    print(f"\n[{idx}/{len(sampled)}] Processing {cv_path.name}...")
    try:
        resp = queue_cv_from_path(str(cv_path))
        cid = resp.get('candidate_id')
        print(f"    ├─ Queued: candidate_id={cid}")
        
        # Poll for completion
        deadline = time.time() + 2400  # 40 min timeout per CV
        final_status = None
        poll_count = 0
        while time.time() < deadline:
            row = db.query(Candidate).filter(Candidate.id == cid).first()
            final_status = row.status if row else 'missing'
            poll_count += 1
            if poll_count % 15 == 1:  # Log every ~2 minutes
                print(f"    ├─ Status: {final_status}")
            if final_status in {'completed', 'failed', 'not_found'}:
                break
            db.expire_all()
            time.sleep(8)
        
        if final_status == 'completed':
            completed_ids.append(cid)
            print(f"    └─ ✓ COMPLETED")
        else:
            print(f"    └─ ✗ FAILED/TIMEOUT: {final_status}")
    except Exception as e:
        print(f"    └─ ✗ ERROR: {e}")

db.close()

print(f"\n{'=' * 110}")
print(f"[SUMMARY] Completed: {len(completed_ids)}/{len(sampled)} CVs")
print(f"[SUMMARY] Candidate IDs: {completed_ids}")
print(f"{'=' * 110}\n")

# Step 3: Generate XLSX
print("[EXPORT] Generating master XLSX report...")
db = SessionLocal()
try:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = f'/app/data/exports/Master_CV_Report_batch10_{ts}.xlsx'
    report_path = ExcelExporter(db).generate_master_report(output_path=out_path)
    print(f"[EXPORT] ✓ Report generated: {report_path}\n")
finally:
    db.close()

print("[DONE] Batch processing complete.")
