from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExtractionSource:
    source_pdf: str
    page: int
    region_type: str
    method: str
    raw_text: str
    confidence: float
    bbox: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class PageInspection:
    page: int
    width: float
    height: float
    orientation: str
    text_chars: int
    image_count: int
    drawing_count: int
    has_text_layer: bool
    scanned_likely: bool
    page_type: str


@dataclass(frozen=True)
class Dimension:
    value: str
    nominal_value: float | None
    value_min: float | None
    value_max: float | None
    upper_tolerance: float | None
    lower_tolerance: float | None
    unit: str
    dimension_type: str
    thread_designation: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class TechnicalParameter:
    name: str
    value: str
    value_min: float | None
    value_max: float | None
    unit: str
    tolerance: str
    qualifier: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class MaterialRecord:
    material: str
    grade: str
    standard: str
    finish: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class StandardRecord:
    standard: str
    applies_to: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class BOMItem:
    reference: str
    part_number: str
    quantity: str
    description: str
    material: str
    standard: str
    raw_row: str
    source: ExtractionSource


@dataclass(frozen=True)
class EngineeringTable:
    table_id: str
    page: int
    region_type: str
    row_count: int
    column_count: int
    headers: list[str]
    rows: list[list[str]]
    source: ExtractionSource


@dataclass(frozen=True)
class TorqueRequirement:
    reference: str
    quantity: str
    safety_class: str
    thread: str
    torque: str
    unit: str
    instruction: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class RevisionEvent:
    revision: str
    date: str
    change_type: str
    affected_reference: str
    description: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class DrawingView:
    label: str
    view_type: str
    scale: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class DrawingReference:
    reference: str
    related_part_number: str
    relationship_confidence: float
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class ComponentRecord:
    reference: str
    part_number: str
    description: str
    quantity: str
    material: str
    source: ExtractionSource


@dataclass(frozen=True)
class AssemblyRecord:
    name: str
    assembly_type: str
    component_refs: list[str]
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class FastenerRecord:
    reference: str
    fastener_type: str
    thread: str
    quantity: str
    standard: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class VariantRecord:
    code: str
    variant_type: str
    value: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class SchematicRecord:
    label: str
    function: str
    connection: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class IdentificationRecord:
    identifier_type: str
    value: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class EngineeringNote:
    category: str
    text: str
    source: ExtractionSource


@dataclass(frozen=True)
class ConnectionRecord:
    function: str
    thread_type: str
    thread_size: str
    pitch: str
    standard: str
    raw_text: str
    source: ExtractionSource


@dataclass(frozen=True)
class RawExtraction:
    page: int
    region_type: str
    method: str
    text: str
    confidence: float
    bbox: tuple[float, float, float, float] | None = None


@dataclass
class EngineeringDocument:
    source_pdf: str
    page_count: int
    ocr_available: bool = False
    ocr_used: bool = False
    inspections: list[PageInspection] = field(default_factory=list)
    dimensions: list[Dimension] = field(default_factory=list)
    parameters: list[TechnicalParameter] = field(default_factory=list)
    materials: list[MaterialRecord] = field(default_factory=list)
    standards: list[StandardRecord] = field(default_factory=list)
    bom_items: list[BOMItem] = field(default_factory=list)
    tables: list[EngineeringTable] = field(default_factory=list)
    torque_requirements: list[TorqueRequirement] = field(default_factory=list)
    revisions: list[RevisionEvent] = field(default_factory=list)
    drawing_views: list[DrawingView] = field(default_factory=list)
    drawing_references: list[DrawingReference] = field(default_factory=list)
    components: list[ComponentRecord] = field(default_factory=list)
    assemblies: list[AssemblyRecord] = field(default_factory=list)
    fasteners: list[FastenerRecord] = field(default_factory=list)
    variants: list[VariantRecord] = field(default_factory=list)
    schematics: list[SchematicRecord] = field(default_factory=list)
    identifications: list[IdentificationRecord] = field(default_factory=list)
    notes: list[EngineeringNote] = field(default_factory=list)
    connections: list[ConnectionRecord] = field(default_factory=list)
    raw_data: list[RawExtraction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "pages": self.page_count,
            "dimensions": len(self.dimensions),
            "parameters": len(self.parameters),
            "materials": len(self.materials),
            "standards": len(self.standards),
            "bom_items": len(self.bom_items),
            "tables": len(self.tables),
            "torque_requirements": len(self.torque_requirements),
            "revisions": len(self.revisions),
            "drawing_views": len(self.drawing_views),
            "drawing_references": len(self.drawing_references),
            "components": len(self.components),
            "assemblies": len(self.assemblies),
            "fasteners": len(self.fasteners),
            "variants": len(self.variants),
            "schematics": len(self.schematics),
            "identifications": len(self.identifications),
            "notes": len(self.notes),
            "connections": len(self.connections),
            "raw_data": len(self.raw_data),
            "warnings": len(self.warnings),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_pdf": self.source_pdf,
            "ocr_available": self.ocr_available,
            "ocr_used": self.ocr_used,
            "counts": self.counts(),
            "warnings": self.warnings,
        }
