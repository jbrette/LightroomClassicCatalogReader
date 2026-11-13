# Copyright (c) 2020 Larry Pearson
# SPDX-License-Identifier: MIT
"""Read an Adobe Lightroom Classic catalog and list the image/video files it references."""

import sqlite3
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Self, cast, override

if TYPE_CHECKING:
    from types import TracebackType

__version__ = "26.11.13"

type SQLValue = str | int | float | bytes | None
type Record = dict[str, SQLValue]

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


class CatalogOpenError(ValueError):
    """The catalog file is missing, unreadable or locked."""

    def __init__(self, path: str | Path) -> None:
        """Build the message for the catalog at ``path``."""
        super().__init__(f"Invalid path, permission or lock: {path}")


class CatalogQueryError(RuntimeError):
    """The catalog opened but reading it failed."""

    problem: ClassVar[str] = "Catalog query problem"

    def __init__(self, path: str | Path) -> None:
        """Build the message for the catalog at ``path``."""
        super().__init__(f"{self.problem}: {path}")


class CatalogSchemaError(CatalogQueryError):
    """The Lightroom tables are missing: the file is not a Lightroom catalog."""

    problem = "Database/table Problem"


class CatalogFetchError(CatalogQueryError):
    """A row could not be fetched from the catalog."""

    problem = "Row Fetch Problem"


def dict_factory(cursor: sqlite3.Cursor, row: tuple[SQLValue, ...]) -> Record:
    """Map a result row to a dict keyed by column alias (a ``sqlite3`` row factory)."""
    columns = cast("tuple[tuple[str, ...], ...]", cursor.description)
    return {col[0]: row[idx] for idx, col in enumerate(columns)}


def path_to_uri(path: str | Path) -> str:
    """Build a read-only SQLite URI; as_uri() percent-encodes spaces, '?' and '#'."""
    return f"{Path(path).resolve().as_uri()}?mode=ro"


class LightroomFileFinder:
    """Iterate over the image/video file records in a Lightroom Classic catalog."""

    def __init__(self, path: str | Path, *, verbose: bool = False) -> None:
        """Prepare to read the catalog at ``path``; nothing is opened until iteration."""
        self.path: str | Path = path
        self.verbose: bool = verbose
        self.db: sqlite3.Connection | None = None
        self.cursor: sqlite3.Cursor | None = None

    def _report(self, exc: BaseException, message: str) -> None:
        if self.verbose:
            print(f"\nException: {exc!r}", file=sys.stderr)
            print(f"{message}: {self.path}\n", file=sys.stderr)

    def __iter__(self) -> Self:
        """Open the catalog read-only and start the query, closing any previous run."""
        self.close()
        try:
            self.db = sqlite3.connect(path_to_uri(self.path), uri=True)
        except sqlite3.Error as e:
            self._report(e, "Invalid path, permission or lock")
            raise CatalogOpenError(self.path) from e
        try:
            self.db.row_factory = dict_factory
            self.cursor = self.db.execute(SQL_SELECT)
        except sqlite3.Error as e:
            self._report(e, "Database/table Problem")
            self.close()
            raise CatalogSchemaError(self.path) from e
        return self

    def __next__(self) -> Record:
        """Return the next file record; close the connection when exhausted."""
        if self.cursor is None:
            raise StopIteration
        try:
            row = cast("Record | None", self.cursor.fetchone())
        except sqlite3.Error as e:
            self._report(e, "Row Fetch Problem")
            self.close()
            raise CatalogFetchError(self.path) from e
        if row is None:
            self.close()
            raise StopIteration
        return row

    def close(self) -> None:
        """Close the database connection, if open."""
        if self.db is not None:
            self.db.close()
        self.db = None
        self.cursor = None

    def __enter__(self) -> Self:
        """Return self; the connection opens when iteration starts."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the connection on leaving the ``with`` block."""
        self.close()


def format_record(record: Record) -> str:
    """Format a record as the partial-output line ``root/folder/file``."""
    root, folder, name = (
        str(record[key]) for key in ("root_name", "folder_path_from_root", "file_original_name")
    )
    return f"{root}/{folder}{name}"


class Arguments(Namespace):
    """Typed command-line arguments."""

    path: str
    full: bool
    verbose: bool

    @override
    def __init__(self) -> None:
        """Set the defaults ``parse_args`` overwrites."""
        super().__init__()
        self.path = ""
        self.full = False
        self.verbose = False


def main(argv: list[str] | None = None) -> int:
    """Run the ``lr-reader`` command line and return its exit code."""
    parser = ArgumentParser(
        description=(
            "Lightroom Reader - Search for image files in Lightroom SQLite DB"
            " and output records with useful info."
        ),
    )
    parser.add_argument("path", help="Relative or absolute path to a Lightroom SQLite database.")
    parser.add_argument(
        "--full",
        help="Print full record, default is partial record printing",
        action="store_true",
    )
    parser.add_argument("-v", "--verbose", help="Enable verbose mode", action="store_true")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv, namespace=Arguments())

    if args.verbose:
        print("path:", args.path, file=sys.stderr)
        print("full:", args.full, file=sys.stderr)
        print("verbose:", args.verbose, file=sys.stderr)

    with LightroomFileFinder(args.path, verbose=args.verbose) as lrff:
        for record in lrff:
            print(record if args.full else format_record(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
