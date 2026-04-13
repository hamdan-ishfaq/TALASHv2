#!/usr/bin/env python3
"""
Export all processed CV data to CSV files
"""

import csv
import psycopg2
from pathlib import Path
from datetime import datetime

DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "database": "talash",
    "user": "talash",
    "password": "talash",
}

OUTPUT_DIR = Path("csv_exports")
OUTPUT_DIR.mkdir(exist_ok=True)

def export_candidates():
    """Export all candidates"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name, email, status, file_path, 
                   LENGTH(raw_text) as raw_text_length,
                   LENGTH(summary) as summary_length
            FROM candidates
            ORDER BY id
        """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        csv_file = OUTPUT_DIR / "001_candidates.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Name', 'Email', 'Status', 'File Path', 'Raw Text Length', 'Summary Length'])
            for row in rows:
                writer.writerow(row)
        
        print(f"✓ Exported {len(rows)} candidates to {csv_file}")
        return len(rows)
    except Exception as e:
        print(f"✗ Error exporting candidates: {e}")
        return 0

def export_education():
    """Export all education records"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT e.id, e.candidate_id, c.name as candidate_name, 
                   e.degree_level, e.title, e.institution, 
                   e.passing_year, e.cgpa
            FROM education_records e
            JOIN candidates c ON e.candidate_id = c.id
            ORDER BY e.candidate_id, e.id
        """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        csv_file = OUTPUT_DIR / "002_education_records.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Candidate ID', 'Candidate Name', 'Degree Level', 'Title', 'Institution', 'Passing Year', 'CGPA'])
            for row in rows:
                writer.writerow(row)
        
        print(f"✓ Exported {len(rows)} education records to {csv_file}")
        return len(rows)
    except Exception as e:
        print(f"✗ Error exporting education: {e}")
        return 0

def export_work():
    """Export all work experience records"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT w.id, w.candidate_id, c.name as candidate_name,
                   w.job_title, w.organization, w.location,
                   w.start_date, w.end_date, w.is_current
            FROM work_experiences w
            JOIN candidates c ON w.candidate_id = c.id
            ORDER BY w.candidate_id, w.id
        """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        csv_file = OUTPUT_DIR / "003_work_experiences.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Candidate ID', 'Candidate Name', 'Job Title', 'Organization', 'Location', 'Start Date', 'End Date', 'Is Current'])
            for row in rows:
                writer.writerow(row)
        
        print(f"✓ Exported {len(rows)} work experience records to {csv_file}")
        return len(rows)
    except Exception as e:
        print(f"✗ Error exporting work experience: {e}")
        return 0

def export_publications():
    """Export all publication records"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT p.id, p.candidate_id, c.name as candidate_name,
                   p.title, p.authors, p.venue, p.year, p.type
            FROM publications p
            JOIN candidates c ON p.candidate_id = c.id
            ORDER BY p.candidate_id, p.id
        """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        csv_file = OUTPUT_DIR / "004_publications.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Candidate ID', 'Candidate Name', 'Title', 'Authors', 'Venue', 'Year', 'Type'])
            for row in rows:
                writer.writerow(row)
        
        print(f"✓ Exported {len(rows)} publication records to {csv_file}")
        return len(rows)
    except Exception as e:
        print(f"✗ Error exporting publications: {e}")
        return 0

def export_skills():
    """Export all skill records"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT s.id, s.candidate_id, c.name as candidate_name,
                   s.name as skill_name, s.proficiency_level, 
                   s.years_of_experience
            FROM skills s
            JOIN candidates c ON s.candidate_id = c.id
            ORDER BY s.candidate_id, s.id
        """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        csv_file = OUTPUT_DIR / "005_skills.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Candidate ID', 'Candidate Name', 'Skill Name', 'Proficiency Level', 'Years of Experience'])
            for row in rows:
                writer.writerow(row)
        
        print(f"✓ Exported {len(rows)} skill records to {csv_file}")
        return len(rows)
    except Exception as e:
        print(f"✗ Error exporting skills: {e}")
        return 0

def export_patents():
    """Export all patent records"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT pt.id, pt.candidate_id, c.name as candidate_name,
                   pt.title, pt.inventors, pt.patent_no, pt.year, pt.status
            FROM patents pt
            JOIN candidates c ON pt.candidate_id = c.id
            ORDER BY pt.candidate_id, pt.id
        """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        csv_file = OUTPUT_DIR / "006_patents.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Candidate ID', 'Candidate Name', 'Title', 'Inventors', 'Patent Number', 'Year', 'Status'])
            for row in rows:
                writer.writerow(row)
        
        print(f"✓ Exported {len(rows)} patent records to {csv_file}")
        return len(rows)
    except Exception as e:
        print(f"✗ Error exporting patents: {e}")
        return 0

def export_books():
    """Export all book records"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT b.id, b.candidate_id, c.name as candidate_name,
                   b.title, b.authors, b.publisher, b.year, b.isbn
            FROM books b
            JOIN candidates c ON b.candidate_id = c.id
            ORDER BY b.candidate_id, b.id
        """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        csv_file = OUTPUT_DIR / "007_books.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Candidate ID', 'Candidate Name', 'Title', 'Authors', 'Publisher', 'Year', 'ISBN'])
            for row in rows:
                writer.writerow(row)
        
        print(f"✓ Exported {len(rows)} book records to {csv_file}")
        return len(rows)
    except Exception as e:
        print(f"✗ Error exporting books: {e}")
        return 0

def export_supervision():
    """Export all supervision records"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT sp.id, sp.candidate_id, c.name as candidate_name,
                   sp.level, sp.student_name, sp.year
            FROM supervision_records sp
            JOIN candidates c ON sp.candidate_id = c.id
            ORDER BY sp.candidate_id, sp.id
        """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        csv_file = OUTPUT_DIR / "008_supervision_records.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'Candidate ID', 'Candidate Name', 'Level', 'Student Name', 'Year'])
            for row in rows:
                writer.writerow(row)
        
        print(f"✓ Exported {len(rows)} supervision records to {csv_file}")
        return len(rows)
    except Exception as e:
        print(f"✗ Error exporting supervision: {e}")
        return 0

def export_summary():
    """Export extraction summary statistics"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                c.id, c.name, c.status,
                COUNT(DISTINCT e.id) as education_count,
                COUNT(DISTINCT w.id) as work_count,
                COUNT(DISTINCT p.id) as publications_count,
                COUNT(DISTINCT s.id) as skills_count,
                COUNT(DISTINCT pt.id) as patents_count,
                COUNT(DISTINCT b.id) as books_count,
                COUNT(DISTINCT sp.id) as supervision_count,
                (COUNT(DISTINCT e.id) + COUNT(DISTINCT w.id) + COUNT(DISTINCT p.id) + 
                 COUNT(DISTINCT s.id) + COUNT(DISTINCT pt.id) + COUNT(DISTINCT b.id) + 
                 COUNT(DISTINCT sp.id)) as total_records
            FROM candidates c
            LEFT JOIN education_records e ON c.id = e.candidate_id
            LEFT JOIN work_experiences w ON c.id = w.candidate_id
            LEFT JOIN publications p ON c.id = p.candidate_id
            LEFT JOIN skills s ON c.id = s.candidate_id
            LEFT JOIN patents pt ON c.id = pt.candidate_id
            LEFT JOIN books b ON c.id = b.candidate_id
            LEFT JOIN supervision_records sp ON c.id = sp.candidate_id
            GROUP BY c.id, c.name, c.status
            ORDER BY c.id
        """)
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        csv_file = OUTPUT_DIR / "000_SUMMARY.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Candidate ID', 'Name', 'Status', 'Education', 'Work', 'Publications', 
                           'Skills', 'Patents', 'Books', 'Supervision', 'TOTAL RECORDS'])
            for row in rows:
                writer.writerow(row)
        
        print(f"✓ Exported summary for {len(rows)} candidates to {csv_file}")
        return len(rows)
    except Exception as e:
        print(f"✗ Error exporting summary: {e}")
        return 0

if __name__ == "__main__":
    print("=" * 80)
    print("EXPORTING ALL PROCESSED CV DATA TO CSV")
    print("=" * 80)
    print(f"\nOutput Directory: {OUTPUT_DIR}\n")
    
    total_records = 0
    
    # Export in order
    total_records += export_summary()
    print()
    total_records += export_candidates()
    total_records += export_education()
    total_records += export_work()
    total_records += export_publications()
    total_records += export_skills()
    total_records += export_patents()
    total_records += export_books()
    total_records += export_supervision()
    
    print("\n" + "=" * 80)
    print(f"EXPORT COMPLETE - Total records exported: {total_records}")
    print("=" * 80)
    print("\nCSV Files created:")
    for csv_file in sorted(OUTPUT_DIR.glob("*.csv")):
        size = csv_file.stat().st_size
        print(f"  • {csv_file.name} ({size:,} bytes)")
