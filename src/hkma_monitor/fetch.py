"""
Data acquisition layer (standard library only).

Responsibilities
----------------
* Call the HKMA API with ``urllib`` (no third-party dependency).
* Retry transient network/HTTP errors with exponential backoff.
* Page through every result with ``offset`` / ``pagesize``.
* Save each raw page as JSON under ``data/raw`` so a run is auditable and
  the whole pipeline can be replayed offline (``--offline``).
* Validate the API envelope and fail loudly if the response shape changes.

The raw cache is the *only* thing this module writes.  Cleaning and database
loading happen in :mod:`hkma_monitor.transform` and :mod:`hkma_monitor.db`.
"""
from __future__ import annotations

import glob
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import raw_dir
from .datasets import DATASETS

log = logging.getLogger(__name__)


class FetchError(RuntimeError):
    """Raised when the API cannot be reached or returns an unexpected shape."""


# ---------------------------------------------------------------------------
# Low-level HTTP
# ---------------------------------------------------------------------------
def _build_url(cfg: dict, dataset_key: str, offset: int) -> str:
    spec = DATASETS[dataset_key]
    params = {
        "pagesize": cfg["page_size"],
        "offset": offset,
        "fields": ",".join(spec["fields"]),
    }
    return (
        cfg["base_url"].rstrip("/")
        + "/" + spec["endpoint"].lstrip("/")
        + "?" + urllib.parse.urlencode(params)
    )


def _http_get_json(url: str, cfg: dict) -> dict:
    """GET one URL and parse JSON, with retries and backoff."""
    last_error: Exception | None = None
    for attempt in range(1, cfg["max_retries"] + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": cfg["user_agent"], "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=cfg["request_timeout_seconds"]) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                payload = resp.read().decode(charset)
            return json.loads(payload)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            last_error = exc
            # 4xx errors (other than 429) will not fix themselves: stop early.
            status = getattr(exc, "code", None)
            if isinstance(status, int) and 400 <= status < 500 and status != 429:
                raise FetchError(f"HTTP {status} for {url}") from exc
            wait = cfg["retry_backoff_seconds"] * (2 ** (attempt - 1))
            log.warning("attempt %d/%d failed for %s (%s); retrying in %ss",
                        attempt, cfg["max_retries"], url, exc, wait)
            time.sleep(wait)
        except json.JSONDecodeError as exc:
            raise FetchError(f"Response was not valid JSON for {url}") from exc
    raise FetchError(f"Failed after {cfg['max_retries']} attempts: {url} ({last_error})")


def _validate_envelope(page: dict, url: str) -> list:
    """Return records from a page or raise if the API shape is unexpected."""
    if not isinstance(page, dict) or "header" not in page or "result" not in page:
        raise FetchError(f"Unexpected envelope (missing header/result): {url}")
    header = page["header"]
    if not header.get("success"):
        raise FetchError(
            f"API reported failure: {header.get('err_code')} {header.get('err_msg')} ({url})"
        )
    result = page.get("result")
    if result is None:
        # A successful call with zero rows returns result=None in this API.
        return []
    records = result.get("records")
    if not isinstance(records, list):
        raise FetchError(f"result.records is not a list: {url}")
    return records


# ---------------------------------------------------------------------------
# Raw cache helpers
# ---------------------------------------------------------------------------
def _cache_path(raw: Path, dataset_key: str, offset: int) -> Path:
    return raw / f"{dataset_key}__offset-{offset}.json"


def _write_cache(raw: Path, dataset_key: str, offset: int, page: dict) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    path = _cache_path(raw, dataset_key, offset)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(page, fh, ensure_ascii=False)


def _read_cache(raw: Path, dataset_key: str) -> list[dict]:
    """Read and validate every cached page for one dataset (offline mode)."""
    paths = sorted(glob.glob(str(raw / f"{dataset_key}__offset-*.json")))
    if not paths:
        raise FetchError(f"No cached pages found in {raw} for {dataset_key}")
    records: list[dict] = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as fh:
            page = json.load(fh)
        records.extend(_validate_envelope(page, p))
    return records


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def fetch_dataset(cfg: dict, dataset_key: str, *, offline: bool = False) -> list[dict]:
    """Fetch all rows for one dataset.

    offline=True  -> read previously cached JSON pages (no network).
    offline=False -> page through the live API and overwrite the cache.
    """
    if dataset_key not in DATASETS:
        raise KeyError(f"Unknown dataset: {dataset_key}")
    raw = raw_dir(cfg)

    if offline:
        log.info("[%s] OFFLINE: loading cached pages from %s", dataset_key, raw)
        return _read_cache(raw, dataset_key)

    all_records: list[dict] = []
    page_size = cfg["page_size"]
    offset = 0
    while True:
        url = _build_url(cfg, dataset_key, offset)
        log.info("[%s] GET offset=%d", dataset_key, offset)
        page = _http_get_json(url, cfg)
        records = _validate_envelope(page, url)
        _write_cache(raw, dataset_key, offset, page)
        all_records.extend(records)
        if len(records) < page_size:
            break  # last page
        offset += page_size
    log.info("[%s] fetched %d rows (live)", dataset_key, len(all_records))
    return all_records


def fetch_all(cfg: dict, *, offline: bool = False) -> dict[str, list[dict]]:
    return {key: fetch_dataset(cfg, key, offline=offline) for key in cfg["datasets"]}
