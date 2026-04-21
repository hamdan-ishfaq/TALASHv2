"""
╔═══════════════════════════════════════════════════════════════════════════════════╗
║                   TALASH v3 QUICK START GUIDE                                   ║
║                                                                                   ║
║  Complete instructions for starting the backend and monitoring CV processing     ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
"""

# ============================================================================
# STEP 1: START THE ENTIRE BACKEND STACK
# ============================================================================

QUICK START:
─────────────────────────────────────────────────────────────────────────────

Option A: Using the startup script (RECOMMENDED)

  🐧 Linux/Mac:
     chmod +x START_BACKEND.sh
     ./START_BACKEND.sh

  🪟 Windows:
     START_BACKEND.bat
     
     (Or run in PowerShell:)
     powershell -ExecutionPolicy Bypass -File START_BACKEND.bat


Option B: Manual startup with Docker Compose

  1. Navigate to project root:
     cd talashv3

  2. Build and start all services:
     docker-compose up -d --build

  3. Wait 10 seconds for all services to start:
     sleep 10

  4. Verify services are running:
     docker-compose ps
     
     Expected output:
     NAME                        STATUS
     talashv3-db                 Up 
     talashv3-redis              Up 
     talashv3-backend            Up 
     talashv3-worker             Up 
     talashv3-flower             Up 


# ============================================================================
# STEP 2: ACCESS THE API DOCUMENTATION & SERVICES
# ============================================================================

SWAGGER API DOCUMENTATION (Interactive):
─────────────────────────────────────────────────────────────────────────────
   🌐 http://localhost:8000/docs
   
   This is the Swagger UI where you can:
   • View all API endpoints
   • Test endpoints interactively
   • Upload CVs
   • Check database status
   • Flush incomplete records


CELERY MONITORING (Task Queue Dashboard):
─────────────────────────────────────────────────────────────────────────────
   🌐 http://localhost:5555
   
   Flower shows:
   • Active tasks being processed
   • Task history and results
   • Worker status and availability
   • Task failure details and retries


HEALTH CHECK ENDPOINT:
─────────────────────────────────────────────────────────────────────────────
   GET http://localhost:8000/health
   
   Returns: {"system": "healthy"}


# ============================================================================
# STEP 3: REAL-TIME LOG MONITORING (MOST IMPORTANT!)
# ============================================================================

To see CV processing happening in REAL-TIME, use one of these commands
in your terminal/PowerShell:

OPTION 1: Watch ALL Service Logs (Everything)
─────────────────────────────────────────────────────────────────────────────
Windows (PowerShell):
   docker-compose logs -f --tail=100

Linux/Mac:
   docker-compose logs -f --tail=100

Output: Shows all containers' logs live (DB, Redis, Backend, Worker, Flower)


OPTION 2: Watch ONLY Backend Logs (API requests)
─────────────────────────────────────────────────────────────────────────────
Windows (PowerShell):
   docker-compose logs -f backend --tail=100

Linux/Mac:
   docker-compose logs -f backend --tail=100

Output: Only FastAPI backend logs (CV upload requests, etc.)


OPTION 3: Watch ONLY CV Processing Logs (WORKER - BEST FOR DEBUGGING)
─────────────────────────────────────────────────────────────────────────────
Windows (PowerShell):
   docker-compose logs -f worker --tail=100

Linux/Mac:
   docker-compose logs -f worker --tail=100

Output: Only Celery worker logs (actual CV extraction pipeline)
        Shows all the detailed STAGE-1, STAGE-2, STAGE-3, STAGE-4 logs


OPTION 4: Watch CV Processing with Color-Filtered Output (RECOMMENDED)
─────────────────────────────────────────────────────────────────────────────

Windows (PowerShell):
   docker-compose logs -f worker --tail=100 | findstr /I "STAGE TASK ERROR SUCCESS Duration"

Linux/Mac:
   docker-compose logs -f worker --tail=100 | grep -E "(STAGE|TASK|ERROR|SUCCESS|Duration)"

Output: Only shows important CV processing events:
        ✓ [STAGE-1] LOAD CANDIDATE
        ✓ [STAGE-2] EXTRACT PDF
        ✓ [STAGE-3] LLM EXTRACTION
        ✓ [STAGE-4] DATABASE PERSISTENCE
        ✓ [TASK-SUCCESS]
        ✗ [TASK-FAILED]


OPTION 5: Follow a Single CV Processing Task LIVE
─────────────────────────────────────────────────────────────────────────────

Windows (PowerShell):
   docker-compose logs -f worker --tail=200 | findstr "CandidateID: X"
   # Replace X with actual candidate ID

Linux/Mac:
   docker-compose logs -f worker --tail=200 | grep "CandidateID: X"

Output: Shows only logs for that specific candidate


OPTION 6: Monitor Task Queue Status (Celery)
─────────────────────────────────────────────────────────────────────────────

Windows (PowerShell):
   docker-compose logs -f worker --tail=100 | findstr /I "active reserved"

Linux/Mac:
   docker-compose logs -f worker --tail=100 | grep -i "active\|reserved"

Output: Shows active tasks in the queue


OPTION 7: Find Failed Tasks ONLY
─────────────────────────────────────────────────────────────────────────────

Windows (PowerShell):
   docker-compose logs worker --tail=500 | findstr /I "FAILED ERROR Exception"

Linux/Mac:
   docker-compose logs worker --tail=500 | grep -i "FAILED\|ERROR\|Exception"

Output: Only shows failed processing attempts


# ============================================================================
# STEP 4: UPLOAD A CV AND WATCH IT PROCESS
# ============================================================================

METHOD 1: Using Swagger UI (Easy)
─────────────────────────────────────────────────────────────────────────────
   1. Go to http://localhost:8000/docs
   2. Find "/upload" endpoint
   3. Click "Try it out"
   4. Select a PDF file from backend/data/cvs/
   5. Click "Execute"
   
   ✨ Your CV is now in the processing queue!


METHOD 2: Using cURL or Invoke-WebRequest
─────────────────────────────────────────────────────────────────────────────

Windows (PowerShell):
   $file = "C:\path\to\cv.pdf"
   $form = @{ file = Get-Item $file }
   Invoke-WebRequest -Uri "http://localhost:8000/upload" `
                     -Method Post `
                     -Form $form

Linux/Mac (cURL):
   curl -X POST -F "file=@backend/data/cvs/sample.pdf" \
        http://localhost:8000/upload


REAL-TIME MONITORING FLOW:
─────────────────────────────────────────────────────────────────────────────

Terminal 1: Upload the CV
   $ curl -X POST -F "file=@sample.pdf" http://localhost:8000/upload
   # Returns: {"candidate_id": 42, "status": "queued"}

Terminal 2: Watch processing in real-time
   $ docker-compose logs -f worker --tail=100 | grep -E "(STAGE|TASK|Duration)"
   
   Output:
   ======================================================
   [TASK-START] CandidateID: 42
   [STAGE-1] LOAD CANDIDATE... ✓ Duration: 0.12 sec
   [STAGE-2] EXTRACT PDF... ✓ Duration: 1.34 sec
   [STAGE-3] LLM EXTRACTION... ✓ Duration: 8.67 sec
   [STAGE-4] DB PERSISTENCE... ✓ Duration: 0.89 sec
   [TASK-SUCCESS] Total: 11.02 sec
   ======================================================


# ============================================================================
# STEP 5: ADMIN ENDPOINTS FOR DATABASE MANAGEMENT
# ============================================================================

CHECK DATABASE STATUS:
─────────────────────────────────────────────────────────────────────────────

Windows (PowerShell):
   (Invoke-WebRequest http://localhost:8000/api/admin/db-status).Content | ConvertFrom-Json

Linux/Mac (cURL):
   curl http://localhost:8000/api/admin/db-status | python -m json.tool

Response:
   {
     "completed": 5,
     "processing": 0,
     "failed": 2,
     "pending": 1
   }


FLUSH INCOMPLETE RECORDS (Before batch runs):
─────────────────────────────────────────────────────────────────────────────

Windows (PowerShell):
   Invoke-WebRequest -Method POST http://localhost:8000/api/admin/flush-incomplete

Linux/Mac (cURL):
   curl -X POST http://localhost:8000/api/admin/flush-incomplete

Response:
   {
     "status": "success",
     "deleted": {
       "candidates": 2,
       "education": 8,
       "experience": 6,
       "journals": 15,
       ...
     },
     "total": 93
   }


# ============================================================================
# STEP 6: STOPPING AND DEBUGGING
# ============================================================================

STOP ALL SERVICES:
─────────────────────────────────────────────────────────────────────────────

Windows/Linux/Mac:
   docker-compose down

   (Keep data - database won't be deleted)


STOP ALL AND REMOVE DATA (Clean reset):
─────────────────────────────────────────────────────────────────────────────

Windows/Linux/Mac:
   docker-compose down -v

   ⚠️ WARNING: This deletes all database data!


VIEW LOGS FROM PAST (Not live, just history):
─────────────────────────────────────────────────────────────────────────────

Windows/Linux/Mac:
   docker-compose logs backend --tail=200     # Backend logs
   docker-compose logs worker --tail=200      # Worker logs
   docker-compose logs db --tail=50           # Database logs


REBUILD CONTAINERS (If code changed):
─────────────────────────────────────────────────────────────────────────────

Windows/Linux/Mac:
   docker-compose up -d --build

   FastAPI will auto-reload on file changes (--reload flag in docker-compose.yml)


SHELL INTO A CONTAINER (For debugging):
─────────────────────────────────────────────────────────────────────────────

Windows/Linux/Mac - Access backend shell:
   docker-compose exec backend bash

Access database shell:
   docker-compose exec db psql -U talash -d talash


# ============================================================================
# HELPFUL REFERENCE: LOG INTERPRETATION GUIDE
# ============================================================================

WHEN YOU SEE THESE LOGS, IT MEANS:
─────────────────────────────────────────────────────────────────────────────

[STAGE-1] LOAD CANDIDATE
└─ Candidate loaded from database (connects to PostgreSQL)
   Duration: ~0.1 sec

[STAGE-2] EXTRACT PDF
└─ Python extracts text from PDF file
   Duration: ~1-3 sec (depends on PDF size/complexity)

[STAGE-3] LLM EXTRACTION
└─ LLM (GPT-4o/Groq/Ollama) extracts structured data from CV text
   Duration: ~5-15 sec (depends on LLM provider and CV length)

[STAGE-4] DB PERSISTENCE
└─ All extracted data saved to PostgreSQL database
   Duration: ~0.5-1.5 sec

[TASK-SUCCESS]
└─ CV processing completed successfully ✨

[TASK-FAILED]
└─ Something went wrong - check error_stage and error_type
   Common causes:
   - Invalid PDF file
   - LLM API timeout
   - Database connection error
   - Insufficient text in PDF


# ============================================================================
# TROUBLESHOOTING
# ============================================================================

Q: I don't see any logs when I run the log command
A: 
   1. Make sure worker container is running: docker-compose ps
   2. Upload a CV to trigger processing: curl -X POST -F "file=@sample.pdf" ...
   3. Try the "all services" log command: docker-compose logs -f --tail=100

Q: Backend won't start
A:
   1. Check if port 8000 is already in use
   2. Clear volumes: docker-compose down -v
   3. Rebuild: docker-compose up -d --build
   4. Check logs: docker-compose logs backend

Q: CV processing shows FAILED - what went wrong?
A:
   1. Check error_stage in logs (1, 2, 3, or 4)
   2. Find the [TASK-FAILED] error message
   3. Refer to "Log Interpretation Guide" above
   4. Check specific error logs: docker-compose logs worker | grep "stage-X"

Q: "Insufficient text in PDF" error
A:
   1. Verify PDF is not image-only (no OCR installed)
   2. Use a text-based PDF, not scanned image
   3. Ensure PDF has at least 100 characters of extractable text

Q: LLM extraction timing out
A:
   1. Check if LLM provider (Groq/OpenRouter) is responding
   2. Test: curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer YOUR_KEY"
   3. Try different provider: modify env vars in docker-compose.yml
   4. Increase timeout: modify max_tokens in extractor.py


═══════════════════════════════════════════════════════════════════════════════════
                              YOU'RE ALL SET! 🚀
═══════════════════════════════════════════════════════════════════════════════════
"""
