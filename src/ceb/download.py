"""Download every raw input. Files are cached in data/raw and never edited.

Run through scripts/01_download.py. Set CENSUS_API_KEY in your environment
(free key: https://api.census.gov/data/key_signup.html); the API works
without one but limits how many calls you can make.
"""
import os
import zipfile

import pandas as pd
import requests

from . import config


def fetch(url, dest, force=False):
    """Download url to dest unless it is already there."""
    if dest.exists() and not force:
        print(f"  cached  {dest.name}")
        return dest
    print(f"  get     {url}")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.rename(dest)
    return dest


def unzip(path, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        z.extractall(dest_dir)
    return dest_dir


def download_lead():
    z = fetch(config.LEAD_ZIP_URL, config.RAW / "IL-2022-LEAD-data.zip")
    unzip(z, config.RAW / "lead_il_2022")
    try:
        fetch(config.LEAD_DICTIONARY_URL, config.RAW / "LEAD_data_dictionary_2022.xlsx")
    except requests.HTTPError as e:
        print(f"  note    data dictionary not fetched ({e}); download it by hand from OEDI 6219")


def download_tiger():
    for url, name in [(config.TIGER_TRACT_URL, "tracts"), (config.TIGER_PLACE_URL, "places")]:
        z = fetch(url, config.RAW / url.rsplit("/", 1)[-1])
        unzip(z, config.RAW / f"tiger_{name}_{config.TIGER_YEAR}")


# ACS variables. E = estimate, M = margin of error (90% level).
ACS_VARS = {
    "B19013_001": "med_hh_income",
    "B03002_001": "pop_total",
    "B03002_003": "pop_nh_white",
    "B03002_004": "pop_nh_black",
    "B03002_012": "pop_hispanic",
    "B25003_001": "occ_units",
    "B25003_003": "renter_units",
    "B25034_001": "units_total_yb",
    "B25034_010": "units_1940_49",
    "B25034_011": "units_pre1940",
    "B25035_001": "med_year_built",
    "B25024_001": "units_total_str",
    "B25024_006": "units_5_9",
    "B25024_007": "units_10_19",
    "B25024_008": "units_20_49",
    "B25024_009": "units_50plus",
    "B25040_001": "heat_total",
    "B25040_002": "heat_utility_gas",
    "B25040_004": "heat_electric",
    "C17002_001": "pov_universe",
    "C17002_002": "pov_under_050",
    "C17002_003": "pov_050_099",
}


def _census_get(url, params, key, tries=3):
    """Call the Census API and return its rows, with readable errors.

    The API answers some problems (an unactivated or wrong key, a bad
    variable name, rate limits) with an HTML or text page instead of JSON.
    Show that message, and if a key was rejected, retry without it.
    """
    import time

    for attempt in range(1, tries + 1):
        p = dict(params, key=key) if key else params
        r = requests.get(url, params=p, timeout=120)
        try:
            r.raise_for_status()
            return r.json()
        except (ValueError, requests.HTTPError):
            text = " ".join(r.text.split())[:400]
            print(f"  census  HTTP {r.status_code}, not data (attempt {attempt}): {text or '(empty response)'}")
            if key and ("key" in text.lower() or r.status_code in (401, 403)):
                print("  census  API key rejected; retrying without a key. "
                      "Check the CENSUS_API_KEY secret and that the key was activated by email.")
                key = None
                continue
            if "unknown variable" in text.lower() or r.status_code == 400:
                raise RuntimeError(f"Census API rejected the request: {text}")
            time.sleep(5 * attempt)
    raise RuntimeError("Census API did not return data after several tries; see messages above.")


def download_acs(year=config.ACS_YEAR):
    """Pull ACS 5-year tract estimates and MOEs for the counties in config."""
    dest = config.RAW / f"acs5_{year}_tracts.csv"
    if dest.exists():
        print(f"  cached  {dest.name}")
        return dest
    fields = [f"{v}{s}" for v in ACS_VARS for s in ("E", "M")]
    key = os.environ.get("CENSUS_API_KEY")
    frames = []
    for county in config.COUNTY_FIPS:
        parts = []
        # The API accepts at most 50 variables per call.
        for i in range(0, len(fields), 45):
            params = {
                "get": ",".join(["NAME"] + fields[i:i + 45]),
                "for": "tract:*",
                "in": f"state:{config.STATE_FIPS} county:{county}",
            }
            rows = _census_get(config.ACS_API.format(year=year), params, key)
            df = pd.DataFrame(rows[1:], columns=rows[0])
            df["GEOID"] = df["state"] + df["county"] + df["tract"]
            parts.append(df.set_index("GEOID").drop(columns=["state", "county", "tract"]))
        merged = pd.concat(parts, axis=1)
        frames.append(merged.loc[:, ~merged.columns.duplicated()])
    out = pd.concat(frames).reset_index()
    out.to_csv(dest, index=False)
    print(f"  saved   {dest.name} ({len(out)} tracts)")
    return dest
