"""
Lossless TALASH schema migration.

This migration extends the current schema so extraction does not lose
information from the CV pipeline.

Usage:
    python migration_lossless.py --apply
    python migration_lossless.py --status
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import inspect, text

from app.db import engine
from app.models.models import Base

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


COLUMN_ADDITIONS: dict[str, list[tuple[str, str]]] = {
    "candidates": [
        ("target_job_description", "TEXT"),
        ("phone", "VARCHAR(50)"),
        ("linkedin_url", "VARCHAR(500)"),
        ("personal_website", "VARCHAR(500)"),
        ("other_urls", "TEXT"),
        ("raw_extraction_json", "TEXT"),
        ("analysis_json", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ],
    "education_records": [
        ("institution_type", "VARCHAR(100)"),
        ("start_month", "INTEGER"),
        ("end_month", "INTEGER"),
        ("institution_ranking_source", "VARCHAR(100)"),
        ("institution_ranking_year", "INTEGER"),
        ("institution_ranking_value", "VARCHAR(100)"),
        ("evidence_text", "TEXT"),
        ("confidence_score", "FLOAT"),
    ],
    "work_experiences": [
        ("start_month", "INTEGER"),
        ("start_year", "INTEGER"),
        ("end_month", "INTEGER"),
        ("end_year", "INTEGER"),
        ("job_responsibilities", "TEXT"),
        ("evidence_text", "TEXT"),
        ("confidence_score", "FLOAT"),
    ],
    "journal_publications": [
        ("doi", "VARCHAR(255)"),
        ("volume", "VARCHAR(100)"),
        ("issue", "VARCHAR(100)"),
        ("pages", "VARCHAR(100)"),
        ("abstract_or_summary", "TEXT"),
        ("keywords_json", "TEXT"),
        ("author_affiliations_json", "TEXT"),
        ("source_verification_url", "VARCHAR(1000)"),
        ("confidence_score", "FLOAT"),
    ],
    "conference_publications": [
        ("conference_location", "VARCHAR(255)"),
        ("publisher", "VARCHAR(255)"),
        ("doi", "VARCHAR(255)"),
        ("abstract_or_summary", "TEXT"),
        ("keywords_json", "TEXT"),
        ("author_affiliations_json", "TEXT"),
        ("source_verification_url", "VARCHAR(1000)"),
        ("confidence_score", "FLOAT"),
    ],
    "supervision_records": [
        ("thesis_title", "TEXT"),
        ("evidence_text", "TEXT"),
        ("confidence_score", "FLOAT"),
    ],
    "books": [
        ("evidence_text", "TEXT"),
        ("confidence_score", "FLOAT"),
    ],
    "patents": [
        ("date_granted", "DATE"),
        ("evidence_text", "TEXT"),
        ("confidence_score", "FLOAT"),
    ],
    "skills": [
        ("proficiency_level", "VARCHAR(100)"),
        ("years_of_experience", "INTEGER"),
        ("work_evidence", "TEXT"),
        ("research_evidence", "TEXT"),
        ("confidence_score", "FLOAT"),
    ],
    "candidate_assessments": [
        ("jd_alignment_score", "FLOAT"),
    ],
}


NEW_TABLES = [
    "extraction_runs",
    "publication_authors",
    "education_gaps",
    "employment_gaps",
    "institution_rankings",
    "topic_clusters",
    "collaboration_edges",
    "candidate_assessments",
    "missing_information_requests",
]


def create_missing_tables() -> None:
    logger.info("Creating any missing tables defined in ORM metadata...")
    Base.metadata.create_all(bind=engine)


def add_columns_if_missing() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table_name, columns in COLUMN_ADDITIONS.items():
            if table_name not in existing_tables:
                logger.info("Skipping column migration for missing table: %s", table_name)
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_type in columns:
                if column_name in existing_columns:
                    continue
                logger.info("Adding column %s.%s", table_name, column_name)
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_name} {column_type}")
                )


def show_status() -> None:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info("=== TALASH lossless schema status ===")
    for table_name in sorted(set(list(COLUMN_ADDITIONS.keys()) + NEW_TABLES + tables)):
        if table_name not in tables:
            logger.info("[MISSING TABLE] %s", table_name)
            continue
        logger.info("[TABLE OK] %s", table_name)
        if table_name in COLUMN_ADDITIONS:
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, _ in COLUMN_ADDITIONS[table_name]:
                status = "OK" if column_name in existing_columns else "MISSING"
                logger.info("  - %s: %s", column_name, status)


def apply_migrations() -> None:
    logger.info("=== Applying TALASH lossless schema migration ===")
    create_missing_tables()
    add_columns_if_missing()
    logger.info("=== Migration complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply TALASH lossless schema migration")
    parser.add_argument("--apply", action="store_true", help="Apply migration")
    parser.add_argument("--status", action="store_true", help="Show migration status")
    args = parser.parse_args()

    if args.apply:
        apply_migrations()
    elif args.status:
        show_status()
    else:
        parser.print_help()
