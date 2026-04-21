from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime
from pathlib import Path

import fitz

from app.db import SessionLocal
from app.models.models import Candidate
from app.services.cv_queue import queue_cv_from_path
from app.services.excel_exporter import ExcelExporter

POOL_DIR = Path('/app/data/tmp_split/random_pool')
E2E_DIR = Path('/app/data/cvs/e2e_random')
E2E_DIR.mkdir(parents=True, exist_ok=True)


def _existing_hashes(db) -> set[str]:
    return {c.file_hash for c in db.query(Candidate).all() if c.file_hash}


def _rehydrate_pdf(src: Path, dst: Path) -> None:
    """Rewrite the same pages to produce a new binary hash without changing content."""
    doc = fitz.open(str(src))
    out = fitz.open()
    out.insert_pdf(doc)
    # Add deterministic metadata marker for test traceability.
    md = out.metadata or {}
    md['producer'] = 'talash-e2e-three-cv-test'
    md['creationDate'] = datetime.utcnow().strftime("D:%Y%m%d%H%M%S")
    out.set_metadata(md)
    out.save(str(dst), garbage=4, deflate=True)
    out.close()
    doc.close()


def main() -> int:
    db = SessionLocal()
    try:
        pool = sorted(POOL_DIR.glob('pool_cv_*.pdf'))
        if len(pool) < 3:
            print('FAIL: not enough pool files')
            return 2

        random.seed(20260421)
        candidates = random.sample(pool, 3)

        generated = []
        existing = _existing_hashes(db)
        for idx, src in enumerate(candidates, 1):
            dst = E2E_DIR / f'e2e_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}_{idx:02d}_{src.name}'
            _rehydrate_pdf(src, dst)
            new_hash = hashlib.sha256(dst.read_bytes()).hexdigest()
            if new_hash in existing:
                print(f'WARN: regenerated hash still duplicate for {dst.name}, skipping')
                continue
            generated.append(dst)
            existing.add(new_hash)

        if len(generated) < 3:
            print(f'FAIL: could not prepare 3 unique test files (prepared={len(generated)})')
            return 3

        completed_ids: list[int] = []
        attempted_ids: list[int] = []
        results: list[dict] = []

        for pdf in generated:
            q = queue_cv_from_path(str(pdf))
            if q.get('status') != 'queued':
                results.append({'file': pdf.name, 'queue': q, 'final_status': 'not_queued'})
                continue

            cid = q['candidate_id']
            attempted_ids.append(cid)

            final_status = 'timeout'
            for _ in range(180):
                row = db.query(Candidate).filter(Candidate.id == cid).first()
                st = row.status if row else 'missing'
                if st in {'completed', 'failed', 'not_found'}:
                    final_status = st
                    break
                db.expire_all()
                import time
                time.sleep(5)

            row = db.query(Candidate).filter(Candidate.id == cid).first()
            results.append(
                {
                    'candidate_id': cid,
                    'file': pdf.name,
                    'queue_task_id': q.get('task_id'),
                    'final_status': final_status,
                    'name': row.name if row else None,
                    'email': row.email if row else None,
                }
            )
            if final_status == 'completed':
                completed_ids.append(cid)

        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        out_path = f'/app/data/exports/Master_CV_Report_e2e_three_{ts}.xlsx'
        report_path = ExcelExporter(db).generate_master_report(output_path=out_path)

        print('E2E_RESULTS_START')
        for item in results:
            print(json.dumps(item, default=str))
        print('E2E_RESULTS_END')
        print('COMPLETED_IDS', completed_ids)
        print('ATTEMPTED_IDS', attempted_ids)
        print('XLSX_PATH', report_path)

        return 0 if len(completed_ids) == 3 else 4
    finally:
        db.close()


if __name__ == '__main__':
    raise SystemExit(main())
