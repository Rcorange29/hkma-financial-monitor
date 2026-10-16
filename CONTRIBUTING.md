# Contributing / Development Guide

This is a small, dependency-light project: the data pipeline uses only the
Python standard library; `streamlit` and `pandas` are required only for the
optional interactive dashboard.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # only needed for the Streamlit dashboard
cp config.example.json config.json   # the pipeline works with the defaults
```

## Common commands

```bash
# Reproduce the pipeline from the bundled raw JSON (no internet needed):
python3 scripts/run_pipeline.py --offline

# Run the full pipeline against the live HKMA API (internet required):
python3 scripts/run_pipeline.py

# Data-quality checks and the static HTML report:
python3 scripts/run_quality.py
python3 scripts/build_html_report.py

# Interactive dashboard:
streamlit run app/streamlit_app.py

# Tests:
python3 -m unittest discover -s tests -v
```

## Project layout

```
src/hkma_monitor/   fetch -> transform -> db (tidy SQLite), plus quality
scripts/            thin command-line entry points
app/                Streamlit dashboard
sql/                hand-written analytical SQL
tests/              unittest suite (standard library only)
data/raw/           raw JSON pages as received from the API (audit trail)
data/processed/     generated SQLite database and quality report (gitignored)
docs/               data catalog, one-page summary, screenshots, Chinese guide
```

## How to add a new HKMA dataset

1. Verify the endpoint on the
   [HKMA API docs](https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/)
   and confirm it returns `header.success = true` with `result.records`.
2. Add an entry to `DATASETS` in `src/hkma_monitor/datasets.py`
   (`endpoint`, `date_field`, `freq`, `date_format`, `fields`, `metrics`).
   Set physical-plausibility hard bounds and explain them in
   `docs/DATA_CATALOG.md`.
3. Add the dataset key to `datasets` in `config.json`.
4. Run the pipeline and the tests; run the quality checks and confirm the new
   series behaves as expected (gaps, bounds, outliers).
5. Document the metric definitions, units, frequency, date range and
   limitations in `docs/DATA_CATALOG.md`.

An in-progress example for the long, paginated monthly money-supply table
(2.2.2) is included at the bottom of `datasets.py`; it is disabled until its
exact API slug is verified against the docs.

## Conventions

- Keep the core pipeline standard-library-only.
- Never hard-code secrets; `config.json` is gitignored.
- Quality checks **flag, never delete**; do not silently drop observations.
- Keep data provenance: cache every raw JSON page under `data/raw/`.
- Write clear commit messages (imperative mood) and keep commits focused.

## Notes for portfolio maintainers

- The `monetary-statistics` summary feed is capped at 20 rows; see
  `docs/DATA_CATALOG.md` for the long-history Money tables.
- The dashboard and live pull require network access; the offline pipeline and
  static HTML report are the fully reproducible fallback.
- This project is an educational data-engineering work, not investment advice.
