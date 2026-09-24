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


@dataclass
class EngineeringDocument:
    source_pdf: str
    page_count: int
    inspections: list[PageInspection] = field(default_factory=list)
    dimensions: list[Dimension] = field(default_factory=list)
    parameters: list[TechnicalParameter] = field(default_factory=list)
    materials: list[MaterialRecord] = field(default_factory=list)
    standards: list[StandardRecord] = field(default_factory=list)
    bom_items: list[BOMItem] = field(default_factory=list)
    torque_requirements: list[TorqueRequirement] = field(default_factory=list)
    revisions: list[RevisionEvent] = field(default_factory=list)
    drawing_views: list[DrawingView] = field(default_factory=list)
    drawing_references: list[DrawingReference] = field(default_factory=list)
    notes: list[EngineeringNote] = field(default_factory=list)
    connections: list[ConnectionRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "pages": self.page_count,
            "dimensions": len(self.dimensions),
            "parameters": len(self.parameters),
            "materials": len(self.materials),
            "standards": len(self.standards),
            "bom_items": len(self.bom_items),
            "torque_requirements": len(self.torque_requirements),
            "revisions": len(self.revisions),
            "drawing_views": len(self.drawing_views),
            "drawing_references": len(self.drawing_references),
            "notes": len(self.notes),
            "connections": len(self.connections),
            "warnings": len(self.warnings),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_pdf": self.source_pdf,
            "counts": self.counts(),
            "warnings": self.warnings,
        }
