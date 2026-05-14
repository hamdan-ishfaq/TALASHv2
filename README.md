# TALASH (talashv3)

Academic hiring / CV intelligence pipeline: upload CVs (PDF), extract structured profiles with LLMs, run analysis stages (education, experience, research, skills, gaps, missing-info), rank candidates, and export reports.

## Team

| Name |
|------|
| **Khadija Faisal** |
| **Hamdan Ishfaq** |

---

## Architecture

| Layer | Stack |
|--------|--------|
| **API** | FastAPI (`backend/app/main.py`), port **8000** |
| **Worker** | Celery + Redis (async CV processing) |
| **DB** | PostgreSQL 15 (`talash` / user `talash`, host port **5433**) |
| **Frontend** | React (Vite) under `frontend/` |
| **Optional** | Flower on **5555** for Celery monitoring |

Docker Compose file: `docker-compose.yml` (project name `talashv3`).

---

## Prerequisites

- Docker and Docker Compose
- A project-root **`.env`** with API keys (see below). Compose loads `.env` for backend and worker.

---

## Environment (`.env`)

Create `.env` in the **repository root** (same folder as `docker-compose.yml`). Typical variables include:

- **`OPENROUTER_API_KEY`** (or your chosen provider) — used for extraction routing when `LLM_PROVIDER=openrouter`
- Keys for analysis / summary LLMs if configured in your deployment (e.g. Groq / Gemini as used in analysis modules)
- Optional: **`TALASH_CORS_ORIGINS`** — comma-separated list for the API (defaults include `http://localhost:3000`)
- Optional: **`TALASH_MAX_CV_CHARS`** — max characters sent to extraction LLM (default `120000`)
- Optional: **`TALASH_CV_POOL_DIR`** — PDF pool path for batch scripts inside the container

Exact names are defined in backend settings and `docker-compose.yml`; mirror whatever your team already uses in `.env.example` if present.

---

## Run with Docker

From the repo root:

```bash
docker compose up --build
```

Services:

- API: <http://localhost:8000> (docs: `/docs`)
- Postgres: `localhost:5433`
- Redis: `localhost:6379`
- Flower: <http://localhost:5555>

- **Watcher / hot folder:** put PDFs you want processed under **`backend/data/cvs/`** (mounted at `/app/data/cvs`). The API folder monitor only watches this directory.
- **Merged bundle:** keep a single **`CVs.pdf`** at the **repository root** (optional to track; see `.gitignore` exception). Split it into per-CV files with blank-page separators — outputs go to **`backend/data/cvs_split/`**, not the watcher folder. Then copy only the PDFs you want into `backend/data/cvs/` (or upload via `/docs`).

```bash
# Host (repo root), needs PyMuPDF (also installed in the backend image):
python3 backend/scripts/split_cvs_bundle.py --clear-output

# Or inside Docker:
docker compose exec backend python scripts/split_cvs_bundle.py --clear-output
# If CVs.pdf is not under /app, pass: --input /path/to/CVs.pdf
```

Optional data files (see `docker-compose.yml` comments):

- **`CORE.csv`** — conference rankings (mounted read-only)
- **`scimagojr 2025.csv`** — journal metadata
- QS/THE ranking spreadsheets — mount as documented in compose if you use institution rankings

---

## Frontend (local dev)

```bash
cd frontend
npm install
npm run dev
```

Point the UI at the API URL your team uses (often `http://localhost:8000`). Ensure CORS includes your dev origin (`TALASH_CORS_ORIGINS`).

---

## Useful backend commands (inside a container)

```bash
# Example: open a shell in the worker
docker compose exec worker bash

# Flush DB (drops and recreates tables + optional columns)
docker compose exec worker python flush_db.py

# Batch sample (up to 10 random PDFs from pool + cvs_split + data/cvs)
docker compose exec worker python run_batch_10_cvs.py
```

Working directory in containers: **`/app`** (mapped to `./backend`).

---

## Repository layout (high level)

| Path | Role |
|------|------|
| `backend/app/` | FastAPI app, routers, models, services |
| `backend/scripts/split_cvs_bundle.py` | Split root `CVs.pdf` into `backend/data/cvs_split/` (blank-page separators) |
| `backend/worker/` | Celery tasks (CV pipeline) |
| `frontend/` | React SPA |
| `docker-compose.yml` | Local full stack |

---

## License / course context

Add your course code (e.g. CS417), institution, and license here if required for submission.
