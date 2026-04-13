"""
Database migration script for TALASH v3 Milestone 2 additions.

Adds:
1. OCR support to the PDF parser (pytesseract in requirements)
2. Conference fields to PUBLICATIONS table
3. PUBLICATION_TOPICS table for topic variability analysis
4. Folder monitoring capability

Usage:
    python migration_m2.py --apply     # Apply all migrations
    python migration_m2.py --rollback  # Rollback migrations (if supported)
    python migration_m2.py --status    # Check migration status
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text, inspect
from app.db import engine, SessionLocal
from app.models.models import Base

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def add_conference_fields_to_publications() -> None:
    """Add conference-specific fields to PUBLICATIONS table."""
    logger.info("Adding conference fields to PUBLICATIONS table...")
    
    conference_fields = [
        ("conference_a_star", "BOOLEAN DEFAULT FALSE"),
        ("conference_a_ranking", "VARCHAR(10)"),
        ("conference_core_ranking", "VARCHAR(50)"),
        ("conference_series_number", "VARCHAR(100)"),
        ("proceedings_indexed_ieee", "BOOLEAN DEFAULT FALSE"),
        ("proceedings_indexed_acm", "BOOLEAN DEFAULT FALSE"),
        ("proceedings_indexed_springer", "BOOLEAN DEFAULT FALSE"),
    ]
    
    # Also add these journal fields for completeness
    journal_fields = [
        ("issn", "VARCHAR(50)"),
        ("wos_indexed", "BOOLEAN DEFAULT FALSE"),
        ("scopus_indexed", "BOOLEAN DEFAULT FALSE"),
        ("quartile", "VARCHAR(10)"),
        ("wos_impact_factor", "FLOAT"),
        ("author_position", "INTEGER"),
        ("corresponding_author", "BOOLEAN DEFAULT FALSE"),
    ]
    
    try:
        with engine.begin() as connection:
            for field_name, field_type in conference_fields + journal_fields:
                if not check_column_exists("publications", field_name):
                    alter_sql = f"ALTER TABLE publications ADD COLUMN {field_name} {field_type};"
                    connection.execute(text(alter_sql))
                    logger.info(f"  ✓ Added column: {field_name}")
                else:
                    logger.info(f"  - Column already exists: {field_name}")
        
        logger.info("✓ Conference fields added successfully")
    
    except Exception as e:
        logger.error(f"✗ Failed to add conference fields: {str(e)}")
        raise


def create_publication_topics_table() -> None:
    """Create PUBLICATION_TOPICS table for topic variability analysis."""
    logger.info("Creating PUBLICATION_TOPICS table...")
    
    try:
        with engine.begin() as connection:
            # Check if table already exists
            inspector = inspect(engine)
            if "publication_topics" in inspector.get_table_names():
                logger.info("  - Table already exists: publication_topics")
                return
            
            create_table_sql = """
            CREATE TABLE publication_topics (
                id SERIAL PRIMARY KEY,
                publication_id INTEGER NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
                topic_name VARCHAR(255) NOT NULL,
                topic_category VARCHAR(100),
                relevance_score FLOAT,
                is_primary_topic BOOLEAN DEFAULT FALSE,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) WITH (OIDS=FALSE);
            
            CREATE INDEX idx_publication_topics_publication_id ON publication_topics(publication_id);
            """
            
            for statement in create_table_sql.strip().split(';'):
                if statement.strip():
                    connection.execute(text(statement))
            
            logger.info("✓ PUBLICATION_TOPICS table created successfully")
    
    except Exception as e:
        logger.error(f"✗ Failed to create PUBLICATION_TOPICS table: {str(e)}")
        raise


def update_requirements() -> None:
    """Verify pytesseract is in requirements.txt."""
    logger.info("Checking requirements.txt for pytesseract...")
    
    requirements_path = Path(__file__).parent / "requirements.txt"
    
    if not requirements_path.exists():
        logger.warning("  - requirements.txt not found")
        return
    
    with open(requirements_path, 'r') as f:
        content = f.read()
    
    if 'pytesseract' in content:
        logger.info("  ✓ pytesseract already in requirements.txt")
    else:
        logger.warning("  ⚠ pytesseract not found in requirements.txt")
        logger.warning("    Please run: pip install pytesseract")


def apply_all_migrations() -> None:
    """Apply all M2 migrations."""
    logger.info("=== Starting TALASH M2 Database Migrations ===\n")
    
    try:
        add_conference_fields_to_publications()
        logger.info("")
        create_publication_topics_table()
        logger.info("")
        update_requirements()
        
        logger.info("\n=== ✓ All migrations completed successfully ===")
        logger.info("\nNext steps:")
        logger.info("1. Install OCR support: pip install pytesseract pdf2image")
        logger.info("2. System dependencies (Ubuntu/Debian):")
        logger.info("   - sudo apt-get install tesseract-ocr")
        logger.info("   - sudo apt-get install libpoppler-cpp-dev")
        logger.info("3. Restart FastAPI backend: uvicorn app.main:app --reload")
        logger.info("4. Folder monitoring is now available in app.services.folder_monitor")
    
    except Exception as e:
        logger.error(f"\n=== ✗ Migration failed ===")
        raise


def check_status() -> None:
    """Check migration status."""
    logger.info("=== TALASH M2 Migration Status ===\n")
    
    # Check conference fields
    logger.info("Checking PUBLICATIONS table fields:")
    conference_fields = [
        "conference_a_star", "conference_a_ranking", "conference_core_ranking",
        "conference_series_number", "proceedings_indexed_ieee",
        "proceedings_indexed_acm", "proceedings_indexed_springer"
    ]
    
    for field in conference_fields:
        exists = check_column_exists("publications", field)
        status = "✓" if exists else "✗"
        logger.info(f"  {status} {field}")
    
    logger.info("\nChecking PUBLICATION_TOPICS table:")
    inspector = inspect(engine)
    if "publication_topics" in inspector.get_table_names():
        logger.info("  ✓ Table exists: publication_topics")
    else:
        logger.info("  ✗ Table missing: publication_topics")
    
    logger.info("\nChecking OCR support:")
    try:
        import pytesseract
        logger.info("  ✓ pytesseract installed")
    except ImportError:
        logger.info("  ✗ pytesseract not installed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="TALASH M2 Database Migration Script"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply all migrations"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check migration status"
    )
    
    args = parser.parse_args()
    
    if args.apply:
        apply_all_migrations()
    elif args.status:
        check_status()
    else:
        parser.print_help()
