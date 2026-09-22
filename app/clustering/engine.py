from __future__ import annotations

import warnings
from typing import Any

import pandas as pd
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


class ClusteringEngine:
    def run(self, df: pd.DataFrame, method: str = "kmeans", n_clusters: int = 4) -> dict[str, Any]:
        features = [c for c in ["Product Family", "Product Name", "Product Type", "Technical attribute 1", "Technical attribute 2", "Technical attribute 3", "Technical attribute 4"] if c in df.columns]
        working = df[df.get("PartNumber", "").astype(bool)].copy()
        working = working[~working["PartNumber"].isin(["TBA", "N/A", "NA"])]
        if len(working) < 2 or not features:
            return {"method": method, "features": features, "points": [], "explanations": []}
        x = working[features].replace("", "UNKNOWN")
        transformer = ColumnTransformer(
            [("cat", Pipeline([("imputer", SimpleImputer(strategy="constant", fill_value="UNKNOWN")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), features)],
            remainder="drop",
        )
        matrix = transformer.fit_transform(x)
        cluster_count = max(2, min(n_clusters, len(working)))
        if method == "hierarchical":
            labels = AgglomerativeClustering(n_clusters=cluster_count).fit_predict(matrix.toarray())
        elif method == "dbscan":
            labels = DBSCAN(eps=1.2, min_samples=2).fit_predict(matrix.toarray())
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                labels = KMeans(n_clusters=cluster_count, random_state=42, n_init="auto").fit_predict(matrix)
            method = "kmeans"
        dense = matrix.toarray() if hasattr(matrix, "toarray") else matrix
        dense = dense.astype(float)
        if dense.shape[1] >= 2:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                coords = PCA(n_components=2, random_state=42, svd_solver="full").fit_transform(dense)
        else:
            coords = [[0, 0] for _ in range(len(working))]
        clustered = working.copy()
        clustered["Cluster"] = labels
        clustered["PCA_X"] = [float(p[0]) for p in coords]
        clustered["PCA_Y"] = [float(p[1]) for p in coords]
        return {
            "method": method,
            "features": features,
            "points": clustered[["PartNumber", "Master PN", "Product Family", "Product Name", "Product Type", "Cluster", "PCA_X", "PCA_Y"]].to_dict("records"),
            "explanations": self._explain(clustered, features),
        }

    def _explain(self, df: pd.DataFrame, features: list[str]) -> list[dict[str, Any]]:
        explanations: list[dict[str, Any]] = []
        for cluster, group in df.groupby("Cluster"):
            common = []
            for feature in features:
                vc = group[feature].replace("", "UNKNOWN").value_counts(normalize=True)
                if not vc.empty:
                    common.append({"Feature": feature, "Value": vc.index[0], "Share": round(float(vc.iloc[0]), 2)})
            explanations.append(
                {
                    "Cluster": int(cluster),
                    "Products": int(len(group)),
                    "Common": common,
                    "RepresentativeProducts": group["PartNumber"].head(5).tolist(),
                }
            )
        return explanations
