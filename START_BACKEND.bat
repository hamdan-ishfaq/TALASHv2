@echo off
REM ============================================================================
REM TALASH v3 Backend Startup Script (Windows)
REM ============================================================================
REM This script starts the entire Docker stack with all services
REM ============================================================================

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ╔══════════════════════════════════════════════════════════════════════════════════════╗
echo ║                    TALASH v3 BACKEND STARTUP SEQUENCE                               ║
echo ╚══════════════════════════════════════════════════════════════════════════════════════╝
echo.

REM Check if Docker is running
echo [1/5] Checking Docker daemon...
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running. Please start Docker Desktop.
    pause
    exit /b 1
)
echo ✓ Docker is running
echo.

REM Stop existing containers
echo [2/5] Cleaning up existing containers...
docker-compose down --remove-orphans 2>nul
echo ✓ Cleanup complete
echo.

REM Build images
echo [3/5] Building Docker images (this may take a few minutes)...
docker-compose build --no-cache
if errorlevel 1 (
    echo ❌ Build failed
    pause
    exit /b 1
)
echo ✓ Images built successfully
echo.

REM Start services
echo [4/5] Starting all services...
docker-compose up -d
if errorlevel 1 (
    echo ❌ Failed to start services
    pause
    exit /b 1
)
echo ✓ All containers started
echo.

REM Wait for services
echo [5/5] Waiting for services to be ready...
timeout /t 5 /nobreak
echo.

echo ╔══════════════════════════════════════════════════════════════════════════════════════╗
echo ║                     SERVICE STATUS ^& CONNECTION DETAILS                            ║
echo ╚══════════════════════════════════════════════════════════════════════════════════════╝
echo.
echo ✓ PostgreSQL (port 5433)
echo   └─ Connection: postgres://talash:talash@localhost:5433/talash
echo.
echo ✓ Redis (port 6379)
echo   └─ Connection: redis://localhost:6379/0
echo.
echo ✓ FastAPI Backend (port 8000)
echo.

echo ╔══════════════════════════════════════════════════════════════════════════════════════╗
echo ║                         IMPORTANT LINKS ^& COMMANDS                                  ║
echo ╚══════════════════════════════════════════════════════════════════════════════════════╝
echo.
echo 📚 API DOCUMENTATION (Swagger/OpenAPI):
echo    → http://localhost:8000/docs
echo.
echo 📊 CELERY MONITORING (Flower):
echo    → http://localhost:5555
echo.
echo 🏥 HEALTH CHECK:
echo    → http://localhost:8000/health
echo.
echo ────────────────────────────────────────────────────────────────────────────────────────────
echo.
echo 🔴 REAL-TIME LOG MONITORING (Copy ^& paste these commands in PowerShell):
echo.
echo  1️⃣  Watch ALL services in real-time:
echo     docker-compose logs -f --tail=100
echo.
echo  2️⃣  Watch ONLY Backend (FastAPI) logs:
echo     docker-compose logs -f backend --tail=100
echo.
echo  3️⃣  Watch ONLY CV Processing (Celery Worker) logs:
echo     docker-compose logs -f worker --tail=100
echo.
echo  4️⃣  Watch CV Processing with color-coded extraction stages:
echo     docker-compose logs -f worker --tail=100 ^| findstr /I "STAGE TASK ERROR SUCCESS Duration"
echo.
echo ────────────────────────────────────────────────────────────────────────────────────────────
echo.
echo 💡 QUICK COMMANDS (PowerShell):
echo.
echo  Check database status:
echo    Invoke-WebRequest http://localhost:8000/api/admin/db-status ^| ConvertFrom-Json
echo.
echo  Flush incomplete records:
echo    Invoke-WebRequest -Method POST http://localhost:8000/api/admin/flush-incomplete ^| ConvertFrom-Json
echo.
echo ────────────────────────────────────────────────────────────────────────────────────────────
echo.
echo ✅ BACKEND IS READY!
echo.
echo Next steps:
echo  1. Open http://localhost:8000/docs in your browser
echo  2. Upload a CV
echo  3. Use the log commands above to see processing in real-time
echo.
echo To stop all services:
echo  docker-compose down
echo.

pause
