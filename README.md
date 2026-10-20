# Lightroom Classic Catalog Image File Reader

`lr_reader` lists the image and video files referenced by an Adobe Lightroom Classic catalog (`.lrcat`, a SQLite database). It provides a command-line program and a reusable Python class, `LightroomFileFinder`.

It uses only the Python standard library ([sqlite3](https://docs.python.org/3/library/sqlite3.html)) and requires Python 3.14 or newer. Catalogs are always opened read-only.

## Installation

The project is managed with [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/jbrette/LightroomClassicCatalogReader.git
cd LightroomClassicCatalogReader
uv sync                   # creates .venv (Python 3.14), installs lr_reader in editable mode plus pytest
uv run lr-reader --help   # or: uv run python -m lr_reader --help
```

To install the `lr-reader` command globally: `uv tool install .`

## Development

```bash
uv run pytest                                               # all tests
uv run pytest tests/test_lr_reader.py::test_cli_full_output # a single test
uv build                                                    # sdist and wheel into dist/
```

The tests build a small synthetic catalog in a temporary directory, so no real Lightroom catalog is needed.

## Command-Line Usage

```text
$ uv run lr-reader --help
usage: lr-reader [-h] [--full] [-v] path

Lightroom Reader - Search for image files in Lightroom SQLite DB and output records with useful info.

positional arguments:
  path           Relative or absolute path to a Lightroom SQLite database.

options:
  -h, --help     show this help message and exit
  --full         Print full record, default is partial record printing
  -v, --verbose  Enable verbose mode
```

Verbose diagnostics are written to stderr, so stdout stays clean for piping.

### Output

By default each line is `root_name/folder_path_from_root/file_original_name`. Lightroom stores paths with `/` separators on every platform, including Windows.

```text
2019/2019-12-29/20191229-2019-12-29 08.20.46.png
2019/2019-12-29/20191229-2019-12-29 08.35.47.png
2019/2019-12-31/20191231-2019-12-31 12.22.03.png
```

With `--full`, each line is the full record as a Python dictionary:

```text
{'root_name': '2010', 'folder_path_from_root': '2010-05-04/', 'file_original_name': '20100504-IMG_7360.CR2', 'root_absolute_path': 'C:/Users/human/Pictures/2010/', 'root_rel_path_from_catalog': '../2010/', 'file_base_name': '20100504-IMG_7360', 'file_extension': 'CR2', 'root_id': 53016, 'folder_id': 53019, 'file_id': 53102}
```

Records are sorted by root name, folder path and original file name.

### Fields

| Field | Meaning |
| --- | --- |
| `root_name` | Name of the Lightroom root folder, often a year such as `2019`, depending on how the catalog is organized. |
| `folder_path_from_root` | Directories between the root folder and the file, ending in `/`. For `C:/Users/human/Pictures/2019/2019-12-31/photo.png` with root `2019`, this is `2019-12-31/`. |
| `file_original_name` | File name assigned by Lightroom Classic at import. |
| `root_absolute_path` | Absolute path of the root folder on the host, e.g. `C:/Users/human/Pictures/2019/`. |
| `root_rel_path_from_catalog` | Path of the root folder relative to the catalog file, e.g. `../2019/` when catalogs live in `Pictures/Lightroom`. For files moved to another drive this can look like `../../../../F:/`. |
| `file_base_name` | File name without extension. Usually similar to, but not the same as, the name the camera produced. |
| `file_extension` | Image or video extension, e.g. `jpg`, `png`, `CR2`, `MOV`. |
| `root_id`, `folder_id`, `file_id` | Primary keys of the rows in the three tables that produced the record. |

### Combining Multiple Catalogs

Work on copies of the `.lrcat` files. The following lists every file across several catalogs, strips drive prefixes, and removes duplicates:

```bash
for db in Lightroom*.lrcat; do
  uv run lr-reader "${db}"
done | sed -e 's/F:\/Pictures\///g' -e 's/F:\///g' | sort -u | tee image-files.txt
```

## Python API

### `LightroomFileFinder(path, verbose=False)`

An iterator yielding one dictionary per file, with the fields listed above.

- `path` (`str` or `pathlib.Path`): relative or absolute path to the catalog, e.g. `Lightroom Catalog-2.lrcat` or `C:\Users\human\Pictures\Lightroom\Lightroom Catalog-2.lrcat`. Spaces and special characters in the name are handled.
- `verbose`: when `True`, underlying error details are printed to stderr.

The database connection opens when iteration starts and closes when it ends. Use the object as a context manager to also close it when stopping early. Iterating again reopens the catalog.

```python
from lr_reader import LightroomFileFinder

with LightroomFileFinder("Pictures/Lightroom/Lightroom 5 Catalog.lrcat") as catalog:
    for record in catalog:
        print(record)
```

### Errors

| Situation | Exception |
| --- | --- |
| Catalog file missing, unreadable or locked at open | `ValueError` |
| Required tables missing (not a Lightroom catalog) | `RuntimeError` |
| Error while reading rows | `RuntimeError` |

The original `sqlite3.Error` is available as the exception's `__cause__`. A catalog that is open in a running Lightroom Classic may be locked; work on a copy.

## Catalog Schema

The program reads three tables. The full schema can be inspected with the [SQLite command-line shell](https://sqlite.org/cli.html), preferably on a copy of the catalog:

```text
$ sqlite3 'Lightroom Catalog-2.lrcat'
sqlite> .schema --indent
sqlite> .once lrcat-2.schema
sqlite> .schema --indent
sqlite> .excel
sqlite> SELECT * FROM AgLibraryFile;
```

On Windows 10, `.shell dir` from inside `sqlite3` was observed to trigger BitDefender, which killed the shell.

```sql
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
  errorMessage,
  errorTime,
  extension NOT NULL DEFAULT '',
  externalModTime,
  folder INTEGER NOT NULL DEFAULT 0,
  idx_filename NOT NULL DEFAULT '',
  importHash,
  lc_idx_filename NOT NULL DEFAULT '',
  lc_idx_filenameExtension NOT NULL DEFAULT '',
  md5,
  modTime,
  originalFilename NOT NULL DEFAULT '',
  sidecarExtensions
);
```

The query used by `lr_reader`:

```sql
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
```

## License

MIT; see [LICENSE.md](LICENSE.md). Originally written by Larry Pearson ([thatlarrypearson/LightroomClassicCatalogReader](https://github.com/thatlarrypearson/LightroomClassicCatalogReader)).
