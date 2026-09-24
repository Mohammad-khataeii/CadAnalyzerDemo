from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Iterable

import fitz

from app.engineering.model import (
    AssemblyRecord,
    BOMItem,
    ComponentRecord,
    ConnectionRecord,
    Dimension,
    DrawingReference,
    DrawingView,
    EngineeringDocument,
    EngineeringNote,
    EngineeringTable,
    ExtractionSource,
    FastenerRecord,
    IdentificationRecord,
    MaterialRecord,
    PageInspection,
    RawExtraction,
    RevisionEvent,
    SchematicRecord,
    StandardRecord,
    TechnicalParameter,
    TorqueRequirement,
    VariantRecord,
)
from app.utils.text import clean_cell, normalize_part_number


class EngineeringDocumentExtractor:
    """Native-PDF-first generic engineering entity extractor."""

    standard_pattern = re.compile(
        r"\b(?:DIN\s+EN\s+ISO|DIN\s+EN|UNI[-\s]?ISO|ISO|DIN|UNI|EN|NF\s*E)\s*[-\s]?[A-Z]{0,3}\s*\d[-A-Z0-9./:]*",
        re.I,
    )
    material_pattern = re.compile(
        r"\b(?:STAINLESS STEEL|ACCIAIO INOX|AC\.INOX|ALUMINIUM|ALLUMINIO|BRASS|CuSn8|"
        r"X5CrNi18-10|AC42100\s*T6|AW\s*6060\s*T6|C40\s*E|DX51D\+Z|CR-EPDM|EPDM|"
        r"KLINGER GRAPHITE|FLEXOID|PVC\+EPDM|RAL\s*\d{4})\b",
        re.I,
    )
    thread_pattern = re.compile(r"\b(M\d+(?:[xX]\d+(?:[,.]\d+)?)?|G\d(?:/\d)?\"|[13]/[24]\"\s*GAS|3/8\"\s*B\.S\.W\.)\b", re.I)

    parameter_units = (
        "bar(g)",
        "bar",
        "°C",
        "rpm",
        "kW",
        "Vac",
        "Vdc",
        "V",
        "A",
        "m³/s",
        "m3/s",
        "1/min",
        "l/min",
        "kg",
        "%",
        "Nm",
        "W",
    )

    part_number_pattern = re.compile(r"FT\d{7}-\d{3}|\b\d/\d{6}\b|\b\d{3}\s?\d{3}\s?\d{2}\s?\d{2}\b", re.I)
    revision_pattern = re.compile(r"\b(?:REV(?:ISION)?\.?\s*)?([A-Z]\d{2}|[A-Z]{2}\d{2}|L\d{2}|[A-Z]{1,2})\b", re.I)

    def __init__(self) -> None:
        self._current_bboxes: dict[str, tuple[float, float, float, float]] = {}
        self._current_bbox_items: list[tuple[str, tuple[float, float, float, float]]] = []
        self._ocr_available = self._detect_ocr()

    def extract(self, path: Path, doc: fitz.Document, page_text: dict[int, str]) -> EngineeringDocument:
        engineering = EngineeringDocument(source_pdf=path.name, page_count=doc.page_count, ocr_available=self._ocr_available)
        page_lines = {page: [clean_cell(line) for line in text.splitlines() if clean_cell(line)] for page, text in page_text.items()}
        for page_number in range(1, doc.page_count + 1):
            page = doc[page_number - 1]
            text = page_text.get(page_number, "")
            inspection = self._inspect_page(page_number, page, text)
            engineering.inspections.append(inspection)
            text_items = self._text_items(page)
            self._set_current_bboxes(text_items)
            lines = page_lines.get(page_number, [])
            ocr_lines = self._ocr_lines(path.name, page_number, page, inspection)
            if ocr_lines:
                engineering.ocr_used = True
                lines = [*lines, *ocr_lines]
            engineering.raw_data.extend(self._raw_extractions(page_number, lines, text_items, bool(ocr_lines)))
            if self._table_candidate(lines):
                engineering.tables.extend(self._tables(path.name, page_number, page))
            engineering.dimensions.extend(self._dimensions(path.name, page_number, lines))
            engineering.parameters.extend(self._parameters(path.name, page_number, lines))
            engineering.materials.extend(self._materials(path.name, page_number, lines))
            engineering.standards.extend(self._standards(path.name, page_number, lines))
            engineering.bom_items.extend(self._bom_items(path.name, page_number, lines))
            engineering.bom_items.extend(self._bom_from_tables(path.name, engineering.tables, page_number))
            engineering.torque_requirements.extend(self._torque(path.name, page_number, lines))
            engineering.revisions.extend(self._revisions(path.name, page_number, lines))
            engineering.drawing_views.extend(self._views(path.name, page_number, lines))
            engineering.drawing_references.extend(self._references(path.name, page_number, lines))
            engineering.drawing_references.extend(self._visual_references(path.name, page_number, text_items))
            engineering.components.extend(self._components(path.name, page_number, lines))
            engineering.assemblies.extend(self._assemblies(path.name, page_number, lines))
            engineering.fasteners.extend(self._fasteners(path.name, page_number, lines))
            engineering.variants.extend(self._variants(path.name, page_number, lines))
            engineering.schematics.extend(self._schematics(path.name, page_number, lines))
            engineering.identifications.extend(self._identifications(path.name, page_number, lines))
            engineering.notes.extend(self._notes(path.name, page_number, lines))
            engineering.connections.extend(self._connections(path.name, page_number, lines))
        self._dedupe(engineering)
        engineering.warnings.extend(self._validate(engineering))
        return engineering

    def _detect_ocr(self) -> bool:
        if not shutil.which("tesseract"):
            return False
        try:
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
        except Exception:
            return False
        return True

    def _text_items(self, page: fitz.Page) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        try:
            raw = page.get_text("dict")
        except Exception:
            return items
        for block in raw.get("blocks", []):
            if block.get("type", 0) != 0:
                continue
            for line in block.get("lines", []):
                text = self._compact(" ".join(span.get("text", "") for span in line.get("spans", [])))
                if not text:
                    continue
                items.append({"text": text, "bbox": self._bbox_tuple(line.get("bbox"))})
        return items

    def _set_current_bboxes(self, text_items: list[dict[str, Any]]) -> None:
        self._current_bboxes = {}
        self._current_bbox_items = []
        for item in text_items:
            text = str(item.get("text", ""))
            bbox = item.get("bbox")
            if not text or not bbox:
                continue
            self._current_bboxes.setdefault(text, bbox)
            self._current_bbox_items.append((text, bbox))

    def _raw_extractions(self, page: int, lines: list[str], text_items: list[dict[str, Any]], ocr_used: bool) -> list[RawExtraction]:
        rows: list[RawExtraction] = []
        for item in text_items:
            text = self._compact(str(item.get("text", "")))
            if text:
                rows.append(RawExtraction(page, "text_line", "NATIVE_LAYOUT", text[:1200], 0.9, item.get("bbox")))
        if ocr_used:
            for line in lines[-50:]:
                rows.append(RawExtraction(page, "ocr_text_line", "OCR", line[:1200], 0.55, None))
        return rows

    def _ocr_lines(self, pdf: str, page_number: int, page: fitz.Page, inspection: PageInspection) -> list[str]:
        if not inspection.scanned_likely or not self._ocr_available:
            return []
        try:
            import pytesseract
            from PIL import Image

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(image, config="--psm 6")
        except Exception:
            return []
        return [clean_cell(line) for line in text.splitlines() if clean_cell(line)]

    def _tables(self, pdf: str, page_number: int, page: fitz.Page) -> list[EngineeringTable]:
        if not hasattr(page, "find_tables"):
            return []
        tables: list[EngineeringTable] = []
        try:
            found = page.find_tables()
        except Exception:
            return tables
        for index, table in enumerate(getattr(found, "tables", []) or [], start=1):
            try:
                extracted = [[self._compact(str(cell or "")) for cell in row] for row in (table.extract() or [])]
            except Exception:
                continue
            extracted = [row for row in extracted if any(row)]
            if not extracted:
                continue
            headers = extracted[0]
            body = extracted[1:] if len(extracted) > 1 else []
            bbox = self._bbox_tuple(getattr(table, "bbox", None))
            raw = " | ".join(" ; ".join(row) for row in extracted[:10])
            tables.append(
                EngineeringTable(
                    f"T{page_number}-{index}",
                    page_number,
                    self._table_region_type(extracted),
                    len(body),
                    max(len(row) for row in extracted),
                    headers,
                    body,
                    self._source(pdf, page_number, "table", "PDF_TABLE", raw, 0.7, bbox),
                )
            )
        return tables

    def _table_candidate(self, lines: list[str]) -> bool:
        text = "\n".join(lines)
        if re.search(r"\b(pos|item|ref|qty|q\.ty|quantity|material|designation|description|revision|torque|Nm)\b", text, re.I):
            return True
        return len(self.part_number_pattern.findall(text)) >= 2

    def _inspect_page(self, page_number: int, page: fitz.Page, text: str) -> PageInspection:
        rect = page.rect
        text_chars = len(clean_cell(text))
        image_count = len(page.get_images(full=True))
        drawing_count = len(page.get_drawings())
        orientation = "landscape" if rect.width >= rect.height else "portrait"
        scanned_likely = text_chars < 60 and image_count > 0
        page_type = "drawing-heavy"
        if scanned_likely:
            page_type = "scanned-likely"
        elif text_chars > 2500:
            page_type = "text-heavy"
        elif image_count > 0 and drawing_count < 20:
            page_type = "image-heavy"
        return PageInspection(
            page=page_number,
            width=round(rect.width, 2),
            height=round(rect.height, 2),
            orientation=orientation,
            text_chars=text_chars,
            image_count=image_count,
            drawing_count=drawing_count,
            has_text_layer=text_chars > 0,
            scanned_likely=scanned_likely,
            page_type=page_type,
        )

    def _dimensions(self, pdf: str, page: int, lines: list[str]) -> Iterable[Dimension]:
        patterns = [
            re.compile(r"(?P<diam>[Øø]\s*)?(?P<nom>\d+(?:[,.]\d+)?)(?:\s*(?P<pm>±)\s*(?P<tol>\d+(?:[,.]\d+)?))\s*(?P<unit>mm)?\b"),
            re.compile(r"(?P<thread>M(?P<td>\d+(?:[,.]\d+)?)[xX](?P<pitch>\d+(?:[,.]\d+)?))\b"),
            re.compile(r"\b(?P<slot>\d+(?:[,.]\d+)?\s*[xX]\s*\d+(?:[,.]\d+)?(?:\s*[xX]\s*\d+(?:[,.]\d+)?)?)\b"),
            re.compile(r"\b(?P<angle>\d+(?:[,.]\d+)?)\s*°\b"),
            re.compile(r"\b(?P<radius>R\s*\d+(?:[,.]\d+)?)\b", re.I),
        ]
        for line in lines:
            if self._is_administrative(line):
                continue
            if not self._dimension_context(line):
                continue
            for pattern in patterns:
                for match in pattern.finditer(line):
                    raw = self._compact(match.group(0))
                    if self._dimension_noise(raw, line):
                        continue
                    yield self._dimension_from_match(pdf, page, raw, line, match)

    def _dimension_from_match(self, pdf: str, page: int, raw: str, line: str, match: re.Match[str]) -> Dimension:
        source = self._source(pdf, page, "dimension_area", "NATIVE_TEXT", line, 0.68)
        if match.groupdict().get("thread"):
            nominal = self._num(match.groupdict().get("td"))
            pitch = match.groupdict().get("pitch", "").replace(",", ".")
            return Dimension(raw, nominal, None, None, None, None, "mm", "thread", raw.upper().replace(",", "."), line, source)
        if match.groupdict().get("slot"):
            return Dimension(raw, None, None, None, None, None, "mm", "slot", "", line, source)
        if match.groupdict().get("angle"):
            nominal = self._num(match.groupdict().get("angle"))
            return Dimension(raw, nominal, None, None, None, None, "deg", "angle", "", line, source)
        if match.groupdict().get("radius"):
            nominal = self._num(re.sub(r"[Rr]\s*", "", raw))
            return Dimension(raw, nominal, None, None, None, None, "mm", "radius", "", line, source)
        nominal = self._num(match.groupdict().get("nom"))
        tol = self._num(match.groupdict().get("tol"))
        dim_type = "diameter" if match.groupdict().get("diam") else "linear"
        value_min = nominal - tol if nominal is not None and tol is not None else None
        value_max = nominal + tol if nominal is not None and tol is not None else None
        return Dimension(raw, nominal, value_min, value_max, tol, -tol if tol is not None else None, "mm", dim_type, "", line, source)

    def _parameters(self, pdf: str, page: int, lines: list[str]) -> Iterable[TechnicalParameter]:
        unit_re = "|".join(re.escape(unit) for unit in self.parameter_units)
        value_pattern = re.compile(rf"(?P<value>-?\d+(?:[,.]\d+)?(?:\s+[-+]?\d+(?:[,.]\d+)?)?)\s*(?P<unit>{unit_re})\b(?:\s*(?P<tol>±\s*\d+\s*%))?", re.I)
        range_pattern = re.compile(r"(?P<min>-?\d+(?:[,.]\d+)?)\s*°?\s*C?\s*(?:to|bis|à|a|÷|-)\s*(?P<max>[+]?\d+(?:[,.]\d+)?)\s*°?\s*C", re.I)
        for line in lines:
            if self._is_administrative(line):
                continue
            label = self._parameter_label(line)
            if not label and not re.search(r"pressure|temperature|voltage|current|power|flow|delivery|speed|weight|class|ip|duty|cycle", line, re.I):
                continue
            range_match = range_pattern.search(line)
            if range_match:
                yield TechnicalParameter(
                    label or "Temperature range",
                    f"{range_match.group('min')} to {range_match.group('max')}",
                    self._num(range_match.group("min")),
                    self._num(range_match.group("max")),
                    "°C",
                    "",
                    "range",
                    line,
                    self._source(pdf, page, "technical_parameter", "NATIVE_TEXT", line, 0.8),
                )
            for match in value_pattern.finditer(line):
                unit = match.group("unit")
                value = self._compact(match.group("value")).replace(",", ".")
                qualifier = "maximum" if re.search(r"\bmax\.?|maximum", line, re.I) else ""
                yield TechnicalParameter(
                    label or self._unit_parameter_name(unit),
                    value,
                    None,
                    None,
                    unit,
                    self._compact(match.group("tol") or ""),
                    qualifier,
                    line,
                    self._source(pdf, page, "technical_parameter", "NATIVE_TEXT", line, 0.74),
                )

    def _materials(self, pdf: str, page: int, lines: list[str]) -> Iterable[MaterialRecord]:
        for line in lines:
            if self._is_administrative(line) and not re.search(r"material|finish|paint|coating|surface", line, re.I):
                continue
            for match in self.material_pattern.finditer(line):
                material = self._compact(match.group(0).upper())
                standard = self._first_standard(line)
                finish = self._finish(line)
                yield MaterialRecord(material, self._grade(material), standard, finish, line, self._source(pdf, page, "material_specification", "NATIVE_TEXT", line, 0.76))

    def _standards(self, pdf: str, page: int, lines: list[str]) -> Iterable[StandardRecord]:
        for line in lines:
            if self._is_administrative(line):
                continue
            for match in self.standard_pattern.finditer(line):
                standard = self._compact(match.group(0).upper())
                if len(standard) < 5:
                    continue
                yield StandardRecord(standard, self._applies_to(line), line, self._source(pdf, page, "standard_reference", "NATIVE_TEXT", line, 0.72))

    def _bom_items(self, pdf: str, page: int, lines: list[str]) -> Iterable[BOMItem]:
        for idx, line in enumerate(lines):
            if not re.search(r"FT\d{7}-\d{3}|\b\d/\d{6}\b|\b\d{3}\s?\d{3}\s?\d{2}\s?\d{2}\b", line, re.I):
                continue
            window = lines[max(0, idx - 3) : min(len(lines), idx + 6)]
            raw = " | ".join(window)
            part = normalize_part_number(re.search(r"FT\d{7}-\d{3}|\b\d/\d{6}\b|\b\d{3}\s?\d{3}\s?\d{2}\s?\d{2}\b", line, re.I).group(0))
            ref = self._near_ref(window)
            qty = self._near_qty(window)
            description = self._near_description(window)
            material = next((m.group(0).upper() for item in window for m in self.material_pattern.finditer(item)), "")
            standard = self._first_standard(raw)
            yield BOMItem(ref, part, qty, description, material, standard, raw, self._source(pdf, page, "bom", "NATIVE_TEXT", raw, 0.62))

    def _torque(self, pdf: str, page: int, lines: list[str]) -> Iterable[TorqueRequirement]:
        patterns = [
            re.compile(r"\b(?P<ref>[A-Z]\d{3}|[A-L])\b[^\n]{0,80}?(?P<thread>M\d+(?:[xX]\d+)?)?[^\n]{0,40}?(?P<torque>\d+(?:[,.]\d+)?)\s*Nm\b", re.I),
            re.compile(r"\b(?P<torque>\d+(?:[,.]\d+)?)\s*Nm\b", re.I),
        ]
        for line in lines:
            if not re.search(r"torque|tightening|serraggio|Nm|class\s+M", line, re.I):
                continue
            for pattern in patterns:
                for match in pattern.finditer(line):
                    torque = match.groupdict().get("torque", "")
                    ref = match.groupdict().get("ref", "")
                    thread = match.groupdict().get("thread", "") or self._first_thread(line)
                    safety = "Class M" if re.search(r"class\s+M", line, re.I) else ""
                    yield TorqueRequirement(ref, self._near_qty([line]), safety, thread.upper(), torque.replace(",", "."), "Nm", line, line, self._source(pdf, page, "torque_table", "NATIVE_TEXT", line, 0.78))

    def _revisions(self, pdf: str, page: int, lines: list[str]) -> Iterable[RevisionEvent]:
        rev_pattern = re.compile(r"\b(?P<rev>[A-Z]\d{2}|[A-Z]{2}\d{2}|L\d{2})\b")
        for line in lines:
            if not re.search(r"change|changed|removed|replaced|introduction|revision|ECO|EC\d|PSC|PR\b", line, re.I):
                continue
            rev_match = rev_pattern.search(line)
            if not rev_match:
                continue
            change_type = self._change_type(line)
            affected = self._near_ref([line])
            date = self._first(r"\b\d{2}[-/]\d{2}(?:[-/]\d{2,4})?\b", line)
            yield RevisionEvent(rev_match.group("rev"), date, change_type, affected, line, line, self._source(pdf, page, "revision_table", "NATIVE_TEXT", line, 0.65))

    def _views(self, pdf: str, page: int, lines: list[str]) -> Iterable[DrawingView]:
        for line in lines:
            if re.search(r"isometric view|vista isometrica", line, re.I):
                yield DrawingView("ISOMETRIC VIEW", "isometric", "", line, self._source(pdf, page, "drawing_view", "NATIVE_TEXT", line, 0.82))
            for match in re.finditer(r"\b(?:SECTION|SEZIONE)\s+([A-Z]-[A-Z])\b|\bDETAIL\s+([A-Z0-9]+)\b|\b([A-Z]-[A-Z])\b", line, re.I):
                label = next(group for group in match.groups() if group)
                view_type = "section" if "-" in label else "detail"
                scale = self._first(r"\b\d+\s*:\s*\d+(?:[,.]\d+)?\b", line)
                yield DrawingView(label.upper(), view_type, scale, line, self._source(pdf, page, "drawing_view", "NATIVE_TEXT", line, 0.68))

    def _references(self, pdf: str, page: int, lines: list[str]) -> Iterable[DrawingReference]:
        for line in lines:
            if self._is_administrative(line):
                continue
            if not re.search(r"\bREF\b|\bPOS\b|\bITEM\b|\bBLOW-OUT\b", line, re.I):
                continue
            for ref in re.findall(r"\b(?:REF\.?\s*)?(\d{1,3}|[A-Z]\d{3})\b", line, re.I):
                yield DrawingReference(ref.upper(), "", 0.45, line, self._source(pdf, page, "drawing_reference", "NATIVE_TEXT", line, 0.45))

    def _notes(self, pdf: str, page: int, lines: list[str]) -> Iterable[EngineeringNote]:
        for line in lines:
            if not re.match(r"^\s*[-*•]?\s*(?:NOTE|NOTES|N\.B\.|ATTENTION|CAUTION|ADHESIVE|INSTALLATION|OPERATING|AIR QUALITY|SAFETY|GENERAL)", line, re.I):
                continue
            yield EngineeringNote(self._note_category(line), line, self._source(pdf, page, "notes", "NATIVE_TEXT", line, 0.64))

    def _connections(self, pdf: str, page: int, lines: list[str]) -> Iterable[ConnectionRecord]:
        for line in lines:
            if not re.search(r"connection|fitting|inlet|outlet|port|thread|terminal|gas|raccordo|verschraubung", line, re.I):
                continue
            for match in self.thread_pattern.finditer(line):
                raw = match.group(0).upper().replace(",", ".")
                pitch = ""
                size = raw
                thread_type = "metric" if raw.startswith("M") else "pipe"
                metric = re.match(r"M(?P<size>\d+(?:[,.]\d+)?)(?:X(?P<pitch>\d+(?:[,.]\d+)?))?", raw, re.I)
                if metric:
                    size = metric.group("size").replace(",", ".")
                    pitch = (metric.group("pitch") or "").replace(",", ".")
                function = "inlet" if re.search(r"inlet|entrata|einlass", line, re.I) else "outlet" if re.search(r"outlet|uscita", line, re.I) else "connection"
                yield ConnectionRecord(function, thread_type, size, pitch, self._first_standard(line), line, self._source(pdf, page, "connection", "NATIVE_TEXT", line, 0.74))

    def _bom_from_tables(self, pdf: str, tables: list[EngineeringTable], page: int) -> Iterable[BOMItem]:
        for table in tables:
            if table.page != page or table.region_type not in {"bom_table", "parts_table", "generic_table"}:
                continue
            headers = [header.lower() for header in table.headers]
            for row in table.rows:
                raw = " | ".join(row)
                if not raw:
                    continue
                part_match = self.part_number_pattern.search(raw)
                ref = self._table_value(row, headers, "pos", "item", "ref", "reference") or self._near_ref(row)
                qty = self._table_value(row, headers, "qty", "q.ty", "quantity", "q.b.") or self._near_qty(row)
                description = self._table_value(row, headers, "description", "denomination", "descrizione", "designation") or self._near_description(row)
                material = self._table_value(row, headers, "material", "mat") or next((m.group(0).upper() for m in self.material_pattern.finditer(raw)), "")
                part_number = normalize_part_number(part_match.group(0)) if part_match else ""
                if not any([part_number, ref, qty, description, material]):
                    continue
                yield BOMItem(ref, part_number, qty, description, material, self._first_standard(raw), raw, self._source(pdf, page, "bom_table", "PDF_TABLE", raw, 0.72, table.source.bbox))

    def _visual_references(self, pdf: str, page: int, text_items: list[dict[str, Any]]) -> Iterable[DrawingReference]:
        for item in text_items:
            text = self._compact(str(item.get("text", "")))
            if not re.fullmatch(r"\d{1,3}|[A-Z]\d{2,3}", text):
                continue
            if self._is_administrative(text):
                continue
            bbox = item.get("bbox")
            confidence = 0.52 if text.isdigit() else 0.48
            yield DrawingReference(text.upper(), "", confidence, text, self._source(pdf, page, "drawing_balloon", "NATIVE_LAYOUT", text, confidence, bbox))

    def _components(self, pdf: str, page: int, lines: list[str]) -> Iterable[ComponentRecord]:
        for bom in self._bom_items(pdf, page, lines):
            yield ComponentRecord(bom.reference, bom.part_number, bom.description, bom.quantity, bom.material, bom.source)
        for line in lines:
            if not re.search(r"assembly|compressor|gauge|manometer|valve|cock|body|piston|cylinder|shaft|motor|cooler|fan|bracket|flange|cover|tube|switch", line, re.I):
                continue
            part_match = self.part_number_pattern.search(line)
            ref = self._near_ref([line])
            description = self._near_description([line]) or line
            yield ComponentRecord(ref, normalize_part_number(part_match.group(0)) if part_match else "", description[:180], self._near_qty([line]), "", self._source(pdf, page, "component", "NATIVE_TEXT", line, 0.56))

    def _assemblies(self, pdf: str, page: int, lines: list[str]) -> Iterable[AssemblyRecord]:
        for line in lines:
            if not re.search(r"assembly|assy|assemblato|gruppo|unit|compressor|manometer|pressure gauge", line, re.I):
                continue
            refs = re.findall(r"\b(?:REF\.?|POS\.?|ITEM)\s*[:#-]?\s*([A-Z]?\d{1,3})\b", line, re.I)
            assembly_type = "compressor" if re.search(r"compressor", line, re.I) else "gauge" if re.search(r"gauge|manometer", line, re.I) else "assembly"
            yield AssemblyRecord(self._near_description([line]) or line[:80], assembly_type, [ref.upper() for ref in refs], line, self._source(pdf, page, "assembly", "NATIVE_TEXT", line, 0.6))

    def _fasteners(self, pdf: str, page: int, lines: list[str]) -> Iterable[FastenerRecord]:
        for line in lines:
            if not re.search(r"screw|bolt|nut|washer|helicoil|stud|vite|rondella|dado|fastener|class\s+[0-9A-Z.]+", line, re.I):
                continue
            fastener_type = self._first(r"screw|bolt|nut|washer|helicoil|stud|vite|rondella|dado", line).lower()
            thread = self._first_thread(line)
            ref = self._near_ref([line])
            qty = self._near_qty([line])
            yield FastenerRecord(ref, fastener_type or "fastener", thread, qty, self._first_standard(line), line, self._source(pdf, page, "fastener", "NATIVE_TEXT", line, 0.66))

    def _variants(self, pdf: str, page: int, lines: list[str]) -> Iterable[VariantRecord]:
        for line in lines:
            for match in self.part_number_pattern.finditer(line):
                code = normalize_part_number(match.group(0))
                yield VariantRecord(code, "part_number", code, line, self._source(pdf, page, "variant_code", "NATIVE_TEXT", line, 0.7))
            if re.search(r"optional|variant|version|configuration|without|with |left|right|flanged|threaded", line, re.I):
                value = self._compact(line)[:180]
                yield VariantRecord("", "configuration", value, line, self._source(pdf, page, "variant_note", "NATIVE_TEXT", line, 0.55))

    def _schematics(self, pdf: str, page: int, lines: list[str]) -> Iterable[SchematicRecord]:
        terms = {
            "inlet": r"\b(?:air\s+)?inlet|entrata|suction\b",
            "outlet": r"\b(?:air\s+)?outlet|uscita|delivery\b",
            "drain": r"\bdrain|scarico\b",
            "cooling": r"\binter-?cooler|after-?cooler|cooling\b",
            "safety": r"\brelief valve|safety valve|blow[- ]?out\b",
            "filtering": r"\bfilter|water separator|separator\b",
            "gauge": r"\bmanometer|pressure gauge|gauge\b",
        }
        for line in lines:
            for function, pattern in terms.items():
                if not re.search(pattern, line, re.I):
                    continue
                connection = self._first_thread(line)
                label = self._first(pattern, line) or function
                yield SchematicRecord(label.upper(), function, connection, line, self._source(pdf, page, "schematic_label", "NATIVE_TEXT", line, 0.62))

    def _identifications(self, pdf: str, page: int, lines: list[str]) -> Iterable[IdentificationRecord]:
        for line in lines:
            for match in self.part_number_pattern.finditer(line):
                yield IdentificationRecord("part_number", normalize_part_number(match.group(0)), line, self._source(pdf, page, "identification", "NATIVE_TEXT", line, 0.75))
            title_match = re.search(r"\b(?:title|main title)\b[:\s-]*(.+)$", line, re.I)
            if title_match:
                yield IdentificationRecord("drawing_title", self._compact(title_match.group(1))[:180], line, self._source(pdf, page, "identification", "NATIVE_TEXT", line, 0.58))
            rev_match = re.search(r"\b(?:rev(?:ision)?\.?|index)\s*[:#-]?\s*([A-Z]\d{2}|[A-Z]{1,2}\d{0,2}|L\d{2})\b", line, re.I)
            if rev_match:
                yield IdentificationRecord("revision", rev_match.group(1).upper(), line, self._source(pdf, page, "identification", "NATIVE_TEXT", line, 0.58))

    def _dedupe(self, engineering: EngineeringDocument) -> None:
        for attr, key_fn in {
            "dimensions": lambda item: (item.dimension_type, item.value, item.source.page),
            "parameters": lambda item: (item.name.lower(), item.value, item.unit, item.source.page),
            "materials": lambda item: (item.material, item.source.page),
            "standards": lambda item: (item.standard, item.source.page),
            "bom_items": lambda item: (item.part_number, item.reference),
            "tables": lambda item: (item.table_id, item.source.page),
            "torque_requirements": lambda item: (item.reference, item.thread, item.torque),
            "revisions": lambda item: (item.revision, item.description),
            "drawing_views": lambda item: (item.label, item.view_type, item.source.page),
            "drawing_references": lambda item: (item.reference, item.source.page),
            "components": lambda item: (item.reference, item.part_number, item.description, item.source.page),
            "assemblies": lambda item: (item.name, item.assembly_type, item.source.page),
            "fasteners": lambda item: (item.reference, item.fastener_type, item.thread, item.raw_text),
            "variants": lambda item: (item.code, item.variant_type, item.value, item.source.page),
            "schematics": lambda item: (item.label, item.function, item.source.page),
            "identifications": lambda item: (item.identifier_type, item.value, item.source.page),
            "notes": lambda item: (item.category, item.text),
            "connections": lambda item: (item.function, item.thread_size, item.pitch, item.source.page),
            "raw_data": lambda item: (item.page, item.method, item.text),
        }.items():
            seen = {}
            for item in getattr(engineering, attr):
                seen.setdefault(key_fn(item), item)
            setattr(engineering, attr, list(seen.values()))

    def _validate(self, engineering: EngineeringDocument) -> list[str]:
        warnings: list[str] = []
        if any(page.scanned_likely for page in engineering.inspections):
            if engineering.ocr_available and not engineering.ocr_used:
                warnings.append("One or more pages look scanned; OCR fallback was available but no OCR text was produced.")
            elif not engineering.ocr_available:
                warnings.append("One or more pages look scanned; OCR fallback requires Tesseract/pytesseract on this machine.")
            else:
                warnings.append("One or more pages look scanned; OCR fallback was used for low-text pages.")
        bom_refs = {item.reference for item in engineering.bom_items if item.reference}
        drawing_refs = {item.reference for item in engineering.drawing_references if item.reference}
        for ref in sorted(drawing_refs - bom_refs)[:20]:
            warnings.append(f"Drawing reference {ref} has no matched BOM reference.")
        for ref in sorted(bom_refs - drawing_refs)[:20]:
            warnings.append(f"BOM reference {ref} has no matched drawing balloon/reference.")
        for torque in engineering.torque_requirements:
            if torque.torque and not torque.thread:
                warnings.append(f"Torque value {torque.torque} Nm has no extracted thread.")
        for dimension in engineering.dimensions:
            if dimension.dimension_type != "thread" and not dimension.unit:
                warnings.append(f"Dimension {dimension.value} has no unit.")
        return warnings[:100]

    def _source(
        self,
        pdf: str,
        page: int,
        region: str,
        method: str,
        raw: str,
        confidence: float,
        bbox: tuple[float, float, float, float] | None = None,
    ) -> ExtractionSource:
        compact = self._compact(raw)[:700]
        return ExtractionSource(pdf, page, region, method, compact, confidence, bbox or self._bbox_for_text(compact))

    def _bbox_tuple(self, bbox: Any) -> tuple[float, float, float, float] | None:
        if not bbox or len(bbox) != 4:
            return None
        return tuple(round(float(value), 2) for value in bbox)  # type: ignore[return-value]

    def _bbox_for_text(self, text: str) -> tuple[float, float, float, float] | None:
        if not text:
            return None
        if text in self._current_bboxes:
            return self._current_bboxes[text]
        for candidate, bbox in self._current_bbox_items:
            if text in candidate or candidate in text:
                return bbox
        return None

    def _dimension_context(self, line: str) -> bool:
        return bool(
            re.search(r"[Øø]|±|M\d+[xX]|mm\b|°|radius|diameter|dimension|slot|hole|thread|section|detail|envelope|length|width|height|pitch", line, re.I)
            or re.fullmatch(r"\d+(?:[,.]\d+)?", line)
        )

    def _dimension_noise(self, raw: str, line: str) -> bool:
        if re.search(r"font|writings height|schrift|caratteri|scale|sheet|page", line, re.I):
            return True
        if re.fullmatch(r"\d+(?:[,.]\d+)?", raw):
            value = self._num(raw)
            return value is not None and value < 2
        return False

    def _parameter_label(self, line: str) -> str:
        label_map = {
            "working pressure": "Working pressure",
            "pressure": "Pressure",
            "operating temperature": "Operating temperature",
            "working temperature": "Working temperature",
            "temperature": "Temperature",
            "motor rotation speed": "Motor rotation speed",
            "cooling air flow": "Cooling air flow",
            "free air delivery": "Free air delivery",
            "electrical power consumption": "Electrical power consumption",
            "current consumption": "Current consumption",
            "electric power supply": "Electric power supply",
            "duty cycle": "Duty cycle",
            "starts per hour": "Starts per hour",
            "weight": "Weight",
            "protection degree": "Protection degree",
            "accuracy": "Accuracy class",
        }
        lower = line.lower()
        for key, value in label_map.items():
            if key in lower:
                return value
        return ""

    def _unit_parameter_name(self, unit: str) -> str:
        if "bar" in unit.lower():
            return "Pressure"
        if unit.lower() in {"vac", "vdc", "v", "a", "kw", "w"}:
            return "Electrical rating"
        if unit.lower() in {"rpm", "m³/s", "m3/s", "1/min", "l/min"}:
            return "Performance"
        if unit == "°C":
            return "Temperature"
        if unit.lower() == "kg":
            return "Weight"
        if unit.lower() == "nm":
            return "Torque"
        return "Technical parameter"

    def _near_ref(self, window: list[str]) -> str:
        joined = " | ".join(window)
        match = re.search(r"\b(?:REF\.?|POS\.?|ITEM)\s*[:#-]?\s*([A-Z]?\d{1,3})\b", joined, re.I)
        return match.group(1).upper() if match else ""

    def _near_qty(self, window: list[str]) -> str:
        joined = " | ".join(window)
        match = re.search(r"\b(?:QTY|Q\.TY|Q\.b\.|QUANTITY)\s*[:#-]?\s*(\d+|[0-9]+x|as required)\b", joined, re.I)
        if match:
            return match.group(1)
        for token in window:
            if re.fullmatch(r"\d+", token):
                return token
        return ""

    def _near_description(self, window: list[str]) -> str:
        for token in window:
            if re.search(r"assembly|compressor|gauge|cock|valve|piston|cylinder|shaft|flange|screw|bolt|washer|ring|body|tube|motor|cooler|fan|seal|joint", token, re.I):
                return token
        return ""

    def _table_region_type(self, rows: list[list[str]]) -> str:
        text = " | ".join(" ; ".join(row) for row in rows[:8])
        if re.search(r"\b(pos|item|ref|qty|q\.ty|quantity|part|material|description|designation)\b", text, re.I):
            return "bom_table"
        if re.search(r"\b(rev|revision|change|date|description)\b", text, re.I):
            return "revision_table"
        if re.search(r"\b(torque|Nm|thread|class)\b", text, re.I):
            return "torque_table"
        return "generic_table"

    def _table_value(self, row: list[str], headers: list[str], *keys: str) -> str:
        if not headers:
            return ""
        for index, header in enumerate(headers):
            if index >= len(row):
                continue
            normalized = re.sub(r"[^a-z0-9.]+", "", header.lower())
            for key in keys:
                if re.sub(r"[^a-z0-9.]+", "", key.lower()) in normalized:
                    return row[index]
        return ""

    def _first_standard(self, text: str) -> str:
        match = self.standard_pattern.search(text)
        return self._compact(match.group(0).upper()) if match else ""

    def _first_thread(self, text: str) -> str:
        match = self.thread_pattern.search(text)
        return self._compact(match.group(0).upper()).replace(",", ".") if match else ""

    def _first(self, pattern: str, text: str) -> str:
        match = re.search(pattern, text, re.I)
        return self._compact(match.group(0)) if match else ""

    def _finish(self, text: str) -> str:
        terms = []
        for pattern in (r"anodized", r"painted\s+\w+", r"not painted", r"RAL\s*\d{4}", r"zinc plated", r"black", r"white", r"red", r"yellow"):
            terms.extend(re.findall(pattern, text, re.I))
        return "; ".join(dict.fromkeys(self._compact(term) for term in terms))

    def _grade(self, material: str) -> str:
        if re.search(r"X5CRNI18-10|AC42100|AW\s*6060|C40|DX51D|CUSN8", material, re.I):
            return material
        return ""

    def _applies_to(self, line: str) -> str:
        if re.search(r"accuracy", line, re.I):
            return "accuracy"
        if re.search(r"fitting|connection|thread", line, re.I):
            return "connection"
        if re.search(r"material|steel|aluminium|brass", line, re.I):
            return "material"
        if re.search(r"ip|protection", line, re.I):
            return "protection"
        return ""

    def _change_type(self, line: str) -> str:
        if re.search(r"removed|delete", line, re.I):
            return "component_removed"
        if re.search(r"replaced", line, re.I):
            return "component_replaced"
        if re.search(r"introduced|introduction|new", line, re.I):
            return "component_added"
        if re.search(r"quantity|qty", line, re.I):
            return "quantity_changed"
        return "changed"

    def _note_category(self, line: str) -> str:
        if re.search(r"installation|mounting", line, re.I):
            return "installation"
        if re.search(r"safety|blow|fire|smoke", line, re.I):
            return "safety"
        if re.search(r"operating|temperature|pressure|air quality", line, re.I):
            return "operation"
        if re.search(r"adhesive|label|marking", line, re.I):
            return "marking"
        return "general"

    def _is_administrative(self, line: str) -> bool:
        return bool(re.search(r"all rights reserved|drawn by|checked by|approved by|document type|sheet|revision index|main title", line, re.I))

    def _num(self, value: str | None) -> float | None:
        if not value:
            return None
        try:
            return float(value.replace(",", ".").replace("+", ""))
        except ValueError:
            return None

    def _compact(self, value: str) -> str:
        return re.sub(r"\s+", " ", clean_cell(value)).strip(" ;|")
