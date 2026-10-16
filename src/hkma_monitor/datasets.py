"""
Dataset registry for the HKMA open data feeds used in this project.

Every entry documents:
  - endpoint    : path appended to the configured ``base_url``
  - source_url  : human-facing official documentation page (for citation)
  - date_field  : name of the date/period column in the API JSON
  - freq        : "daily" or "monthly"
  - date_format : how the API spells the date ("%Y-%m-%d" or "%Y-%m")
  - fields      : the columns we request with the API ``fields=`` parameter
  - metrics     : mapping of JSON field -> (human label, unit, category,
                  hard_min, hard_max)

Hard bounds (hard_min / hard_max) are *physical plausibility* limits, NOT
deletion rules.  They are explained in docs/DATA_CATALOG.md.  A value outside
them is flagged for review; it is never deleted automatically.
"""

# Each metric value: (label, unit, category, hard_min, hard_max)
# hard_min / hard_max = None means "no hard domain bound for this metric".

DATASETS = {
    # ------------------------------------------------------------------
    # 1) Daily exchange rates and the Effective Exchange Rate Index (EERI)
    # ------------------------------------------------------------------
    "fx_daily": {
        "endpoint": "monthly-statistical-bulletin/er-ir/er-eeri-daily",
        "source_url": "https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/er-ir/er-eeri-daily/",
        "title": "Daily exchange rates and Effective Exchange Rate Index (EERI)",
        "date_field": "end_of_day",
        "freq": "daily",
        "date_format": "%Y-%m-%d",
        "fields": [
            "end_of_day", "usd", "gbp", "jpy", "cny", "eur",
            "neeri_2020_trade_wgt",
        ],
        "metrics": {
            "usd": ("USD/HKD", "HKD per 1 USD", "exchange_rate", 7.60, 7.95),
            "gbp": ("GBP/HKD", "HKD per 1 GBP", "exchange_rate", 5.0, 20.0),
            "jpy": ("JPY/HKD", "HKD per 1 JPY", "exchange_rate", 0.03, 0.15),
            "cny": ("CNY/HKD", "HKD per 1 CNY", "exchange_rate", 0.8, 1.4),
            "eur": ("EUR/HKD", "HKD per 1 EUR", "exchange_rate", 6.0, 12.0),
            "neeri_2020_trade_wgt": ("NEERI trade-weighted (Jan 2020=100)", "index", "index", 50.0, 200.0),
        },
    },

    # ------------------------------------------------------------------
    # 2) Daily figures of interbank liquidity (rates, CU band, Aggregate
    #    Balance, Trade Weighted Index)
    # ------------------------------------------------------------------
    "interbank_daily": {
        "endpoint": "daily-monetary-statistics/daily-figures-interbank-liquidity",
        "source_url": "https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/daily-monetary-statistics/daily-figures-interbank-liquidity/",
        "title": "Daily figures of interbank liquidity",
        "date_field": "end_of_date",
        "freq": "daily",
        "date_format": "%Y-%m-%d",
        "fields": [
            "end_of_date", "cu_strongside", "cu_weakside",
            "disc_win_base_rate", "hibor_overnight", "hibor_fixing_1m",
            "twi", "closing_balance",
        ],
        "metrics": {
            "cu_strongside": ("Convertibility Undertaking strong-side (Bid)", "USD/HKD", "exchange_rate", 7.60, 7.95),
            "cu_weakside": ("Convertibility Undertaking weak-side (Offer)", "USD/HKD", "exchange_rate", 7.60, 7.95),
            "disc_win_base_rate": ("Discount Window Base Rate", "% per annum", "interest_rate", 0.0, 30.0),
            "hibor_overnight": ("Overnight HIBOR", "% per annum", "interest_rate", 0.0, 30.0),
            "hibor_fixing_1m": ("HKAB 1-month HIBOR fixing", "% per annum", "interest_rate", 0.0, 30.0),
            "twi": ("Trade Weighted Index (TWI)", "index", "index", 50.0, 200.0),
            "closing_balance": ("Closing Aggregate Balance", "HK$ million", "monetary_stock", 0.0, 1000000.0),
        },
    },

    # ------------------------------------------------------------------
    # 3) Monthly monetary statistics (monetary base, M1/M2/M3, monthly
    #    average rates)
    # ------------------------------------------------------------------
    "monetary_monthly": {
        "endpoint": "monthly-statistical-bulletin/financial/monetary-statistics",
        "source_url": "https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/monthly-statistical-bulletin/financial/monetary-statistics/",
        "title": "Monthly monetary statistics",
        "date_field": "end_of_month",
        "freq": "monthly",
        "date_format": "%Y-%m",
        "fields": [
            "end_of_month",
            "notes_coins_circulation", "aggr_balance", "ef_bills_notes",
            "monetary_base_total",
            "m1_total", "m2_total", "m2_hkd", "m3_total", "m3_hkd",
            "exrate_hkd_usd", "nominal_eff_exrate_index",
            "hibor_fixing_overnight", "hibor_fixing_3m",
            "deposit_rate_saving", "deposit_rate_3m",
            "yield_efpaper_3m", "yield_govbond_10y",
            "best_lending_rate", "discount_window_base_rate",
        ],
        "metrics": {
            "notes_coins_circulation": ("Notes & coins in circulation", "HK$ million", "monetary_stock", 0.0, 1000000.0),
            "aggr_balance": ("Aggregate Balance", "HK$ million", "monetary_stock", 0.0, 1000000.0),
            "ef_bills_notes": ("Exchange Fund Bills & Notes outstanding", "HK$ million", "monetary_stock", 0.0, 3000000.0),
            "monetary_base_total": ("Monetary Base total", "HK$ million", "monetary_stock", 0.0, 5000000.0),
            "m1_total": ("Money supply M1 total", "HK$ million", "monetary_stock", 0.0, 8000000.0),
            "m2_total": ("Money supply M2 total", "HK$ million", "monetary_stock", 0.0, 30000000.0),
            "m2_hkd": ("Money supply M2 HKD", "HK$ million", "monetary_stock", 0.0, 15000000.0),
            "m3_total": ("Money supply M3 total", "HK$ million", "monetary_stock", 0.0, 30000000.0),
            "m3_hkd": ("Money supply M3 HKD", "HK$ million", "monetary_stock", 0.0, 15000000.0),
            "exrate_hkd_usd": ("USD/HKD (monthly)", "HKD per 1 USD", "exchange_rate", 7.60, 7.95),
            "nominal_eff_exrate_index": ("Nominal Effective Exchange Rate Index", "index", "index", 50.0, 200.0),
            "hibor_fixing_overnight": ("HIBOR fixing overnight", "% per annum", "interest_rate", 0.0, 30.0),
            "hibor_fixing_3m": ("HIBOR fixing 3-month", "% per annum", "interest_rate", 0.0, 30.0),
            "deposit_rate_saving": ("Savings deposit rate", "% per annum", "interest_rate", 0.0, 30.0),
            "deposit_rate_3m": ("3-month time deposit rate", "% per annum", "interest_rate", 0.0, 30.0),
            "yield_efpaper_3m": ("3-month Exchange Fund paper yield", "% per annum", "interest_rate", 0.0, 30.0),
            "yield_govbond_10y": ("10-year Government Bond yield", "% per annum", "interest_rate", 0.0, 30.0),
            "best_lending_rate": ("Best lending rate (HSBC)", "% per annum", "interest_rate", 0.0, 30.0),
            "discount_window_base_rate": ("Discount Window Base Rate (monthly)", "% per annum", "interest_rate", 0.0, 30.0),
        },
    },
}
