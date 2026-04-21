"""
TALASH v3 - CV Processing Debugging & Cleanup Guide

This document explains how to use the enhanced logging system and database cleanup
utilities for troubleshooting failed CV processing and maintaining clean data.
"""

# =============================================================================
# 1. DATABASE CLEANUP & FLUSHING
# =============================================================================

"""
The system provides multiple ways to flush incomplete records before running
new CV extractions:

A) VIA HTTP ADMIN ENDPOINTS:
═══════════════════════════════════════════════════════════════════════════════

1. CHECK DATABASE STATUS
   GET http://localhost:8000/api/admin/db-status
   
   Response:
   {
     "completed": 5,
     "processing": 0,
     "failed": 2,
     "pending": 3
   }

2. FLUSH INCOMPLETE RECORDS (failed, processing, pending)
   POST http://localhost:8000/api/admin/flush-incomplete
   
   Response:
   {
     "status": "success",
     "deleted": {
       "candidates": 2,
       "education": 8,
       "experience": 6,
       "journals": 15,
       "conferences": 12,
       "skills": 45,
       "patents": 0,
       "books": 2,
       "supervision": 3
     },
     "total": 93,
     "message": "Successfully flushed 93 incomplete records"
   }

3. FLUSH ALL RECORDS (⚠️ WARNING - total database reset)
   POST http://localhost:8000/api/admin/flush-all
   
   Response:
   {
     "status": "success",
     "deleted": {...},
     "total": 150,
     "warning": "ALL candidates and related records have been permanently deleted"
   }

B) VIA PYTHON SCRIPT:
═══════════════════════════════════════════════════════════════════════════════

from backend.app.db import SessionLocal
from backend.app.utils.db_cleanup import flush_incomplete_records, get_cleanup_summary

db = SessionLocal()

# 1. Preview records to delete
summary = get_cleanup_summary(db)
# Output:
# [CLEANUP-SUMMARY]
#   ├─ COMPLETED: 5
#   ├─ PROCESSING (incomplete): 0
#   ├─ FAILED: 2
#   └─ PENDING (not started): 3

# 2. Flush specific statuses
deleted = flush_incomplete_records(db, statuses=["failed", "processing", "pending"])
# Output shows detailed breakdown of deleted records

# 3. Flush all records
deleted = flush_incomplete_records(db, statuses=["all"])

db.close()

C) VIA CELERY WORKER CLI:
═══════════════════════════════════════════════════════════════════════════════

If you want to create a Celery task for cleanup (optional):

from celery import shared_task
from backend.app.db import SessionLocal
from backend.app.utils.db_cleanup import flush_incomplete_records

@shared_task(name="cleanup_incomplete_records")
def cleanup_task():
    db = SessionLocal()
    result = flush_incomplete_records(db, statuses=["failed", "processing"])
    db.close()
    return result

# Then invoke:
# celery -A backend.worker.celery_app call cleanup_incomplete_records
"""

# =============================================================================
# 2. ENHANCED LOGGING SYSTEM
# =============================================================================

"""
The CV processing pipeline now includes comprehensive stage-by-stage logging
with timing information and detailed error reporting.

LOG LEVELS & FORMAT:
═══════════════════════════════════════════════════════════════════════════════

Each task execution now generates logs in this structure:

[TASK-START]              → Task initialization (TaskID, CandidateID, Retry count)
[STAGE-1] LOAD            → Details about loading candidate from database
[STAGE-2] PDF             → PDF extraction with text length and timing
[STAGE-3] LLM             → LLM call with provider info, token counts, timing
[STAGE-4] DB              → Database persistence with record counts by type
[TASK-SUCCESS]            → Final summary with all timings
[TASK-FAILED]             → Error analysis with stage, type, and traceback

EXAMPLE LOG OUTPUT:
═══════════════════════════════════════════════════════════════════════════════

======================================================================================================================
[TASK-START] ===== CV PROCESSING TASK STARTED =====
[TASK-START] TaskID: 6a9c2d4b-f1e3-4c5a-9d2e-3f1a4b5c6d7e | CandidateID: 42 | Retry: 0/2
======================================================================================================================
[STAGE-1] LOAD CANDIDATE FROM DATABASE
======================================================================================================================
[1.1] Querying database for candidate...
[1.2] Candidate loaded successfully
      ├─ Name: Ahmed Hassan
      ├─ Email: ahmed@example.com
      ├─ File Path: backend/data/cvs/ahmed_hassan.pdf
      ├─ Status: pending
      └─ Duration: 0.12 sec
[1.3] Candidate status set to 'processing' (lock acquired)

======================================================================================================================
[STAGE-2] EXTRACT TEXT FROM PDF
======================================================================================================================
[2.1] Reading PDF file: backend/data/cvs/ahmed_hassan.pdf
[2.2] PDF extraction successful
      ├─ Text length: 8,547 characters
      ├─ Paragraphs: ~127
      └─ Duration: 1.34 sec

======================================================================================================================
[STAGE-3] SEND TO LLM FOR STRUCTURED EXTRACTION
======================================================================================================================
[3.1] Initializing LLM extraction service...
[3.2] Sending CV text to LLM (max_tokens=4000, temp=0)...
[3.3] LLM extraction successful
      ├─ Candidate Name: Ahmed Hassan
      ├─ Email: ahmed@example.com
      ├─ Education Records: 3
      ├─ Work Experiences: 2
      ├─ Journal Publications: 5
      ├─ Conference Publications: 2
      ├─ Supervision Records: 0
      ├─ Skills: 12
      ├─ Patents: 0
      ├─ Books: 1
      └─ Duration: 8.67 sec

======================================================================================================================
[STAGE-4] PERSIST EXTRACTED DATA TO DATABASE
======================================================================================================================
[4.1] Updating candidate PII...
[4.2] Inserting education records...
[4.2] ✓ Education: 3 records queued
[4.3] Inserting work experience records...
[4.3] ✓ Work Experience: 2 records queued
[4.4] Inserting journal publication records...
[4.4] ✓ Journal Publications: 5 records queued
[4.5] Inserting conference publication records...
[4.5] ✓ Conference Publications: 2 records queued
[4.6] Inserting supervision records...
[4.6] ✓ Supervision Records: 0 records queued
[4.7] Inserting skill records...
[4.7] ✓ Skills: 12 records queued
[4.8] Inserting patent records...
[4.8] ✓ Patents: 0 records queued
[4.9] Inserting book records...
[4.9] ✓ Books: 1 records queued
[4.10] Committing all changes to database...
[4.10] ✓ Commit successful - all data persisted
        Summary:
          ├─ Education: 3
          ├─ Work Experiences: 2
          ├─ Journal Publications: 5
          ├─ Conference Publications: 2
          ├─ Supervision Records: 0
          ├─ Skills: 12
          ├─ Patents: 0
          └─ Books: 1
        Duration: 0.89 sec

======================================================================================================================
[TASK-SUCCESS] ===== CV PROCESSING COMPLETED SUCCESSFULLY =====
[TASK-SUCCESS] CandidateID: 42 | Name: Ahmed Hassan
[TASK-SUCCESS] Total Duration: 11.02 sec
[TASK-SUCCESS] Stage Breakdown:
       ├─ Load: 0.12 sec
       ├─ PDF Extraction: 1.34 sec
       ├─ LLM Extraction: 8.67 sec
       └─ DB Persistence: 0.89 sec
======================================================================================================================


UNDERSTANDING ERROR LOGS:
═══════════════════════════════════════════════════════════════════════════════

When a task fails, the error log provides:

1. ERROR STAGE: Which stage failed (1-4)
   - Stage 1: Database load failure
   - Stage 2: PDF extraction failure (missing file, corrupted PDF, etc.)
   - Stage 3: LLM API failure (timeout, rate limit, invalid response)
   - Stage 4: Database persist failure (constraint violation, connection error)

2. ERROR TYPE: Python exception class name
   - ValueError: Invalid data (e.g., empty PDF text, missing name)
   - ConnectionError: Network/API connectivity issue
   - DatabaseError: SQL/constraint violation
   - TimeoutError: LLM API exceeded timeout
   - FileNotFoundError: PDF file path doesn't exist

3. ERROR MESSAGE: Detailed description of what went wrong

4. TRACEBACK: Full Python stack trace for debugging

Example Error Log:
──────────────────────────────────────────────────────────────────────────────
======================================================================================================================
[TASK-FAILED] ===== CV PROCESSING FAILED =====
[TASK-FAILED] CandidateID: 42 | TaskID: 6a9c2d4b-f1e3-4c5a-9d2e-3f1a4b5c6d7e
[TASK-FAILED] Error Stage: 3
[TASK-FAILED] Error Type: TimeoutError
[TASK-FAILED] Error Message: LLM extraction failed: Request timed out after 30s. Ensure LLM API is responding.
[TASK-FAILED] Total Duration: 10.45 sec
[TASK-FAILED] Traceback:
   ...full stack trace...
======================================================================================================================
"""

# =============================================================================
# 3. QUICK TROUBLESHOOTING GUIDE
# =============================================================================

"""
ISSUE 1: "PDF extraction yielded insufficient text"
───────────────────────────────────────────────────────────────────────────────
CAUSE: PDF file is corrupted, encrypted, or image-only (no text)
SOLUTION:
  1. Check if PDF file exists and is readable
  2. Verify PDF is not password-protected
  3. If PDF is image-heavy, ensure Tesseract OCR is installed (for fallback)
  4. Re-upload PDF file

LOG TO CHECK:
[STAGE-2] EXTRACT TEXT FROM PDF
[2-PDF-ERROR] PDF extraction yielded insufficient text (245 chars, minimum required: 100)


ISSUE 2: "LLM extraction returned invalid name"
───────────────────────────────────────────────────────────────────────────────
CAUSE: LLM failed to extract candidate name (API error, rate limit, invalid response)
SOLUTION:
  1. Check LLM API key and connectivity
  2. Verify CV text is not truncated/corrupted
  3. Check for API rate limits (delay before retrying)
  4. Verify LLM provider is responding (test with simple curl call)

LOG TO CHECK:
[STAGE-3] SEND TO LLM FOR STRUCTURED EXTRACTION
[3-LLM-ERROR] LLM extraction returned invalid name: 'Extraction Failed'
[3-LLM-ERROR-REASON] LLM Error (groq): Connection timeout


ISSUE 3: "Database error: Duplicate entry"
───────────────────────────────────────────────────────────────────────────────
CAUSE: Candidate email already exists (duplicate candidate or re-processing issue)
SOLUTION:
  1. Flush incomplete records: POST /api/admin/flush-incomplete
  2. Check if candidate already exists with completed status
  3. If re-processing needed, manually set status to "pending" first

LOG TO CHECK:
[STAGE-4] PERSIST EXTRACTED DATA TO DATABASE
[4-DB-ERROR] Failed to insert work experience: Duplicate entry for 'candidates.email'


ISSUE 4: "Candidate status set to 'processing' but never completed"
───────────────────────────────────────────────────────────────────────────────
CAUSE: Task crashed before completing, leaving candidate in "processing" state
SOLUTION:
  1. Check task logs for [TASK-FAILED] to see where it crashed
  2. Fix underlying issue (API, file, database)
  3. Flush incomplete records: POST /api/admin/flush-incomplete
  4. Re-submit CV

LOG TO CHECK:
Search for [TASK-FAILED] in logs to identify root cause


ISSUE 5: "Half-processed records contaminating results"
───────────────────────────────────────────────────────────────────────────────
CAUSE: Previous extraction crashed, leaving incomplete data
SOLUTION:
  1. Flush all incomplete records: POST /api/admin/flush-incomplete
  2. This removes any candidate with status != "completed"
  3. Verify cleanup with: GET /api/admin/db-status

LOG TO CHECK:
[CLEANUP-SUMMARY]
  ├─ COMPLETED: 5
  ├─ PROCESSING (incomplete): 2      ← These will be flushed
  ├─ FAILED: 3                       ← These will be flushed
  └─ PENDING (not started): 1        ← These will be flushed
"""

# =============================================================================
# 4. MONITORING & BEST PRACTICES
# =============================================================================

"""
SETTING UP MONITORING:
═══════════════════════════════════════════════════════════════════════════════

1. CHECK DATABASE HEALTH BEFORE PROCESSING
   GET /api/admin/db-status
   
   Ensure no "processing" or "failed" candidates exist
   If they do, run: POST /api/admin/flush-incomplete

2. MONITOR TASK LOGS IN REAL-TIME
   
   # Watch Celery worker logs
   tail -f backend/logs/celery.log | grep -i "task"
   
   # Filter for failures
   tail -f backend/logs/celery.log | grep -i "failed"
   
   # Filter for timing analysis
   tail -f backend/logs/celery.log | grep -i "duration"

3. SET UP ALERTING FOR FAILURES
   
   Search logs for: [TASK-FAILED]
   Alert when any CV processing fails
   Investigate error_stage + error_type to diagnose

4. TRACK PERFORMANCE METRICS
   
   Extract timing data from logs:
   - Load time: typically 0.1-0.2 sec
   - PDF extraction: typically 1-3 sec (depends on PDF size)
   - LLM extraction: typically 5-15 sec (depends on LLM provider)
   - DB persistence: typically 0.5-1.5 sec
   
   Total: expect 7-20 sec per CV

BEST PRACTICES:
═══════════════════════════════════════════════════════════════════════════════

1. BEFORE EACH BATCH RUN:
   - Check db-status endpoint
   - Flush incomplete records if needed
   - Verify LLM API is healthy
   - Verify all PDF files exist

2. DURING PROCESSING:
   - Monitor logs for [TASK-FAILED]
   - Watch for timeouts or rate limits
   - Track stage durations to spot bottlenecks

3. AFTER BATCH PROCESSING:
   - Verify all records have status="completed"
   - Check for any "failed" records
   - Export reports for billing/auditing

4. REGULAR MAINTENANCE:
   - Weekly: Review and delete failed records
   - Monthly: Archive completed records to cold storage
   - Quarterly: Analyze performance metrics and optimize
"""
