from __future__ import annotations

from typing import Any

import pandas as pd

from app.models.domain import PDFDocumentAnalysis


class AnomalyDetector:
    def detect(self, catalogue: pd.DataFrame, analyses: list[PDFDocumentAnalysis], rule_results: dict[str, Any]) -> list[dict[str, Any]]:
        anomalies: list[dict[str, Any]] = []
        technical = [c for c in catalogue.columns if c.startswith("Technical attribute")]
        keys = [c for c in ["Product Family", "Product Name", "Product Type", *technical] if c in catalogue.columns]
        if keys and "PartNumber" in catalogue.columns:
            dupes = catalogue.groupby(keys, dropna=False)["PartNumber"].nunique().reset_index(name="part_count")
            for row in dupes[dupes["part_count"] > 1].head(50).to_dict("records"):
                anomalies.append({"Type": "Same characteristics -> different PartNumbers", "Severity": "MEDIUM", "Evidence": row})
            valid_parts = catalogue[~catalogue["PartNumber"].isin(["", "TBA", "N/A", "NA"])]
            conflicts = valid_parts.groupby("PartNumber", dropna=False)[technical].nunique().sum(axis=1)
            for part, count in conflicts[conflicts > len(technical)].head(50).items():
                anomalies.append({"Type": "Same PartNumber -> conflicting characteristics", "Severity": "HIGH", "Evidence": {"PartNumber": part, "ConflictScore": int(count)}})

        matrix = rule_results.get("configuration_matrix", {})
        if matrix.get("missing", 0):
            anomalies.append({"Type": "Missing expected combinations", "Severity": "LOW", "Evidence": matrix})

        catalogue_parts = set(catalogue.get("PartNumber", pd.Series(dtype=str)).astype(str))
        for analysis in analyses:
            detected = set(analysis.part_numbers)
            if detected and not detected.intersection(catalogue_parts):
                anomalies.append({"Type": "PDF not found in catalogue", "Severity": "HIGH", "Evidence": {"SourcePDF": analysis.source_pdf.name, "PartNumbers": sorted(detected)[:20]}})
            for field, value in analysis.fields.items():
                if value in {"NEEDS REVIEW", "UNKNOWN", "NOT_FOUND"}:
                    anomalies.append({"Type": "Low-confidence extraction", "Severity": "MEDIUM", "Evidence": {"SourcePDF": analysis.source_pdf.name, "Field": field, "Value": value}})
            variants = {v for v in analysis.variants if v.isdigit()}
            pn_suffixes = {p[-6:-2] for p in analysis.part_numbers if p.startswith("725") and len(p) >= 10}
            if variants and pn_suffixes and not variants.intersection(pn_suffixes):
                anomalies.append({"Type": "Variant mapping inconsistency", "Severity": "LOW", "Evidence": {"SourcePDF": analysis.source_pdf.name, "Variants": sorted(variants)[:20], "PartNumberSegments": sorted(pn_suffixes)[:20]}})
        return anomalies[:200]
