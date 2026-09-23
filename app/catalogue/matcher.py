from __future__ import annotations

import pandas as pd

from app.models.domain import MatchResult, PDFDocumentAnalysis
from app.utils.text import normalize_part_number


class CatalogueMatcher:
    def match(self, catalogue: pd.DataFrame, analyses: list[PDFDocumentAnalysis]) -> list[MatchResult]:
        results: list[MatchResult] = []
        if "PartNumber" not in catalogue.columns:
            return results
        normalized = catalogue.copy()
        normalized["PartNumber"] = normalized["PartNumber"].map(normalize_part_number)
        normalized["Master PN"] = normalized.get("Master PN", "").map(normalize_part_number)
        for analysis in analyses:
            direct = [pn for pn in analysis.part_numbers if pn in set(normalized["PartNumber"])]
            master = [pn for pn in analysis.part_numbers if pn in set(normalized["Master PN"])]
            if direct:
                row = normalized[normalized["PartNumber"] == direct[0]].iloc[0]
                drawing = normalize_part_number(analysis.fields.get("Drawing number", ""))
                is_exact = not drawing or direct[0] == drawing or row.get("Master PN", "") == drawing
                status = "MATCH" if is_exact else "REFERENCE MATCH"
                reason = "PartNumber appears in catalogue." if is_exact else "A variant/reference PartNumber from the PDF appears in catalogue; the drawing code remains the generated PartNumber."
                results.append(MatchResult(analysis.source_pdf.name, status, direct[0], row.get("Master PN", ""), reason, 1))
                continue
            if master:
                candidates = normalized[normalized["Master PN"] == master[0]]
                results.append(MatchResult(analysis.source_pdf.name, "MATCH", candidates.iloc[0]["PartNumber"], master[0], "Drawing number matches Master PN.", len(candidates)))
                continue
            char_candidates = self._characteristic_candidates(normalized, analysis)
            if len(char_candidates) == 1:
                row = char_candidates.iloc[0]
                results.append(MatchResult(analysis.source_pdf.name, "PREDICTED MATCH", row["PartNumber"], row.get("Master PN", ""), "Unique row matches extracted diameter/contact/product hierarchy.", 1))
            elif len(char_candidates) > 1:
                results.append(MatchResult(analysis.source_pdf.name, "AMBIGUOUS", "", "", "Multiple rows match extracted diameter/contact/product hierarchy.", len(char_candidates)))
            else:
                results.append(MatchResult(analysis.source_pdf.name, "UNMATCHED", "", "", "No catalogue row matches extracted identifiers or characteristics.", 0))
        return results

    def _characteristic_candidates(self, catalogue: pd.DataFrame, analysis: PDFDocumentAnalysis) -> pd.DataFrame:
        candidates = catalogue
        field_map = {
            "Product Family": "Product Family",
            "Product Name": "Product Name",
            "Product Type": "Product Type",
            "Diameter": "Technical attribute 1",
            "Contact": "Technical attribute 3",
        }
        for field, column in field_map.items():
            value = analysis.fields.get(field, "")
            if value and value not in {"UNKNOWN", "NOT_FOUND", "NEEDS REVIEW"} and column in candidates.columns:
                candidates = candidates[candidates[column].str.upper() == value.upper()]
        return candidates
