from datetime import datetime

import pandas as pd
from sqlalchemy import text

from app.db import engine

# Only include the first 6 fully processed candidates.
TARGET_IDS = [1, 2, 3, 4, 5, 6]

OUT_PATH = f"/app/data/exports/Master_CV_Report_completed6_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

SHEETS = {
    "Candidates": "SELECT * FROM candidates WHERE id = ANY(:ids) ORDER BY id",
    "Education": "SELECT * FROM education_records WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "Experience": "SELECT * FROM work_experiences WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "Journals": "SELECT * FROM journal_publications WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "Conferences": "SELECT * FROM conference_publications WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "Supervision": "SELECT * FROM supervision_records WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "Books": "SELECT * FROM books WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "Patents": "SELECT * FROM patents WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "Skills": "SELECT * FROM skills WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "ExtractionRuns": "SELECT * FROM extraction_runs WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "PublicationAuthors": "SELECT * FROM publication_authors WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "EducationGaps": "SELECT * FROM education_gaps WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "EmploymentGaps": "SELECT * FROM employment_gaps WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "InstitutionRankings": "SELECT * FROM institution_rankings WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "TopicClusters": "SELECT * FROM topic_clusters WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "CollaborationEdges": "SELECT * FROM collaboration_edges WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "Assessments": "SELECT * FROM candidate_assessments WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
    "MissingInfoRequests": "SELECT * FROM missing_information_requests WHERE candidate_id = ANY(:ids) ORDER BY candidate_id, id",
}

with engine.connect() as conn:
    with pd.ExcelWriter(OUT_PATH, engine="openpyxl") as writer:
        summary = pd.read_sql(
            text(
                """
                SELECT id, name, status, file_path, created_at, updated_at
                FROM candidates
                WHERE id = ANY(:ids)
                ORDER BY id
                """
            ),
            conn,
            params={"ids": TARGET_IDS},
        )
        summary.to_excel(writer, sheet_name="Summary", index=False)

        for sheet_name, sql in SHEETS.items():
            df = pd.read_sql(text(sql), conn, params={"ids": TARGET_IDS})
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)

print(OUT_PATH)
