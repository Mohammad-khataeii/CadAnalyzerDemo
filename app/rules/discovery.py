from __future__ import annotations

from itertools import combinations
from typing import Any

import pandas as pd


class RuleDiscoveryEngine:
    def discover(self, df: pd.DataFrame) -> dict[str, Any]:
        technical = [c for c in df.columns if c.startswith("Technical attribute")]
        working = df[df.get("PartNumber", "").astype(str).str.len() > 0].copy()
        working = working[~working["PartNumber"].isin(["TBA", "N/A", "NA"])]
        influence: list[dict[str, Any]] = []
        for column in technical + ["Product Family", "Product Name", "Product Type", "Master PN"]:
            if column not in working:
                continue
            support = int(working[column].astype(bool).sum())
            unique = int(working[column].nunique(dropna=True))
            if support == 0:
                score = 0.0
            else:
                grouped = working.groupby(column)["PartNumber"].nunique()
                score = float((grouped > 1).sum() / max(1, unique))
            influence.append(
                {
                    "Characteristic": column,
                    "Influence": self._label(score, support),
                    "Support": support,
                    "DistinctValues": unique,
                    "Confidence": round(min(0.95, score + min(support / 500, 0.35)), 2),
                }
            )
        mappings = self._segment_mappings(working, technical)
        return {"influence": influence, "mappings": mappings, "configuration_matrix": self._configuration_matrix(working, technical)}

    def _label(self, score: float, support: int) -> str:
        if support < 3:
            return "INSUFFICIENT DATA"
        if score >= 0.55:
            return "HIGH"
        if score >= 0.25:
            return "MEDIUM"
        if score > 0:
            return "LOW"
        return "NO CLEAR SIGNAL"

    def _segment_mappings(self, df: pd.DataFrame, technical: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for column in technical:
            for value, group in df.groupby(column):
                if not value:
                    continue
                suffixes = group["PartNumber"].astype(str).str[-4:].value_counts()
                if not suffixes.empty and suffixes.iloc[0] >= 2:
                    out.append(
                        {
                            "Characteristic": column,
                            "Value": value,
                            "ObservedPartNumberSegment": suffixes.index[0],
                            "Support": int(suffixes.iloc[0]),
                            "Confidence": round(float(suffixes.iloc[0] / len(group)), 2),
                        }
                    )
        return out[:100]

    def _configuration_matrix(self, df: pd.DataFrame, technical: list[str]) -> dict[str, Any]:
        populated = [c for c in technical if c in df and df[c].astype(bool).sum() >= 3]
        key_cols = populated[:4]
        if not key_cols:
            return {"features": [], "observed": 0, "expected": 0, "missing": 0, "duplicates": []}
        expected = 1
        for column in key_cols:
            expected *= max(1, df[column].replace("", pd.NA).dropna().nunique())
        observed = df[key_cols].drop_duplicates().shape[0]
        duplicates = (
            df.groupby(key_cols, dropna=False)["PartNumber"]
            .nunique()
            .reset_index(name="PartNumberCount")
            .query("PartNumberCount > 1")
            .to_dict("records")
        )
        return {"features": key_cols, "observed": int(observed), "expected": int(expected), "missing": int(max(0, expected - observed)), "duplicates": duplicates[:50]}

