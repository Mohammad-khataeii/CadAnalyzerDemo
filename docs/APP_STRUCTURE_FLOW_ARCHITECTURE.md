# Product Analyzer App Structure and Flow

## Purpose

Product Analyzer is a local desktop demo for analyzing an engineering product catalogue and technical PDF drawings.

It focuses on the `B - ISOLATING COCKS` product category, extracts technical characteristics from drawings, maps them into catalogue-compatible Excel rows, and generates visual cluster/affinity analysis.

## Main Inputs

- Source catalogue Excel:
  - `data/input/PrM_Lean-Catalogue_v2s (2)-rev1.xlsx`
- Example engineering drawings:
  - `data/input/725958XX08_AH00.pdf`
  - `data/input/FT0120872-100_C00.pdf`

The desktop app also allows selecting another catalogue and other PDFs from the UI.

## Main Outputs

Generated files are written to:

- Source run: `data/output/`
- Packaged Mac app run: `~/Documents/ProductAnalyzer/output/`

Important outputs:

- `catalogue_generated.xlsx`: extracted PDF data mapped into the catalogue format.
- `isolating_cocks_catalogue.xlsx`: focused catalogue rows for isolating cocks.
- `extraction_evidence.csv`: traceability for extracted fields.
- `analysis_results.json`: structured analysis result.
- `anomalies.csv`: detected catalogue/data issues.
- `DEMO_ANALYSIS_REPORT.md`: generated analysis report.
- HTML/PNG charts for clusters, affinity, rules, confidence, and distributions.

## High-Level Flow

1. Load catalogue Excel.
2. Filter focused category: `Product Name = B - ISOLATING COCKS`.
3. Read selected PDF drawings.
4. Extract drawing metadata and technical fields.
5. Keep evidence for each extracted value.
6. Match PDFs to catalogue rows using detected part numbers.
7. Generate catalogue-compatible rows.
8. Discover PartNumber and configuration rules.
9. Cluster similar catalogue rows.
10. Detect anomalies and missing/duplicate configurations.
11. Generate charts, exports, and report.
12. Display all results in the PySide6 desktop UI.

## App Architecture

```text
app/
  main.py                    Entry point for GUI or --demo CLI run
  config/settings.py         Paths and demo configuration
  models/domain.py           Shared dataclasses/results

  catalogue/
    loader.py                Reads Excel/CSV catalogue
    matcher.py               Matches PDF findings to catalogue rows

  pdf/
    analyzer.py              Reads PDF text and BOM-like rows

  extraction/
    characteristics.py       Extracts fields from drawing text

  services/
    demo_runner.py           Main orchestration pipeline

  clustering/
    engine.py                Builds cluster labels and PCA-style coordinates

  similarity/
    engine.py                Finds technically similar products

  rules/
    discovery.py             Finds attribute/PartNumber signals

  anomalies/
    detector.py              Flags conflicts, missing combinations, low confidence

  bom/
    analyzer.py              Summarizes component-like rows

  visualization/
    charts.py                Generates PNG and interactive HTML charts

  reporting/
    report.py                Builds the Markdown report

  ui/
    main_window.py           PySide6 desktop interface
```

## UI Pages

- Dashboard: summary of demo scope, PDFs, clusters, gaps, and anomalies.
- PDF Import: selected files, detected identifiers, variants, warnings.
- Extraction Review: evidence and confidence for extracted values.
- Generated Catalogue: Excel-compatible generated output.
- Product Explorer: focused isolating cock catalogue rows.
- Clusters: scatter, dendrogram, heatmap, bubble, Sankey, radar, and cluster tables.
- Family Explorer: product type distribution and characteristic flow.
- Characteristic Analysis: diameter/handle and drain/contact relationships.
- Part Number Rules: attribute influence and configuration matrix.
- Anomalies: detected data issues and review queue.
- Similar Products: technical similarity results.
- BOM Analysis: component-like rows from PDFs.
- Reports: generated Markdown report.
- Settings: paths and demo boundaries.

Each page has a bottom-right `?` button that explains what the page shows.

## Generated Chart Types

Core charts:

- Product type distribution
- Diameter vs handle
- Drain vs contact
- Attribute completeness
- Rule influence
- Anomaly breakdown
- Extraction confidence
- BOM frequency

Advanced cluster charts:

- Scatter plot with clusters
- Colored cluster map
- Hierarchical dendrogram
- Affinity heatmap
- Bubble cluster
- Sankey by characteristics
- Cluster radar

These charts are generated from real catalogue/PDF analysis data, not static mockups.

## Extraction Logic

PDF extraction is deterministic and local.

The app extracts:

- Drawing number
- Revision
- Drawing title
- Diameter
- Contact count
- Product family/name/type
- Pressure and temperature when visible
- Foolproofing
- Drain
- Handle
- Connector
- Variants
- BOM-like component rows

If a value cannot be read confidently, it is marked as:

- `NEEDS REVIEW`
- `UNKNOWN`
- `NOT_FOUND`

This avoids presenting uncertain values as confirmed facts.

## Current Boundaries

Implemented:

- Local PDF text extraction
- Catalogue loading
- Catalogue-compatible Excel export
- Evidence tracking
- Clustering
- Similarity
- Rule discovery
- Anomaly detection
- Visual analytics
- Desktop UI
- Mac DMG packaging
- Windows EXE build script

Not yet production-grade:

- OCR for scanned drawings
- Real CAD/STEP/STP geometry analysis
- External AI/vision extraction
- Persistent human validation database
- Full BOM table parser

## Run Locally

```bash
.venv/bin/python -m app.main --demo
```

Launch GUI:

```bash
.venv/bin/python -m app.main
```

## Build Packages

Mac:

```bash
./build_dmg.sh
```

Windows:

```bat
build_exe.bat
```

The Windows build must be run on Windows. PyInstaller cannot create a real Windows `.exe` from macOS.

