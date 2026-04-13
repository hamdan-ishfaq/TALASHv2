#!/usr/bin/env python3
"""Generate Excel export of extracted CV data"""
import sys
sys.path.insert(0, '/app')

from app.db import SessionLocal
from app.services.excel_exporter import ExcelExporter
from datetime import datetime

db = SessionLocal()

try:
    # Export candidatesand all related data
    output_file = f"/tmp/cv_extraction_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    print(f"Generating Excel export to {output_file}...")
    
    exporter = ExcelExporter()
    exporter.export_candidates_to_excel(db, output_file)
    
    print(f"✓ Excel export generated successfully!")
    print(f"  File: {output_file}")
    print(f"  Size: ~{open(output_file).tell()} bytes")
    
    # Summary statistics
    from app.models.models import Candidate, EducationRecord, WorkExperience, Publication, Skill
    
    cand_count = db.query(Candidate).count()
    edu_count = db.query(EducationRecord).count()
    exp_count = db.query(WorkExperience).count()
    pub_count = db.query(Publication).count()
    skill_count = db.query(Skill).count()
    
    print(f"\nExtraction Summary:")
    print(f"  Candidates: {cand_count}")
    print(f"  Education Records: {edu_count}")
    print(f"  Work Experience: {exp_count}")
    print(f"  Publications: {pub_count}")
    print(f"  Skills: {skill_count}")
    
finally:
    db.close()
