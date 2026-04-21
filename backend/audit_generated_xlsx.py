from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from app.db import SessionLocal

EXPORT_DIR = Path('/app/data/exports')
TARGETS = sorted(EXPORT_DIR.glob('Master_CV_Report_random3_*.xlsx'))

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LINKEDIN_RE = re.compile(r"linkedin\.com/[A-Za-z0-9_\-/%]+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s()]{7,}\d)")


def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


for path in TARGETS:
    print('=' * 120)
    print('FILE:', path.name)
    xls = pd.ExcelFile(path)
    sheets = {name: pd.read_excel(path, sheet_name=name) for name in xls.sheet_names}

    print('SHEETS:', ', '.join(xls.sheet_names))
    print('ROW_COUNTS:')
    for name, df in sheets.items():
        print(f'  - {name}: {len(df)}')

    cand_df = sheets.get('Candidates', pd.DataFrame())
    if cand_df.empty:
        print('No Candidates sheet found or it is empty.')
        continue

    id_col = pick_col(cand_df, ['id', 'candidate_id'])
    name_col = pick_col(cand_df, ['name'])
    status_col = pick_col(cand_df, ['status'])
    email_col = pick_col(cand_df, ['email'])
    phone_col = pick_col(cand_df, ['phone'])
    linkedin_col = pick_col(cand_df, ['linkedin_url', 'linkedin'])

    candidate_ids = [int(v) for v in cand_df[id_col].dropna().tolist()] if id_col else []

    print('\nCANDIDATE_CONTACT_MISSING:')
    for _, row in cand_df.iterrows():
        cid = int(row[id_col]) if id_col and pd.notna(row[id_col]) else None
        name = str(row[name_col]) if name_col and pd.notna(row[name_col]) else '<unknown>'
        status = str(row[status_col]) if status_col and pd.notna(row[status_col]) else ''
        email = str(row[email_col]).strip() if email_col and pd.notna(row[email_col]) else ''
        phone = str(row[phone_col]).strip() if phone_col and pd.notna(row[phone_col]) else ''
        linkedin = str(row[linkedin_col]).strip() if linkedin_col and pd.notna(row[linkedin_col]) else ''
        missing = []
        if not email:
            missing.append('email')
        if not phone:
            missing.append('phone')
        if not linkedin:
            missing.append('linkedin')
        print(f'  - id={cid} name={name} status={status} missing_contact={missing}')

    # Per-candidate coverage across major extracted sheets
    major_sheets = ['Education', 'Experience', 'Journals', 'Conferences', 'Supervision', 'Books', 'Patents', 'Skills']
    coverage = defaultdict(lambda: defaultdict(int))

    for sname in major_sheets:
        df = sheets.get(sname, pd.DataFrame())
        if df.empty:
            continue
        cid_col = pick_col(df, ['candidate_id', 'id'])
        if not cid_col:
            continue
        vc = df[cid_col].value_counts(dropna=True)
        for k, v in vc.items():
            try:
                coverage[int(k)][sname] = int(v)
            except Exception:
                pass

    print('\nCANDIDATE_ENTITY_COVERAGE:')
    for cid in candidate_ids:
        counts = {s: coverage[cid].get(s, 0) for s in major_sheets}
        total = sum(counts.values())
        print(f'  - id={cid} total_entities={total} details={counts}')

    # Compare DB raw_text hints vs extracted contact fields for these candidate IDs
    if candidate_ids:
        db = SessionLocal()
        try:
            sql = text(
                'select id, name, coalesce(email,\'\') as email, coalesce(phone,\'\') as phone, '
                'coalesce(linkedin_url,\'\') as linkedin_url, coalesce(raw_text,\'\') as raw_text '
                'from candidates where id = any(:ids) order by id'
            )
            rows = db.execute(sql, {'ids': candidate_ids}).mappings().all()

            print('\nRAW_TEXT_VS_EXTRACTED_CONTACT_MISSES:')
            for r in rows:
                raw = r['raw_text'] or ''
                found_email = bool(EMAIL_RE.search(raw))
                found_phone = bool(PHONE_RE.search(raw))
                found_linkedin = bool(LINKEDIN_RE.search(raw))

                missed = []
                if found_email and not r['email']:
                    missed.append('email_present_in_raw_text_but_not_extracted')
                if found_phone and not r['phone']:
                    missed.append('phone_present_in_raw_text_but_not_extracted')
                if found_linkedin and not r['linkedin_url']:
                    missed.append('linkedin_present_in_raw_text_but_not_extracted')

                print(
                    f"  - id={r['id']} name={r['name']} found(email/phone/linkedin)="
                    f"{found_email}/{found_phone}/{found_linkedin} misses={missed}"
                )
        finally:
            db.close()

print('=' * 120)
