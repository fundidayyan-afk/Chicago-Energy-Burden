"""Step 1: download LEAD, TIGER/Line boundaries, and ACS tables into data/raw."""
from ceb import download

if __name__ == "__main__":
    print("LEAD 2022 (Illinois)")
    download.download_lead()
    print("TIGER/Line tracts and places")
    download.download_tiger()
    print("ACS 5-year, 2018-2022 and 2020-2024")
    download.download_acs(2022)
    try:
        download.download_acs(2024)   # robustness check only; skip if not yet published
    except Exception as e:
        print(f"  note    ACS 2020-2024 not downloaded ({e}); robustness check will be skipped")
    try:
        download.download_acs_utility(2022)   # for the independent burden check
    except Exception as e:
        print(f"  note    ACS utility tables not downloaded ({e}); validation will be skipped")
    try:
        download.download_basemap()           # web map background
    except Exception as e:
        print(f"  note    basemap layers not downloaded ({e})")
    print("Done.")
