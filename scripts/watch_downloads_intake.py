from __future__ import annotations

import argparse
from pathlib import Path

from src.downloads_watcher import DownloadsWatcherService


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch Downloads and auto-intake PDFs into PaperPipe storage.")
    parser.add_argument("--downloads-dir", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--storage-dir", type=Path, default=Path("storage/pdfs"))
    parser.add_argument("--fuzzy-threshold", type=float, default=0.90)
    args = parser.parse_args()

    service = DownloadsWatcherService(
        downloads_dir=args.downloads_dir,
        storage_dir=args.storage_dir,
        fuzzy_threshold=args.fuzzy_threshold,
    )
    service.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
