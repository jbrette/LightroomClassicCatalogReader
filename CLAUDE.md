# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Single-module Python tool (`lr_reader.py`) that reads an Adobe Lightroom Classic catalog (`.lrcat`, a SQLite database) and lists the image/video files it references. Standard library only (`sqlite3`, `argparse`); Python >= 3.14 (uses `type` aliases and `typing.Self`). Managed with uv via `pyproject.toml` (hatchling backend, wheel contains only `lr_reader.py`); there is no linter config or CI.

## Commands

```bash
uv sync                                   # .venv on Python 3.14 (.python-version), editable install + pytest
uv run pytest                             # full test suite
uv run pytest tests/test_lr_reader.py::test_cli_full_output   # single test
uv run lr-reader path/to/Catalog.lrcat            # one "root/folder/file" line per file
uv run lr-reader --full path/to/Catalog.lrcat     # one dict per file with all joined fields
uv run lr-reader -v path/to/Catalog.lrcat         # diagnostics go to stderr
uv build                                  # sdist + wheel into dist/
```

Tests never need a real catalog: `tests/conftest.py` builds a synthetic `.lrcat` from the README schema (including an orphan file and an empty folder that the join must drop) and defines `EXPECTED_LINES`, the expected partial output in sort order.

`catalogs/` is gitignored and is the place to drop local `.lrcat` files for manual testing (a stray empty `.lrcat-wal` is tracked there despite the ignore rule).

## Architecture

- `SQL_SELECT` joins `AgLibraryRootFolder` → `AgLibraryFolder` (on `folder.rootFolder`) → `AgLibraryFile` (on `file.folder`) and aliases columns to the snake_case keys that make up the public record format (`root_name`, `folder_path_from_root`, `file_original_name`, `root_absolute_path`, etc.). Renaming an alias changes the output contract documented in README.md.
- `LightroomFileFinder` is the reusable API (`from lr_reader import LightroomFileFinder`). It is an iterator: the DB connection and query happen lazily in `__iter__`, rows become dicts via `dict_factory` set as the connection's `row_factory`. The connection closes on exhaustion, on error, or via the context-manager protocol; re-iterating reopens it. Connection failures raise `ValueError`; query/fetch failures raise `RuntimeError` (both chained from the `sqlite3.Error`).
- The catalog is opened read-only through a SQLite URI (`file:<path>?mode=ro`), built by `path_to_uri` with `Path.resolve().as_uri()` so spaces, `#` and `?` in catalog names are percent-encoded. The tool never writes to a catalog.
- Lightroom stores paths with `/` separators on all platforms; `folder_path_from_root` already ends in `/`, which the partial-output format relies on.
- `main(argv=None)` accepts an argv list and returns an exit code, so tests call it directly instead of spawning a process. It is also the `lr-reader` console script.

README.md contains the relevant table schemas and notes on inspecting a catalog with the `sqlite3` CLI.
