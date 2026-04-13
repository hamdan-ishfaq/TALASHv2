# TALASH v3

Milestone 1 focuses on the backend preprocessing pipeline for CV extraction. The repo is currently in a working-but-incomplete state: PDF ingestion, parsing, database persistence, and CSV export are functioning, while the semantic extraction layer still has gaps.

## What Works

- FastAPI upload endpoints accept CVs from the API and from filesystem paths.
- The Celery worker processes CVs asynchronously and stores results in PostgreSQL.
- PDF preprocessing extracts text successfully from the real CV set using a hybrid PyMuPDF + pdfplumber flow.
- The database layer persists candidates and related tables for education, work experience, publications, skills, patents, books, and supervision records.
- CSV export is working and produces the milestone output set in `csv_exports/`.
- Ollama-based extraction works when the backend container can reach the Windows-hosted Ollama service.

## What Is Wrong

- Some extracted rows are still noisy, duplicated, or partially malformed.
- Publications are the most inconsistent output category.
- A few education and work rows still contain placeholder or incomplete values.
- Scanned or low-quality PDFs remain limited by text-based preprocessing.
- If the model endpoint is unavailable, the pipeline falls back to reduced extraction.

## What Is Next

- Tighten extraction prompts and normalization for publications, patents, and books.
- Add OCR or image-aware handling for PDFs that do not yield clean text.
- Add field-level confidence and provenance metadata.
- Add stronger deduplication and validation before writing to the database.
- Re-run the remaining CVs after the extractor rules are improved.

## Current Output

- `csv_exports/000_SUMMARY.csv`
- `csv_exports/001_candidates.csv`
- `csv_exports/002_education_records.csv`
- `csv_exports/003_work_experiences.csv`
- `csv_exports/004_publications.csv`
- `csv_exports/005_skills.csv`
- `csv_exports/006_patents.csv`
- `csv_exports/007_books.csv`
- `csv_exports/008_supervision_records.csv`

## Git Identity

- GitHub username: hamdan-ishfaq
- GitHub email: mhamdanishfaq@gmail.com
