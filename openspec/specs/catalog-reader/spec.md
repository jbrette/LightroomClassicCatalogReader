# catalog-reader Specification

## Purpose
Read an Adobe Lightroom Classic catalog (`.lrcat`, a SQLite database) and expose every image or video file it references as a record, through the reusable `LightroomFileFinder` Python API.

## Requirements

### Requirement: File records are joined from root, folder and file tables
The reader SHALL produce one record per row of `AgLibraryFile` whose `folder` matches an `AgLibraryFolder.id_local` whose `rootFolder` matches an `AgLibraryRootFolder.id_local`. Files without a matching folder, and folders without files, SHALL NOT produce records.

#### Scenario: Orphan file is dropped
- **WHEN** an `AgLibraryFile` row references a folder id that does not exist
- **THEN** no record is produced for that file

#### Scenario: Empty folder is dropped
- **WHEN** an `AgLibraryFolder` row has no files
- **THEN** no record is produced for that folder

### Requirement: Records are ordered by root name, folder path and original filename
The reader SHALL yield records sorted by `root_name`, then `folder_path_from_root`, then `file_original_name`, regardless of the insertion order or ids in the catalog.

#### Scenario: Catalog rows inserted out of order
- **WHEN** roots, folders and files are stored in an order different from their names
- **THEN** records are yielded in ascending order of root name, folder path and original filename

### Requirement: Record keys
Each record SHALL be a dict with exactly the keys `root_name`, `folder_path_from_root`, `file_original_name`, `root_absolute_path`, `root_rel_path_from_catalog`, `file_base_name`, `file_extension`, `root_id`, `folder_id` and `file_id`. Renaming a key is a breaking change.

#### Scenario: Column mapping
- **WHEN** a record is built from a joined row
- **THEN** `root_name`, `root_absolute_path`, `root_rel_path_from_catalog` and `root_id` come from `AgLibraryRootFolder` `name`, `absolutePath`, `relativePathFromCatalog` and `id_local`; `folder_path_from_root` and `folder_id` from `AgLibraryFolder` `pathFromRoot` and `id_local`; `file_original_name`, `file_base_name`, `file_extension` and `file_id` from `AgLibraryFile` `originalFilename`, `baseName`, `extension` and `id_local`

#### Scenario: Full record contents
- **WHEN** the catalog holds root `2019` at `C:/Users/human/Pictures/2019/` (relative `../2019/`, id 1), folder `2019-12-29/` (id 11) and file `20191229-IMG_9.png` (base `20191229-IMG_9`, extension `png`, id 102)
- **THEN** the record is `{"root_name": "2019", "folder_path_from_root": "2019-12-29/", "file_original_name": "20191229-IMG_9.png", "root_absolute_path": "C:/Users/human/Pictures/2019/", "root_rel_path_from_catalog": "../2019/", "file_base_name": "20191229-IMG_9", "file_extension": "png", "root_id": 1, "folder_id": 11, "file_id": 102}`

### Requirement: Record values are passed through unchanged
Record values SHALL be the SQLite values as stored: text as `str`, ids as `int`, NULL as `None`. Paths SHALL keep Lightroom's `/` separators on every platform, and `folder_path_from_root` keeps its trailing `/`.

#### Scenario: Windows catalog read on any platform
- **WHEN** a root's absolute path is stored as `C:/Users/human/Pictures/2019/`
- **THEN** `root_absolute_path` is exactly `C:/Users/human/Pictures/2019/`

### Requirement: Partial record line
`format_record(record)` SHALL return `<root_name>/<folder_path_from_root><file_original_name>`, relying on `folder_path_from_root` already ending in `/`.

#### Scenario: Formatting a record
- **WHEN** a record has root `2019`, folder `2019-12-29/` and file `20191229-IMG_9.png`
- **THEN** the line is `2019/2019-12-29/20191229-IMG_9.png`

### Requirement: Catalog path input
`LightroomFileFinder(path, *, verbose=False)` SHALL accept `path` as a `str` or `pathlib.Path`, relative or absolute. Names containing spaces, `#` or `?` SHALL be opened correctly. `verbose` SHALL be keyword-only.

#### Scenario: String path
- **WHEN** the path is given as a `str`
- **THEN** the same records are yielded as for the equivalent `Path`

#### Scenario: Special characters in the catalog name
- **WHEN** the catalog file is named `Lightroom Catalog #1.lrcat`
- **THEN** the catalog opens and its records are yielded

#### Scenario: URI encoding
- **WHEN** `path_to_uri` is given `a b#c?.lrcat`
- **THEN** it returns an absolute `file:///` URI ending in `a%20b%23c%3F.lrcat?mode=ro`

### Requirement: Catalog is opened read-only
The reader SHALL open the catalog through a SQLite URI with `mode=ro` and SHALL NOT write to it.

#### Scenario: Write attempt on the reader's connection
- **WHEN** a statement that modifies the catalog is executed on the reader's connection
- **THEN** SQLite rejects it with a read-only `sqlite3.OperationalError`

### Requirement: Lazy, re-iterable connection lifecycle
Constructing a `LightroomFileFinder` SHALL NOT open the catalog. Starting iteration SHALL open it and run the query, closing any connection left from a previous iteration. The connection SHALL close when iteration is exhausted, when an error is raised, when `close()` is called, or on leaving a `with` block. Iterating again SHALL reopen the catalog and yield the same records. Calling `next()` after exhaustion SHALL raise `StopIteration` again.

#### Scenario: Exhaustion closes the connection
- **WHEN** every record has been consumed
- **THEN** the finder holds no open connection

#### Scenario: Early exit from a with block
- **WHEN** iteration stops after one record inside `with LightroomFileFinder(path) as finder:`
- **THEN** the connection is open inside the block and closed after it

#### Scenario: Iterating twice
- **WHEN** the same finder is iterated to completion twice
- **THEN** both iterations yield identical record lists

#### Scenario: next() after exhaustion
- **WHEN** `next()` is called on an exhausted finder
- **THEN** `StopIteration` is raised

### Requirement: Open failure raises CatalogOpenError
When the catalog is missing, unreadable or locked at open, starting iteration SHALL raise `CatalogOpenError`, a subclass of `ValueError`, with the message `Invalid path, permission or lock: <path>`.

#### Scenario: Missing catalog
- **WHEN** the path does not exist
- **THEN** `CatalogOpenError` (a `ValueError`) is raised when iteration starts

### Requirement: Query failures raise CatalogQueryError subclasses
When the Lightroom tables are missing, starting iteration SHALL raise `CatalogSchemaError` with the message `Database/table Problem: <path>`. When fetching a row fails, `next()` SHALL raise `CatalogFetchError` with the message `Row Fetch Problem: <path>`. Both SHALL subclass `CatalogQueryError`, a subclass of `RuntimeError`.

#### Scenario: Not a Lightroom catalog
- **WHEN** the path is a valid SQLite database without the Lightroom tables
- **THEN** `CatalogSchemaError` (a `RuntimeError`) is raised when iteration starts

#### Scenario: Fetch failure
- **WHEN** fetching a row fails with a `sqlite3.Error`
- **THEN** `CatalogFetchError` (a `RuntimeError`) is raised

### Requirement: Errors are chained and close the connection
Every reader exception SHALL have the original `sqlite3.Error` as its `__cause__`, and the finder SHALL hold no open connection after raising it.

#### Scenario: Fetch failure cleanup
- **WHEN** `CatalogFetchError` is raised
- **THEN** its `__cause__` is the `sqlite3.Error` and the finder's connection is closed

### Requirement: Verbose error diagnostics
When `verbose` is true, the reader SHALL print the exception repr and the failure message with the path to stderr before raising. The reader SHALL never print to stdout.

#### Scenario: Verbose diagnostics
- **WHEN** `verbose=True` and the catalog is missing
- **THEN** stderr contains `Invalid path, permission or lock` and stdout is empty
