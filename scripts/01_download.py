"""Step 1: download LEAD, TIGER/Line boundaries, and ACS tables into data/raw."""
from ceb import download

if __name__ == "__main__":
    print("LEAD 2022 (Illinois)")
    download.download_lead()
    print("TIGER/Line tracts and places")
    download.download_tiger()
    print("ACS 5-year, 2018-2022 and 2020-2024")
    download.download_acs(2022)
    download.download_acs(2024)
    print("Done.")
