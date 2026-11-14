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


def _diag(lag, err, rlag=1.0, rerr=1.0, rlag_s=0.0, rerr_s=0.0):
    return {"lm_lag_p": lag, "lm_error_p": err, "rlm_lag_p": rlag, "rlm_error_p": rerr,
            "rlm_lag": rlag_s, "rlm_error": rerr_s}


def test_spatial_model_choice():
    from ceb.models import choose_spatial
    assert choose_spatial(_diag(0.5, 0.5))[0] == "none"
    assert choose_spatial(_diag(0.01, 0.5))[0] == "lag"
    assert choose_spatial(_diag(0.5, 0.01))[0] == "error"
    assert choose_spatial(_diag(0.01, 0.01, rlag=0.01, rerr=0.4))[0] == "lag"
    assert choose_spatial(_diag(0.01, 0.01, rlag=0.4, rerr=0.01))[0] == "error"
    assert choose_spatial(_diag(0.01, 0.01, 0.01, 0.01, rlag_s=3, rerr_s=9))[0] == "error"


class _Resp:
    def __init__(self, status, text):
        self.status_code, self.text = status, text

    def raise_for_status(self):
        import requests
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        import json
        return json.loads(self.text)


def test_census_missing_key_message(monkeypatch):
    from ceb import download
    monkeypatch.setattr(download.requests, "get",
                        lambda url, params, timeout: _Resp(200, "<html><title>Missing Key</title></html>"))
    with pytest.raises(RuntimeError, match="CENSUS_API_KEY"):
        download._census_get("u", {"get": "NAME"}, key=None)


def test_census_returns_rows(monkeypatch):
    from ceb import download
    monkeypatch.setattr(download.requests, "get",
                        lambda url, params, timeout: _Resp(200, '[["NAME","state"],["Illinois","17"]]'))
    assert download._census_get("u", {"get": "NAME"}, key="k")[1][0] == "Illinois"


def test_valid_unit_scaling_and_no_data_cohorts():
    rows = lead_rows()
    # Cohort 0: only half its households have valid data -> totals double.
    rows["HINCP UNITS"] = [50, 300, 200, 0]
    rows["ELEP UNITS"] = [50, 300, 200, 0]
    rows["GASP UNITS"] = [50, 300, 200, 0]
    rows["FULP UNITS"] = [50, 300, 200, 0]
    t = lead.tract_burden(rows).set_index("tract")
    a = t.loc["17031010100"]
    assert a["income_total"] == pytest.approx(2_000_000 + 30_000_000)
    assert a["energy_total"] == pytest.approx(300_000 + 600_000)
    # Last cohort has no valid income data and is dropped (200 households).
    assert t.attrs["households_dropped_no_income_data"] == 200
    assert t.loc["17031010200", "households"] == 200


def test_bin_midpoints():
    from ceb.robustness import bin_midpoint
    assert bin_midpoint("Estimate!!Total:!!Charged for electricity:!!Less than $50") == 25
    assert bin_midpoint("Estimate!!Total:!!Charged for electricity:!!$50 to $99") == 75
    assert bin_midpoint("Estimate!!Total:!!Charged for electricity:!!$250 or more") == 312.5
    assert bin_midpoint("Estimate!!Total:!!$1,000 to $1,499") == 1250
    assert bin_midpoint("Estimate!!Total:!!Electricity included in rent") is None
    assert bin_midpoint("Estimate!!Total:") is None


def test_acs_burden_and_agreement():
    from ceb.robustness import acs_burden, agreement
    labels = {"B25132_001E": "Estimate!!Total:", "B25132_004E": "Estimate!!Total:!!Less than $50",
              "B25132_005E": "Estimate!!Total:!!$50 to $99",
              "B25133_001E": "Estimate!!Total:", "B25133_004E": "Estimate!!Total:!!$25 to $49"}
    util = pd.DataFrame({"GEOID": ["1", "2"], "B25132_001E": [10, 10], "B25132_004E": [10, 0],
                         "B25132_005E": [0, 10], "B25133_001E": [5, 5], "B25133_004E": [5, 5]})
    inc = pd.DataFrame({"GEOID": ["1", "2"], "med_hh_income": [12_000, 24_000]})
    out = acs_burden(util, labels, inc).set_index("GEOID")
    assert out.loc["1", "acs_annual_cost"] == pytest.approx(12 * (25 + 37.5))
    assert out.loc["2", "acs_burden_pct"] == pytest.approx(100 * 12 * (75 + 37.5) / 24_000)
    assert agreement(pd.Series([1, 2, 3, 4, 5.0]), pd.Series([2, 4, 6, 8, 10.0]))["spearman"] == pytest.approx(1)


def test_fractional_logit_runs():
    from ceb.robustness import fractional_logit
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.normal(size=(300, 2)), columns=["a", "b"])
    df["share"] = 1 / (1 + np.exp(-(0.5 * df["a"] - 0.2)))
    out = fractional_logit(df, "share", ["a", "b"]).set_index("term")
    assert out.loc["a", "coef"] == pytest.approx(0.5, abs=0.05)
    assert out.loc["a", "ame"] > 0
