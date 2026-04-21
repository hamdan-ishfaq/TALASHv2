import random
import time
from datetime import datetime
from pathlib import Path

from app.db import SessionLocal
from app.models.models import Candidate
from app.services.cv_queue import queue_cv_from_path
from app.services.excel_exporter import ExcelExporter

POOL_DIR = Path('/app/data/tmp_split/random_pool')
if not POOL_DIR.exists():
    raise SystemExit(f'Pool directory not found: {POOL_DIR}')

all_files = sorted(POOL_DIR.glob('pool_cv_*.pdf'), key=lambda p: p.stat().st_size)
if len(all_files) < 3:
    raise SystemExit('Not enough pool files to sample from.')

# Randomly sample from the smallest 20 files to reduce max_tokens truncation risk.
small_pool = all_files[:20]
random.shuffle(small_pool)

print(f'STEP 1: candidates in small random pool: {len(small_pool)}')

completed_ids = []
attempted_ids = []
selected_files = []


def wait_terminal(db, candidate_id: int, timeout_seconds: int = 2400) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        row = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        status = row.status if row else 'missing'
        print(f'    status[{candidate_id}]={status}')
        if status in {'completed', 'failed', 'not_found'}:
            return status
        db.expire_all()
        time.sleep(8)
    return 'timeout'


db = SessionLocal()
try:
    print('STEP 2: queueing random CVs until 3 complete...')
    for p in small_pool:
        if len(completed_ids) >= 3:
            break

        resp = queue_cv_from_path(str(p))
        queue_status = resp.get('status')
        if queue_status != 'queued':
            print(f'  skipped ({queue_status}): {p.name}')
            continue

        cid = resp['candidate_id']
        attempted_ids.append(cid)
        selected_files.append(str(p))
        print(f'  queued: candidate_id={cid} file={p.name}')

        final_status = wait_terminal(db, cid)
        if final_status == 'completed':
            completed_ids.append(cid)
            print(f'  completed: candidate_id={cid}')
        else:
            print(f'  not completed: candidate_id={cid} status={final_status}')

    if len(completed_ids) < 3:
        raise SystemExit(
            f'Could not complete 3 CVs. completed={len(completed_ids)} attempted={attempted_ids}'
        )

    print('STEP 3: generating XLSX export...')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = f'/app/data/exports/Master_CV_Report_random3_{ts}.xlsx'
    report_path = ExcelExporter(db).generate_master_report(output_path=out_path)

    print('EXPORT_OK', report_path)
    print('COMPLETED_CANDIDATE_IDS', completed_ids)
    print('ATTEMPTED_CANDIDATE_IDS', attempted_ids)
    print('SELECTED_FILES')
    for f in selected_files:
        print(f'  {f}')
finally:
    db.close()
