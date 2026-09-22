from __future__ import annotations

import re
from pathlib import Path

from app.models.domain import Evidence, NOT_FOUND, UNKNOWN
from app.utils.text import clean_cell, compact_unique, normalize_part_number


class CharacteristicExtractor:
    """Deterministic local extraction for drawing metadata and catalogue attributes."""

    pn_patterns = [
        r"FT\d{7}-\d{3}",
        r"\b\d/\d{6}\b",
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

        product_kind = self._product_kind(full_text)

        diameter = self._extract_diameter(full_text, product_kind)
        fields["Diameter"] = diameter
        if diameter:
            evidence.append(self._ev("Diameter", fields["Diameter"], pdf_path, self._page_of(page_text, diameter), diameter, 0.93, "engineering_term_pattern"))

        contact = self._extract_contacts(full_text)
        fields["Contact"] = contact
        if contact != UNKNOWN:
            evidence.append(self._ev("Contact", contact, pdf_path, self._page_of(page_text, contact.split()[0]), self._line_around(full_text, r"(?:\d+\s*(?:cts|CONTACTS?|SWITCH(?:E|ES)?))"), 0.82, "engineering_term_pattern"))

        fields["Product Family"], fields["Product Name"], fields["Product Type"] = self._product_hierarchy(full_text, product_kind)

        fields["Pressure"] = self._extract_pressure(full_text)
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
        fields["LED"] = "WITH LED" if re.search(r"\bLED\b", full_text, re.I) else UNKNOWN
        fields["Mounting"] = self._extract_mounting(full_text)

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
        if match:
            return match.group(1)
        slash_match = re.match(r"(\d)-(\d{6})", stem)
        return f"{slash_match.group(1)}/{slash_match.group(2)}" if slash_match else ""

    def _title_line(self, text: str) -> str:
        lines = [clean_cell(line) for line in text.splitlines() if clean_cell(line)]
        for pattern in (r"^Insulation cock\b", r"^FLANGEABLE COCK\b", r"pressure gauge", r"manometer", r"manometro", r"compressor"):
            for line in lines:
                if re.search(pattern, line, re.I):
                    return line
        for i, line in enumerate(lines[:-1]):
            if line.upper() == "COCK":
                return f"{line} {lines[i + 1]}"
        for line in lines:
            if re.search(r"\bROBINET\b|\bCOCK\b|pressure gauge|manometer|manometro|compressor", line, re.I):
                return line
        return ""

    def _product_kind(self, text: str) -> str:
        if re.search(r"pressure gauge|manometer|manometro|manom[èe]tre|doppelmanometer", text, re.I):
            return "MANOMETER"
        if re.search(r"compressor|motocompressor|buran|typhoon", text, re.I):
            return "COMPRESSOR"
        if re.search(r"\bcock\b|robinet", text, re.I):
            return "COCK"
        return ""

    def _product_hierarchy(self, text: str, product_kind: str) -> tuple[str, str, str]:
        if product_kind == "MANOMETER":
            product_type = "B - DOUBLE POINTER" if re.search(r"duplex|double|doppelmanometer|2\s*(?:pointers?|aiguilles?)", text, re.I) else "A - SINGLE POINTER"
            return "D - MONITORING DEVICES", "D - MANOMETERS", product_type
        if product_kind == "COMPRESSOR":
            product_type = self._compressor_type(text)
            return "A - MOTOCOMPRESSOR", "A-BURAN COMPRESSOR", product_type
        if product_kind == "COCK":
            product_type = "X - FLANGED" if re.search(r"flange|flasqu", text, re.I) else "X - PIPE" if re.search(r"\bpipe\b|tube", text, re.I) else UNKNOWN
            return "B - AIR DISTRIBUTION AND MANAGEMENT", "B - ISOLATING COCKS", product_type
        return UNKNOWN, UNKNOWN, UNKNOWN

    def _compressor_type(self, text: str) -> str:
        if re.search(r"BURAN\s*20.*4P|20\s*4P", text, re.I):
            return "H - BURAN 20 4P"
        if re.search(r"BURAN\s*20.*6P|20\s*6P", text, re.I):
            return "G - BURAN 20 6P"
        if re.search(r"BURAN\s*10", text, re.I):
            return "F - BURAN 10 6P"
        if re.search(r"BURAN\s*8.*PSC|8.*PSC", text, re.I):
            return "E - BURAN 8 - PSC"
        if re.search(r"BURAN\s*8", text, re.I):
            return "D - BURAN 8"
        if re.search(r"BURAN\s*5L", text, re.I):
            return "C - BURAN 5L"
        if re.search(r"BURAN\s*5.*TOT|5.*TOT", text, re.I):
            return "B - BURAN 5 ToT"
        if re.search(r"BURAN\s*5", text, re.I):
            return "A - BURAN 5"
        return UNKNOWN

    def _extract_diameter(self, text: str, product_kind: str) -> str:
        if product_kind == "MANOMETER":
            match = re.search(r"(?:ø|Ø|DIAM(?:ETER)?\s*|PRESSURE\s+GAUGE\s+)(60|80|100)\b", text, re.I)
            return f"DIAMETER {match.group(1)}" if match else UNKNOWN
        match = re.search(r"\b(DN\s?\d+)\b", text, re.I)
        return f"PNEU DIAMETER {match.group(1).replace(' ', '')}" if match else UNKNOWN

    def _extract_pressure(self, text: str) -> str:
        explicit = self._first(r"(?:Maximum pressure|Pression maximum)[^\n:]*:?\s*([^\n]+)", text)
        if explicit:
            return explicit
        gauge_range = self._first(r"(?:INDICATING RANGE\s*)?(\d+\s*(?:-|÷|/|to)\s*\d+\s*bar)", text)
        if gauge_range:
            normalized = re.sub(r"\s+", "", gauge_range).replace("÷", "-").replace("TO", "-").replace("to", "-")
            return f"PRESS RANGE {normalized}"
        bourdon = self._first(r"(?:burdon|bourdon)[^\n]*?(\d+\s*bar)", text)
        if bourdon:
            bourdon_value = re.sub(r"\s+", "", bourdon)
            return f"PRESS RANGE 0-{bourdon_value}"
        return UNKNOWN

    def _extract_mounting(self, text: str) -> str:
        mounting = self._first(r"(MOUNTING\s*[^\n]+)", text)
        if mounting:
            return mounting.upper()
        angle = self._first(r"((?:\d{2}\s*°\s*(?:-|to|/)?\s*){1,2}(?:\([^\n]+\))?)", text)
        return f"MOUNTING {angle}".upper() if angle else UNKNOWN

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
