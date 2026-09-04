from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List

SUPPORTED_EXTS = {".md", ".mdx", ".rst", ".txt"}


@dataclass
class DocRecord:
    path: str
    size: int
    words: int
    heading: str | None
    hash: str


def read_doc(path: Path) -> DocRecord:
    text = path.read_text(encoding="utf-8", errors="ignore")
    heading = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip()
            break
    words = len(text.split())
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return DocRecord(
        path=str(path),
        size=path.stat().st_size,
        words=words,
        heading=heading,
        hash=digest,
    )


def scan_docs(root: Path) -> List[DocRecord]:
    records: List[DocRecord] = []
    for path in sorted(root.rglob("*")):
        try:
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
                records.append(read_doc(path))
        except OSError:
            continue
    return records


def group_by(records: Iterable[DocRecord], key: str) -> dict[str, list[DocRecord]]:
    buckets: dict[str, list[DocRecord]] = {}
    for rec in records:
        value = getattr(rec, key)
        if value in (None, ""):
            continue
        buckets.setdefault(value, []).append(rec)
    return buckets


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit documentation files for duplicates and anomalies")
    parser.add_argument("root", nargs="?", default="docs", help="Root folder to scan (default: docs)")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Output JSON for downstream tooling")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Path not found: {root}")

    records = scan_docs(root)
    duplicates = {k: v for k, v in group_by(records, "hash").items() if len(v) > 1}
    duplicate_headings = {k: v for k, v in group_by(records, "heading").items() if len(v) > 1}
    empty_docs = [rec for rec in records if rec.size == 0 or rec.words == 0]

    if args.as_json:
        payload = {
            "root": str(root),
            "total_docs": len(records),
            "records": [asdict(r) for r in records],
            "duplicates": [[asdict(r) for r in recs] for recs in duplicates.values()],
            "duplicate_headings": [[asdict(r) for r in recs] for recs in duplicate_headings.values()],
            "empty_docs": [asdict(r) for r in empty_docs],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"Scanned root: {root}")
    print(f"Total docs: {len(records)}")
    print(f"Exact duplicate groups: {len(duplicates)}")
    for digest, recs in duplicates.items():
        print(f"\nHash {digest}")
        for rec in recs:
            print(f"  {rec.path} ({rec.words} words)")

    print(f"\nDuplicate headings: {len(duplicate_headings)}")
    for heading, recs in duplicate_headings.items():
        print(f"\nHeading '{heading}'")
        for rec in recs:
            print(f"  {rec.path} ({rec.words} words)")

    print(f"\nEmpty docs: {len(empty_docs)}")
    for rec in empty_docs:
        print(f"  {rec.path}")


if __name__ == "__main__":
    main()
