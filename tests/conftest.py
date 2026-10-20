import sqlite3
from pathlib import Path

import pytest

# Subset of the Lightroom Classic schema used by lr_reader (see README.md).
SCHEMA = """
CREATE TABLE AgLibraryRootFolder(
  id_local INTEGER PRIMARY KEY,
  id_global UNIQUE NOT NULL,
  absolutePath UNIQUE NOT NULL DEFAULT '',
  name NOT NULL DEFAULT '',
  relativePathFromCatalog
);
CREATE TABLE AgLibraryFolder(
  id_local INTEGER PRIMARY KEY,
  id_global UNIQUE NOT NULL,
  parentId INTEGER,
  pathFromRoot NOT NULL DEFAULT '',
  rootFolder INTEGER NOT NULL DEFAULT 0,
  visibility INTEGER
);
CREATE TABLE AgLibraryFile(
  id_local INTEGER PRIMARY KEY,
  id_global UNIQUE NOT NULL,
  baseName NOT NULL DEFAULT '',
  extension NOT NULL DEFAULT '',
  folder INTEGER NOT NULL DEFAULT 0,
  originalFilename NOT NULL DEFAULT ''
);
"""

ROOTS = [
    (2, "r2", "C:/Users/human/Pictures/2020/", "2020", "../2020/"),
    (1, "r1", "C:/Users/human/Pictures/2019/", "2019", "../2019/"),
]
FOLDERS = [
    (10, "f10", "2019-12-31/", 1),
    (11, "f11", "2019-12-29/", 1),
    (20, "f20", "2020-01-01/", 2),
    (30, "f30", "empty/", 1),
]
FILES = [
    (100, "a100", "20191231-IMG_2", "CR2", 10, "20191231-IMG_2.CR2"),
    (101, "a101", "20191231-IMG_1", "CR2", 10, "20191231-IMG_1.CR2"),
    (102, "a102", "20191229-IMG_9", "png", 11, "20191229-IMG_9.png"),
    (200, "a200", "20200101-IMG_5", "jpg", 20, "20200101-IMG_5.jpg"),
    (999, "a999", "orphan", "jpg", 404, "orphan.jpg"),
]

# Partial-output lines in catalog order (root name, folder path, original filename).
EXPECTED_LINES = [
    "2019/2019-12-29/20191229-IMG_9.png",
    "2019/2019-12-31/20191231-IMG_1.CR2",
    "2019/2019-12-31/20191231-IMG_2.CR2",
    "2020/2020-01-01/20200101-IMG_5.jpg",
]


def build_catalog(path: Path) -> Path:
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        db.executemany("INSERT INTO AgLibraryRootFolder VALUES (?, ?, ?, ?, ?)", ROOTS)
        db.executemany(
            "INSERT INTO AgLibraryFolder (id_local, id_global, pathFromRoot, rootFolder) VALUES (?, ?, ?, ?)",
            FOLDERS,
        )
        db.executemany("INSERT INTO AgLibraryFile VALUES (?, ?, ?, ?, ?, ?)", FILES)
    db.close()
    return path


@pytest.fixture
def catalog(tmp_path: Path) -> Path:
    # Space and '#' in the name exercise URI encoding of the path.
    return build_catalog(tmp_path / "Lightroom Catalog #1.lrcat")
