# Repository assessment and MVP stages

## Before implementation

Inspected all nine original Python files, README and requirements, all data files
and folder layouts, raw CSV contents, and both virtual-environment configs.
`notebooks/` was empty; no AGENTS.md was found. This folder was not a Git repository.
Both virtual environments used Python 3.14.3 and provided pandas, requests, and
openpyxl. Streamlit and pytest were absent.

The project used executable scripts with top-level work. `config.py` supplied a
single country, period, indicator mapping and relative storage folders. Extraction
created country/period raw folders; merging built annual grids; validation wrote
quality reports; the terminal interface read processed files and exported Excel.
`run_pipeline.py` ran only merge and validation stages.

Problems identified: filename-only caches, discarded API metadata, no robust
pagination in extraction, minimal malformed-response checks, import-time side
effects, and an undefined `dataset` variable after invalid terminal inputs. The
Nigeria inflation file in the 1990_2025 directory actually spans 1960–2025. FDI was
configured but its raw file was absent. Thirteen existing dataset files were hashed
before edits; no merge, migration or legacy extraction was run.

## Implementation plan and completed stages

1. Add a standalone reusable service rather than changing working legacy scripts.
   Use World Bank source 2, dynamic catalogues, per-country/code/period identity,
   validated JSON caches, bounded HTTP calls, and explicit missing/failure states.
   Verification: backend regression tests without real network requests.
2. Add a Streamlit app with beginner guidance, search, country comparison, annual
   charts, missing reports, original metadata, sources, and in-memory downloads.
   Keep archives separate and read-only. Verification: Streamlit AppTest flows,
   local browser review, and an opt-in live World Bank smoke check.
3. Document Windows startup and free hosting, pin verified runtime dependencies,
   retain original docs, and verify original dataset checksums. Prepare deployment
   without publishing. Verification: full tests, pip dependency check, checksums.

The runtime requirements omit Jupyter to reduce deployment dependencies; notebooks
remain supported through `requirements-dev.txt`. Only Streamlit and its required
dependencies were installed into `.venv`. No database, authentication, paid API,
or new hosting account was introduced.

## Deliberate MVP limits

Annual WDI observations only; five countries and ten indicators per request.
First catalogue load requires internet unless a validated cache already exists.
Requests are sequential with a five-second connect and 25-second read timeout;
many unavailable series can take time to finish. No scheduler or retry loop is
added. Shared disk caches are disposable and atomic, not a database.
Original CLI issues are documented and unchanged because the new app uses its own
validated backend. Public accessibility remains pending deployment approval.

## Verification results — 9 October 2026

- Stage 1: 14 backend tests passed.
- Stage 2: five Streamlit AppTest flows passed (19 total at that stage).
- Final suite: 24 tests passed, including country comparison, lowercase original
  indicator codes, empty selections, source mismatches, zero-page empty responses,
  read-only cache storage, and expired catalogue fallback.
- Live API check: 217 countries/economies and 1,498 WDI indicators loaded; Nigeria
  GDP growth for 2020–2022 retrieved. API reported last update 2026-10-08.
- Browser review: catalogues reused validated caches; data table, original codes,
  GDP chart, and CSV/Excel download controls rendered successfully. The chart's
  displayed values matched the fetched observations. A preview is saved as
  `docs/mvp-preview.jpg`.
- `pip check`: no broken requirements. Checksum verification: all 13 original
  dataset files unchanged. Legacy Python scripts and config were not edited.

The sandbox stalled Windows temporary-file creation and blocked network access.
Installation, tests, the live smoke check, and the localhost server were completed
with approved execution access. Stalled test/server processes were cleaned up;
the working localhost server remains available. No public repository or deployment
was created.
