from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


UNKNOWN = "UNKNOWN"
NOT_FOUND = "NOT_FOUND"


@dataclass
class Evidence:
    field: str
    value: str
    source_pdf: str
    page: int
    evidence_text: str
    confidence: float
    extraction_method: str
    status: str = "ACCEPTED"


@dataclass
class PDFDocumentAnalysis:
    source_pdf: Path
    page_count: int
    page_text: dict[int, str]
    fields: dict[str, str]
    evidence: list[Evidence] = field(default_factory=list)
    part_numbers: list[str] = field(default_factory=list)
    variants: list[str] = field(default_factory=list)
    bom_rows: list[dict[str, Any]] = field(default_factory=list)
    engineering: Any | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def drawing_number(self) -> str:
        return self.fields.get("Drawing number", NOT_FOUND)


@dataclass
class CatalogueProfile:
    path: Path
    sheet_name: str
    digit_metadata: dict[str, str]
    columns: list[str]
    row_count: int
    part_rows: int
    family_counts: dict[str, int]
    technical_columns: list[str]


@dataclass
class MatchResult:
    source_pdf: str
    status: str
    matched_part_number: str
    matched_master_pn: str
    reason: str
    candidate_count: int


@dataclass
class DemoRunResult:
    catalogue_profile: CatalogueProfile
    pdf_analyses: list[PDFDocumentAnalysis]
    generated_catalogue_rows: int
    evidence_rows: int
    demo_focus: dict[str, Any]
    matches: list[MatchResult]
    rule_results: dict[str, Any]
    anomalies: list[dict[str, Any]]
    clusters: dict[str, Any]
    similarity: list[dict[str, Any]]
    output_files: dict[str, Path]
