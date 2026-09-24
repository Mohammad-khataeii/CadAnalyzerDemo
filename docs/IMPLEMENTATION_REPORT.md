# Implementation Report

## 1. Existing architecture

The application loaded a sample Excel catalogue as a schema, read PDF native text with PyMuPDF, extracted a focused set of product fields, matched them back to the catalogue, generated CSV/XLSX outputs, and produced visual charts. The main flow is `DemoRunner -> PDFAnalyzer -> CharacteristicExtractor -> catalogue/visual/report modules`.

## 2. Problems found

- The old pipeline was catalogue-first and did not preserve a broad engineering model.
- Most extraction lived as flat fields and evidence rows.
- Dimension, torque, revision, view, and BOM-like data existed in PDFs but was not normalized.
- Workbook output was drifting into auxiliary sheets/files, while the client needs one sample-style catalogue file.

## 3. New architecture

Added a normalized engineering layer under `app/engineering`:

- `EngineeringDocument`
- `PageInspection`
- `Dimension`
- `TechnicalParameter`
- `MaterialRecord`
- `StandardRecord`
- `BOMItem`
- `TorqueRequirement`
- `RevisionEvent`
- `DrawingView`
- `DrawingReference`
- `ConnectionRecord`
- `EngineeringNote`
- `ExtractionSource`

`PDFAnalyzer` now produces both the previous catalogue fields and a richer `engineering` object for every PDF.

## 4. Extraction pipeline

The updated flow is:

PDF -> native text/page inspection -> generic engineering extraction -> deterministic catalogue extraction -> normalized engineering model -> sample-style catalogue workbook.

OCR is not automatically run. The app inspects likely scanned pages and records a warning; native text/vector PDF extraction remains the first source.

## 5. Entity model

The new model keeps entities separated instead of using one giant text blob. Each entity has source/provenance data where applicable: PDF, page, region type, extraction method, raw text, and confidence.

## 6. Relationship model

The current implementation creates first-pass relationships through shared references:

- drawing references vs BOM references
- BOM item part numbers
- torque reference/thread/value
- standards/materials tied to source text
- drawing views and section/detail labels

Validation reports unmatched reference/BOM relationships rather than silently fixing them.

## 7. Excel structure

The client-facing XLSX is now one workbook with one catalogue sheet styled from the customer sample:

- `BRAKES_LEAN-CATALOGUE V2_TECH`

The original catalogue columns are preserved. Additional data is added in the same structure as the sample using:

- `Technical attribute 5` through `Technical attribute 12`

## 8. Visual analysis approach

The new `PageInspection` layer records page orientation, size, text volume, image count, drawing object count, and likely scanned status. Visual symbol recognition is not fully implemented yet, but the model now has a place to attach visual-analysis entities.

## 9. OCR strategy

OCR remains a fallback strategy. The current code detects likely scanned pages and records warnings. It does not OCR all pages automatically because native PDF text is more reliable for these supplied drawings.

## 10. Dimension extraction approach

Dimensions are extracted generically from native text patterns:

- linear dimensions
- toleranced dimensions such as `135 ±0.5`
- diameter values such as `Ø84`
- angle values
- slot forms such as `8x7x40`
- thread forms such as `M16x1.5`

Values are normalized into nominal/tolerance/unit/type fields where possible, while preserving raw text.

## 11. BOM extraction approach

The BOM extraction is generic and searches for part-number-like rows plus nearby quantity, reference, description, material, and standard context. It preserves the raw row/window as source evidence.

## 12. Technical parameter extraction

The generic parameter extractor recognizes common engineering units and labels:

- pressure
- temperature
- rpm
- voltage/current/power
- flow
- weight
- torque
- duty cycle-like values

It keeps raw text, unit, value, tolerance, qualifier, and confidence.

## 13. Variant handling

Existing variant detection remains in `CharacteristicExtractor`. The engineering layer preserves product references and revision/configuration context, ready for deeper variant comparison.

## 14. Revision handling

Revision-like lines are extracted into `RevisionEvent` records with revision, date when visible, change type, affected reference where detectable, description, source page, and confidence.

## 15. Confidence/provenance

Existing `Evidence` rows now include promoted engineering entities. The JSON output also stores engineering counts and warnings per PDF. Every normalized engineering entity stores `ExtractionSource`.

## 16. Validation

Implemented first-pass validation:

- scanned-page warning
- drawing reference without BOM reference
- BOM reference without drawing reference
- torque without thread
- dimension without unit

## 17. Tests performed

Automated tests verify:

- catalogue loading
- PDF text extraction
- catalogue matching
- rule discovery
- clustering
- demo exports
- sample-style workbook structure
- promoted technical attributes
- structured engineering model extraction for gauge and compressor drawings

Latest local result: `10 passed`.

## 18. Known limitations

- OCR fallback is detected but not executed.
- True visual dimension geometry is not yet extracted from vector line placement.
- BOM parsing is heuristic and can still over-detect title-block part numbers.
- Relationship confidence is first-pass and should be improved with spatial layout data.
- Schematic symbol interpretation is not yet complete.

## 19. Remaining risks

- Very low-quality scans need OCR integration.
- Complex merged tables need a deeper table model.
- Some multilingual duplicate values still need language-specific separation.
- Drawing balloons need visual/spatial extraction for stronger BOM linking.

## 20. Files changed

- `app/engineering/model.py`
- `app/engineering/extractor.py`
- `app/pdf/analyzer.py`
- `app/models/domain.py`
- `app/services/demo_runner.py`
- `tests/test_pipeline.py`

## 21. How to run

```bash
.venv/bin/python -m app.main --demo
```

## 22. How to generate the XLSX

Run the demo command above. The catalogue is written to:

```text
data/output/catalogue_generated.xlsx
```

## 23. Example extraction results

From the supplied PDFs, the system now extracts examples such as:

- pressure gauge diameter and pressure range
- `IP54` protection
- `M16x1.5` connections
- `DIN EN 837-1`, `ISO 8573-1`, `UNI-ISO 228`
- stainless steel, aluminium, brass, RAL colors
- compressor envelope dimensions
- `135 ±0.5`, `67.5 ±0.25`, `31 ±0.2`
- torque values in `Nm`
- revision events
- section/detail/isometric view labels
- BOM-like component part rows

The first sheet remains compatible with the customer catalogue format.
