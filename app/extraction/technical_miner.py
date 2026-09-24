from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.utils.text import clean_cell


@dataclass(frozen=True)
class TechnicalCharacteristic:
    category: str
    name: str
    value: str
    evidence: str
    confidence: float


class TechnicalOntologyModel:
    """Tiny local TF-IDF model that classifies extracted drawing snippets."""

    ontology = {
        "dimension": "diameter dimension envelope length width height pitch hole slot section scale mm tolerance radius angle degree",
        "pressure": "pressure range working pressure full scale bar gauge pneumatic relief valve inlet outlet",
        "temperature": "temperature operating working start up ambient celsius nominal condition",
        "torque": "torque tightening couple serraggio nm threaded assembly screw nut bolt",
        "electrical": "voltage current power supply lamp led vac vdc watt ampere electrical absorbed consumption",
        "connection": "fitting connection inlet outlet gas thread m16 helicoil hose pipe raccordo anschluss",
        "mounting": "mounting installation fixation hanged ground panel u clamp position holes",
        "material": "material steel stainless aluminium brass copper graphite epdm ral color painted anodized",
        "standard": "standard iso en din uni nf norm acc according tolerance class",
        "weight": "weight peso kg mass",
        "performance": "duty cycle starts per hour cooling air flow free air delivery rpm motor rotation",
        "configuration": "configuration standard high humidity variant code reference",
        "protection": "protection ip fire smoke safety class blow out breather",
        "illumination": "illumination led lamp light voltage ba9s terminal",
    }

    def __init__(self) -> None:
        self.categories = list(self.ontology)
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode")
        self.matrix = self.vectorizer.fit_transform(self.ontology.values())

    def classify(self, text: str) -> tuple[str, float]:
        if not clean_cell(text):
            return "technical", 0.0
        vector = self.vectorizer.transform([text])
        scores = cosine_similarity(vector, self.matrix)[0]
        best_idx = int(scores.argmax())
        return self.categories[best_idx], float(scores[best_idx])


class TechnicalCharacteristicMiner:
    """Extracts broad technical facts from native PDF text using regex + local TF-IDF ranking."""

    max_rows_per_category = 45

    noise_terms = re.compile(
        r"technical specifications|standard features|writings height|schrift|font|caratteri|"
        r"main title|designed by|checked by|approved by|drawn by|document type|scale|sheet|"
        r"revision|rev\.|change|projection|tolerances unless|general tolerance|this drawing|"
        r"all rights reserved|cad model|do not scale",
        re.I,
    )

    def __init__(self) -> None:
        self.model = TechnicalOntologyModel()

    def extract(self, text: str) -> list[TechnicalCharacteristic]:
        lines = [clean_cell(line) for line in text.splitlines() if clean_cell(line)]
        full_text = "\n".join(lines)
        candidates: list[TechnicalCharacteristic] = []

        candidates.extend(self._known_label_patterns(full_text))
        candidates.extend(self._line_value_patterns(lines))
        candidates.extend(self._standards(lines))
        candidates.extend(self._materials(lines))
        candidates.extend(self._torque_rows(lines))
        candidates.extend(self._thread_rows(lines))
        candidates.extend(self._dimension_candidates(lines))
        candidates.extend(self._electrical_rows(lines))
        candidates.extend(self._pressure_temperature_rows(lines))

        return self._dedupe_and_limit(candidates)

    def _known_label_patterns(self, text: str) -> Iterable[TechnicalCharacteristic]:
        patterns = [
            ("pressure", "Working pressure", r"WORKING PRESSURE[\s\S]{0,90}?MAX\.?\s+(\d+(?:[,.]\d+)?\s*bar(?:\(g\))?)", 0.9),
            ("temperature", "Working temperature", r"WORKING TEMPERATURE[\s\S]{0,140}?FROM\s+(-?\d+\s*°?\s*C?[\s\S]{0,30}?TO\s+[+]?\d+\s*°?\s*C)", 0.88),
            ("temperature", "Startup temperature", r"START\s*UP\s+ALLOWED\s+FROM\s+(-?\d+\s*°?\s*C?\s+TO\s+[+]?\d+\s*°?\s*C)", 0.9),
            ("performance", "Duty cycle", r"DUTY CYCLE[\s\S]{0,120}?FROM\s+(\d+\s+.*?TO\s+\d+\s*%)", 0.86),
            ("performance", "Starts per hour", r"STARTS PER HOUR[\s\S]{0,50}?MAX\.?\s*(?:N°\s*)?(\d+)", 0.88),
            ("weight", "Weight standard", r"WEIGHT[\s\S]{0,120}?STANDARD CONFIGURATION\s+(\d+(?:[,.]\d+)?\s*kg)", 0.9),
            ("weight", "Weight high humidity", r"WEIGHT[\s\S]{0,150}?HIGH HUMIDITY CONFIGURATION\s+(\d+(?:[,.]\d+)?)(?:\s*kg)?", 0.86),
            ("performance", "Motor rotation speed", r"MOTOR ROTATION SPEED[\s\S]{0,120}?(\d+\s+\d+\s*rpm\s*±\s*\d+\s*%)", 0.82),
            ("performance", "Cooling air flow", r"COOLING AIR FLOW[\s\S]{0,120}?(\d+(?:[,.]\d+)?\s+\d+(?:[,.]\d+)?\s*m[³3]/s)", 0.82),
            ("performance", "Free air delivery", r"FREE AIR DELIVERY[\s\S]{0,140}?(\d+\s+\d+\s*1/min\s*±\s*\d+\s*%)", 0.82),
            ("electrical", "Electrical power consumption", r"ELECTRICAL POWER CONSUMPTION[\s\S]{0,140}?(\d+(?:[,.]\d+)?\s+\d+(?:[,.]\d+)?\s*kW\s*±\s*\d+\s*%)", 0.82),
            ("electrical", "Current consumption", r"CURRENT CONSUMPTION[\s\S]{0,140}?(\d+(?:[,.]\d+)?\s+\d+(?:[,.]\d+)?\s*A\s*±\s*\d+\s*%)", 0.82),
            ("electrical", "Electric power supply", r"ELECTRIC POWER SUPPLY[\s\S]{0,100}?(\d+\s+\d+\s*Vac\s*±\s*\d+\s*%)", 0.82),
            ("protection", "Protection degree", r"(IP\s*54[^\n]*)", 0.82),
            ("illumination", "Illumination", r"((?:DIRECT\s+)?ILLUMINATION[^\n]*(?:LED|LAMP)[^\n]*)", 0.78),
            ("mounting", "Installation", r"((?:INSTALLATION|INSTALLAZIONE|EINBAU)[^\n]*(?:\d{2}\s*°|VERTICAL|PANEL|U-CLAMP)[^\n]*)", 0.84),
        ]
        for category, name, pattern, confidence in patterns:
            for match in re.finditer(pattern, text, re.I):
                value = self._compact_value(match.group(1))
                yield TechnicalCharacteristic(category, name, value, self._snippet(text, match.start(), match.end()), confidence)

    def _line_value_patterns(self, lines: list[str]) -> Iterable[TechnicalCharacteristic]:
        label_terms = re.compile(
            r"pressure|temperature|weight|voltage|current|power|fitting|connection|diameter|class|"
            r"material|mounting|installation|illumination|flow|delivery|cycle|speed|protection|thread|torque",
            re.I,
        )
        value_terms = re.compile(
            r"\b\d+(?:[,.]\d+)?\s*(?:bar(?:\(g\))?|°C|kg|Nm|rpm|kW|Vac|Vdc|A|m[³3]/s|1/min|%)\b|"
            r"\b(?:M\d+(?:x\d+(?:[,.]\d+)?)?|G\d(?:/\d)?\"|IP\s*\d+|RAL\s*\d+|Ø\s*\d+|"
            r"\d+\s*[xX]\s*\d+(?:\s*[xX]\s*\d+)?)\b",
            re.I,
        )
        for idx, line in enumerate(lines):
            window_lines = lines[idx : min(len(lines), idx + 3)]
            source_line = next((item for item in window_lines if label_terms.search(item) and value_terms.search(item)), "")
            if not source_line:
                continue
            window = " | ".join(window_lines)
            if self._is_noise_window(source_line):
                continue
            values = value_terms.findall(source_line)
            if not values:
                continue
            category, score = self.model.classify(window)
            label = self._label_from_line(source_line)
            value = "; ".join(self._compact_value(v) for v in values[:6])
            yield TechnicalCharacteristic(category, label, value, source_line[:700], max(0.55, min(0.86, score + 0.45)))

    def _standards(self, lines: list[str]) -> Iterable[TechnicalCharacteristic]:
        pattern = re.compile(
            r"\b(?:DIN\s+EN\s+ISO|DIN\s+EN|UNI[-\s]?ISO|ISO|DIN|UNI)\s*[-\s]?\d[-A-Z0-9./:]*|"
            r"\bEN\s+(?:AW|AB)?\s*[-]?\s*\d[-A-Z0-9./:]*|"
            r"\bNF\s*E\s*\d[-A-Z0-9./:]*",
            re.I,
        )
        for line in lines:
            if self._is_noise_window(line):
                continue
            for match in pattern.finditer(line):
                value = self._compact_value(match.group(0).upper())
                if len(value) < 5:
                    continue
                yield TechnicalCharacteristic("standard", "Standard / norm", value, line, 0.72)

    def _materials(self, lines: list[str]) -> Iterable[TechnicalCharacteristic]:
        pattern = re.compile(
            r"\b(?:STAINLESS STEEL|ACCIAIO INOX|AC\.INOX|ALUMINIUM|ALLUMINIO|BRASS|CuSn8|"
            r"KLINGER GRAPHITE|CR-EPDM|EPDM|FLEXOID|PVC\+EPDM|X5CrNi18-10|RAL\s*\d{4})\b",
            re.I,
        )
        for line in lines:
            if self._is_noise_window(line) and not re.search(r"material|surface|finish|vernici|paint|color|colour", line, re.I):
                continue
            for match in pattern.finditer(line):
                yield TechnicalCharacteristic("material", "Material / finish", self._compact_value(match.group(0).upper()), line, 0.76)

    def _torque_rows(self, lines: list[str]) -> Iterable[TechnicalCharacteristic]:
        patterns = [
            re.compile(r"\b([A-L])\s+(\d+(?:[,.]\d+)?)\s*Nm\b", re.I),
            re.compile(r"\b([FR]\d{3})\s+(?:\d+\s+)?(?:CLASS\s+M\s+)?([MG]\d(?:/\d)?\"?(?:X\d+)?|3/8\"\s*B\.S\.W\.)?\s+(\d+(?:[,.]\d+)?)\s*Nm\b", re.I),
        ]
        for line in lines:
            for pattern in patterns:
                for match in pattern.finditer(line):
                    if len(match.groups()) == 2:
                        ref, torque = match.groups()
                        value = f"{ref.upper()} {torque.replace(',', '.')} Nm"
                    else:
                        ref, thread, torque = match.groups()
                        value = f"{ref.upper()} {self._compact_value(thread or '').upper()} {torque.replace(',', '.')} Nm".strip()
                    yield TechnicalCharacteristic("torque", f"Torque {value.split()[0]}", value, line, 0.86)

    def _thread_rows(self, lines: list[str]) -> Iterable[TechnicalCharacteristic]:
        pattern = re.compile(r"\b(?:M\d+(?:x\d+(?:[,.]\d+)?)?|G\d(?:/\d)?\"|3/8\"\s*B\.S\.W\.|M16x1[,.]5)\b", re.I)
        for line in lines:
            if not re.search(r"thread|fitting|connection|helicoil|screw|nut|raccordo|anschluss|gas", line, re.I):
                continue
            for match in pattern.finditer(line):
                yield TechnicalCharacteristic("connection", "Thread / fitting", self._compact_value(match.group(0).upper()).replace(",", "."), line, 0.76)

    def _dimension_candidates(self, lines: list[str]) -> Iterable[TechnicalCharacteristic]:
        pattern = re.compile(r"\b(?:Ø\s*)?\d+(?:[,.]\d+)?(?:\s*[xX]\s*\d+(?:[,.]\d+)?){1,2}\b|\b\d+(?:[,.]\d+)?\s*(?:±\s*\d+(?:[,.]\d+)?)?\s*mm\b", re.I)
        for line in lines:
            if self._is_noise_window(line):
                continue
            if not re.search(r"diameter|dimension|height|slot|section|detail|envelope|hole|lug|thickness|length|width|mm|Ø", line, re.I):
                continue
            for match in pattern.finditer(line):
                value = self._compact_value(match.group(0))
                if self._looks_like_font_size(value, line):
                    continue
                yield TechnicalCharacteristic("dimension", "Dimension candidate", value, line, 0.62)

    def _electrical_rows(self, lines: list[str]) -> Iterable[TechnicalCharacteristic]:
        pattern = re.compile(
            r"\b\d+(?:[,.]\d+)?\s*(?:Vac|Vdc|V|A|kW|W)\b(?:\s*[±+-]\s*\d+\s*%)?|\bIP\s*\d{2}\b",
            re.I,
        )
        for line in lines:
            if self._is_noise_window(line):
                continue
            if not re.search(r"electric|electrical|voltage|current|power|supply|consumption|motor|lamp|led|ip|protection", line, re.I):
                continue
            for match in pattern.finditer(line):
                raw = self._compact_value(match.group(0))
                category = "protection" if raw.upper().startswith("IP") else "electrical"
                name = "Protection degree" if category == "protection" else "Electrical rating"
                yield TechnicalCharacteristic(category, name, raw, line, 0.74)

    def _pressure_temperature_rows(self, lines: list[str]) -> Iterable[TechnicalCharacteristic]:
        pattern = re.compile(
            r"\b-?\d+(?:[,.]\d+)?\s*°?\s*C\b|"
            r"\b\d+(?:[,.]\d+)?\s*bar(?:\(g\))?\b|"
            r"\b\d+(?:[,.]\d+)?\s*(?:l/min|1/min|m[³3]/s|rpm)\b",
            re.I,
        )
        for line in lines:
            if self._is_noise_window(line):
                continue
            if not re.search(r"temperature|pressure|delivery|flow|speed|rpm|working|startup|ambient|range", line, re.I):
                continue
            for match in pattern.finditer(line):
                value = self._compact_value(match.group(0))
                category, score = self.model.classify(line)
                if category not in {"temperature", "pressure", "performance"}:
                    category = "temperature" if re.search(r"°?\s*C\b", value, re.I) else "pressure" if "bar" in value.lower() else "performance"
                yield TechnicalCharacteristic(category, category.title(), value, line, max(0.68, min(0.84, score + 0.45)))

    def _dedupe_and_limit(self, rows: list[TechnicalCharacteristic]) -> list[TechnicalCharacteristic]:
        deduped: dict[tuple[str, str, str], TechnicalCharacteristic] = {}
        for row in rows:
            if not self._is_useful(row):
                continue
            key = (row.category, row.name, row.value.upper())
            existing = deduped.get(key)
            if not existing or row.confidence > existing.confidence:
                deduped[key] = row

        category_counts: dict[str, int] = {}
        limited: list[TechnicalCharacteristic] = []
        for row in sorted(deduped.values(), key=lambda item: (-item.confidence, item.category, item.name, item.value)):
            count = category_counts.get(row.category, 0)
            if count >= self.max_rows_per_category:
                continue
            category_counts[row.category] = count + 1
            limited.append(row)
        return sorted(limited, key=lambda item: (item.category, item.name, item.value))

    def _label_from_line(self, line: str) -> str:
        if re.search(r"working pressure", line, re.I):
            return "Working pressure"
        if re.search(r"working temperature|operating temperature", line, re.I):
            return "Working temperature"
        if re.search(r"electric power supply", line, re.I):
            return "Electric power supply"
        if re.search(r"current consumption", line, re.I):
            return "Current consumption"
        if re.search(r"electrical power consumption", line, re.I):
            return "Electrical power consumption"
        if re.search(r"protection|degree of protection", line, re.I):
            return "Protection degree"
        label = re.sub(r"[:\-]*\s*\d.*$", "", line).strip()
        label = label[:70] if label else "Technical value"
        return self._compact_value(label.title())

    def _compact_value(self, value: str) -> str:
        return re.sub(r"\s+", " ", clean_cell(value)).strip(" ;|")

    def _snippet(self, text: str, start: int, end: int) -> str:
        return self._compact_value(text[max(0, start - 180) : min(len(text), end + 180)])[:700]

    def _is_noise_window(self, text: str) -> bool:
        if not self.noise_terms.search(text):
            return False
        return not re.search(
            r"pressure|temperature|voltage|current|power|material|finish|weight|torque|"
            r"connection|fitting|mounting|installation|protection|illumination|dimension|slot|hole",
            text,
            re.I,
        )

    def _looks_like_font_size(self, value: str, evidence: str) -> bool:
        if re.search(r"font|writings height|schrift|caratteri", evidence, re.I):
            return True
        match = re.fullmatch(r"(\d+(?:[,.]\d+)?)\s*mm", value, re.I)
        return bool(match and float(match.group(1).replace(",", ".")) < 6)

    def _is_useful(self, row: TechnicalCharacteristic) -> bool:
        value = self._compact_value(row.value)
        if not value or value.upper() in {"M3", "M4", "M5"} and row.category not in {"connection", "mounting"}:
            return False
        if len(value) < 2:
            return False
        if self._is_noise_window(row.evidence) and row.confidence < 0.84:
            return False
        if row.category == "dimension" and self._looks_like_font_size(value, row.evidence):
            return False
        if row.category == "material" and re.fullmatch(
            r"(?:M\d+(?:X\d+(?:[,.]\d+)?)?|\d+(?:[,.]\d+)?\s*bar|IP\s*\d+|"
            r"\d+(?:[,.]\d+)?\s*(?:°C|kg|Nm|rpm|kW|Vac|Vdc|A|%))",
            value,
            re.I,
        ):
            return False
        if row.category == "electrical" and re.search(r"\bbar\b|°\s*C|kg|Nm|rpm|m[³3]/s|1/min", value, re.I):
            return False
        if row.category == "pressure" and not re.search(r"\bbar(?:\(g\))?\b|PRESS RANGE|pressure", value, re.I):
            return False
        if row.category == "temperature" and not re.search(r"°?\s*C\b|temperature", value, re.I):
            return False
        if row.category == "performance" and re.fullmatch(r"\d+(?:[,.]\d+)?\s*bar(?:\(g\))?", value, re.I):
            return False
        if row.category == "protection" and not re.search(r"\bIP\s*\d{2}\b|protection", value, re.I):
            return False
        if row.category == "mounting" and re.fullmatch(r"M\d+(?:X\d+(?:[,.]\d+)?)?", value, re.I):
            return False
        if row.name.startswith("-") and row.confidence < 0.86:
            return False
        if row.category == "standard" and re.fullmatch(r"(?:EN|DIN|ISO|UNI)\s*\d{1,2}", value, re.I):
            return False
        if re.search(r"^(?:page|sheet|scale|rev|date|name)\b", row.name, re.I):
            return False
        return True
