---
name: Bug report
about: Report a problem with fetching, cleaning, storage, quality checks, or the dashboard
title: "[Bug] "
labels: bug
assignees: ''
---

## What happened
A clear description of what went wrong.

## Steps to reproduce
1. Command you ran (e.g. `python3 scripts/run_pipeline.py --offline`):
2.
3.

## Expected behavior
What you expected to happen.

## Actual behavior / error
Paste the full traceback or the JSON `header.err_msg` from the HKMA response.

## Environment
- OS:
- Python version (`python3 --version`):
- Live or offline (`--offline`):
- Dataset(s) involved (`fx_daily`, `interbank_daily`, `monetary_monthly`):

## Additional context
If an API response changed, paste the raw JSON page from `data/raw/` (or the
relevant part) — the pipeline is sensitive to API schema changes.
