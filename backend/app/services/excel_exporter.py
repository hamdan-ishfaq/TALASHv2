"""Export extracted candidate data to Excel spreadsheet."""

import logging
from datetime import datetime
from io import BytesIO

import pandas as pd
from sqlalchemy.orm import Session

from app.models.models import Candidate, EducationRecord, WorkExperience

logger = logging.getLogger(__name__)


class ExcelExporter:
    """Generate Excel spreadsheet from extracted candidate data."""

    @staticmethod
    def export_candidates_to_excel(db: Session, output_path: str = None) -> bytes:
        """
        Export all candidates and their data to Excel spreadsheet.
        
        Returns bytes if output_path is None, otherwise saves to file.
        """
        logger.info("[EXCEL-EXPORT] Starting candidates export")
        
        try:
            # Get all candidates
            candidates = db.query(Candidate).all()
            logger.info(f"[EXCEL-EXPORT] Found {len(candidates)} candidates")
            
            # Create Excel writer
            output = BytesIO() if output_path is None else output_path
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                
                # Sheet 1: Candidates summary
                candidates_data = [
                    {
                        "ID": c.id,
                        "Name": c.name,
                        "Email": c.email,
                        "Status": c.status,
                        "File": c.file_path.split("/")[-1] if c.file_path else None,
                        "Education Count": len(c.education_records or []),
                        "Experience Count": len(c.work_experiences or []),
                        "Summary": c.summary[:100] if c.summary else None,
                    }
                    for c in candidates
                ]
                df_candidates = pd.DataFrame(candidates_data)
                df_candidates.to_excel(writer, sheet_name="Candidates", index=False)
                logger.debug("[EXCEL-EXPORT] Wrote Candidates sheet")
                
                # Sheet 2: Education records
                education_data = []
                for c in candidates:
                    for edu in c.education_records or []:
                        education_data.append({
                            "Candidate ID": c.id,
                            "Candidate Name": c.name,
                            "Degree": edu.degree_level,
                            "Title": edu.title,
                            "Institution": edu.institution,
                            "Passing Year": edu.passing_year,
                            "CGPA": edu.cgpa,
                        })
                if education_data:
                    df_education = pd.DataFrame(education_data)
                    df_education.to_excel(writer, sheet_name="Education", index=False)
                    logger.debug(f"[EXCEL-EXPORT] Wrote Education sheet ({len(education_data)} records)")
                
                # Sheet 3: Work experience
                experience_data = []
                for c in candidates:
                    for exp in c.work_experiences or []:
                        experience_data.append({
                            "Candidate ID": c.id,
                            "Candidate Name": c.name,
                            "Job Title": exp.job_title,
                            "Organization": exp.organization,
                            "Location": exp.location,
                            "Start Date": exp.start_date,
                            "End Date": exp.end_date,
                            "Current": "Yes" if exp.is_current else "No",
                        })
                if experience_data:
                    df_experience = pd.DataFrame(experience_data)
                    df_experience.to_excel(writer, sheet_name="Experience", index=False)
                    logger.debug(f"[EXCEL-EXPORT] Wrote Experience sheet ({len(experience_data)} records)")
                
                # Sheet 4: Raw data for reference
                raw_data = [
                    {
                        "ID": c.id,
                        "Name": c.name,
                        "Raw Text": c.raw_text[:500] if c.raw_text else None,
                        "Summary": c.summary,
                        "Status": c.status,
                    }
                    for c in candidates
                ]
                df_raw = pd.DataFrame(raw_data)
                df_raw.to_excel(writer, sheet_name="Raw Data", index=False)
                logger.debug("[EXCEL-EXPORT] Wrote Raw Data sheet")
            
            logger.info("[EXCEL-EXPORT] ✅ Export complete")
            
            if output_path is None:
                return output.getvalue()
            else:
                logger.info(f"[EXCEL-EXPORT] Saved to {output_path}")
                return None
                
        except Exception as e:
            logger.error(f"[EXCEL-EXPORT-ERROR] {e}", exc_info=True)
            raise
