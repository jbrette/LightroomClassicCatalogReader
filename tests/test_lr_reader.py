# Copyright (c) 2020 Larry Pearson
# SPDX-License-Identifier: MIT
"""Tests for lr_reader."""

import sqlite3
from typing import TYPE_CHECKING

import pytest

from conftest import EXPECTED_LINES
from lr_reader import (
    CatalogFetchError,
    CatalogOpenError,
    CatalogSchemaError,
    LightroomFileFinder,
    format_record,
    main,
    path_to_uri,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_iterates_records_in_order(catalog: Path) -> None:
    """Records come out joined and sorted; orphans and empty folders drop."""
    records = list(LightroomFileFinder(catalog))
    assert [format_record(r) for r in records] == EXPECTED_LINES


def test_full_record_fields(catalog: Path) -> None:
    """A record carries every aliased column."""
    with LightroomFileFinder(catalog) as finder:
        first = next(iter(finder))
    assert first == {
        "root_name": "2019",
        "folder_path_from_root": "2019-12-29/",
        "file_original_name": "20191229-IMG_9.png",
        "root_absolute_path": "C:/Users/human/Pictures/2019/",
        "root_rel_path_from_catalog": "../2019/",
        "file_base_name": "20191229-IMG_9",
        "file_extension": "png",
        "root_id": 1,
        "folder_id": 11,
        "file_id": 102,
    }


def test_accepts_str_path(catalog: Path) -> None:
    """The path may be a plain string."""
    assert len(list(LightroomFileFinder(str(catalog)))) == len(EXPECTED_LINES)


def test_can_iterate_twice(catalog: Path) -> None:
    """Iterating again reopens the catalog."""
    finder = LightroomFileFinder(catalog)
    assert list(finder) == list(finder)


def test_connection_closed_after_exhaustion(catalog: Path) -> None:
    """Exhausting the iterator closes the connection."""
    finder = LightroomFileFinder(catalog)
    list(finder)
    assert finder.db is None


def test_context_manager_closes_early(catalog: Path) -> None:
    """Leaving the with block closes a half-read connection."""
    with LightroomFileFinder(catalog) as finder:
        next(iter(finder))
        assert finder.db is not None
    assert finder.db is None


def test_opens_read_only(catalog: Path) -> None:
    """The catalog connection rejects writes."""
    finder = LightroomFileFinder(catalog)
    iter(finder)
    assert finder.db is not None
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        finder.db.execute("DELETE FROM AgLibraryFile")
    finder.close()


def test_path_to_uri_encodes_special_characters(tmp_path: Path) -> None:
    """Spaces, '#' and '?' are percent-encoded in the URI."""
    uri = path_to_uri(tmp_path / "a b#c?.lrcat")
    assert uri.startswith("file:///")
    assert uri.endswith("a%20b%23c%3F.lrcat?mode=ro")


def test_next_after_exhaustion_stops(catalog: Path) -> None:
    """next() on an exhausted finder keeps raising StopIteration."""
    finder = LightroomFileFinder(catalog)
    list(finder)
    with pytest.raises(StopIteration):
        next(finder)


def test_fetch_failure_raises_runtime_error(catalog: Path) -> None:
    """A failing row fetch raises CatalogFetchError and closes the finder."""
    finder = iter(LightroomFileFinder(catalog))
    assert finder.db is not None
    finder.db.close()  # the cursor now fails on fetch
    with pytest.raises(CatalogFetchError, match="Row Fetch Problem") as exc:
        next(finder)
    assert isinstance(exc.value, RuntimeError)
    assert isinstance(exc.value.__cause__, sqlite3.ProgrammingError)
    assert finder.db is None


def test_missing_file_raises_value_error(tmp_path: Path) -> None:
    """A missing catalog raises CatalogOpenError, a ValueError."""
    with pytest.raises(CatalogOpenError, match="Invalid path") as exc:
        iter(LightroomFileFinder(tmp_path / "missing.lrcat"))
    assert isinstance(exc.value, ValueError)


def test_non_catalog_db_raises_runtime_error(tmp_path: Path) -> None:
    """A non-Lightroom database raises CatalogSchemaError, a RuntimeError."""
    db_path = tmp_path / "other.sqlite"
    sqlite3.connect(db_path).close()
    with pytest.raises(CatalogSchemaError, match="Database/table Problem") as exc:
        iter(LightroomFileFinder(db_path))
    assert isinstance(exc.value, RuntimeError)


def test_verbose_errors_go_to_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verbose diagnostics go to stderr only."""
    with pytest.raises(ValueError, match="Invalid path"):
        iter(LightroomFileFinder(tmp_path / "missing.lrcat", verbose=True))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Invalid path, permission or lock" in captured.err


def test_cli_partial_output(catalog: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The CLI prints one partial line per file."""
    assert main([str(catalog)]) == 0
    assert capsys.readouterr().out.splitlines() == EXPECTED_LINES


def test_cli_full_output(catalog: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--full prints one dict per file."""
    main(["--full", str(catalog)])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(EXPECTED_LINES)
    assert lines[0].startswith("{'root_name': '2019'")


def test_cli_verbose_keeps_stdout_clean(catalog: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """-v writes diagnostics to stderr, not stdout."""
    main(["-v", str(catalog)])
    captured = capsys.readouterr()
    assert captured.out.splitlines() == EXPECTED_LINES
    assert "path:" in captured.err


def test_cli_requires_path() -> None:
    """The CLI exits 2 without a path."""
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
