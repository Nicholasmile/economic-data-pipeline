
# Economic Research Data Platform

🚀 **Live Application:** [Launch Economic Research Data Platform](https://economic-data-pipeline-rnyti7ab459xa8h3zbd9sc.streamlit.app/)

A browser-based research workspace for students, researchers, economists, and data
analysts. Select countries, years, and World Bank economic indicators; inspect
observations and missing values; download CSV or a documented Excel workbook.
No API key, paid service, application account, or database is required.

## Quick start on Windows

Open PowerShell in the project folder:

```powershell
cd D:\Data_Science_Projects\economic_data_pipeline
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open **http://localhost:8501**. Using the virtual environment's Python explicitly
avoids activation policy issues. Verified with the existing `.venv`, Python 3.14.3.
`.venv-1` is untouched; install requirements there if you choose that environment.

1. Click **Load World Bank catalogues**. First load needs internet; subsequent
   loads reuse validated caches.
2. Choose a research preset (growth/inflation, employment, or trade/investment),
   or search by name, code, or definition. Customize up to ten indicators.
3. Select up to five countries and a year range from 1960 to the current year.
   Period shortcuts include the last ten completed calendar years and since 2000.
4. Click **Build research dataset**. Follow retrieval progress and explore Data
   table, Charts, Coverage, Indicator guide, and Sources.
5. Download CSV or Excel, plus a suggested citation and a JSON record of your
   research settings and source dates.

GDP growth and inflation are selected by default when available. Each chart has
its own scale. The original Nigeria archive is also available in the offline
viewer, clearly labelled as an archive without verified API provenance.

## Features and scope

- Dynamic country and World Development Indicators catalogues, with search.
- Multiple-country comparisons and original indicator codes in output columns.
- Original definitions, units where supplied, providers, and dataset IDs.
- Complete annual grids, blank missing observations, and missing-value reports.
- Presets, period shortcuts, and readable table headings with a code toggle.
- Coverage percentages and first/last observed years for each series.
- Charts with indicator choice, country highlighting, zoom and PNG toolbar export.
- Charts preserve missing-year gaps, with separate scales per indicator.
- Input validation, HTTP timeouts, pagination, and visible partial failures.
- Retrieval status, retrieval timestamp, API update date, and source URLs.
- In-memory CSV/Excel downloads; no overwrite of processed datasets.
- Retry only failed series while retaining successful observations and provenance.
- Downloadable suggested citations and exact research settings.

The MVP supports **annual World Development Indicators (World Bank source 2)**.
Regional/income aggregates and other World Bank datasets are excluded. An empty
series is retained as missing values; a failed retrieval is explicitly labelled.
Missing economic observations are never filled, interpolated, or replaced by zero.

## Architecture

```text
app.py                         Streamlit interface and session state
src/platform_service.py        API client, cache, tables, quality, exports
src/research_experience.py     Presets, readable coverage, charts, citation/settings
config.py                      Existing CLI settings; frontend starting defaults
.streamlit/config.toml         Theme and headless server defaults
tests/test_backend.py          Deterministic backend regression tests
tests/test_app.py              Streamlit user-flow tests
scripts/smoke_world_bank.py    Optional live API check
data/platform_cache/           Disposable JSON caches (ignored by Git)
data/raw/ and data/processed/  Original datasets, preserved
docs/ASSESSMENT.md             Inspection findings and staged implementation
docs/DEPLOYMENT.md             Free hosting and publication instructions
```

The reusable backend has no Streamlit dependency and no work occurs on import.
The browser app does not execute original standalone scripts. `config.py` provides
starting defaults without changing when researchers choose a different request.

The builder and results run in separate Streamlit fragments. Searching and changing
selections does not regenerate result charts or exports; result controls update
their own section. Only the chosen result view is rendered. Excel is generated
once per dataset and reused, and download buttons do not trigger an app rerun.

## Cache policy and provenance

API responses are cached for **24 hours**. Identities include API URL, source ID,
country, indicator, start year and end year as appropriate. Records have a schema
version, timestamp, checksum and validated contents. Observations are checked for
country and indicator identity, year range, unique years, finite numeric values
and matching metadata. Invalid files are ignored. Successful responses replace
only their corresponding platform cache file atomically.

**Refresh observations** bypasses fresh caches. If the API fails, an expired but
valid matching cache may be used and labelled **stale cache — API unavailable**,
retaining the original retrieval timestamp. Failed requests are not cached as empty
results. Cached series retain the metadata recorded with those observations.
Checksums detect accidental corruption; they are not authenticity signatures.

Existing raw CSVs have no reliable API retrieval metadata; an inflation file also
contains years outside its folder's stated period. Legacy files remain unchanged
and are never automatically reused as verified API caches. The offline viewer
shows them as an archive, without claiming current API validation.

Cache writes are best effort; retrieval can work when cache storage is unavailable.
On free hosting, files may disappear after restarts. Caches are an optimization,
not durable research storage. Retain downloaded workbooks for reproducibility.

## Tests and manual verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\verify_original_data.py
```

Tests use mocked responses and isolated temporary caches, requiring no network and
never modifying original datasets. Coverage includes validation, pagination, cache
isolation/corruption, invalid observations, timeouts, stale fallback, partial
failures, missing values, exports, and browser flows.

The UX release also tests presets, period shortcuts, progress accounting, coverage
years, retry isolation, chart gaps, citation/settings accuracy, export reuse, and
upgrading an existing browser session. The current suite contains 34 tests.

After changing backend code, restart Streamlit with Ctrl+C followed by the launch
command above, so the server loads the new Python modules.

Optional live check (catalogues and one Nigeria GDP series, reusing cache):

```powershell
.\.venv\Scripts\python.exe scripts\smoke_world_bank.py
```

For a manual check, build Nigeria and Ghana GDP growth for 2000–2020; inspect
country-specific rows and URLs, then download both formats. Build again and check
Sources for cache reuse. Change the years: the previous result remains labelled
until you rebuild. Try reversed years to see a friendly error without an API call.
Use unemployment from 1960 to inspect missing coverage. Stop the server with
**Ctrl+C** in its terminal.

`dataset_hashes_before.json` records checksums of all 13 original dataset files.
The verification script checks them without altering any files.

## Original command-line tools

All original Python scripts and `config.py` remain unchanged:

```powershell
.\.venv\Scripts\python.exe src\multiple_indicators.py
.\.venv\Scripts\python.exe run_pipeline.py
.\.venv\Scripts\python.exe research_interface.py
```

These remain legacy tools: extraction trusts filenames, `run_pipeline.py` merges
and validates rather than extracting, and terminal invalid-input handling is not
robust. The browser provides the new validated workflow. Running legacy merge and
validation can overwrite processed outputs as before; these scripts were not run
during MVP implementation.

The original README and requirements are retained as `README.legacy.md` and
`requirements.legacy.txt`. Jupyter is optional via `requirements-dev.txt` and is
not required on the hosting server.

## Deployment

Prepared for **Streamlit Community Cloud**. See [deployment instructions](docs/DEPLOYMENT.md)
for GitHub preparation, entry point, Python selection, dependencies and verification.
Public deployment and repository publication require the owner's approval.
Nothing was published during MVP implementation.

## Source and research use

Data comes from [World Bank Open Data](https://data.worldbank.org/) through its
[Indicators API](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures).
Definitions and provider attributions are retained. World Bank can revise historical
values; record retrieval dates and definitions in your research. Consult the
[dataset terms](https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets)
before redistribution and cite original providers as appropriate.
