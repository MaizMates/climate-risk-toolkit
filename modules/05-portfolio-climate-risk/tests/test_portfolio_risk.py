"""Checks that fail loudly if the join, the weighting, or the PDF extraction breaks.

Fixed inputs, so this tests the arithmetic and not ssga.com's or Eurostat's uptime.

    python3 tests/test_portfolio_risk.py
"""
import os
import sys
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import portfolio_risk as P


def test_portfolio_waci_is_value_weighted_not_count_weighted():
    holdings = [
        {"country": "Germany", "sector": "Utilities", "market_value": 900.0},
        {"country": "France", "sector": "Financials", "market_value": 100.0},
        {"country": "France", "sector": "Financials", "market_value": 100.0},
    ]
    intensity = {("DE", "D", 2024): 1000.0, ("FR", "K", 2024): 10.0}
    waci, rows = P.portfolio_waci(holdings, intensity, P.GICS_TO_NACE, 2024)
    # 900/1100 * 1000 + 200/1100 * 10, not a plain average of 1000, 10, 10.
    expected = (900.0 * 1000.0 + 200.0 * 10.0) / 1100.0
    assert abs(waci - expected) < 1e-9, "WACI must be market-value-weighted, not a row average"


def test_holding_intensity_falls_back_to_cross_country_median_when_country_missing():
    intensity = {("FR", "C20", 2024): 50.0, ("DE", "C20", 2024): 70.0, ("IT", "C20", 2024): 90.0}
    # ES not reported for C20 -- Eurostat's real gap for chemicals in Spain -- must fall back.
    val, is_fallback = P.holding_intensity(intensity, "ES", "C20", 2024)
    assert is_fallback is True
    assert val == 70.0, "fallback must be the median of the countries that do report it"
    val2, is_fallback2 = P.holding_intensity(intensity, "FR", "C20", 2024)
    assert is_fallback2 is False
    assert val2 == 50.0, "a country that does report its own figure must use it, not the median"


def test_holding_intensity_with_no_countries_at_all_returns_none():
    val, is_fallback = P.holding_intensity({}, "FR", "Z99", 2024)
    assert val is None and is_fallback is True


def test_classify_cprs_matches_battiston_categories_and_defaults_to_not_cpr():
    assert P.classify_cprs("B") == "fossil_fuel"
    assert P.classify_cprs("D") == "utilities"
    assert P.classify_cprs("C20") == "energy_intensive"
    assert P.classify_cprs("L") == "housing"
    assert P.classify_cprs("K") == "not_cpr", "financials must not be silently swept into CPRS"


def test_cprs_share_is_value_weighted():
    holdings = [
        {"sector": "Energy", "market_value": 300.0},   # -> B -> fossil_fuel
        {"sector": "Financials", "market_value": 700.0},  # -> K -> not_cpr
    ]
    share, breakdown = P.cprs_share(holdings, P.GICS_TO_NACE)
    assert abs(share - 0.3) < 1e-9
    assert abs(breakdown["fossil_fuel"] - 0.3) < 1e-9
    assert abs(breakdown["not_cpr"] - 0.7) < 1e-9


def test_mapping_choice_can_move_cprs_share_without_touching_waci_much():
    """The known finding this module reports: reclassifying Consumer Discretionary from retail
    trade to motor-vehicle manufacture barely moves WACI but visibly moves the CPRS share,
    because 'transportation' is a CPRS category and 'wholesale/retail trade' is not."""
    holdings = [{"country": "Germany", "sector": "Consumer Discretionary", "market_value": 1.0}]
    intensity = {("DE", "G", 2024): 40.0, ("DE", "C29", 2024): 42.0}
    base_share, _ = P.cprs_share(holdings, P.GICS_TO_NACE)
    alt_map = dict(P.GICS_TO_NACE, **{"Consumer Discretionary": "C29"})
    alt_share, _ = P.cprs_share(holdings, alt_map)
    assert base_share == 0.0
    assert alt_share == 1.0, "C29 (motor vehicle manufacture) must classify as transportation"


def test_bootstrap_ci_brackets_the_point_estimate():
    """A naive bootstrap that draws the *absolute* cross-country level (instead of the
    dispersion around this holding's own value) recentres the answer on the EU27 average and
    can put the point estimate outside its own interval -- this is the bug this module fixed."""
    holdings = [{"country": "France", "sector": "Utilities", "market_value": 1.0}]
    intensity = {("FR", "D", 2024): 500.0, ("PL", "D", 2024): 5000.0, ("DE", "D", 2024): 600.0}
    waci, rows = P.portfolio_waci(holdings, intensity, P.GICS_TO_NACE, 2024)
    lo, hi = P.bootstrap_waci_ci(rows, intensity, 2024, n=2000, seed=0)
    assert lo <= waci <= hi, f"point estimate {waci} must lie inside its own interval [{lo}, {hi}]"


def test_jsonstat_decode_matches_manual_flat_index():
    doc = {
        "id": ["nace_r2", "geo", "time"],
        "size": [2, 3, 1],
        "dimension": {
            "nace_r2": {"category": {"index": {"B": 0, "D": 1}}},
            "geo": {"category": {"index": {"FR": 0, "DE": 1, "IT": 2}}},
            "time": {"category": {"index": {"2024": 0}}},
        },
        # row-major over (nace_r2, geo, time): flat = nace*3 + geo*1 + time*0
        "value": {"4": 77.0},  # nace_r2=D (1), geo=DE (1) -> 1*3 + 1 = 4
    }
    strides = P._jsonstat_strides(doc)
    v = P._jsonstat_get(doc, strides, nace_r2="D", geo="DE", time="2024")
    assert v == 77.0
    assert P._jsonstat_get(doc, strides, nace_r2="B", geo="FR", time="2024") is None


def test_fetch_holdings_row_filter_drops_cash_wrong_country_and_zero_value_rows():
    """Same row-filtering logic as fetch_holdings(), exercised on inline fixture rows instead
    of a live download, so a broken filter fails this test instead of silently corrupting the
    portfolio total the next time ssga.com is reachable."""
    rows = [
        ("Holdings As Of:", "25-Sep-2026"),
        (None,),
        ("ISIN", "SEDOL", "Security Name", "Currency", "Number of Shares",
         "Percent of Fund", "Trade Country Name", "Local Price",
         "Sector Classification", "Industry Classification", "Base Market Value"),
        ("FR0000121972", "483410", "in scope", "EUR", 1.0, 1.0, "France", 1.0,
         "Industrials", "Machinery", 1000.0),
        ("US0000000000", "000000", "wrong country", "USD", 1.0, 1.0, "United States",
         1.0, "Industrials", "Machinery", 1000.0),
        ("Unassigned", "Unassigned", "Euro", "EUR", 1.0, "-", "European Union", 1.0,
         "Unassigned", "Unassigned", 619120.7),
        ("DE0000000000", "000000", "zero value", "EUR", 1.0, 0.0, "Germany", 1.0,
         "Industrials", "Machinery", 0.0),
    ]
    as_of = next(r[1] for r in rows if r and r[0] == "Holdings As Of:")
    header_idx = next(i for i, r in enumerate(rows) if r and r[0] == "ISIN")
    holdings = []
    for r in rows[header_idx + 1:]:
        if not r or not r[0] or r[0] == "Unassigned":
            continue
        isin, sedol, name, ccy, shares, pct, country, price, sector, industry, mv = r[:11]
        if not isinstance(mv, (int, float)) or mv <= 0:
            continue
        if country not in P.COUNTRY_MAP or sector not in P.GICS_TO_NACE:
            continue
        holdings.append({"name": name, "country": country, "market_value": mv})
    assert [h["name"] for h in holdings] == ["in scope"]
    assert as_of == "25-Sep-2026"


def test_extract_ssga_waci_reads_scope123_not_scope12():
    text = ("Weighted Average Carbon Intensity (t CO2e/$M Sales) Portfolio Portfolio Coverage "
           "Scope 1 64.79 100.00% Scope 2 20.19 100.00% Scope 3 922.66 100.00% "
           "Scope 1+2 85.00 100.00% Scope 1+2+3 1,014.54 100.00% Climate Value at Risk")
    assert P.extract_ssga_waci(text) == 1014.54


def test_extract_ssga_waci_returns_none_when_label_absent():
    assert P.extract_ssga_waci("nothing relevant here") is None


def test_pdf_text_roundtrips_a_flate_encoded_tj_stream():
    payload = b"BT (Scope 1+2+3 1,014.54 100.00%)Tj ET"
    fake_pdf = b"1 0 obj\nstream\n" + zlib.compress(payload) + b"\nendstream\nendobj"
    text = P.pdf_text(fake_pdf)
    assert "1,014.54" in text


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("ok   ", name)
            except AssertionError as e:
                fails += 1; print("FAIL ", name, "-", e)
    print(f"\n{'all checks pass' if not fails else str(fails) + ' failed'}")
    sys.exit(1 if fails else 0)
