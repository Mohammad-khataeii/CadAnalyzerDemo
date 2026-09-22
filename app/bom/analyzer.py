from __future__ import annotations

from collections import Counter
from typing import Any

from app.models.domain import PDFDocumentAnalysis


class BOMAnalyzer:
    def summarize(self, analyses: list[PDFDocumentAnalysis]) -> dict[str, Any]:
        rows = [row for analysis in analyses for row in analysis.bom_rows]
        component_counts = Counter(row["ComponentPartNumber"] for row in rows)
        shared = [part for part, count in component_counts.items() if count > 1]
        return {
            "row_count": len(rows),
            "component_frequency": component_counts.most_common(30),
            "shared_components": shared[:30],
            "unique_components": [part for part, count in component_counts.items() if count == 1][:30],
        }

