# Product Analyzer - Architecture Summary

## What The App Does

Product Analyzer is a local desktop application for turning engineering PDF drawings into a structured product catalogue and visual analysis package.

The user selects:

- The customer Excel catalogue/template.
- One or more engineering PDF drawings.

The app then reads the PDFs, extracts technical characteristics, maps them into the customer catalogue structure, builds engineering review sheets, and generates dashboards/charts for presentation.

It does not need internet access for the current workflow. The analysis runs locally on the computer.

## Main Processing Flow

1. **Input loading**
   The app loads the Excel catalogue to preserve the customer structure, column names, colors, and main catalogue format.

2. **PDF analysis**
   PDFs are read with `PyMuPDF`, which extracts native PDF text, page layout, coordinates, tables, drawing labels, and visible technical text.

3. **Technical extraction**
   The app extracts engineering data such as:
   dimensions, tolerances, threads, pressure, temperature, voltage, RPM, materials, standards, BOM rows, components, torque, fasteners, revisions, drawing references, views, notes, and schematic labels.

4. **Local AI / ML layer**
   The app uses deterministic engineering rules plus local ML techniques:
   TF-IDF similarity, clustering, PCA projection, and similarity matrices.
   This is used to group similar products, detect patterns, and create useful cluster graphics.

5. **Catalogue mapping**
   Extracted PDF data is mapped back into the customer catalogue columns, including `PartNumber`, `Master PN`, product hierarchy, and `Technical attribute 1-12`.

6. **Validation and review**
   The app keeps confidence scores and source evidence for extracted data.
   Uncertain items are marked for review instead of being hidden.

## Interface

The desktop dashboard shows:

- Selected input files.
- PDF extraction status.
- Extracted catalogue rows.
- Product clusters.
- Technical characteristics.
- BOM/component findings.
- Anomalies and review items.
- Generated charts and output paths.

This makes the workflow usable for both technical review and client demo.

## Outputs

The main output is one Excel workbook:

`catalogue_generated.xlsx`

It contains:

- The customer-style catalogue sheet first.
- Summary dashboard.
- Product catalogue.
- Products and variants.
- BOM, components, dimensions, parameters, materials, standards.
- Torque/fasteners, assemblies, drawing views/references.
- Connections, schematics, notes, revisions.
- Extraction sources, quality review, and raw data.

The app also generates:

- Level 1 visual PDF: manager-friendly charts.
- Level 2 visual PDF: technical engineering charts.
- PNG/HTML charts for dashboard use.
- CSV/JSON exports for traceability.
- Markdown analysis report.

## Current Technical Base

Key libraries and techniques:

- `PyMuPDF` for PDF text/layout/table extraction.
- `pandas` and `openpyxl` for Excel processing and styled workbook generation.
- `scikit-learn` for clustering, TF-IDF, PCA, and similarity analysis.
- `matplotlib` and `plotly` for charts.
- Optional OCR fallback with Tesseract/pytesseract when scanned PDFs need it.

In short: the app converts engineering drawings into structured catalogue data, keeps traceability, shows the result in a dashboard, and produces Excel/PDF outputs ready for client review.
