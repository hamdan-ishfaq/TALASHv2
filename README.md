# TALASH v3 - CV Processing Pipeline

## Project Status: Partially Working (Fallback Mode Active)

### ✅ Fully Functional Components

#### Backend Infrastructure
- **FastAPI Server** (Port 8000) - ✅ Running with auto-reload
- **PostgreSQL Database** (Port 5433) - ✅ Connected and operational
- **Redis** (Port 6379) - ✅ Message broker for Celery
- **Celery Worker** - ✅ Processing async tasks
- **Flower** (Port 5555) - ✅ Celery monitoring dashboard

#### API Endpoints
- `POST /upload` - ✅ Multipart file upload with deduplication via SHA-256 hash
- `POST /upload-from-path` - ✅ Direct filesystem upload (for testing)
- Returns: `{candidate_id, status, duplicate, task_id}`

#### PDF Processing
- **Hybrid Extraction** - ✅ Combines PyMuPDF (fitz) + pdfplumber
- **Text Extraction** - ✅ Successfully extracts PDF text (tested: 25,960 chars from candidate_006.pdf)
- **Fallback Parser** - ✅ Gracefully handles extraction errors

#### Database Operations
- **Candidate Model** - ✅ Stores PII, raw_text, summary, status
- **Relationships** - ✅ EducationRecord, WorkExperience, Publication, etc.
- **Task Queueing** - ✅ Celery tasks persist with file_hash for idempotency
- **Data Persistence** - ✅ Confirmed working (tested with candidate_id=3)

#### Logging & Monitoring
- **Comprehensive Logging** - ✅ ~400+ structured stage markers throughout pipeline
  - `[STAGE-1]` Database lookup
  - `[STAGE-2]` PDF parsing
  - `[STAGE-3]` LLM extraction
  - `[STAGE-4]` Core data commit
  - `[STAGE-5]` Summary generation
- **Error Handling** - ✅ Graceful exception handling with rollback support
- **Status Tracking** - ✅ `queued` → `processing` → `completed_with_fallback` / `failed`

#### Task Processing
- **Celery Integration** - ✅ Tasks queue and execute properly
- **Execution Pipeline** - ✅ 5-stage processing works end-to-end
- **Idempotency** - ✅ File hash prevents duplicate processing
- **Tested Execution Time** - 47.27 seconds for candidate_006.pdf (2nd pass had Ollama failures)

### ⚠️ Partially Working / Fallback Mode

#### LLM-Based Extraction
- **Status**: ⚠️ Ollama integration not active (service not running)
- **Behavior**: System gracefully falls back to basic extraction
- **Fallback Mechanism**: ✅ 
  - Extracts name from first non-empty line
  - Attempts regex email parsing (not found in test PDF)
  - Generates fallback summary text
- **Result Status**: `completed_with_fallback` instead of `completed`

#### Structured Data Extraction (Education/Experience)
- **Status**: ❌ Not extracted (0 records)
- **Reason**: Requires successful LLM extraction; fallback skips structured fields
- **When Working**: Will extract and deduplicate education/experience records

#### Summary Generation
- **Status**: ⚠️ Fallback summary only
- **Current**: Generic text ("Fallback extraction (Ollama unavailable) - Basic PII extraction completed")
- **When Working**: AI-generated 4-6 line professional summary

### ❌ Not Yet Implemented

- Ollama/LLM service in docker-compose (requires large image download)
- Full two-pass extraction (Pass A: headers + Pass B: full text)
- Publication, Supervision, Book, Patent, Skill extraction
- Score/Rating system
- Batch processing UI
- Resume PDF generation from extracted data
- Email notifications
- Authentication/Authorization

### Test Results

#### Last Execution (Task ID: 775b6c93-8fd4-4382-bbd2-f70dfd9bb888)
- **File**: candidate_006.pdf (547.8 KB)
- **Candidate ID**: 3
- **Execution Time**: 47.27 seconds
- **Final Status**: `completed_with_fallback`
- **Database Result**: ✅ Record created with raw_text (25,960 chars) and summary

#### Detailed Execution Log
```
[STAGE-1] Database lookup ✅
[STAGE-2] PDF parsing ✅ (25,960 characters extracted)
[STAGE-3] LLM extraction ⚠️ (Ollama unavailable, fallback triggered)
[STAGE-4] Core data commit ✅ (0 education, 0 experience records)
[STAGE-5] Summary generation ✅ (fallback summary)
RESULT: completed_with_fallback ✅
```

### Architecture

```
FastAPI Backend (8000)
    ↓
Celery Worker + Redis (6379)
    ↓
PostgreSQL (5433)
    ↓
[PDF Parser] → [LLM Extractor] → [Database]
```

### Environment & Dependencies

**Python**: 3.11-slim in Docker
**Key Packages**:
- fastapi==0.135.0, uvicorn
- sqlalchemy==2.0.23, psycopg2-binary
- celery==5.6.3
- redis==5.0.1
- instructor==1.15.1 (LLM structured output)
- ollama (client library - service not running)
- PyMuPDF==1.24.8 (fitz)
- pdfplumber==0.11.2
- flower==2.0.1

### Running the System

```bash
# Start all services
docker compose up -d --build

# View logs
docker compose logs -f worker
docker compose logs -f backend

# Process a CV from filesystem
curl -X POST "http://localhost:8000/upload-from-path?file_path=/app/data/cvs/candidate_006.pdf"

# Check database
docker exec talashv3-db psql -U talash -d talash \
  -c "SELECT id, name, status, LENGTH(raw_text) FROM candidates;"
```

### Next Steps to Full Functionality

1. **Add Ollama with lightweight model** (e.g., `phi-3` instead of `llama3.1`)
   - Update docker-compose.yml
   - Pull model: `ollama pull phi-3`
   - Restart worker

2. **Test LLM extraction**
   - Reprocess test CVs
   - Verify education/experience extraction
   - Check structured output

3. **Scale to batch processing**
   - Process all 41 CVs in cv_holding directory
   - Monitor task queue and performance

4. **Add web UI**
   - Dashboard for upload/status
   - Result viewing interface

### Known Issues & Workarounds

| Issue | Workaround |
|-------|-----------|
| Ollama not running | System uses fallback - no crash, graceful degradation |
| LLM extraction fails | Falls back to basic name extraction |
| No structured data | Education/experience not extracted in fallback mode |
| Flower sometimes slow | Redis cache can be cleared: `redis-cli FLUSHALL` |

### Git Configuration

- **Author**: khadijafaisal
- **Email**: Kfaisal.bsds23seecs@seecs.edu.pk
- **Repository**: https://github.com/hamdan-ishfaq/TALASHv2

### Files Structure

```
backend/
  ├── app/
  │   ├── models/models.py          # 9 SQLAlchemy models
  │   ├── services/
  │   │   ├── pdf_parser.py        # Hybrid PDF extraction
  │   │   ├── extractor.py         # LLM-based extraction
  │   ├── routers/upload.py        # Upload endpoints
  │   ├── db.py                    # Database session
  │   ├── worker.py                # Celery app config
  │   └── main.py                  # FastAPI app
  ├── worker/
  │   └── cv_tasks.py              # Celery task (5-stage pipeline)
  ├── data/cvs/                    # PDF storage
  ├── Dockerfile
  └── requirements.txt
docker-compose.yml
.gitignore
README.md
```

---

**Last Updated**: April 13, 2026
**Status**: In Development - Core pipeline working with graceful fallback
