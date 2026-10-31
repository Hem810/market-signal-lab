def weights(group):
    g = group.copy()
    g["weight"] = 0.0
    eligible = (
        g[g.prediction > 0].sort_values(["prediction", "symbol"], ascending=[False, True]).head(4)
    )
    g.loc[eligible.index, "weight"] = 0.24
    return g
