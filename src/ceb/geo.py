"""Select Chicago's census tracts and build spatial weights."""
import geopandas as gpd
import libpysal

from . import config


def chicago_tracts(tract_shp_dir, place_shp_dir, min_overlap=config.CITY_OVERLAP_MIN):
    """Tracts with at least `min_overlap` of their land area inside the city.

    Census tracts do not nest inside cities, so some straddle the boundary.
    The overlap share is kept as a column so the rule can be changed and
    reported.
    """
    tracts = gpd.read_file(next(tract_shp_dir.rglob("*.shp")))
    places = gpd.read_file(next(place_shp_dir.rglob("*.shp")))
    city = places[places["GEOID"] == config.CHICAGO_PLACE_GEOID].to_crs(config.PROJECTED_CRS)
    tracts = tracts[tracts["COUNTYFP"].isin(config.COUNTY_FIPS)].to_crs(config.PROJECTED_CRS)
    tracts = tracts[tracts["ALAND"] > 0]

    inter = gpd.overlay(tracts[["GEOID", "geometry"]], city[["geometry"]], how="intersection")
    inter["in_city_area"] = inter.area
    tracts = tracts.merge(inter[["GEOID", "in_city_area"]].groupby("GEOID").sum(),
                          on="GEOID", how="left").fillna({"in_city_area": 0})
    tracts["city_overlap"] = tracts["in_city_area"] / tracts.area
    keep = tracts[tracts["city_overlap"] >= min_overlap]
    return keep[["GEOID", "NAMELSAD", "ALAND", "city_overlap", "geometry"]].reset_index(drop=True)


def weights(gdf, kind="queen"):
    """Row-standardized spatial weights. Islands are reported, not hidden."""
    if kind == "queen":
        w = libpysal.weights.Queen.from_dataframe(gdf, use_index=False)
    elif kind == "knn":
        pts = gdf.copy()
        pts["geometry"] = gdf.geometry.representative_point()
        w = libpysal.weights.KNN.from_dataframe(pts, k=config.KNN_K, use_index=False)
    else:
        raise ValueError(kind)
    if w.islands:
        print(f"  warning: {len(w.islands)} island tract(s) with no neighbors: {w.islands}")
    w.transform = "r"
    return w
