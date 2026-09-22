from __future__ import annotations

import re
from pathlib import Path

from app.models.domain import Evidence, NOT_FOUND, UNKNOWN
from app.utils.text import clean_cell, compact_unique, normalize_part_number


class CharacteristicExtractor:
    """Deterministic local extraction for drawing metadata and catalogue attributes."""

    pn_patterns = [
        r"FT\d{7}-\d{3}",
        r"\b\d{3}\s?\d{3}\s?\d{2}\s?\d{2}\b",
        r"\b\d{6}XX\d{2}\b",
    ]

    def extract_fields(self, pdf_path: Path, page_text: dict[int, str]) -> tuple[dict[str, str], list[Evidence], list[str], list[str]]:
        full_text = "\n".join(page_text.values())
        evidence: list[Evidence] = []
        fields: dict[str, str] = {}

        drawing = self._drawing_from_filename(pdf_path) or self._first(r"\b(FT\d{7}-\d{3}|\d{6}XX\d{2})\b", full_text)
        fields["Drawing number"] = drawing or NOT_FOUND
        if drawing:
            evidence.append(self._ev("Drawing number", drawing, pdf_path, self._page_of(page_text, drawing), drawing, 0.96, "native_pdf_text"))

        revision = self._first(r"\b([A-Z]{1,2}\d{2})\b", full_text)
        fields["Drawing revision"] = revision or NOT_FOUND
        if revision:
            evidence.append(self._ev("Drawing revision", revision, pdf_path, self._page_of(page_text, revision), revision, 0.86, "title_block_pattern"))

        product_line = self._title_line(full_text)
        fields["Drawing title"] = clean_cell(product_line) or UNKNOWN
        if product_line:
            evidence.append(self._ev("Drawing title", clean_cell(product_line), pdf_path, self._page_of(page_text, product_line), product_line, 0.88, "native_pdf_text"))

        diameter = self._first(r"\b(DN\s?\d+)\b", full_text)
        fields["Diameter"] = f"PNEU DIAMETER {diameter.replace(' ', '')}" if diameter else UNKNOWN
        if diameter:
            evidence.append(self._ev("Diameter", fields["Diameter"], pdf_path, self._page_of(page_text, diameter), diameter, 0.93, "engineering_term_pattern"))

        contact = self._extract_contacts(full_text)
        fields["Contact"] = contact
        if contact != UNKNOWN:
            evidence.append(self._ev("Contact", contact, pdf_path, self._page_of(page_text, contact.split()[0]), self._line_around(full_text, r"(?:\d+\s*(?:cts|CONTACTS?|SWITCH(?:E|ES)?))"), 0.82, "engineering_term_pattern"))

        fields["Product Family"] = "B - AIR DISTRIBUTION AND MANAGEMENT" if "cock" in full_text.lower() or "robinet" in full_text.lower() else UNKNOWN
        fields["Product Name"] = "B - ISOLATING COCKS" if "cock" in full_text.lower() or "robinet" in full_text.lower() else UNKNOWN
        fields["Product Type"] = "X - FLANGED" if re.search(r"flange|flasqu", full_text, re.I) else UNKNOWN

        fields["Pressure"] = self._first(r"(?:Maximum pressure|Pression maximum)[^\n:]*:?\s*([^\n]+)", full_text) or UNKNOWN
        if fields["Pressure"] != UNKNOWN:
            evidence.append(self._ev("Pressure", fields["Pressure"], pdf_path, self._page_of(page_text, fields["Pressure"]), fields["Pressure"], 0.86, "note_pattern"))

        temp = self._first(r"(?:Operating temperature|Temp[ée]rature de fonctionnement)[^\n:]*:?\s*([^\n]+)", full_text)
        fields["Temperature"] = temp or UNKNOWN
        if temp:
            evidence.append(self._ev("Temperature", temp, pdf_path, self._page_of(page_text, temp), temp, 0.85, "note_pattern"))

        fields["Foolproofing"] = self._extract_foolproofing(full_text)
        fields["Drain"] = self._extract_drain(full_text)
        fields["Handle"] = self._extract_handle(full_text)
        fields["Handle colour"] = self._extract_colour(full_text)
        fields["Connector"] = "ISO BASE" if re.search(r"ISO BASE|EMBASE ISO", full_text, re.I) else UNKNOWN
        fields["Connector orientation"] = "NEEDS REVIEW" if re.search(r"orientation", full_text, re.I) else UNKNOWN
        fields["Weight"] = "See bom" if re.search(r"See bom", full_text, re.I) else UNKNOWN

        part_numbers = self._extract_part_numbers(full_text)
        variants = self._extract_variants(full_text)
        return fields, evidence, part_numbers, variants

    def _extract_part_numbers(self, text: str) -> list[str]:
        values: list[str] = []
        for pattern in self.pn_patterns:
            values.extend(re.findall(pattern, text, re.I))
        return compact_unique(normalize_part_number(v) for v in values)

    def _drawing_from_filename(self, pdf_path: Path) -> str:
        stem = pdf_path.stem.upper()
        match = re.match(r"(FT\d{7}-\d{3}|\d{6}XX\d{2})", stem)
        return match.group(1) if match else ""

    def _title_line(self, text: str) -> str:
        lines = [clean_cell(line) for line in text.splitlines() if clean_cell(line)]
        for pattern in (r"^Insulation cock\b", r"^FLANGEABLE COCK\b"):
            for line in lines:
                if re.search(pattern, line, re.I):
                    return line
        for i, line in enumerate(lines[:-1]):
            if line.upper() == "COCK":
                return f"{line} {lines[i + 1]}"
        for line in lines:
            if re.search(r"\bROBINET\b|\bCOCK\b", line, re.I):
                return line
        return ""

    def _extract_variants(self, text: str) -> list[str]:
        raw = re.findall(r"\b(?:Var\.?|VAR|Variant(?:e)?s?)\s*(?:/ Variants)?\s*[:.]?\s*([A-Z0-9/ \-\u00e0toFT]+)", text, re.I)
        values: list[str] = []
        for item in raw:
            values.extend(re.findall(r"FT\d{7}-\d{3}|\b\d{2,3}\b", item, re.I))
        return compact_unique(values)

    def _extract_contacts(self, text: str) -> str:
        if re.search(r"\b2\s*(?:cts|contacts?|switch(?:e|es)?)\b", text, re.I):
            return "2 CONTACTS"
        if re.search(r"\b1\s*(?:contact|switch(?:e)?)\b", text, re.I):
            return "1 CONTACT"
        if re.search(r"\bno\s+contact\b", text, re.I):
            return "NO CONTACT"
        return UNKNOWN

    def _extract_drain(self, text: str) -> str:
        if re.search(r"with drain|draining cock|free drain", text, re.I):
            return "WITH DRAIN"
        if re.search(r"no drain", text, re.I):
            return "NO DRAIN"
        return "NEEDS REVIEW"

    def _extract_handle(self, text: str) -> str:
        if re.search(r"butterfly handle", text, re.I):
            return "BUTTERFLY HANDLE"
        if re.search(r"self-?locking handle", text, re.I):
            return "SELF-LOCKING HANDLE"
        if re.search(r"straight (?:handle|lever)", text, re.I):
            return "STRAIGHT HANDLE"
        if re.search(r"handle|poign", text, re.I):
            return "NEEDS REVIEW"
        return UNKNOWN

    def _extract_colour(self, text: str) -> str:
        colours = re.findall(r"\b(yellow|black|red|blue|green|white)\b", text, re.I)
        return ", ".join(sorted({c.upper() for c in colours})) if colours else UNKNOWN

    def _extract_foolproofing(self, text: str) -> str:
        if re.search(r"without foolproof|sans d[ée]trompeur", text, re.I):
            return "WITHOUT FOOLPROOF PIN"
        if re.search(r"with foolproof|avec d[ée]trompeur|foolproofing", text, re.I):
            return "WITH FOOLPROOF PIN"
        return UNKNOWN

    def _ev(self, field: str, value: str, pdf_path: Path, page: int, text: str, confidence: float, method: str) -> Evidence:
        return Evidence(field, value, pdf_path.name, page, clean_cell(text)[:500], confidence, method)

    def _first(self, pattern: str, text: str) -> str:
        match = re.search(pattern, text, re.I)
        return clean_cell(match.group(1) if match and match.groups() else match.group(0) if match else "")

    def _page_of(self, page_text: dict[int, str], needle: str) -> int:
        low = needle.lower()
        for page, text in page_text.items():
            if low in text.lower():
                return page
        return 1

    def _line_around(self, text: str, pattern: str) -> str:
        for line in text.splitlines():
            if re.search(pattern, line, re.I):
                return line
        return ""
