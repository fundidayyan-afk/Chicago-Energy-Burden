"""Project-wide settings: paths, geography, and source URLs.

Everything that might change between runs lives here, so the rest of the
code never hard-codes a path or a year.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
OUTPUT = ROOT / "output"
FIGURES = OUTPUT / "figures"
TABLES = OUTPUT / "tables"

for _p in (RAW, INTERIM, PROCESSED, FIGURES, TABLES):
    _p.mkdir(parents=True, exist_ok=True)

# Geography -----------------------------------------------------------------
STATE_FIPS = "17"                 # Illinois
COUNTY_FIPS = ["031", "043"]      # Cook, DuPage (Chicago reaches into DuPage at O'Hare)
CHICAGO_PLACE_GEOID = "1714000"   # Census place code for the City of Chicago
CITY_OVERLAP_MIN = 0.5            # keep a tract if at least half its land area is in the city
PROJECTED_CRS = "EPSG:26971"      # NAD83 / Illinois East (meters), for areas and distances

# Data vintages -------------------------------------------------------------
ACS_YEAR = 2022                   # 2018-2022 5-year, to match LEAD 2022
ACS_YEAR_CHECK = 2024             # 2020-2024 5-year, robustness check
TIGER_YEAR = 2022                 # 2020 tract boundaries, as published in TIGER 2022

# Sources -------------------------------------------------------------------
LEAD_ZIP_URL = "https://data.openei.org/files/6219/IL-2022-LEAD-data.zip"
LEAD_DICTIONARY_URL = "https://data.openei.org/files/6219/Data%20Dictionary%202022.xlsx"
TIGER_TRACT_URL = (
    f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/TRACT/tl_{TIGER_YEAR}_{STATE_FIPS}_tract.zip"
)
TIGER_PLACE_URL = (
    f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/PLACE/tl_{TIGER_YEAR}_{STATE_FIPS}_place.zip"
)
ACS_API = "https://api.census.gov/data/{year}/acs/acs5"
# Basemap layers for the web map (drawn by us, no tile service needed)
TIGER_WATER_URL = (
    f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/AREAWATER/tl_{TIGER_YEAR}_{STATE_FIPS}031_areawater.zip"
)
COMMUNITY_AREA_URLS = [
    "https://data.cityofchicago.org/resource/igwz-8jzy.geojson?$limit=200",
    "https://data.cityofchicago.org/api/geospatial/igwz-8jzy?method=export&format=GeoJSON",
    "https://data.cityofchicago.org/api/geospatial/cauq-8yn6?method=export&format=GeoJSON",
]

# Analysis settings ---------------------------------------------------------
BURDEN_HIGH = 6.0                 # percent of income: "high" energy burden
BURDEN_SEVERE = 10.0              # percent of income: "severe" energy burden
MIN_HOUSEHOLDS = 100              # tracts with fewer households are flagged as unstable
ACS_CV_UNRELIABLE = 0.40          # coefficient of variation above this = unreliable estimate
KNN_K = 6                         # k for the nearest-neighbor robustness weights
LISA_PERMUTATIONS = 9999
ALPHA = 0.05
SEED = 20270601

# Benchmarks quoted in the proposal (ACEEE). Used only for validation.
ACEEE_2024_CHICAGO = {"all_households_median": 2.2, "low_income_median": 7.2}
ACEEE_2020_CHICAGO_METRO = {"all_households_median": 2.7, "low_income_median": 8.0}
