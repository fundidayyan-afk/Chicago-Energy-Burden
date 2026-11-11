import numpy as np
import pandas as pd
import pytest

from ceb import acs, lead


def lead_rows():
    # Two tracts, two income cohorts each. Money columns are totals (x UNITS).
    return pd.DataFrame({
        "FIP": [17031010100, 17031010100, 17031010200, 17031010200],
        "AMI150": ["0-30%", "100%+", "30-60%", "80-100%"],
        "UNITS": [100, 300, 200, 200],
        "HINCP*UNITS": [1_000_000, 30_000_000, 6_000_000, 16_000_000],
        "ELEP*UNITS": [80_000, 300_000, 150_000, 150_000],
        "GASP*UNITS": [70_000, 300_000, 150_000, 150_000],
        "FULP*UNITS": [0, 0, 0, 0],
    })


def test_burden_is_ratio_of_sums():
    t = lead.tract_burden(lead_rows()).set_index("tract")
    a = t.loc["17031010100"]
    assert a["households"] == 400
    assert a["burden_pct"] == pytest.approx(100 * 750_000 / 31_000_000)
    # Only the 0-30% cohort (burden 15%) is above 6% and above 10%.
    assert a["share_high"] == pytest.approx(0.25)
    assert a["share_severe"] == pytest.approx(0.25)
    assert a["li_burden_pct"] == pytest.approx(15.0)


def test_low_income_rule():
    assert lead.is_low_income("0-30%")
    assert lead.is_low_income("60-80%")
    assert not lead.is_low_income("80-100%")
    assert not lead.is_low_income("100%+")


def test_nonpositive_income_dropped_and_counted():
    rows = lead_rows()
    rows.loc[0, "HINCP*UNITS"] = 0
    t = lead.tract_burden(rows)
    assert t.attrs["households_dropped_nonpositive_income"] == 100


def test_missing_column_message_lists_columns():
    with pytest.raises(KeyError, match="Columns are"):
        lead.standardize_columns(lead_rows().drop(columns=["GASP*UNITS"]))


def test_weighted_median():
    assert lead.weighted_median([1, 2, 10], [1, 1, 10]) == 10
    assert lead.weighted_median([1, 2, 3], [1, 1, 1]) == 2


def test_proportion_moe_matches_census_formula():
    # ACS Handbook worked example style: p = 20/100, MOEs 5 and 10.
    p, moe = acs._prop(20.0, 5.0, 100.0, 10.0)
    assert p == pytest.approx(0.2)
    assert moe == pytest.approx(np.sqrt(25 - 0.04 * 100) / 100)
