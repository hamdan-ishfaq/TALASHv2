#!/bin/bash
# Run PDF splitter in Docker backend container (which has pymupdf installed)

cd "$(dirname "$0")"

echo "================================================================================"
echo "[PDF-SPLITTER] Running in Docker backend container..."
echo "================================================================================"

docker-compose exec -T backend python3 - <<'PYTHON_SCRIPT'
import logging
import os
from pathlib import Path
import fitz

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def is_blank_page(page) -> bool:
    """Check if a page is mostly blank."""
    try:
        text = page.get_text().strip()
        return len(text) < 10
    except:
        return False

def split_pdf(input_pdf: str, output_dir: str, max_cvs: int = 3) -> list:
    logger.info("=" * 80)
    logger.info(f"[SPLITTER-START] input={input_pdf} | limit={max_cvs} CVs")
    logger.info("=" * 80)
    
    if not os.path.exists(input_pdf):
        logger.error(f"[ERROR] Input PDF not found: {input_pdf}")
        return []
    
    os.makedirs(output_dir, exist_ok=True)
    
    doc = fitz.open(input_pdf)
    total_pages = len(doc)
    logger.info(f"[PDF-LOAD] Total pages: {total_pages}")
    
    # Find blank pages
    blank_pages = []
    for i in range(total_pages):
        if is_blank_page(doc[i]):
            blank_pages.append(i)
    
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
    
    logger.info(f"[BOUNDARIES] Total segments: {len(cv_boundaries)}")
    
    # Extract and save (capped at max_cvs)
    generated = []
    for idx, (start, end) in enumerate(cv_boundaries[:max_cvs]):
        cv_num = idx + 1
        new_doc = fitz.open()
        for page_num in range(start, min(end, total_pages)):
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
        
        output_file = f"cv_{cv_num:03d}.pdf"
        output_path = os.path.join(output_dir, output_file)
        new_doc.save(output_path)
        new_doc.close()
        generated.append(output_path)
        logger.info(f"[CV-{cv_num}-OK] Pages {start+1}-{end} → {output_file}")
    
    doc.close()
    
    logger.info("=" * 80)
    logger.info(f"[SPLITTER-DONE] Extracted {len(generated)} CVs")
    logger.info("=" * 80)
    
    return generated

# Run splitter
input_pdf = "/app/../CVs.pdf"
output_dir = "/app/data/cvs"

# Try to find the PDF
if os.path.exists(input_pdf):
    files = split_pdf(input_pdf, output_dir, max_cvs=3)
    if files:
        logger.info("\n✓ Generated PDFs ready for processing:")
        for f in files:
            logger.info(f"  - {os.path.basename(f)}")
else:
    logger.error(f"CVs.pdf not found at {input_pdf}")
PYTHON_SCRIPT

echo ""
echo "================================================================================"
echo "[DONE] Check backend/data/cvs/ for generated PDFs"
echo "================================================================================"
