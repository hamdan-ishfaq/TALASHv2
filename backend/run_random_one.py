import random
import time
from pathlib import Path
from datetime import datetime

import fitz

from app.db import SessionLocal
from app.models.models import Candidate, ExtractionRun
from app.services.cv_queue import queue_cv_from_path


POOL_DIR = Path('/app/data/tmp_split/random_pool')
OUTPUT_DIR = Path('/app/data/cvs/e2e_random')


def main() -> None:
    if not POOL_DIR.exists():
        raise SystemExit(f'Pool directory not found: {POOL_DIR}')

    pool = sorted(POOL_DIR.glob('pool_cv_*.pdf'))
    if not pool:
        raise SystemExit(f'No pool CVs found in {POOL_DIR}')

    selected = random.choice(pool)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    staged = OUTPUT_DIR / f'one_random_{stamp}_{selected.name}'
    source_doc = fitz.open(str(selected))
    staged_doc = fitz.open()
    staged_doc.insert_pdf(source_doc)
    staged_doc.set_metadata({
        "producer": f"talash-{stamp}",
        "title": f"one_random_{stamp}",
    })
    staged_doc.save(str(staged), garbage=4, deflate=True)
    staged_doc.close()
    source_doc.close()

    print(f'SELECTED {selected.name}')
    print(f'STAGED {staged.name}')

    response = queue_cv_from_path(str(staged))
    print(f'QUEUE_RESPONSE {response}')

    candidate_id = response.get('candidate_id')
    if not candidate_id:
        raise SystemExit(f'Queue response missing candidate_id: {response}')

    db = SessionLocal()
    try:
        deadline = time.time() + 2400
        final_status = None
        while time.time() < deadline:
            candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
            final_status = candidate.status if candidate else 'missing'
            print(f'STATUS {candidate_id} {final_status}')
            if final_status in {'completed', 'failed', 'not_found'}:
                break
            db.expire_all()
            time.sleep(8)

        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        runs = db.query(ExtractionRun).filter(ExtractionRun.candidate_id == candidate_id).all()

        print('FINAL_STATUS', final_status)
        print('CANDIDATE', {
            'id': candidate.id if candidate else None,
            'name': candidate.name if candidate else None,
            'email': candidate.email if candidate else None,
            'status': candidate.status if candidate else None,
        })
        print('EXTRACTION_RUNS', [
            {
                'status': run.status,
                'provider': run.provider,
                'model_name': run.model_name,
                'parsed_ok': run.parsed_ok,
                'error_message': run.error_message,
            }
            for run in runs
        ])
    finally:
        db.close()


if __name__ == '__main__':
    main()