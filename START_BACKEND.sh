#!/bin/bash
# ============================================================================
# TALASH v3 Backend Startup Script
# ============================================================================
# This script starts the entire Docker stack with all services:
# - PostgreSQL Database
# - Redis (Cache & Message Queue)
# - FastAPI Backend (with auto-reload)
# - Celery Worker (CV Processing Tasks)
# - Flower (Celery Monitoring)
# ============================================================================

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════════════════╗"
echo "║                       TALASH v3 BACKEND STARTUP SEQUENCE                                ║"
echo "╚══════════════════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if Docker is running
echo "[1/5] Checking Docker daemon..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop or daemon."
    exit 1
fi
echo "✓ Docker is running"
echo ""

# Stop any existing containers
echo "[2/5] Cleaning up existing containers..."
docker-compose down --remove-orphans 2>/dev/null || true
echo "✓ Cleanup complete"
echo ""

# Build images
echo "[3/5] Building Docker images (this may take a few minutes)..."
docker-compose build --no-cache
echo "✓ Images built successfully"
echo ""

# Start services
echo "[4/5] Starting all services..."
docker-compose up -d
echo "✓ All containers started"
echo ""

# Wait for services to be ready
echo "[5/5] Waiting for services to be ready..."
sleep 5

# Check service health
echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════════════════╗"
echo "║                       SERVICE STATUS & CONNECTION DETAILS                               ║"
echo "╚══════════════════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check PostgreSQL
if docker-compose exec -T db pg_isready -U talash > /dev/null 2>&1; then
    echo "✓ PostgreSQL (port 5433)"
    echo "  └─ Connection: postgres://talash:talash@localhost:5433/talash"
else
    echo "⚠ PostgreSQL still starting..."
fi
echo ""

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis (port 6379)"
    echo "  └─ Connection: redis://localhost:6379/0"
else
    echo "⚠ Redis still starting..."
fi
echo ""

# Check Backend
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ FastAPI Backend (port 8000)"
else
    echo "⚠ Backend still starting..."
fi
echo ""

# Display API endpoints
echo "╔══════════════════════════════════════════════════════════════════════════════════════════╗"
echo "║                            IMPORTANT LINKS & COMMANDS                                   ║"
echo "╚══════════════════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📚 API DOCUMENTATION (Swagger/OpenAPI):"
echo "   → http://localhost:8000/docs"
echo ""
echo "📊 CELERY MONITORING (Flower):"
echo "   → http://localhost:5555"
echo ""
echo "🏥 HEALTH CHECK:"
echo "   → http://localhost:8000/health"
echo ""
echo "────────────────────────────────────────────────────────────────────────────────────────────"
echo ""
echo "🔴 REAL-TIME LOG MONITORING (Copy & paste these commands):"
echo ""
echo "  1️⃣  Watch ALL services in real-time:"
echo "     docker-compose logs -f --tail=100"
echo ""
echo "  2️⃣  Watch ONLY Backend (FastAPI) logs:"
echo "     docker-compose logs -f backend --tail=100"
echo ""
echo "  3️⃣  Watch ONLY CV Processing (Celery Worker) logs:"
echo "     docker-compose logs -f worker --tail=100"
echo ""
echo "  4️⃣  Watch CV Processing with color-coded extraction stages:"
echo "     docker-compose logs -f worker --tail=100 | grep -E '(STAGE|TASK|ERROR|SUCCESS|Duration)'  "
echo ""
echo "  5️⃣  Watch Database (PostgreSQL) logs:"
echo "     docker-compose logs -f db --tail=50"
echo ""
echo "  6️⃣  Watch tasks being added to queue (Redis/Celery):"
echo "     docker-compose logs -f backend --tail=150 | grep -E '(queue|dispatch|submit)'  "
echo ""
echo "────────────────────────────────────────────────────────────────────────────────────────────"
echo ""
echo "💡 QUICK COMMANDS:"
echo ""
echo "  Check database status:"
echo "    curl http://localhost:8000/api/admin/db-status | python -m json.tool"
echo ""
echo "  Flush incomplete records:"
echo "    curl -X POST http://localhost:8000/api/admin/flush-incomplete | python -m json.tool"
echo ""
echo "  Upload a CV (from backend/data/cvs/ folder):"
echo "    curl -X POST http://localhost:8000/upload -F 'file=@backend/data/cvs/sample.pdf'"
echo ""
echo "────────────────────────────────────────────────────────────────────────────────────────────"
echo ""
echo "✅ BACKEND IS READY!"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:8000/docs in your browser"
echo "  2. Upload a CV using the /upload endpoint"
echo "  3. Run one of the log commands above to see processing in real-time"
echo ""
echo "To stop all services:"
echo "  docker-compose down"
echo ""
