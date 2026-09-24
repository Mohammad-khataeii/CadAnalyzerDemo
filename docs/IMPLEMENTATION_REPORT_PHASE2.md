# Phase 2 Implementation Report

## Objective

Phase 2 upgrades the PDF analyzer from a catalogue-only demo into a structured engineering extraction pipeline. The app still produces one client workbook, with the first sheet kept in the same sample catalogue structure and styling, then detailed engineering sheets added behind it for review and traceability.

## Completed

- Preserved the sample workbook structure on the first sheet: `BRAKES_LEAN-CATALOGUE V2_TECH`.
- Added multi-sheet engineering export inside the same generated `.xlsx` file.
- Added native PDF layout extraction with page, method, confidence, evidence text, and bounding-box coordinates where available.
- Added structured extraction for:
  - Dimensions, quotas, threads, tolerances, radii, slots, and angles.
  - Technical parameters such as pressure, temperature, electrical data, flow, speed, weight, and torque.
  - Materials, grades, finishes, and standards.
  - BOM/parts-list rows from text and table-like PDF regions.
  - Components, assemblies, fasteners, connections, drawing views, drawing references/balloons, variants, schematic labels, revisions, notes, and identifiers.
- Added OCR fallback support for scanned drawings when Tesseract and pytesseract are installed.
- Added quality and provenance sheets so extracted values can be reviewed against source evidence.
- Added styled workbook sheets with frozen headers, filters, table styling, wrapped text, confidence coloring, and a summary chart.
- Added tests covering the new multi-sheet workbook and structured engineering extraction.
- Added dashboard metrics for PDFs, pages, products, warnings, entity counts, and high/medium/low confidence extraction buckets.

## Generated Workbook Structure

The main output is:

`data/output/catalogue_generated.xlsx`

Sheet order:

1. `BRAKES_LEAN-CATALOGUE V2_TECH`
2. `SUMMARY`
3. `PRODUCT CATALOGUE`
4. `PRODUCTS`
5. `VARIANTS`
6. `BOM`
7. `COMPONENTS`
8. `DIMENSIONS`
9. `TECHNICAL PARAMETERS`
10. `MATERIALS`
11. `STANDARDS`
12. `TORQUE & FASTENERS`
13. `ASSEMBLIES`
14. `DRAWING VIEWS`
15. `DRAWING REFERENCES`
16. `CONNECTIONS`
17. `SCHEMATICS`
18. `NOTES & INSTRUCTIONS`
19. `REVISION HISTORY`
20. `IDENTIFICATION`
21. `EXTRACTION SOURCES`
22. `QUALITY REVIEW`
23. `RAW DATA`

## Partially Completed

- Visual/spatial extraction: native PDF layout coordinates are captured for text-derived dimensions, references, and raw regions. This is not full CAD geometry interpretation.
- Drawing balloons: isolated visual text labels are extracted with layout coordinates. Relationship matching to BOM is conservative and low-confidence unless direct evidence exists.
- BOM extraction: native text and PyMuPDF table regions are used. Complex merged cells and visually drawn tables may still require manual review.
- Schematic extraction: pneumatic labels such as inlet, outlet, drain, cooler, separator, relief valve, gauge, and pressure labels are captured. Symbol-level interpretation is not claimed.
- Multilingual separation: multilingual keywords are supported in extraction rules, but duplicate language-specific descriptions are not yet fully split into parallel language columns.
- Variant relationships: variant codes and configuration notes are captured, but BOM/dimension/material differences are only represented when evidence is explicit.

## Not Implemented

- Full CAD-level geometry recognition from vector paths.
- Perfect spatial relationship graph from every balloon to every BOM row and component.
- OCR execution on this local machine, because Tesseract/pytesseract is not currently available in the environment. The fallback code is implemented and will run when those dependencies are installed.
- Semantic recognition of all pneumatic/hydraulic symbols independent of nearby text labels.

## Known Limitations

- The current implementation uses deterministic PDF text/layout extraction first, because these drawings contain usable native text.
- OCR is implemented as a fallback, but it only runs on machines where Tesseract and pytesseract are installed.
- The extractor is generic and flexible across similar engineering drawings, but every low-confidence or ambiguous item is intentionally kept in the review/provenance sheets instead of being silently discarded.
- This is suitable for demo and review workflows. Production release should add more client-specific validation rules after the client confirms which dimensions and drawing conventions are mandatory.
