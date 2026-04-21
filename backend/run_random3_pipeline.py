import random
import time
from datetime import datetime
from pathlib import Path

import fitz

from app.db import SessionLocal
from app.models.models import Candidate
from app.services.cv_queue import queue_cv_from_path
from app.services.excel_exporter import ExcelExporter

INPUT = Path('/app/data/tmp_split/source_CVs.pdf')
POOL_DIR = Path('/app/data/tmp_split/random_pool')
POOL_DIR.mkdir(parents=True, exist_ok=True)

if not INPUT.exists():
    raise SystemExit(f'Input PDF not found: {INPUT}')


def is_blank(page):
    return len(page.get_text().strip()) < 10


print('STEP 1: building split pool...')
doc = fitz.open(str(INPUT))
blank_pages = [i for i in range(len(doc)) if is_blank(doc[i])]
boundaries = [[0]]
for b in blank_pages:
    if boundaries[-1][0] < b:
        boundaries[-1].append(b)
        if b + 1 < len(doc):
            boundaries.append([b + 1])
if len(boundaries[-1]) == 1:
    boundaries[-1].append(len(doc))

pool_files = []
for idx, (start, end) in enumerate(boundaries, 1):
    out = POOL_DIR / f'pool_cv_{idx:03d}.pdf'
    if not out.exists():
        nd = fitz.open()
        for p in range(start, min(end, len(doc))):
            nd.insert_pdf(doc, from_page=p, to_page=p)
        nd.save(str(out))
        nd.close()
    pool_files.append(out)

doc.close()
print(f'  pool size: {len(pool_files)} files')

random.shuffle(pool_files)
completed_ids = []
attempted_ids = []
selected_files = []

print('STEP 2: sampling until 3 completed CVs...')
db = SessionLocal()
try:
    for p in pool_files:
        if len(completed_ids) >= 1:
            break

        # Rate limit: Wait 10 seconds before starting next CV attempt
        if attempted_ids:
            print("  rate limit: waiting 10s...")
            time.sleep(10)

        resp = queue_cv_from_path(str(p))
        queue_status = resp.get('status')
        if queue_status != 'queued':
            print(f'  skipped ({queue_status}): {p.name}')
            continue

        cid = resp['candidate_id']
        attempted_ids.append(cid)
        selected_files.append(str(p))
        print(f'  queued: candidate_id={cid} file={p.name}')

        # Wait for this candidate to reach a terminal state before queueing next.
        deadline = time.time() + 3600
        final_state = None
        while time.time() < deadline:
            row = db.query(Candidate).filter(Candidate.id == cid).first()
            final_state = row.status if row else 'missing'
            print(f'    status[{cid}]={final_state}')

            if final_state in {'completed', 'failed', 'not_found'}:
                break

            db.expire_all()
            time.sleep(8)

        if final_state == 'completed':
            completed_ids.append(cid)
            print(f'  completed: candidate_id={cid}')
        else:
            print(f'  not completed: candidate_id={cid} status={final_state}')

    if len(completed_ids) < 1:
        raise SystemExit(
            f'Could not complete 1 CV. completed={len(completed_ids)} attempted={attempted_ids}'
        )

    print('STEP 4: generating XLSX export...')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = f'/app/data/exports/Master_CV_Report_random3_{ts}.xlsx'
    report_path = ExcelExporter(db).generate_master_report(output_path=out_path)
    print('EXPORT_OK', report_path)
    print('SELECTED_FILES')
    for f in selected_files:
        print(f'  {f}')
    print('COMPLETED_CANDIDATE_IDS', completed_ids)
    print('ATTEMPTED_CANDIDATE_IDS', attempted_ids)
finally:
    db.close()
