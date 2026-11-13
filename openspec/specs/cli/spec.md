# cli Specification

## Purpose
Provide the `lr-reader` command, which prints the files referenced by a Lightroom Classic catalog, one per line, for use in shell pipelines.

## Requirements

### Requirement: Command invocation
The `lr-reader` console script (`lr_reader:main`) SHALL take one positional `path` to a catalog and the optional flags `--full`, `-v`/`--verbose` and `-V`/`--version`. `main(argv=None)` SHALL accept an argument list, defaulting to `sys.argv[1:]`, and return the process exit code.

#### Scenario: Successful run
- **WHEN** `lr-reader` runs on a readable catalog
- **THEN** it exits with code 0

#### Scenario: Missing path argument
- **WHEN** `lr-reader` runs with no arguments
- **THEN** argparse prints usage to stderr and the process exits with code 2

### Requirement: Partial output by default
Without `--full`, the command SHALL print one line per file record, in catalog order, formatted as `<root_name>/<folder_path_from_root><file_original_name>`.

#### Scenario: Default output
- **WHEN** `lr-reader` runs on a catalog with four joined files
- **THEN** stdout holds exactly four lines, e.g. `2019/2019-12-29/20191229-IMG_9.png`, in record order

### Requirement: Full output
With `--full`, the command SHALL print one line per file record, each the Python `repr` of the record dict.

#### Scenario: Full output
- **WHEN** `lr-reader --full` runs on the catalog
- **THEN** stdout holds one line per record and the first starts with `{'root_name': '2019'`

### Requirement: Verbose diagnostics go to stderr
With `-v`/`--verbose`, the command SHALL print its parsed `path`, `full` and `verbose` values to stderr and enable the reader's verbose error reporting. Stdout SHALL contain only the record lines.

#### Scenario: Verbose run
- **WHEN** `lr-reader -v` runs on the catalog
- **THEN** stdout equals the default output and stderr contains `path:`

### Requirement: Version flag
`-V`/`--version` SHALL print `lr-reader <version>` to stdout, where `<version>` is `lr_reader.__version__` (calendar `YY.MM.DD`), and exit with code 0.

#### Scenario: Printing the version
- **WHEN** `lr-reader --version` runs
- **THEN** stdout is `lr-reader 26.11.13` for release 26.11.13 and the exit code is 0

### Requirement: Errors propagate
Reader errors (`CatalogOpenError`, `CatalogSchemaError`, `CatalogFetchError`) SHALL NOT be caught by the command; they end the process with a traceback and a non-zero exit code.

#### Scenario: Missing catalog file
- **WHEN** `lr-reader` runs on a path that does not exist
- **THEN** `CatalogOpenError` propagates out of `main`
