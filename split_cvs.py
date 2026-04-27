#!/usr/bin/env python3
"""
PDF Splitter: Break CVs.pdf into individual CVs
Separators: Blank pages
Stores: backend/data/cvs/
Limit: First 3 CVs only
"""

import logging
import os
from pathlib import Path
try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        print("ERROR: pymupdf not available. Run: pip install pymupdf")
        exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def is_blank_page(page) -> bool:
    """Check if a page is mostly blank (white)."""
    try:
        text = page.get_text().strip()
        if len(text) < 10:
            return True
        return False
    except Exception:
        return False


def split_pdf(input_pdf: str, output_dir: str, max_cvs: int = 3) -> list[str]:
    """
    Split PDF by blank page separators.
    
    Args:
        input_pdf: Path to main CVs.pdf
        output_dir: Directory to save split PDFs
        max_cvs: Maximum number of CVs to extract (default 3)
    
    Returns:
        List of generated PDF file paths
    """
    logger.info(f"================================================================================")
    logger.info(f"[SPLITTER-START] Starting PDF split | input={input_pdf} | output_dir={output_dir}")
    logger.info(f"================================================================================")
    
    if not os.path.exists(input_pdf):
        logger.error(f"[ERROR] Input PDF not found: {input_pdf}")
        return []
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Open the PDF
    doc = fitz.open(input_pdf)
    total_pages = len(doc)
    logger.info(f"[PDF-LOAD] Total pages: {total_pages}")
    
    # Find blank pages (separators)
    blank_pages = []
    for i in range(total_pages):
        page = doc[i]
        if is_blank_page(page):
            blank_pages.append(i)
            logger.debug(f"[BLANK-PAGE] Page {i+1} is blank")
    
    logger.info(f"[SEPARATORS] Found {len(blank_pages)} blank pages (separators)")
    
    # Determine CV boundaries
    cv_boundaries = [[0]]  # Start with page 0
    
    for blank_idx in blank_pages:
        # CV ends before blank page, next CV starts after blank page
        if cv_boundaries[-1][0] < blank_idx:
            cv_boundaries[-1].append(blank_idx)  # End of current CV
            if blank_idx + 1 < total_pages:
                cv_boundaries.append([blank_idx + 1])  # Start of next CV
    
    # Close last CV boundary
    if len(cv_boundaries[-1]) == 1:
        cv_boundaries[-1].append(total_pages)
    
    logger.info(f"[BOUNDARIES] Total CV segments found: {len(cv_boundaries)}")
    
    # Extract and save CVs (cap at max_cvs)
    generated_files = []
    for idx, (start_page, end_page) in enumerate(cv_boundaries[:max_cvs]):
        cv_num = idx + 1
        logger.info(f"[CV-{cv_num}] Pages {start_page+1} to {end_page} | num_pages={end_page-start_page}")
        
        # Create new document with selected pages
        new_doc = fitz.open()
        for page_num in range(start_page, end_page):
            if page_num < total_pages:
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
        
        # Save to output directory
        output_filename = f"cv_{cv_num:03d}.pdf"
        output_path = os.path.join(output_dir, output_filename)
        new_doc.save(output_path)
        new_doc.close()
        
        generated_files.append(output_path)
        logger.info(f"[CV-{cv_num}-OK] Saved: {output_filename}")
    
    doc.close()
    
    logger.info(f"================================================================================")
    logger.info(f"[SPLITTER-DONE] Split complete | extracted={len(generated_files)} CVs | capped_at={max_cvs}")
    logger.info(f"================================================================================")
    
    return generated_files


if __name__ == "__main__":
    # Paths
    script_dir = Path(__file__).parent
    input_pdf = str(script_dir / "CVs.pdf")
    output_dir = str(script_dir / "backend" / "data" / "cvs")
    
    # Run splitter (max 3 CVs)
    files = split_pdf(input_pdf, output_dir, max_cvs=5)
    
    if files:
        logger.info(f"\n✓ Generated {len(files)} CV PDFs ready for processing:")
        for f in files:
            logger.info(f"  - {os.path.basename(f)}")
    else:
        logger.warning("No CVs were generated. Check input file and format.")
