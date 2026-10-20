import sqlite3
from pathlib import Path

import pytest

from lr_reader import LightroomFileFinder, format_record, main, path_to_uri

from conftest import EXPECTED_LINES


def test_iterates_records_in_order(catalog: Path) -> None:
    records = list(LightroomFileFinder(catalog))
    assert [format_record(r) for r in records] == EXPECTED_LINES


def test_full_record_fields(catalog: Path) -> None:
    first = next(iter(LightroomFileFinder(catalog)))
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
    assert len(list(LightroomFileFinder(str(catalog)))) == len(EXPECTED_LINES)


def test_can_iterate_twice(catalog: Path) -> None:
    finder = LightroomFileFinder(catalog)
    assert list(finder) == list(finder)


def test_connection_closed_after_exhaustion(catalog: Path) -> None:
    finder = LightroomFileFinder(catalog)
    list(finder)
    assert finder.db is None


def test_context_manager_closes_early(catalog: Path) -> None:
    with LightroomFileFinder(catalog) as finder:
        next(iter(finder))
        assert finder.db is not None
    assert finder.db is None


def test_opens_read_only(catalog: Path) -> None:
    finder = LightroomFileFinder(catalog)
    iter(finder)
    assert finder.db is not None
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        finder.db.execute("DELETE FROM AgLibraryFile")
    finder.close()


def test_path_to_uri_encodes_special_characters(tmp_path: Path) -> None:
    uri = path_to_uri(tmp_path / "a b#c?.lrcat")
    assert uri.startswith("file:///")
    assert uri.endswith("a%20b%23c%3F.lrcat?mode=ro")


def test_missing_file_raises_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid path"):
        iter(LightroomFileFinder(tmp_path / "missing.lrcat"))


def test_non_catalog_db_raises_runtime_error(tmp_path: Path) -> None:
    db_path = tmp_path / "other.sqlite"
    sqlite3.connect(db_path).close()
    with pytest.raises(RuntimeError, match="Database/table Problem"):
        iter(LightroomFileFinder(db_path))


def test_verbose_errors_go_to_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(ValueError):
        iter(LightroomFileFinder(tmp_path / "missing.lrcat", verbose=True))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Invalid path, permission or lock" in captured.err


def test_cli_partial_output(catalog: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(catalog)]) == 0
    assert capsys.readouterr().out.splitlines() == EXPECTED_LINES


def test_cli_full_output(catalog: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["--full", str(catalog)])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(EXPECTED_LINES)
    assert lines[0].startswith("{'root_name': '2019'")


def test_cli_verbose_keeps_stdout_clean(catalog: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["-v", str(catalog)])
    captured = capsys.readouterr()
    assert captured.out.splitlines() == EXPECTED_LINES
    assert "path:" in captured.err


def test_cli_requires_path(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2

