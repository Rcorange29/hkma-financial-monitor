# Data Catalog — HKMA Financial Monitor

All data comes from the **Hong Kong Monetary Authority (HKMA) public open
data API**, base URL `https://api.hkma.gov.hk/public/market-data-and-statistics`.
No authentication or API key is required. Only the columns listed below are
requested (`fields=...`); the pipeline keeps a raw JSON cache of every page.

The bundled offline cache (`data/raw/`) is a small, recent window so the
project runs anywhere without a network. Running the pipeline **without**
`--offline` pages through the live API and can pull a much longer history.

## 1. Daily exchange rates and the Effective Exchange Rate Index

- **Endpoint**: `monthly-statistical-bulletin/er-ir/er-eeri-daily`
- **Documentation**: <https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily/>
- **Date field**: `end_of_day` (`YYYY-MM-DD`)
- **Frequency**: daily (business days)
- **Bundled cache coverage**: 2026-02-23 → 2026-09-30 (180 observations)

| Field | Meaning | Unit |
|---|---|---|
| `usd` | Hong Kong dollar per 1 US dollar (USD/HKD) | HKD per USD |
| `gbp` | HKD per 1 British pound (GBP/HKD) | HKD per GBP |
| `jpy` | HKD per 1 Japanese yen (JPY/HKD) | HKD per JPY |
| `cny` | HKD per 1 renminbi (CNY/HKD) | HKD per CNY |
| `eur` | HKD per 1 euro (EUR/HKD) | HKD per EUR |
| `neeri_2020_trade_wgt` | Nominal Effective Exchange Rate Index, trade-weighted, January 2020 = 100 | index |

Other columns published by the feed (SDR rates, import/export-weighted EERI
series, earlier base years) are not requested; they can be added by extending
the `fields` list and `metrics` registry in `src/hkma_monitor/datasets.py`.

## 2. Daily figures of interbank liquidity

- **Endpoint**: `daily-monetary-statistics/daily-figures-interbank-liquidity`
- **Documentation**: <https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/daily-monetary-statistics/daily-figures-interbank-liquidity/>
- **Date field**: `end_of_date` (`YYYY-MM-DD`)
- **Frequency**: daily (business days; the documentation states the series begins 2002-01-02)
- **Bundled cache coverage**: 2026-01-23 → 2026-10-16 (180 observations)

| Field | Meaning | Unit |
|---|---|---|
| `cu_strongside` | Strong-side Convertibility Undertaking (HKMA *bid* for USD) | USD/HKD |
| `cu_weakside` | Weak-side Convertibility Undertaking (HKMA *offer* of USD) | USD/HKD |
| `disc_win_base_rate` | Discount Window Base Rate | % per annum |
| `hibor_overnight` | Overnight Hong Kong Interbank Offered Rate (HIBOR) | % per annum |
| `hibor_fixing_1m` | 1-month HIBOR fixing published by the Treasury Markets Association | % per annum |
| `twi` | Hong Kong dollar Trade Weighted Index | index |
| `closing_balance` | Closing Aggregate Balance (sum of balances in banks' clearing accounts) | HK$ million |

Under the Linked Exchange Rate system the Convertibility Undertaking rates are
7.75 (strong side) and 7.85 (weak side). Some other raw columns in this feed
are sign-prefixed strings (e.g. `"+0"`, `"-40"`); the loader parses that
format, but those particular columns are not used here.

## 3. Monthly monetary statistics

- **Endpoint**: `monthly-statistical-bulletin/financial/monetary-statistics`
- **Documentation**: <https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/financial/monetary-statistics/>
- **Date field**: `end_of_month`
- **Frequency**: mixed — see the note below
- **Bundled cache coverage**: 15 monthly rows for 2025-07 → 2026-09, plus 5 annual year-end rows for 2021 → 2025 (20 records in total)

### Important frequency detail

This feed returns recent **monthly** rows (`YYYY-MM`, e.g. `2026-09`) together
with **annual, year-end** rows spelled `YYYY-00` (month part `00`, e.g.
`2025-00`). The annual rows are each year's December/year-end values. The
loader keeps both, dates annual rows at `YYYY-12-01`, labels them
`freq = "annual"`, and includes `freq` in the database primary key so an
annual row and a monthly row can share a date without colliding. **Analyses
must filter on `freq`** so annual and monthly points are never mixed.

| Field | Meaning | Unit |
|---|---|---|
| `notes_coins_circulation` | Notes and coins in circulation | HK$ million |
| `aggr_balance` | Aggregate Balance | HK$ million |
| `ef_bills_notes` | Exchange Fund Bills and Notes outstanding | HK$ million |
| `monetary_base_total` | Monetary Base total | HK$ million |
| `m1_total` / `m2_total` / `m3_total` | Money supply M1 / M2 / M3 (total) | HK$ million |
| `m2_hkd` / `m3_hkd` | HKD component of M2 / M3 | HK$ million |
| `exrate_hkd_usd` | USD/HKD (monthly figure) | HKD per USD |
| `nominal_eff_exrate_index` | Nominal Effective Exchange Rate Index | index |
| `hibor_fixing_overnight` | HIBOR fixing, overnight | % per annum |
| `hibor_fixing_3m` | HIBOR fixing, 3-month | % per annum |
| `deposit_rate_saving` | Savings deposit rate | % per annum |
| `deposit_rate_3m` | 3-month time deposit rate | % per annum |
| `yield_efpaper_3m` | 3-month Exchange Fund paper yield | % per annum |
| `yield_govbond_10y` | 10-year Hong Kong Government Bond yield | % per annum |
| `best_lending_rate` | Best lending rate | % per annum |
| `discount_window_base_rate` | Discount Window Base Rate (monthly figure) | % per annum |

**Publication lag.** In the latest monthly row (`2026-09`) the M1/M2/M3
columns are `null` because they have not yet been published. The loader keeps
these as missing cells and the quality layer accounts for them; they are
expected to be back-filled by HKMA.

**Pagination cap (verified).** This summary endpoint returns exactly 20 rows:
requesting `offset=20` returns `err_code 1001 / "No result found"`. It is a
*summary* feed (recent months + annual year-end), not a full monthly archive.
The long, fully paginated monthly money-supply series are published by HKMA as
separate tables in the bulletin's **Money** category
(<https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/money/>),
for example:

- 2.2.1 Money supply – Adjusted for foreign currency swap deposits
- 2.2.2 Money supply – Unadjusted for foreign currency swap deposits

The same figures are also downloadable as Excel tables (T020201/T020202) from
the bulletin table page. To integrate one, open its doc page, copy the API URL,
and add an entry to `DATASETS` in `src/hkma_monitor/datasets.py` with the
correct `date_field`, `fields` and `metrics`; the loader, storage and quality
checks require no other changes. (These detailed Money endpoints were not
wired in here because their exact API slug could not be verified from the
offline build environment — only a verified endpoint should be added.)

By contrast, the two **daily** feeds have no such cap: they page back to
2002-01-02 (about 6,300 rows per feed), and a live run downloads the full
history automatically.

## Data-quality thresholds and their rationale

Findings are **flags for review, never automatic deletions**. Deleting a real
market movement would destroy information.

1. **Hard physical plausibility bounds** (`hard_min` / `hard_max` in
   `datasets.py`). Chosen to be well outside any plausible value, using the
   Linked Exchange Rate design and observed magnitudes:
   - USD/HKD (and CU band): 7.60–7.95, leaving a margin beyond the 7.75–7.85
     Convertibility Undertaking. Monthly averages can sit just outside 7.85
     (e.g. 7.852 in 2025-07), which is why the bound is wider than the band.
   - Interest rates: 0–30 % p.a. Hong Kong HIBOR and policy rates have been
     non-negative in this period and never near 30 %; the bound only catches
     corrupt or misplaced data.
   - Index series (EERI, TWI): 50–200, around the 100 reference level.
   - Monetary stocks: non-negative, with generous upper bounds well above the
     observed levels (e.g. total M2 ≈ HK$22 trillion, cap 30 trillion).
2. **Robust MAD outliers.** The Median Absolute Deviation is insensitive to a
   few extreme days. A value is flagged when the modified z-score
   `0.6745 * |x - median| / MAD` exceeds **6**, and only for series with at
   least 8 points. This intentionally flags only extreme departures.
3. **Rate level shifts.** Same-day moves of at least **1.0 percentage point**
   in a daily interest rate, across a gap of at most a week, are flagged for
   review.
4. **Schedule gaps.** For daily feeds the expected grid is Monday–Friday;
   missing weekdays are flagged, but these include Hong Kong public holidays
   and storm-related closures (the bundled cache's gaps at 2026-04-03,
   2026-05-01, 2026-07-01 coincide with public holidays). Monthly feeds use a
   first-of-month grid. Gaps are cross-checked against the calendar before
   being treated as errors.

## Known limitations

- The bundled daily windows cover only ~8–9 months of 2026; long-horizon
  context comes from just five annual year-end points (2021–2025).
- The data describe what happened, not why. Associations between rates,
  exchange rates and money supply are not causal claims.
- Only the selected columns are loaded; the source feeds publish more.
- Figures are as published by HKMA and can be revised after first release.
