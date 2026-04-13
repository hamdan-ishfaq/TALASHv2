# CV PDF Splitter - Quick Start Guide

## What Changed

✅ **Models Updated:** Simplified database schema (`backend/app/models/models.py`)
✅ **Schemas Updated:** Cleaner Pydantic extraction schemas (`backend/app/schemas/extraction.py`)  
✅ **PDF Splitter Created:** Script to break CVs.pdf into individual PDFs

## How to Use PDF Splitter

### Option 1: Simple One-Liner (Recommended)
Run this command from the project root:

```bash
docker-compose exec -T backend python3 << 'PYEOF'
import fitz, os, logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_blank(page):
    return len(page.get_text().strip()) < 10

doc = fitz.open("/app/../CVs.pdf")
blank_pages = [i for i in range(len(doc)) if is_blank(doc[i])]
logger.info(f"Found {len(blank_pages)} blank page separators")

cv_boundaries = [[0]]
for blank_idx in blank_pages:
    if cv_boundaries[-1][0] < blank_idx:
        cv_boundaries[-1].append(blank_idx)
        if blank_idx + 1 < len(doc):
            cv_boundaries.append([blank_idx + 1])

if len(cv_boundaries[-1]) == 1:
    cv_boundaries[-1].append(len(doc))

for idx, (start, end) in enumerate(cv_boundaries[:3], 1):
    new_doc = fitz.open()
    for p in range(start, min(end, len(doc))):
        new_doc.insert_pdf(doc, from_page=p, to_page=p)
    new_doc.save(f"/app/data/cvs/cv_{idx:03d}.pdf")
    new_doc.close()
    logger.info(f"CV-{idx}: Pages {start+1}-{end} saved")

doc.close()
logger.info("✓ Split complete! First 3 CVs ready")
PYEOF
```

### Option 2: Using Python Script (Host)
Requires `pymupdf` installation from Docker container:

```bash
docker-compose exec -T backend cp /usr/local/lib/python3.11/site-packages/fitz* /tmp/
# Then run locally (after installing pymupdf)
python3 split_cvs.py
```

### Option 3: Using Bash Wrapper (Host)
Make script executable and run:

```bash
chmod +x run_split_cvs.sh
./run_split_cvs.sh
```

## What Gets Created

When you run the splitter:
- ✅ Reads `CVs.pdf` (main file with all CVs)
- ✅ Detects blank pages as CV separators
- ✅ Extracts first 3 CVs only
- ✅ Saves as: `backend/data/cvs/cv_001.pdf`, `cv_002.pdf`, `cv_003.pdf`
- ✅ These files are automatically picked up by the watcher and processed

## Processing Flow

```
CVs.pdf → Split by blank pages → Individual PDF files (cv_001.pdf, cv_002.pdf, cv_003.pdf)
    ↓
Folder watcher detects new PDFs in backend/data/cvs/
    ↓  
Backend API creates Candidate record + queues Celery task
    ↓
Worker processes: PDF text extract → LLM extraction → Database persist
    ↓
Results stored in database (education, work experience, publications, skills, etc.)
```

## Database Schema Changes

### Before
- `degree_level`, `title`, `institution`, `passing_year` (mismatched fields)

### After
- `stage` - Education level (SSE, HSSC, UG, PG, PhD)
- `degree_title` - Full degree name  
- `specialization` - Major/specialization
- `institution` - University/college name
- `board_or_university` - Board (for SSE/HSSC) or university
- `start_year`, `end_year` - Year range
- `cgpa`, `cgpa_scale` - GPA and scale (4.0, 5.0, etc.)
- `marks_percentage` - Alternative percentage score
- Rankings: `institution_the_ranking`, `institution_qs_ranking`
- Gap tracking: `gap_before_start_months`, `gap_justified_by_experience`

## Extraction Schema Enhancements

New Pydantic schema (`CandidateExtraction`) includes:
- ✅ **EducationRecordExtraction** - Full education details with validation
- ✅ **WorkExperienceExtraction** - Job history with academic role detection
- ✅ **JournalPublicationExtraction** - Research papers with indexing details (WoS, Scopus)
- ✅ **ConferencePublicationExtraction** - Conference papers with CORE ranking
- ✅ **SupervisionRecordExtraction** - Student supervision tracking
- ✅ **BookExtraction** - Published books and chapters
- ✅ **PatentExtraction** - Filed/granted patents
- ✅ **SkillExtraction** - Skills with evidence source tracking

Each schema field includes detailed descriptions for LLM extraction guidance.

## Testing

After splitting and processing CVs, query the database:

```sql
-- Check extracted candidates
SELECT id, name, status FROM candidates;

-- View work experiences
SELECT candidate_id, job_title, organization FROM work_experiences;

-- View education
SELECT candidate_id, stage, degree_title, institution, cgpa FROM education_records;

-- View publications
SELECT candidate_id, title, journal_name, year FROM journal_publications;
```

Access via psql:
```bash
docker exec talashv3-db psql -U talash -d talash -c "YOUR_SQL_HERE"
```

## Troubleshooting

**Issue**: `PyMuPDF not available`
- Solution: Run via Docker (Option 1) or use shell wrapper (Option 2)

**Issue**: No blank pages detected
- Solution: PDFs might use form feeds or other separators. Adjust `is_blank()` function

**Issue**: Only some CVs extracted
- Check `split_cvs.py` capped at 3 CVs. Modify `max_cvs=3` to increase

**Issue**: Files not being processed
- Check `backend/data/cvs/` folder exists and is writable
- Verify worker is running: `docker-compose logs worker`
- Check MongoDB/file watcher logs

---

## Quick Commands Reference

```bash
# Run splitter (Option 1 - Recommended)
docker-compose exec -T backend python3 << 'PYEOF'
# [paste Option 1 code above]
PYEOF

# Check generated CV files
ls -lh backend/data/cvs/cv_*.pdf

# Monitor processing
docker-compose logs -f worker

# Query results
docker exec talashv3-db psql -U talash -d talash -c "SELECT * FROM candidates;"

# View extraction details
docker exec talashv3-db psql -U talash -d talash -c "SELECT id, name, status FROM candidates; SELECT COUNT(*) as work_exp FROM work_experiences; SELECT COUNT(*) as education FROM education_records;"
```
