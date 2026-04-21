#!/usr/bin/env python3
"""
Split all CVs from main PDFs and place in watcher folder.
Folder monitor automatically detects and processes each CV.
"""
import os
import sys
import time
import fitz  # PyMuPDF
from pathlib import Path
from typing import List

# Configuration
INPUT_PDFS = ["CVs.pdf", "Talash.pdf"]  # Try both if they exist
OUTPUT_DIR = "backend/data/cvs"

def is_blank_page(page) -> bool:
    """Check if a page is mostly blank."""
    text = page.get_text().strip()
    return len(text) < 10

def split_pdf_all(input_pdf: str, output_dir: str) -> List[str]:
    """
    Split a multi-CV PDF file by detecting blank page separators.
    
    Returns:
        List of output PDF file paths
    """
    if not os.path.exists(input_pdf):
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n[SPLIT] Opening {input_pdf}...")
    doc = fitz.open(input_pdf)
    total_pages = len(doc)
    print(f"[SPLIT] Total pages: {total_pages}")
    
    # Find all blank pages
    blank_pages = []
    for i in range(total_pages):
        if is_blank_page(doc[i]):
            blank_pages.append(i)
    
    print(f"[SPLIT] Found {len(blank_pages)} blank page separators")
    
    # Extract CV page ranges
    cv_ranges = []
    start_page = 0
    
    for blank_idx in blank_pages:
        if blank_idx > start_page:
            cv_ranges.append((start_page, blank_idx))
            start_page = blank_idx + 1
    
    # Add final range
    if start_page < total_pages:
        cv_ranges.append((start_page, total_pages))
    
    print(f"[SPLIT] Extracted {len(cv_ranges)} CV documents")
    
    # Find next available CV number
    existing_files = list(Path(output_dir).glob("cv_*.pdf"))
    next_num = max([int(f.stem.split('_')[1]) for f in existing_files] + [0]) + 1
    
    # Save each CV as individual PDF
    output_files = []
    for cv_idx, (start, end) in enumerate(cv_ranges, 1):
        cv_num = next_num + cv_idx - 1
        output_pdf = os.path.join(output_dir, f"cv_{cv_num:03d}.pdf")
        
        # Skip if already exists
        if os.path.exists(output_pdf):
            print(f"  ⊘ CV {cv_num:3d}: pages {start:3d}-{end:3d} → ALREADY EXISTS")
            continue
        
        # Create new doc with selected pages
        new_doc = fitz.open()
        for page_num in range(start, end):
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
        
        new_doc.save(output_pdf)
        new_doc.close()
        
        file_size_mb = os.path.getsize(output_pdf) / (1024 * 1024)
        print(f"  ✓ CV {cv_num:3d}: pages {start:3d}-{end:3d} → {output_pdf} ({file_size_mb:.2f} MB)")
        output_files.append(output_pdf)
    
    doc.close()
    return output_files

def main():
    print("=" * 90)
    print("CV PDF SPLITTER - Auto-Process via Folder Watcher")
    print("=" * 90)
    
    total_split = 0
    
    # Try each input PDF
    for input_pdf in INPUT_PDFS:
        if not os.path.exists(input_pdf):
            print(f"\n[SKIP] {input_pdf} not found")
            continue
        
        try:
            print(f"\n[START] Processing {input_pdf}")
            cv_files = split_pdf_all(input_pdf, OUTPUT_DIR)
            total_split += len(cv_files)
            print(f"[SUCCESS] Split {len(cv_files)} CVs from {input_pdf}")
        except Exception as e:
            print(f"[ERROR] Failed to process {input_pdf}: {e}")
            continue
    
    # Summary
    print("\n" + "=" * 90)
    print("SPLIT COMPLETE")
    print("=" * 90)
    print(f"Total CVs split: {total_split}")
    print(f"Location: {os.path.abspath(OUTPUT_DIR)}")
    print("\nAutomatic Processing:")
    print("  ✓ Folder monitor is watching for new PDFs in backend/data/cvs/")
    print("  ✓ Split CVs will be automatically detected and queued")
    print("  ✓ Check Celery worker: docker-compose logs worker -f")
    print("  ✓ Monitor progress: http://localhost:5555 (Flower)")
    print("=" * 90)

if __name__ == "__main__":
    main()

