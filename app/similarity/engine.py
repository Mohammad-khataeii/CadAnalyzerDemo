from __future__ import annotations

from typing import Any

import pandas as pd


class SimilarityEngine:
    def find_similar(self, df: pd.DataFrame, part_number: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        features = [c for c in ["Product Family", "Product Name", "Product Type", "Technical attribute 1", "Technical attribute 2", "Technical attribute 3", "Technical attribute 4"] if c in df.columns]
        working = df[df.get("PartNumber", "").astype(bool)].copy()
        working = working[~working["PartNumber"].isin(["TBA", "N/A", "NA"])]
        if working.empty or not features:
            return []
        if part_number:
            target = working[working["PartNumber"] == part_number].head(1).squeeze()
        else:
            richness = working[features].replace("", pd.NA).notna().sum(axis=1)
            target = working.loc[richness.idxmax()]
        if target is None or getattr(target, "empty", False):
            target = working.iloc[0]
        rows: list[dict[str, Any]] = []
        for _, row in working.iterrows():
            if row["PartNumber"] == target["PartNumber"]:
                continue
            matches = [f for f in features if row.get(f, "") and row.get(f, "") == target.get(f, "")]
            score = len(matches) / max(1, len(features))
            rows.append({"Product": row["PartNumber"], "Similarity": round(score * 100, 1), "Reasons": ", ".join(matches), "GeometricSimilarity": "UNAVAILABLE"})
        return sorted(rows, key=lambda r: r["Similarity"], reverse=True)[:limit]
