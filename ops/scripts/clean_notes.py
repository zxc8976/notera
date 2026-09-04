import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from modules.utils.markdown_cleaner import clean_markdown
except ModuleNotFoundError:
    from source.backend.utils.markdown_cleaner import clean_markdown


def iter_markdown_files(root: Path):
    for path in root.rglob("*.md"):
        if path.is_file():
            yield path


def main():
    parser = argparse.ArgumentParser(description="Batch-clean generated markdown notes.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("var/notes"),
        help="Root directory containing markdown notes (default: var/notes)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print files that would be cleaned without modifying them.",
    )
    args = parser.parse_args()

    root = args.root
    if not root.exists():
        print(f"[clean_notes] Root not found: {root}")
        return

    count = 0
    for md_path in iter_markdown_files(root):
        original = md_path.read_text(encoding="utf-8")
        cleaned = clean_markdown(original)
        if cleaned != original:
            count += 1
            if args.dry_run:
                print(f"[dry-run] Would clean: {md_path}")
                continue
            md_path.write_text(cleaned, encoding="utf-8")
            print(f"[cleaned] {md_path}")

    print(f"[clean_notes] Completed. Files updated: {count}")


if __name__ == "__main__":
    main()
