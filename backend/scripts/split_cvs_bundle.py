#!/usr/bin/env python3
"""
Split a merged CV bundle (e.g. CVs.pdf) into one PDF per CV.

Separator pages: blank pages (minimal extractable text), same idea as the old
root-level split scripts — but output goes to data/cvs_split/, NOT data/cvs/.

The folder watcher and API uploads still use data/cvs/. After splitting, copy or
move only the PDFs you want processed into data/cvs/ (or upload via UI).

Usage (from repo root, host Python with PyMuPDF, or inside backend container):

  docker compose exec backend python scripts/split_cvs_bundle.py
  docker compose exec backend python scripts/split_cvs_bundle.py --input /app/CVs.pdf

  python backend/scripts/split_cvs_bundle.py --input CVs.pdf
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz  # type: ignore
    except ImportError:
        print("Install PyMuPDF: pip install pymupdf", file=sys.stderr)
        sys.exit(1)

logger = logging.getLogger(__name__)


def _backend_root() -> Path:
    """Directory that contains app/ and data/ ( /app in Docker, .../backend on host)."""
    return Path(__file__).resolve().parent.parent


def _default_input_pdf(backend: Path) -> Path:
    env = os.environ.get("TALASH_CVS_BUNDLE")
    if env:
        return Path(env).expanduser().resolve()
    candidates: list[Path] = []
    if (backend / "app" / "main.py").is_file():
        candidates.append(backend / "CVs.pdf")
        parent = backend.parent
        if (parent / "docker-compose.yml").is_file():
            candidates.append(parent / "CVs.pdf")
    else:
        candidates.append(backend.parent / "CVs.pdf")
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return candidates[0] if candidates else backend / "CVs.pdf"


def _default_output_dir(backend: Path) -> Path:
    env = os.environ.get("TALASH_CV_SPLIT_OUT")
    if env:
        return Path(env).expanduser().resolve()
    return (backend / "data" / "cvs_split").resolve()


def is_blank_page(page: fitz.Page) -> bool:
    """Treat page as separator if almost no text (blank CV separator sheets)."""
    try:
        text = (page.get_text() or "").strip()
        if len(text) < 10:
            return True
        return False
    except Exception:
        return True


def page_ranges_by_blank_separators(doc: fitz.Document) -> list[tuple[int, int]]:
    """
    Inclusive start, exclusive end page indices (0-based), omitting separator pages.
    Each range is one CV; blank pages are never included in output ranges.
    """
    total = len(doc)
    ranges: list[tuple[int, int]] = []
    s = 0
    for i in range(total):
        if is_blank_page(doc[i]) and i >= s:
            if i > s:
                ranges.append((s, i))
            s = i + 1
    if s < total:
        ranges.append((s, total))
    out: list[tuple[int, int]] = []
    for a, b in ranges:
        if b > a:
            out.append((a, b))
    return out


def clear_cv_pdfs(output_dir: Path, prefix: str) -> int:
    n = 0
    for p in output_dir.glob(f"{prefix}_*.pdf"):
        try:
            p.unlink()
            n += 1
        except OSError as e:
            logger.warning("Could not remove %s: %s", p, e)
    return n


def split_bundle(
    input_pdf: Path,
    output_dir: Path,
    *,
    max_cvs: int | None = None,
    clear_output: bool = False,
    prefix: str = "cv",
) -> list[Path]:
    if not input_pdf.is_file():
        raise FileNotFoundError(f"Input PDF not found: {input_pdf}")

    output_dir.mkdir(parents=True, exist_ok=True)
    if clear_output:
        removed = clear_cv_pdfs(output_dir, prefix)
        logger.info("Cleared %d existing %s_*.pdf in %s", removed, prefix, output_dir)

    doc = fitz.open(input_pdf)
    try:
        ranges = page_ranges_by_blank_separators(doc)
        logger.info(
            "Loaded %s (%d pages) -> %d CV segment(s) (blank-page separated)",
            input_pdf.name,
            len(doc),
            len(ranges),
        )
        if max_cvs is not None:
            ranges = ranges[: max(0, max_cvs)]

        written: list[Path] = []
        for idx, (start, end) in enumerate(ranges, start=1):
            new_doc = fitz.open()
            try:
                for page_num in range(start, end):
                    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                name = f"{prefix}_{idx:03d}.pdf"
                out_path = output_dir / name
                new_doc.save(out_path)
                written.append(out_path)
                logger.info(
                    "Wrote %s (source pages %d-%d, %d pages)",
                    name,
                    start + 1,
                    end,
                    end - start,
                )
            finally:
                new_doc.close()
        return written
    finally:
        doc.close()


def main() -> int:
    backend = _backend_root()
    default_in = _default_input_pdf(backend)
    default_out = _default_output_dir(backend)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=default_in, help="Merged CVs PDF")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_out,
        help="Output directory (default: backend/data/cvs_split — not the watcher folder)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        metavar="N",
        help="Write at most N CV PDFs (default: all)",
    )
    parser.add_argument(
        "--clear-output",
        action="store_true",
        help="Remove existing cv_*.pdf in output dir before writing",
    )
    parser.add_argument("--prefix", default="cv", help="Output filename prefix (default: cv)")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    inp = args.input.expanduser().resolve()
    out_dir = args.output_dir.expanduser().resolve()

    try:
        paths = split_bundle(
            inp,
            out_dir,
            max_cvs=args.max,
            clear_output=args.clear_output,
            prefix=re.sub(r"[^a-zA-Z0-9_-]", "", args.prefix) or "cv",
        )
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 2
    except Exception as e:
        logger.exception("Split failed: %s", e)
        return 1

    logger.info("Done: %d file(s) -> %s", len(paths), out_dir)
    logger.info(
        "Copy PDFs you want processed into backend/data/cvs/ for the folder watcher, "
        "or upload via the API / UI."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
