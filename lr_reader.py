# Lightroom Reader
import sqlite3
import sys
from argparse import ArgumentParser
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Self

type Record = dict[str, Any]

SQL_SELECT = """
SELECT
  root.name AS root_name,
  folder.pathFromRoot AS folder_path_from_root,
  file.originalFilename AS file_original_name,
  root.absolutePath AS root_absolute_path,
  root.relativePathFromCatalog AS root_rel_path_from_catalog,
  file.baseName AS file_base_name,
  file.extension AS file_extension,
  root.id_local AS root_id,
  folder.id_local AS folder_id,
  file.id_local AS file_id
FROM AgLibraryRootFolder root
JOIN AgLibraryFolder folder ON root.id_local = folder.rootFolder
JOIN AgLibraryFile file ON folder.id_local = file.folder
ORDER BY root.name, folder.pathFromRoot, file.originalFilename;
"""


def dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> Record:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def path_to_uri(path: str | Path) -> str:
    """Build a read-only SQLite URI; as_uri() percent-encodes spaces, '?' and '#'."""
    return f"{Path(path).resolve().as_uri()}?mode=ro"


class LightroomFileFinder:
    """Iterate over the image/video file records in a Lightroom Classic catalog."""

    def __init__(self, path: str | Path, verbose: bool = False) -> None:
        self.path = path
        self.verbose = verbose
        self.db: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor | None = None

    def _report(self, exc: BaseException, message: str) -> None:
        if self.verbose:
            print(f"\nException: {exc!r}", file=sys.stderr)
            print(f"{message}: {self.path}\n", file=sys.stderr)

    def __iter__(self) -> Self:
        self.close()
        try:
            self.db = sqlite3.connect(path_to_uri(self.path), uri=True)
        except sqlite3.Error as e:
            self._report(e, "Invalid path, permission or lock")
            raise ValueError(f"Invalid path, permission or lock: {self.path}") from e
        try:
            self.db.row_factory = dict_factory
            self.cursor = self.db.execute(SQL_SELECT)
        except sqlite3.Error as e:
            self._report(e, "Database/table Problem")
            self.close()
            raise RuntimeError(f"Database/table Problem: {self.path}") from e
        return self

    def __next__(self) -> Record:
        if self.cursor is None:
            raise StopIteration
        try:
            row = self.cursor.fetchone()
        except sqlite3.Error as e:
            self._report(e, "Row Fetch Problem")
            self.close()
            raise RuntimeError(f"Row Fetch Problem: {self.path}") from e
        if row is None:
            self.close()
            raise StopIteration
        return row

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
        self.db = None
        self.cursor = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def format_record(record: Record) -> str:
    return f"{record['root_name']}/{record['folder_path_from_root']}{record['file_original_name']}"


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(
        description="Lightroom Reader - Search for image files in Lightroom SQLite DB and output records with useful info."
    )
    parser.add_argument("path", help="Relative or absolute path to a Lightroom SQLite database.")
    parser.add_argument("--full", help="Print full record, default is partial record printing", action="store_true")
    parser.add_argument("-v", "--verbose", help="Enable verbose mode", action="store_true")
    args = parser.parse_args(argv)

    if args.verbose:
        print("path:", args.path, file=sys.stderr)
        print("full:", args.full, file=sys.stderr)
        print("verbose:", args.verbose, file=sys.stderr)

    with LightroomFileFinder(args.path, args.verbose) as lrff:
        for record in lrff:
            print(record if args.full else format_record(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
