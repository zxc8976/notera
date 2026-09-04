#!/usr/bin/env python3
"""Manual OCR diagnostic helper.

This script consolidates the legacy ``test_ocr.py`` and ``test_ocr_simple.py``
utilities into a single entry point that can exercise both PaddleOCR-VL and
Tesseract (when available).  It is intended for on-demand verification when OCR
output appears suspicious, not as part of the automated test suite.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Iterable, List

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def discover_images(root: Path, limit: int | None = None) -> List[Path]:
    """Collect candidate image files for OCR sanity checks."""
    results: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in IMAGE_EXTS:
            results.append(path)
            if limit and len(results) >= limit:
                break
    return results


def run_paddle_ocr(image_paths: Iterable[Path], use_gpu: bool = False) -> None:
    try:
        from modules.core.ocr_utils import ocr_manager
    except Exception as exc:
        logger.error("Unable to import OCR manager: %s", exc)
        return

    config = {
        "ocr": {
            "primary_lang": "japan",
            "languages": ["japan", "ch"],
            "use_gpu": use_gpu,
            "batch_size": 4,
            "layout": {"enabled": True},
        }
    }
    device = "gpu" if use_gpu else "cpu"
    logger.info("Initialising PaddleOCR-VL (device=%s)...", device)
    engine = ocr_manager.get_engine(config, device)

    for path in image_paths:
        logger.info("[PaddleOCR-VL] %s", path)
        structured = engine.extract_text(str(path))
        if not structured or not isinstance(structured, dict):
            logger.warning("  -> no text detected")
            continue

        lines = structured.get("lines") or []
        if not lines:
            logger.warning("  -> no text detected")
            continue

        for line in lines:
            text = (line.get("text") or "").strip()
            confidence = float(line.get("confidence", 0.0))
            if not text:
                continue
            logger.info("  %.2f %% | %s", confidence * 100, text)


def run_tesseract(image_paths: Iterable[Path]) -> None:
    try:
        import cv2
        import pytesseract  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.error("Unable to import Tesseract stack (cv2/pytesseract): %s", exc)
        return

    for path in image_paths:
        logger.info("[Tesseract] %s", path)
        img = cv2.imread(str(path))
        if img is None:
            logger.warning("  -> unable to read image")
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray, lang="jpn+eng")
        if text.strip():
            preview = text.strip().replace("\n", " ")
            logger.info("  text=%s", preview[:200])
        else:
            logger.warning("  -> no text detected")


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual OCR diagnostic helper")
    parser.add_argument(
        "--engine",
        choices=["paddle", "tesseract", "both"],
        default="both",
        help="Which OCR backend(s) to exercise",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Directory to search for sample images (default: current working directory)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Maximum number of sample images to evaluate (default: 3)",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Attempt to use GPU acceleration for PaddleOCR-VL",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging output",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    search_root = args.root.resolve()
    if not search_root.exists():
        logger.error("Search root does not exist: %s", search_root)
        return 1

    images = discover_images(search_root, limit=args.limit)
    if not images:
        logger.error("No image files discovered under %s", search_root)
        return 1

    logger.info("Discovered %d image(s) for diagnostics", len(images))

    if args.engine in {"paddle", "both"}:
        run_paddle_ocr(images, use_gpu=args.gpu)
    if args.engine in {"tesseract", "both"}:
        run_tesseract(images)

    logger.info("Diagnostics complete")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
