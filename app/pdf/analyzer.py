from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz

from app.extraction.characteristics import CharacteristicExtractor
from app.models.domain import PDFDocumentAnalysis
from app.utils.text import clean_cell, normalize_part_number


class PDFAnalyzer:
    """Engineering drawing PDF analyzer using native vector text first."""

    def __init__(self) -> None:
        self.extractor = CharacteristicExtractor()

    def analyze(self, path: Path) -> PDFDocumentAnalysis:
        doc = fitz.open(path)
        page_text = {i + 1: doc[i].get_text("text") for i in range(doc.page_count)}
        fields, evidence, part_numbers, variants = self.extractor.extract_fields(path, page_text)
        bom_rows = self._extract_bom_rows(path, page_text)
        warnings = []
        if not part_numbers:
            warnings.append("No PartNumber pattern detected.")
        if fields.get("Product Name") == "B - ISOLATING COCKS" and fields.get("Drain") == "NEEDS REVIEW":
            warnings.append("Drain was not explicitly identified from text.")
        if fields.get("Product Name") == "B - ISOLATING COCKS" and fields.get("Handle") == "NEEDS REVIEW":
            warnings.append("Handle was mentioned but type/colour is variant-specific or unclear.")
        return PDFDocumentAnalysis(
            source_pdf=path,
            page_count=doc.page_count,
            page_text=page_text,
            fields=fields,
            evidence=evidence,
            part_numbers=part_numbers,
            variants=variants,
            bom_rows=bom_rows,
            warnings=warnings,
        )

    def _extract_bom_rows(self, path: Path, page_text: dict[int, str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        full = "\n".join(page_text.values())
        lines = [clean_cell(line) for line in full.splitlines() if clean_cell(line)]
        for i, line in enumerate(lines):
            pn = self._part_number(line)
            if not pn:
                continue
            window = lines[max(0, i - 3) : i + 8]
            qty = self._near_qty(window)
            description = self._near_description(window)
            rows.append(
                {
                    "SourcePDF": path.name,
                    "ComponentPartNumber": pn,
                    "Quantity": qty,
                    "Description": description,
                    "Specification": self._near_specification(window),
                    "ABC class": self._near_abc(window),
                    "EvidenceText": " | ".join(window[:8])[:700],
                }
            )
        unique: dict[str, dict[str, Any]] = {}
        for row in rows:
            unique.setdefault(row["ComponentPartNumber"], row)
        return list(unique.values())

    def _part_number(self, text: str) -> str:
        for pattern in (r"FT\d{7}-\d{3}", r"\b\d/\d{6}\b", r"\b\d{3}\s?\d{3}\s?\d{2}\s?\d{2}\b"):
            match = re.search(pattern, text, re.I)
            if match:
                return normalize_part_number(match.group(0))
        return ""

    def _near_qty(self, window: list[str]) -> str:
        for token in window:
            if re.fullmatch(r"\d+", token):
                return token
        return ""

    def _near_description(self, window: list[str]) -> str:
        for token in window:
            if re.search(r"cock|body|seal|screw|washer|switch|handle|joint|robinet|vis|rondelle|obturateur|gauge|manometer|compressor|tube|motor", token, re.I):
                return token
        return ""

    def _near_specification(self, window: list[str]) -> str:
        for token in window:
            if re.search(r"ISO|NF |DIN|FT\d|M\d", token, re.I):
                return token
        return ""

    def _near_abc(self, window: list[str]) -> str:
        for token in window:
            if token in {"AA", "AC", "BB", "BC", "CC"}:
                return token
        return ""
