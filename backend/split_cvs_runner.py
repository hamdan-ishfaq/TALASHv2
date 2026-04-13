#!/usr/bin/env python3
"""PDF Splitter - Extract first 3 CVs from CVs.pdf"""

import fitz
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

logger.info("=" * 80)
logger.info("[SPLITTER-START] Splitting CVs.pdf into individual PDFs")
logger.info("=" * 80)

def is_blank(page):
    return len(page.get_text().strip()) < 10

# Paths
pdf_path = "/app/../CVs.pdf"
output_dir = "/app/data/cvs"

# Verify input
if not os.path.exists(pdf_path):
    logger.error(f"PDF not found: {pdf_path}")
    exit(1)

# Open main PDF
doc = fitz.open(pdf_path)
total_pages = len(doc)
logger.info(f"[PDF-LOAD] Total pages: {total_pages}")

# Find blank pages
blank_pages = [i for i in range(total_pages) if is_blank(doc[i])]
logger.info(f"[SEPARATORS] Found {len(blank_pages)} blank page separators")

# Determine CV boundaries
cv_boundaries = [[0]]
for blank_idx in blank_pages:
    if cv_boundaries[-1][0] < blank_idx:
        cv_boundaries[-1].append(blank_idx)
        if blank_idx + 1 < total_pages:
            cv_boundaries.append([blank_idx + 1])

if len(cv_boundaries[-1]) == 1:
    cv_boundaries[-1].append(total_pages)

logger.info(f"[BOUNDARIES] Found {len(cv_boundaries)} total CV segments")

# Create output directory
os.makedirs(output_dir, exist_ok=True)

# Extract and save first 3 CVs
generated_files = []
for idx, (start, end) in enumerate(cv_boundaries[:3], 1):
    logger.info(f"[CV-{idx}] Extracting pages {start+1} to {end}")
    
    new_doc = fitz.open()
    for page_num in range(start, min(end, total_pages)):
        new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
    
    output_file = f"cv_{idx:03d}.pdf"
    output_path = os.path.join(output_dir, output_file)
    new_doc.save(output_path)
    new_doc.close()
    
    generated_files.append(output_file)
    logger.info(f"[CV-{idx}-OK] Saved: {output_file} ({end-start} pages)")

doc.close()

logger.info("=" * 80)
logger.info(f"[SPLITTER-DONE] Successfully extracted {len(generated_files)} CVs")
logger.info("=" * 80)

for f in generated_files:
    logger.info(f"  ✓ {f} ready for processing")
