# Research experience update — 9 October 2026

## Changes

- Three beginner presets, with editable selections and definitions before retrieval.
- Period shortcuts and an explicit country/indicator/year selection summary.
- Per-series progress for cached, successful, and failed requests.
- Friendly table labels; original indicator codes remain available via a toggle
  and are unchanged in all data exports.
- Coverage percentages plus first/last available observation years. Gaps remain
  missing, and retrieval failures remain distinct from unavailable API observations.
- Indicator selection, country highlighting, zoom/pan, and existing PNG chart
  toolbar export. Charts still do not join across missing-year gaps.
- Retry only failed country/indicator pairs, retaining successful data and sources.
- Suggested citation text and downloadable research-settings JSON, including
  exact original codes and recorded retrieval/source details. These are records
  for repeating a selection; settings import is not implemented in this release.
- Existing browser-session upgrade and a persistent read-only archive viewer.

## Performance decisions

The search and selection builder remains interactive within its own fragment.
A separate result fragment handles table/chart controls. Only the chosen result
view renders, rather than eagerly building every chart and tab on each interaction.
CSV is prepared once per research run; Excel is generated once and reused for the
same result. Download buttons do not trigger reruns. No new dependency was needed.

No quantitative speedup is claimed: tests verify avoided API calls and repeated
Excel work; real request latency still depends on World Bank and network conditions.
Requests remain sequential and bounded by the existing HTTP timeouts.

## Verification

- 34 automated tests passed, including all original cache/identity/missing-value
  regressions and new UX, progress, retry, export-reuse, and session-upgrade checks.
- All 13 original dataset files match the pre-implementation checksums.
- No original CLI script, configuration setting, dataset, package requirement,
  public deployment, or hosting configuration changed in this release.
- Browser review confirmed validated catalogue/observation cache reuse, readable
  GDP table headings, the chart selector and PNG toolbar, coverage metrics, and
  result navigation. Preview: `docs/ux-preview.jpg`. The server was restarted to
  load the updated backend and remains available locally on port 8501.

## Manual check

Restart the local server after backend changes and open http://localhost:8501.
Load catalogues, customize a preset, use a period shortcut, and build a small
dataset. Switch between readable names and codes; explore Charts and Coverage;
download data, citation and settings. Change selections and confirm the old result
remains labelled and available until rebuilding. If a series fails, retry it and
confirm successful series remain intact.
