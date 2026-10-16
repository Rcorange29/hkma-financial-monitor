## HKMA Financial Monitor — convenience targets
## The core pipeline (offline/quality/report/test) uses only the Python
## standard library; the dashboard requires `pip install -r requirements.txt`.

PYTHON ?= python3

.PHONY: help setup offline live quality report dashboard test clean

help:
	@echo "Targets:"
	@echo "  setup      create a venv and install dashboard dependencies"
	@echo "  offline    run the pipeline from bundled raw JSON (no internet)"
	@echo "  live       run the pipeline against the live HKMA API (internet)"
	@echo "  quality    run data-quality checks"
	@echo "  report     build the static HTML report"
	@echo "  dashboard  launch the Streamlit dashboard"
	@echo "  test       run the unittest suite"
	@echo "  clean      remove generated artifacts and caches"

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -r requirements.txt
	cp -n config.example.json config.json || true

offline:
	$(PYTHON) scripts/run_pipeline.py --offline

live:
	$(PYTHON) scripts/run_pipeline.py

quality:
	$(PYTHON) scripts/run_quality.py

report:
	$(PYTHON) scripts/build_html_report.py

dashboard:
	streamlit run app/streamlit_app.py

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	rm -rf .venv **/__pycache__ __pycache__
	find . -name '*.pyc' -delete
	rm -f data/processed/hkma.db data/processed/quality_report.json docs/report.html
