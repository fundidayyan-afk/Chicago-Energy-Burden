"""Phase 1 exploratory spatial analysis: global Moran's I and LISA clusters."""
import numpy as np
import pandas as pd
from esda import Moran, Moran_Local, fdr

from . import config

QUADRANTS = {1: "High-High", 2: "Low-High", 3: "Low-Low", 4: "High-Low"}


def global_moran(y, w):
    m = Moran(np.asarray(y, float), w, permutations=config.LISA_PERMUTATIONS)
    return {"I": m.I, "expected_I": m.EI, "z": m.z_sim, "p_sim": m.p_sim}


def lisa(gdf, column, w, alpha=config.ALPHA):
    """Local Moran's I with a false discovery rate cutoff.

    With ~800 tracts, a plain p < 0.05 rule would label about 40 tracts as
    'significant' by chance alone. The FDR threshold controls that.
    """
    y = gdf[column].to_numpy(float)
    lm = Moran_Local(y, w, permutations=config.LISA_PERMUTATIONS, seed=config.SEED)
    cutoff = fdr(lm.p_sim, alpha)
    out = pd.DataFrame({
        "GEOID": gdf["GEOID"].to_numpy(),
        "local_I": lm.Is,
        "p_sim": lm.p_sim,
        "quadrant": pd.Series(lm.q).map(QUADRANTS).to_numpy(),
    })
    out["sig_raw"] = out["p_sim"] < alpha
    out["sig_fdr"] = out["p_sim"] <= cutoff
    out["cluster"] = np.where(out["sig_fdr"], out["quadrant"], "Not significant")
    out.attrs["fdr_cutoff"] = cutoff
    return out
