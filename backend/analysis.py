#!/usr/bin/env python3
"""
Comprehensive CV extraction analysis
Compare extracted data vs raw PDF content
"""
import sys
sys.path.insert(0, '/app')

from app.db import SessionLocal
from app.models.models import Candidate, EducationRecord, WorkExperience, Publication, Skill
from app.services.pdf_parser import extract_pdf_text
import pdfplumber
import json

db = SessionLocal()

try:
    # Get all candidates
    candidates = db.query(Candidate).all()
    
    report = {
        "summary": {
            "total_candidates": len(candidates),
            "candidates_details": []
        },
        "extraction_quality": {},
        "gaps_and_issues": []
    }
    
    print("=" * 100)
    print("CV EXTRACTION ANALYSIS REPORT")
    print("=" * 100)
    
    for candidate in candidates:
        print(f"\n{'='*100}")
        print(f"CANDIDATE {candidate.id}: {candidate.name}")
        print(f"{'='*100}")
        
        cand_data = {
            "candidate_id": candidate.id,
            "name": candidate.name,
            "file_path": candidate.file_path,
            "status": candidate.status,
            "extracted": {
                "education": len(candidate.education_records),
                "experience": len(candidate.work_experiences),
                "publications": len(candidate.publications),
                "skills": len(candidate.skills),
            },
            "gaps": []
        }
        
        # Read raw PDF text
        try:
            raw_text = extract_pdf_text(candidate.file_path)
            raw_text_length = len(raw_text)
            print(f"✓ PDF: {raw_text_length} characters extracted")
        except Exception as e:
            print(f"✗ PDF read error: {e}")
            raw_text = ""
            raw_text_length = 0
        
        # Analyze extracted data
        print(f"\nExtracted Data Found:")
        print(f"  ├─ Education Records: {cand_data['extracted']['education']}")
        for i, edu in enumerate(candidate.education_records, 1):
            print(f"  │  └─ [{i}] {edu.degree_level or 'N/A'} @ {edu.institution or 'N/A'} ({edu.passing_year or 'N/A'})")
        
        print(f"  ├─ Work Experience: {cand_data['extracted']['experience']}")
        for i, exp in enumerate(candidate.work_experiences, 1):
            print(f"  │  └─ [{i}] {exp.job_title or 'N/A'} @ {exp.organization or 'N/A'}")
        
        print(f"  ├─ Publications: {cand_data['extracted']['publications']}")
        for i, pub in enumerate(candidate.publications[:5], 1):  # Show first 5
            print(f"  │  └─ [{i}] {pub.title[:60] if pub.title else 'N/A'}...")
        if len(candidate.publications) > 5:
            print(f"  │  └─ ... and {len(candidate.publications) - 5} more")
        
        print(f"  └─ Skills: {cand_data['extracted']['skills']}")
        
        # Check for name in raw text
        if candidate.name and candidate.name != "Unknown":
            name_lower = candidate.name.lower()
            if name_lower in raw_text.lower():
                print(f"\n✓ Name '{candidate.name}' found in PDF")
            else:
                print(f"\n✗ Name '{candidate.name}' NOT found in PDF - possible extraction gap")
                cand_data['gaps'].append("Name not found in raw text")
        else:
            print(f"\n✗ No name extracted - ISSUE")
            cand_data['gaps'].append("Name extraction failed")
        
        # Check for email
        import re
        if candidate.email:
            if candidate.email in raw_text:
                print(f"✓ Email '{candidate.email}' found in PDF")
            else:
                print(f"⚠ Email extracted but not found in PDF (possible OCR issue)")
        else:
            # Try to find any email in raw text
            email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', raw_text[:1000])
            if email_matches:
                print(f"✗ No email extracted, but found in PDF: {email_matches[0]}")
                cand_data['gaps'].append(f"Email not extracted: {email_matches[0]}")
            else:
                print(f"✓ No email found in PDF (expected)")
        
        # Education gaps
        if "education" in raw_text.lower() or "bachelor" in raw_text.lower() or "master" in raw_text.lower():
            if cand_data['extracted']['education'] == 0:
                print(f"\n✗ CRITICAL: Education section in PDF but NO education records extracted")
                cand_data['gaps'].append("Education extraction failed despite section present")
        
        # Experience gaps
        if "experience" in raw_text.lower() or "employment" in raw_text.lower() or "work" in raw_text.lower():
            if cand_data['extracted']['experience'] == 0:
                print(f"\n✗ CRITICAL: Experience section in PDF but NO experience records extracted")
                cand_data['gaps'].append("Experience extraction failed despite section present")
        
        # Skills gaps
        if "skills" in raw_text.lower() or "competencies" in raw_text.lower():
            if cand_data['extracted']['skills'] == 0:
                print(f"\n⚠ Skills section in PDF but NO skills extracted")
                cand_data['gaps'].append("Skills extraction not implemented")
        
        report['summary']['candidates_details'].append(cand_data)
        if cand_data['gaps']:
            report['gaps_and_issues'].extend([(candidate.id, candidate.name, gap) for gap in cand_data['gaps']])
        
        # Print page count
        try:
            with pdfplumber.open(candidate.file_path) as pdf:
                page_count = len(pdf.pages)
                print(f"\nPDF Pages: {page_count}")
        except:
            pass
    
    # Summary statistics
    print(f"\n\n{'='*100}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*100}")
    
    all_edu = sum(c['extracted']['education'] for c in report['summary']['candidates_details'])
    all_exp = sum(c['extracted']['experience'] for c in report['summary']['candidates_details'])
    all_pub = sum(c['extracted']['publications'] for c in report['summary']['candidates_details'])
    all_skills = sum(c['extracted']['skills'] for c in report['summary']['candidates_details'])
    
    print(f"Candidates Processed: {report['summary']['total_candidates']}")
    print(f"Total Education Records: {all_edu}")
    print(f"Total Experience Records: {all_exp}")
    print(f"Total Publications: {all_pub}")
    print(f"Total Skills: {all_skills}")
    
    if report['gaps_and_issues']:
        print(f"\n{'='*100}")
        print(f"IDENTIFIED GAPS AND ISSUES ({len(report['gaps_and_issues'])} total)")
        print(f"{'='*100}")
        for cand_id, cand_name, gap in report['gaps_and_issues']:
            print(f"  • Candidate {cand_id} ({cand_name}): {gap}")
    
    # Save report to JSON
    with open('/tmp/extraction_analysis.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✓ Full analysis saved to /tmp/extraction_analysis.json")
    
finally:
    db.close()
