from __future__ import annotations

import re
from pathlib import Path

from app.models.domain import Evidence, NOT_FOUND, UNKNOWN
from app.extraction.technical_miner import TechnicalCharacteristicMiner
from app.utils.text import clean_cell, compact_unique, normalize_part_number


class CharacteristicExtractor:
    """Deterministic local extraction for drawing metadata and catalogue attributes."""

    def __init__(self) -> None:
        self.technical_miner = TechnicalCharacteristicMiner()

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

        revision = self._revision_from_filename(pdf_path) or self._drawing_revision(full_text)
        fields["Drawing revision"] = revision or NOT_FOUND
        if revision:
            evidence.append(self._ev("Drawing revision", revision, pdf_path, self._page_of(page_text, revision), revision, 0.86, "title_block_pattern"))

        product_line = self._title_line(full_text)
        fields["Drawing title"] = clean_cell(product_line) or UNKNOWN
        if product_line:
            evidence.append(self._ev("Drawing title", clean_cell(product_line), pdf_path, self._page_of(page_text, product_line), product_line, 0.88, "native_pdf_text"))

        product_kind = self._product_kind(full_text)
        fields["Configuration"] = self._extract_configuration(full_text, drawing or "")
        fields["Status"] = "Released" if re.search(r"\bStatus\s+RELEASED\b|\bRELEASED\b", full_text, re.I) else UNKNOWN

        diameter = self._extract_diameter(full_text, product_kind)
        fields["Diameter"] = diameter
        if diameter:
            evidence.append(self._ev("Diameter", fields["Diameter"], pdf_path, self._page_of(page_text, diameter), diameter, 0.93, "engineering_term_pattern"))

        contact = self._extract_contacts(full_text)
        fields["Contact"] = contact
        if contact != UNKNOWN:
            evidence.append(self._ev("Contact", contact, pdf_path, self._page_of(page_text, contact.split()[0]), self._line_around(full_text, r"(?:\d+\s*(?:cts|CONTACTS?|SWITCH(?:E|ES)?))"), 0.82, "engineering_term_pattern"))

        fields["Product Family"], fields["Product Name"], fields["Product Type"] = self._product_hierarchy(full_text, product_kind)

        fields["Pressure"] = self._extract_pressure(full_text, product_kind)
        if fields["Pressure"] != UNKNOWN:
            evidence.append(self._ev("Pressure", fields["Pressure"], pdf_path, self._page_of(page_text, fields["Pressure"]), fields["Pressure"], 0.86, "note_pattern"))

        temp = self._extract_temperature(full_text)
        fields["Temperature"] = temp or UNKNOWN
        if temp:
            evidence.append(self._ev("Temperature", temp, pdf_path, self._page_of(page_text, temp), temp, 0.85, "note_pattern"))

        fields["Foolproofing"] = self._extract_foolproofing(full_text)
        fields["Drain"] = self._extract_drain(full_text)
        fields["Handle"] = self._extract_handle(full_text)
        fields["Handle colour"] = self._extract_colour(full_text)
        fields["Connector"] = "ISO BASE" if re.search(r"ISO BASE|EMBASE ISO", full_text, re.I) else UNKNOWN
        fields["Connector orientation"] = "NEEDS REVIEW" if re.search(r"orientation", full_text, re.I) else UNKNOWN
        fields["Weight"] = self._extract_weight(full_text, fields["Configuration"])
        fields["LED"] = "WITH LED" if re.search(r"\bLED\b", full_text, re.I) else UNKNOWN
        fields["Mounting"] = self._extract_mounting(full_text)
        fields["Fitting"] = self._extract_fitting(full_text, product_kind)
        fields["Accuracy class"] = self._extract_accuracy_class(full_text)
        fields["Earth lug"] = self._extract_earth_lug(full_text)
        fields["Outlet connection"] = self._extract_outlet_connection(full_text)
        fields["Envelope dimensions"] = self._extract_envelope_dimensions(full_text)
        fields["Mounting holes"] = self._extract_mounting_holes(full_text)
        fields["Key slot"] = self._extract_key_slot(full_text)
        fields["Working pressure"] = self._extract_working_pressure(full_text)
        fields["Working temperature"] = self._extract_working_temperature(full_text)
        fields["Startup temperature"] = self._extract_startup_temperature(full_text)
        fields["Duty cycle"] = self._extract_duty_cycle(full_text)
        fields["Starts per hour"] = self._extract_starts_per_hour(full_text)
        fields["Compressor detail"] = self._extract_compressor_detail(full_text)

        for field in (
            "Fitting",
            "Accuracy class",
            "Earth lug",
            "Weight",
            "Outlet connection",
            "Envelope dimensions",
            "Mounting holes",
            "Key slot",
            "Working pressure",
            "Working temperature",
            "Startup temperature",
            "Duty cycle",
            "Starts per hour",
            "Compressor detail",
        ):
            value = fields.get(field, "")
            if value and value != UNKNOWN:
                evidence.append(self._ev(field, value, pdf_path, self._page_of(page_text, value), self._evidence_line(full_text, value), 0.82, "technical_characteristic_pattern"))

        for idx, characteristic in enumerate(self.technical_miner.extract(full_text), start=1):
            field_key = f"Technical characteristic|{characteristic.category}|{characteristic.name}|{idx:03d}"
            fields[field_key] = characteristic.value
            evidence.append(
                self._ev(
                    f"Technical characteristic: {characteristic.category} / {characteristic.name}",
                    characteristic.value,
                    pdf_path,
                    self._page_of(page_text, characteristic.evidence or characteristic.value),
                    characteristic.evidence,
                    characteristic.confidence,
                    "technical_miner_tfidf",
                )
            )

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

    def _revision_from_filename(self, pdf_path: Path) -> str:
        stem = pdf_path.stem.upper()
        match = re.search(r"_([A-Z]\d{2}|[A-Z]{2}\d{2}|L\d{2})(?:_|$)", stem)
        return match.group(1) if match else ""

    def _drawing_revision(self, text: str) -> str:
        codes = [
            code
            for code in re.findall(r"\b([A-Z]{1,2}\d{2})\b", text)
            if not re.match(r"^(IP|RAL|M|L)\d", code, re.I)
        ]
        if not codes:
            return ""
        ranking = sorted(set(codes), key=lambda code: (code[0], int(code[1:]) if code[1:].isdigit() else -1))
        return ranking[-1]

    def _title_line(self, text: str) -> str:
        lines = [clean_cell(line) for line in text.splitlines() if clean_cell(line)]
        for pattern in (r"^Insulation cock\b", r"^FLANGEABLE COCK\b", r"pressure gauge", r"manometer", r"manometro", r"compressor"):
            for line in lines:
                if re.search(pattern, line, re.I) and not re.search(r"is suitable to operate", line, re.I):
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
        if re.search(r"\bTYPE\s*20\b", text, re.I):
            return "H - BURAN 20 4P"
        standard_block = self._standard_configuration_block(text)
        if re.search(r"BURAN\s*20.*4P|20\s*4P", standard_block, re.I):
            return "H - BURAN 20 4P"
        if re.search(r"BURAN\s*20.*6P|20\s*6P", standard_block, re.I):
            return "G - BURAN 20 6P"
        if re.search(r"BURAN\s*10", standard_block, re.I):
            return "F - BURAN 10 6P"
        if re.search(r"BURAN\s*8.*PSC|8.*PSC", standard_block, re.I):
            return "E - BURAN 8 - PSC"
        if re.search(r"BURAN\s*8", standard_block, re.I):
            return "D - BURAN 8"
        if re.search(r"BURAN\s*5L", standard_block, re.I):
            return "C - BURAN 5L"
        if re.search(r"BURAN\s*5.*TOT|5.*TOT", standard_block, re.I):
            return "B - BURAN 5 ToT"
        if re.search(r"BURAN\s*5", standard_block, re.I):
            return "A - BURAN 5"
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

    def _standard_configuration_block(self, text: str) -> str:
        lines = [clean_cell(line) for line in text.splitlines() if clean_cell(line)]
        chunks: list[str] = []
        for i, line in enumerate(lines):
            if re.search(r"CONFIGURAZIONE STANDARD|STANDARD CONFIGURATION", line, re.I):
                chunks.extend(lines[max(0, i - 12) : i + 18])
        return "\n".join(chunks)

    def _extract_configuration(self, text: str, drawing: str) -> str:
        if not drawing:
            return UNKNOWN
        lines = [clean_cell(line) for line in text.splitlines() if clean_cell(line)]
        for i, line in enumerate(lines):
            if normalize_part_number(line) != drawing:
                continue
            local_after = "\n".join(lines[i : i + 4])
            local_before = "\n".join(lines[max(0, i - 4) : i + 1])
            if re.search(r"CONFIGURAZIONE\s+STANDARD|STANDARD\s+CONFIGURATION", f"{local_before}\n{local_after}", re.I):
                return "STANDARD CONFIGURATION"
            if re.search(r"ALTA\s+UMIDITA|HIGH\s+HUMIDITY", f"{local_before}\n{local_after}", re.I):
                return "HIGH HUMIDITY CONFIGURATION"
        if re.search(rf"{re.escape(drawing)}[\s\S]{{0,80}}(?:CONFIGURAZIONE\s+STANDARD|STANDARD\s+CONFIGURATION)", text, re.I):
            return "STANDARD CONFIGURATION"
        if re.search(rf"{re.escape(drawing)}[\s\S]{{0,80}}(?:ALTA\s+UMIDITA|HIGH\s+HUMIDITY)", text, re.I):
            return "HIGH HUMIDITY CONFIGURATION"
        return UNKNOWN

    def _extract_diameter(self, text: str, product_kind: str) -> str:
        if product_kind == "MANOMETER":
            match = re.search(r"(?:ø|Ø|DIAM(?:ETER)?\s*|PRESSURE\s+GAUGE\s+)(60|80|100)\b", text, re.I)
            return f"DIAMETER {match.group(1)}" if match else UNKNOWN
        match = re.search(r"\b(DN\s?\d+)\b", text, re.I)
        return f"PNEU DIAMETER {match.group(1).replace(' ', '')}" if match else UNKNOWN

    def _extract_pressure(self, text: str, product_kind: str) -> str:
        if product_kind != "MANOMETER":
            return UNKNOWN
        explicit = self._first(r"(?:Maximum pressure|Pression maximum)[^\n:]*:?\s*([^\n]+)", text)
        if explicit:
            return explicit
        gauge_range = self._first(r"(?:INDICATING RANGE\s*)?(\d+\s*(?:-|÷|/|to)\s*\d+\s*bar)", text)
        if gauge_range:
            return f"PRESS RANGE {self._normalize_pressure_value(gauge_range)} bar"
        scale_range = self._first(r"(?:SCALA|SCALE)\s*(\d+\s*(?:-|÷|/|to)\s*\d+)", text)
        if scale_range:
            return f"PRESS RANGE {self._normalize_pressure_value(scale_range)} bar"
        table_range = self._pressure_from_code_table(text)
        if table_range:
            return f"PRESS RANGE 0-{table_range} bar"
        bourdon = self._first(r"(?:burdon|bourdon)[^\n]*?(\d+\s*bar)", text)
        if bourdon:
            bourdon_value = re.sub(r"\s+", "", bourdon)
            return f"PRESS RANGE 0-{bourdon_value}"
        return UNKNOWN

    def _extract_temperature(self, text: str) -> str:
        for pattern in (
            r"(?:Operating temperature|Temp[ée]rature de fonctionnement)\s*:?\s*([^\n]+)",
            r"-\s*OPERATING TEMPERATURE\s+([^\n]+)",
            r"-\s*BETRIEBSTEMPERATUR\s+([^\n]+)",
        ):
            value = self._first(pattern, text)
            if value and re.search(r"\d+\s*°\s*C", value, re.I):
                return value
        return UNKNOWN

    def _extract_working_temperature(self, text: str) -> str:
        direct = self._extract_temperature(text)
        if direct != UNKNOWN:
            return direct
        match = re.search(r"WORKING TEMPERATURE[\s\S]{0,120}?FROM\s+(-?\d+)\s*°?\s*C?[\s\S]{0,40}?TO\s+([+]?\d+)\s*°?\s*C", text, re.I)
        if match:
            return f"{match.group(1)} °C to {match.group(2)} °C"
        return UNKNOWN

    def _extract_startup_temperature(self, text: str) -> str:
        match = re.search(r"START\s*UP\s+ALLOWED\s+FROM\s+(-?\d+)\s*°?\s*C?\s+TO\s+([+]?\d+)\s*°?\s*C", text, re.I)
        if match:
            return f"START UP {match.group(1)} °C to {match.group(2)} °C"
        return UNKNOWN

    def _extract_working_pressure(self, text: str) -> str:
        match = re.search(r"WORKING PRESSURE[\s\S]{0,80}?MAX\.?\s+(\d+(?:[,.]\d+)?)\s*bar", text, re.I)
        if match:
            return f"WORKING PRESSURE {match.group(1).replace(',', '.')} bar(g)"
        return UNKNOWN

    def _extract_duty_cycle(self, text: str) -> str:
        match = re.search(r"DUTY CYCLE[\s\S]{0,100}?FROM\s+(\d+)\s+.*?TO\s+(\d+)\s*%", text, re.I)
        if match:
            return f"DUTY CYCLE {match.group(1)}-{match.group(2)}%"
        direct = self._first(r"(DC\s*\d+\s*-\s*\d+%)", text)
        return direct.upper().replace(" ", "") if direct else UNKNOWN

    def _extract_starts_per_hour(self, text: str) -> str:
        match = re.search(r"STARTS PER HOUR[\s\S]{0,40}?MAX\.?\s*(?:N°\s*)?(\d+)", text, re.I)
        if match:
            return f"MAX {match.group(1)} STARTS/HOUR"
        return UNKNOWN

    def _normalize_pressure_value(self, value: str) -> str:
        normalized = re.sub(r"\s+", "", value).replace("÷", "-").replace("TO", "-").replace("to", "-")
        normalized = normalized.replace("bar", "")
        return normalized

    def _pressure_from_code_table(self, text: str) -> str:
        lines = [clean_cell(line) for line in text.splitlines() if clean_cell(line)]
        for i, line in enumerate(lines):
            if re.fullmatch(r"FT\d{7}-\d{3}", line, re.I):
                window = lines[i + 1 : i + 8]
                numbers = [token for token in window if re.fullmatch(r"\d{1,3}", token)]
                if len(numbers) >= 2:
                    return numbers[1]
        return ""

    def _extract_mounting(self, text: str) -> str:
        installation = self._first(r"(?:Installation position|Installation|Installazione|Einbau)\s*:?\s*([^\n]+)", text)
        if installation:
            normalized = self._normalize_mounting_angle(installation)
            if normalized:
                return normalized
        mounting = self._first(r"(MOUNTING\s*[^\n]+)", text)
        if mounting and not re.search(r"WATER SEPARATOR", mounting, re.I):
            return mounting.upper()
        angle = self._first(r"((?:\d{2}\s*°\s*(?:-|to|/)?\s*){1,2}(?:\([^\n]+\))?)", text)
        return f"MOUNTING {angle}".upper() if angle else UNKNOWN

    def _normalize_mounting_angle(self, text: str) -> str:
        angle = self._first(r"(\d{2}\s*°?\s*(?:-|÷|to)\s*\d{2}\s*°?)", text)
        single = self._first(r"(\d{2}\s*°(?:\s*\+\d+°/-\d+°)?)", text)
        adjustment = self._first(r"(?:adjustment|Einstellung)\s*(\d{2}\s*°)", text)
        value = angle or single
        if not value:
            return ""
        value = value.replace("÷", "-")
        value = re.sub(r"\s+", " ", value).strip()
        value = re.sub(r"(\d{2})(?!\s*°)", r"\1°", value)
        value = value.replace("°-", "° - ").replace("- ", "- ")
        if adjustment:
            return f"MOUNTING {value} (Adjustment {adjustment.replace(' ', '')})"
        return f"MOUNTING {value}"

    def _extract_fitting(self, text: str, product_kind: str) -> str:
        if product_kind == "MANOMETER":
            match = re.search(r"\b(One|Two|\d+|2\s+STCK\.?)[ \t]+(?:FITTINGS?[ \t]+)?M16x1[,.]5(?:[ \t]+(?:GEM\.|ACCORDING TO|ACC\.)[ \t]+[A-Z0-9.,/ \t-]+)?", text, re.I)
            if match:
                value = clean_cell(match.group(0)).upper().replace("STCK.", "FITTINGS").replace(",", ".")
                value = re.sub(r"\s+", " ", value)
                return value
        fitting = self._first(r"\b(\d(?:/\d)?\"\s*GAS\s+UNI-ISO\s+228)\b", text)
        return fitting.upper() if fitting else UNKNOWN

    def _extract_accuracy_class(self, text: str) -> str:
        match = re.search(r"(?:ACCURACY\s+)?CLASS\s+(\d[,.]\d+)", text, re.I)
        if match:
            return f"CLASS {match.group(1).replace(',', '.')}"
        return UNKNOWN

    def _extract_earth_lug(self, text: str) -> str:
        match = re.search(r"Earth Lug\s+With Hole\s+(\d+)", text, re.I)
        if match:
            return f"EARTH LUG HOLE {match.group(1)}"
        return UNKNOWN

    def _extract_outlet_connection(self, text: str) -> str:
        lines = [clean_cell(line) for line in text.splitlines() if clean_cell(line)]
        for i, line in enumerate(lines):
            if re.search(r"COMPRESSED AIR OUTLET|USCITA ARIA COMPRESSA", line, re.I):
                window = lines[i : i + 5]
                for item in window:
                    if re.search(r"\b\d(?:/\d)?\"\s*GAS\s+UNI-ISO\s+228\b", item, re.I):
                        return f"OUTLET {item.upper()}"
        return UNKNOWN

    def _extract_envelope_dimensions(self, text: str) -> str:
        lines = [clean_cell(line) for line in text.splitlines() if clean_cell(line)]
        for i, line in enumerate(lines):
            if re.search(r"AFTER COOLER|INTER COOLER", line, re.I):
                values: list[float] = []
                for item in lines[i : i + 14]:
                    if re.fullmatch(r"\d{2,4}", item):
                        value = float(item)
                        if value >= 100:
                            values.append(value)
                unique: list[float] = []
                for value in values:
                    if value not in unique:
                        unique.append(value)
                if len(unique) >= 3:
                    dims = unique[:3]
                    return "ENVELOPE " + " x ".join(self._format_number(v) for v in dims) + " mm"
        for i, line in enumerate(lines):
            if re.search(r"COMPRESSED AIR OUTLET|USCITA ARIA COMPRESSA", line, re.I):
                values: list[float] = []
                for item in lines[max(0, i - 18) : i]:
                    if re.fullmatch(r"\d{2,4}(?:[,.]\d+)?", item):
                        value = float(item.replace(",", "."))
                        if value >= 100:
                            values.append(value)
                unique: list[float] = []
                for value in values:
                    if value not in unique:
                        unique.append(value)
                if len(unique) >= 4:
                    dims = [unique[0], unique[2], unique[3]]
                    return "ENVELOPE " + " x ".join(self._format_number(v) for v in dims) + " mm"
        return UNKNOWN

    def _extract_mounting_holes(self, text: str) -> str:
        match = re.search(r"(N[°º]\s*4\s+(?:M8\s+HELICOIL|HELI-COILS?\s+M10|HELICOIL\s+M8))", text, re.I)
        if match:
            value = clean_cell(match.group(1)).upper().replace("HELI-COILS", "HELICOILS")
            return re.sub(r"\s+", " ", value)
        return UNKNOWN

    def _extract_key_slot(self, text: str) -> str:
        match = re.search(r"PARALLEL KEY SLOT[\s\S]{0,80}?(\d+\s*[xX]\s*\d+\s*[xX]\s*\d+)", text, re.I)
        if match:
            return f"KEY SLOT {match.group(1).replace(' ', '').upper()}"
        return UNKNOWN

    def _extract_weight(self, text: str, configuration: str) -> str:
        if re.search(r"See bom", text, re.I):
            return "See bom"
        if configuration == "HIGH HUMIDITY CONFIGURATION":
            match = re.search(r"HIGH HUMIDITY CONFIGURATION\s+(\d+(?:[,.]\d+)?)\s*(?:kg)?", text, re.I)
            if match:
                return f"WEIGHT {match.group(1).replace(',', '.')} kg"
        match = re.search(r"WEIGHT[\s\S]{0,100}?STANDARD CONFIGURATION\s+(\d+(?:[,.]\d+)?)\s*kg", text, re.I)
        if match:
            return f"WEIGHT {match.group(1).replace(',', '.')} kg"
        match = re.search(r"\b(\d+(?:[,.]\d+)?)\s*kg\b", text, re.I)
        if match:
            return f"WEIGHT {match.group(1).replace(',', '.')} kg"
        return UNKNOWN

    def _extract_compressor_detail(self, text: str) -> str:
        detail = self._first(r"\b(TYPE\s+\d+\s*-\s*\d+°)", text)
        if detail:
            return detail.upper()
        buran = self._first(r"\b(BURAN\s+\d+[A-Z]?)\b", text)
        return buran.upper() if buran else UNKNOWN

    def _format_number(self, value: float) -> str:
        return str(int(value)) if value.is_integer() else str(value).replace(".", ",")

    def _evidence_line(self, text: str, value: str) -> str:
        token = value.split(" ", 1)[-1].split(";")[0].strip()
        token = token.replace("WEIGHT ", "").replace("OUTLET ", "").replace("ENVELOPE ", "")
        for line in text.splitlines():
            if token and token.lower() in line.lower():
                return line
        return value

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
