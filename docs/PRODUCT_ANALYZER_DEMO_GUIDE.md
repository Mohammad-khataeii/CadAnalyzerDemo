# Product Analyzer Demo Guide

This guide explains the demo logic, what each page shows, and how each chart/table helps during a customer or engineering review.

## 1. Whole App Logic

Product Analyzer is a local desktop demo that reads an engineering catalogue Excel file and a set of engineering drawing PDFs, extracts technical characteristics, maps them back into catalogue-compatible rows, and generates visual analysis.

For this demo, the app is focused on:

- Catalogue filter: `Product Name = B - ISOLATING COCKS`
- Meeting target: `58` isolating cock codes
- Current catalogue result: `57` isolating cock rows found
- Gap shown by the app: `1` missing code versus the stated target

The app does not pretend uncertain information is certain. When a PDF field is unclear, the value is marked as `NEEDS REVIEW`, `UNKNOWN`, or `NOT_FOUND`.

## 2. Processing Flow

1. Load the source catalogue workbook.
   The app reads the Excel catalogue and preserves the original column structure, including product hierarchy, technical attributes, PartNumber, Master PN, maturity, preferred status, and quantity fields.

2. Filter the demo category.
   The app isolates the rows where `Product Name` is `B - ISOLATING COCKS`. This creates the focused demo dataset used for most charts, clusters, rules, and anomalies.

3. Load and analyze PDF drawings.
   The app reads native PDF text using PyMuPDF. It extracts drawing number, revision, title, diameter, contacts, product family, product name, product type, pressure, temperature, foolproofing, drain, handle, connector, variants, and BOM-like rows when visible.

4. Build evidence.
   Every extracted field keeps traceability: source PDF, page number, evidence text, confidence score, extraction method, and review status.

5. Match drawings to catalogue rows.
   The app checks whether detected part numbers or master part numbers exist in the catalogue. For the supplied demo drawings, both example PDFs are matched to catalogue rows.

6. Generate catalogue-compatible output.
   The extracted PDF characteristics are written into the same column structure as the original catalogue. This proves the extraction can feed a catalogue cleanup or enrichment workflow.

7. Discover rules and patterns.
   The app checks how strongly technical characteristics influence PartNumber patterns. It also builds a configuration matrix to find observed, expected, missing, and duplicate combinations.

8. Build clusters.
   The app encodes product family, product name, product type, and technical attributes, then clusters similar isolating cock products. PCA is used to place products into a 2D scatter plot.

9. Detect anomalies.
   The app flags duplicate configurations, conflicting characteristics, missing combinations, unmatched PDFs, low-confidence extractions, and variant mapping inconsistencies.

10. Export outputs.
    The app exports CSV, XLSX, JSON, PNG charts, HTML charts, and a Markdown report.

## 3. Main Outputs

Important generated files:

- `catalogue_generated.xlsx`: PDF-extracted rows mapped into the source catalogue format.
- `isolating_cocks_catalogue.xlsx`: focused Excel export containing only isolating cock catalogue rows.
- `extraction_evidence.csv`: evidence trail for extracted fields.
- `analysis_results.json`: structured machine-readable analysis output.
- `anomalies.csv`: review issues found by the app.
- `bom_components.csv`: component-like rows extracted from the PDFs.
- `DEMO_ANALYSIS_REPORT.md`: generated factual report for the run.

Important focused visuals:

- `isolating_cocks_demo_coverage.png`
- `isolating_cocks_product_type.png`
- `isolating_cocks_diameter_handle.png`
- `isolating_cocks_drain_contact.png`
- `isolating_cocks_characteristic_flow.html`
- `cluster_scatter.html`
- `advanced_scatter_cluster.html`
- `cluster_dendrogram.html`
- `affinity_heatmap.html`
- `cluster_bubble.html`
- `cluster_colored_map.html`
- `cluster_sankey.html`
- `cluster_radar.html`

## 4. Page-By-Page Guide

### Dashboard

The Dashboard is the executive summary of the demo run.

It shows:

- The focused category: `B - ISOLATING COCKS`
- The expected number of codes: `58`
- The number found in the loaded catalogue: `57`
- The gap: `1`
- Number of PDFs analyzed
- Generated catalogue rows
- Evidence rows
- Number of clusters
- Number of fields needing review
- Number of anomalies

Charts/tables:

- Demo scope check: shows found codes versus missing codes.
- Isolating cock product type chart: shows how focused rows split by product type.
- Demo brief table: shows the exact meeting requirements implemented in the app.
- PDF-to-catalogue mapping table: shows whether each PDF matched a catalogue row.

Why it helps:

This page lets you explain the whole demo in under one minute: the app loaded the Excel, focused on isolating cocks, found 57 of the expected 58 rows, analyzed drawings, mapped them to catalogue rows, and produced focused analytics.

### PDF Import

This page shows which PDF drawings are used as inputs.

It shows:

- Selected catalogue file
- Selected PDF files
- Number of analyzed PDFs
- Number of extracted BOM rows
- Number of detected variants
- Detected identifiers per PDF
- Warnings per PDF

Tables:

- PDF input table: one row per analyzed PDF, with page count, identifiers, variants, and warnings.

Why it helps:

It proves which drawings were analyzed and gives a first quality check: if part numbers, variants, or BOM rows are missing, the issue is visible immediately.

### Extraction Review

This page shows the evidence behind extracted values.

It shows:

- Evidence row count
- Fields needing review
- Average confidence by extracted field
- Source PDF and page for each extraction
- Evidence text used by the algorithm
- Extraction method and status

Charts/tables:

- Extraction confidence chart: shows which fields are reliable and which need engineer review.
- Evidence table: shows field, value, source PDF, page, evidence text, confidence, extraction method, and status.

Why it helps:

This page makes the app auditable. Engineers can see why the app extracted a value instead of trusting a black-box result.

### Generated Catalogue

This page shows the Excel-compatible output produced from the drawing analysis.

It shows:

- Generated row count
- Number of columns preserved from the original catalogue
- Number of review flags
- Catalogue-style rows created from PDF data

Charts/tables:

- Attribute completeness chart: shows how complete technical attributes are in the focused dataset.
- Maturity by family chart: shows release/maturity distribution.
- Generated catalogue table: shows the generated rows in the same structure as the source Excel.

Why it helps:

It proves that extracted PDF information can be mapped back into the customer catalogue format instead of staying as unstructured text.

### Product Explorer

This page shows the focused isolating cock catalogue rows.

It shows:

- PartNumber
- Master PN
- Product family
- Product name
- Product type
- Technical attribute 1: usually diameter
- Technical attribute 2: usually drain
- Technical attribute 3: usually contact
- Technical attribute 4: usually handle

Tables:

- Isolating cock catalogue rows: focused rows from the source Excel.
- AI-mapped drawing examples: rows generated from the attached PDF drawings.

Why it helps:

It lets engineers compare existing catalogue data against what the app extracted from drawings.

### Clusters

This page shows groups of similar isolating cock products.

It shows:

- Number of clusters
- Number of clustered products
- Number of encoded features
- PCA scatter plot
- Cluster explanations
- Representative PartNumbers

Charts/tables:

- Cluster PCA scatter: places product rows in 2D based on similar technical attributes.
- Cluster explanation cards: show the most common characteristics inside each cluster.
- Clustered products table: shows the raw point data behind the chart.

Why it helps:

Clusters reveal product families or configurations that behave similarly. This helps identify standard variants, outliers, duplicate configurations, and possible simplification opportunities.

### Family Explorer

This page shows product type distribution inside the focused isolating cock category.

It shows:

- Counts by product type
- Focused characteristic flow
- Product type concentration

Charts/tables:

- Isolating cock product type chart: shows whether the focus category is dominated by flanged, pipe, or other product types.
- Product type mini-bars: compact count view.
- Characteristic flow chart: connects product type, diameter, drain, contact, and handle.

Why it helps:

It shows where most isolating cock codes are concentrated and how configurations flow from broad type to detailed attributes.

### Characteristic Analysis

This page shows relationships between technical attributes.

It shows:

- Diameter versus handle
- Drain versus contact
- Attribute completeness
- Common values for each technical attribute

Charts/tables:

- Diameter vs handle chart: shows which handle types appear for each diameter.
- Drain vs contact matrix: shows how drain options combine with contact options.
- Attribute completeness chart: shows whether technical attribute fields are populated.
- Characteristic values table: lists the value distribution per technical attribute.

Why it helps:

This is the main engineering insight page. It shows common product configurations, missing combinations, repeated patterns, and whether the catalogue attribute structure is consistent.

### Part Number Rules

This page shows discovered relationships between attributes and PartNumber structure.

It shows:

- Rule candidates
- Support count
- Distinct values
- Confidence
- Influence level
- Configuration matrix

Charts/tables:

- Rule influence table: shows which attributes carry PartNumber signal.
- Rule influence chart: visualizes confidence and support.
- Configuration matrix panel: shows observed, expected, missing, and duplicate combinations.

Why it helps:

It helps answer: "Which characteristics explain the product code?" This is useful for catalogue cleanup, code validation, variant generation, and spotting inconsistent product numbering.

### Anomalies

This page shows review issues found by the app.

It shows:

- High severity issues
- Medium severity issues
- Low severity issues
- Duplicate configurations
- Missing expected combinations
- Low-confidence extracted fields
- Variant mapping inconsistencies

Charts/tables:

- Anomaly breakdown chart: shows anomaly types by severity.
- Anomaly table: shows the evidence behind each issue.

Why it helps:

It turns a large catalogue into a review queue. Engineers can focus on the rows most likely to need correction or validation.

### Similar Products

This page shows technically similar products.

It shows:

- Candidate similar products
- Similarity percentage
- Shared attributes used as reasons
- Explicit CAD geometry status

Tables:

- Similarity table: shows PartNumber, score, shared attributes, and geometric similarity status.

Why it helps:

It helps find related product codes or possible alternatives. It also avoids a false claim: CAD/3D geometry similarity is marked as unavailable unless real CAD analysis is implemented.

### BOM Analysis

This page shows component-like rows extracted from drawing text.

It shows:

- Number of BOM rows
- Number of unique components
- Component part numbers
- Quantity when visible
- Description
- Specification
- ABC class
- Evidence text

Charts/tables:

- BOM frequency chart: shows the most reused component identifiers across analyzed PDFs.
- BOM table: lists component-like extraction rows.

Why it helps:

It provides an early view of component reuse and platform commonality. It is useful, but should be treated as provisional until a stronger BOM table parser is implemented.

### Reports

This page shows the generated Markdown report.

It shows:

- Executive summary
- Files analyzed
- Extracted characteristics
- PDF-to-catalogue mapping
- PartNumber patterns
- Master PN patterns
- Clusters and explanations
- Common characteristics
- BOM findings
- Similarity findings
- Missing combinations
- Duplicate configurations
- Anomalies
- Limitations
- Gap analysis
- Future roadmap

Why it helps:

It gives a shareable written record of the demo. It separates facts, algorithm results, limitations, and next development steps.

### Settings

This page shows runtime and demo configuration.

It shows:

- Demo input mode
- Demo focus category
- Expected code count
- Output folder
- AI provider status
- CAD geometry status

Why it helps:

It makes the demo boundaries clear. The current demo is local and deterministic; AI providers and CAD geometry are documented as future extension points.

## 5. Chart Reference

| Chart | File | What it shows | Why it helps |
|---|---|---|---|
| Demo scope check | `isolating_cocks_demo_coverage.png` | Expected 58 codes versus 57 found and 1 missing. | Makes the meeting scope gap visible immediately. |
| Isolating cock product type | `isolating_cocks_product_type.png` | Counts of focused rows by product type. | Shows whether the category is dominated by pipe, flanged, or other product types. |
| Diameter vs handle | `isolating_cocks_diameter_handle.png` | Handle types grouped by diameter. | Shows common configurations and repeated handle patterns. |
| Drain vs contact | `isolating_cocks_drain_contact.png` | Drain options crossed with contact options. | Shows how functional options combine. |
| Characteristic flow | `isolating_cocks_characteristic_flow.html` | Product type to diameter to drain to contact to handle. | Shows common configuration paths across the category. |
| Cluster scatter | `cluster_scatter.html` | Similar products projected into 2D and colored by cluster. | Shows natural groupings and outliers. |
| Advanced scatter cluster | `advanced_scatter_cluster.html` | Scatter plot with cluster color and symbol encoding. | Matches the requested cluster-symbol style using real catalogue data. |
| Hierarchical dendrogram | `cluster_dendrogram.html` | Product affinity tree based on technical attributes. | Shows which FT/product codes are closest by branch distance. |
| Affinity heatmap | `affinity_heatmap.html` | Pairwise similarity between product codes. | Dark cells immediately reveal families of similar products. |
| Bubble cluster | `cluster_bubble.html` | Cluster centroid positions with bubble size based on product count. | Shows which clusters are larger and how far groups are from one another. |
| Colored cluster map | `cluster_colored_map.html` | Manager-friendly PCA map with larger colored cluster points. | Gives a presentation-ready view of product families. |
| Sankey by characteristics | `cluster_sankey.html` | Flow from product type and technical characteristics into clusters. | Explains how codes converge into families/clusters. |
| Cluster radar | `cluster_radar.html` | Radar comparison of clusters across completeness, variety, and concentration metrics. | Compares cluster profiles beyond simple count or position. |
| Attribute completeness | `attribute_completeness.png` | Filled percentage for technical attributes. | Shows where catalogue data is complete or sparse. |
| Rule influence | `rule_influence.png` | Attribute influence on PartNumber patterns. | Helps identify which characteristics drive product code changes. |
| Anomaly breakdown | `anomaly_breakdown.png` | Issue types grouped by severity. | Turns catalogue problems into a review queue. |
| Extraction confidence | `extraction_confidence.png` | Average confidence per extracted field. | Shows which extracted values are reliable. |
| BOM frequency | `bom_frequency.png` | Most reused component identifiers. | Reveals shared components and possible platform reuse. |
| Catalogue hierarchy treemap | `catalogue_hierarchy_treemap.html` | Category, family, product name, and product type volume. | Useful for broad catalogue context. |
| Maturity by family | `maturity_by_family.png` | Maturity status by family. | Helps prioritize released versus incomplete product areas. |
| Contact and handle matrix | `contact_handle_matrix.png` | Contact values crossed with handle values. | Shows relationship between control/contact setup and handle type. |

## 6. Table Reference

| Table | Page | What it shows | Why it helps |
|---|---|---|---|
| Demo brief table | Dashboard | Meeting requirements implemented by the app. | Keeps the demo aligned with the requested scope. |
| PDF-to-catalogue mapping | Dashboard | Match status for each PDF. | Shows whether drawings connect to catalogue rows. |
| PDF input table | PDF Import | PDF pages, identifiers, variants, warnings. | Validates ingestion quality. |
| Evidence table | Extraction Review | Field, value, PDF, page, evidence, confidence, status. | Makes extraction auditable. |
| Generated catalogue table | Generated Catalogue | Catalogue-format rows generated from PDFs. | Shows Excel-ready output. |
| Focused product table | Product Explorer | All isolating cock rows and attributes. | Provides the main product view. |
| AI-mapped drawing rows | Product Explorer | Rows generated from the attached PDFs. | Lets engineers compare source PDF extraction to catalogue structure. |
| Clustered products table | Clusters | PCA coordinates, cluster label, product metadata. | Explains what is plotted in the cluster chart. |
| Product type table | Family Explorer | Counts by product type. | Shows distribution of focused rows. |
| Characteristic values table | Characteristic Analysis | Counts of values per technical attribute. | Shows dominant values and sparse attributes. |
| Rule influence table | Part Number Rules | Influence, support, confidence, distinct values. | Explains PartNumber logic signals. |
| Anomaly table | Anomalies | Severity, type, evidence. | Prioritizes rows needing review. |
| Similarity table | Similar Products | Similar product candidates and shared reasons. | Helps find related or alternative codes. |
| BOM table | BOM Analysis | Component-like rows from PDF text. | Shows component reuse evidence. |

## 7. What The Analysis Helps With

The analysis helps with:

- Checking whether the isolating cock catalogue scope matches the expected code count.
- Mapping drawing data into catalogue-compatible Excel rows.
- Seeing which attributes define product variants.
- Finding common product configurations.
- Detecting missing or duplicate combinations.
- Finding low-confidence extracted fields that need engineer validation.
- Understanding possible PartNumber logic.
- Identifying similar products.
- Finding shared components from drawing BOM text.
- Producing a report that separates facts, algorithmic inferences, and limitations.

## 8. Current Limitations

The current demo is intentionally local and deterministic.

Not yet implemented:

- OCR fallback for scanned drawings.
- Real CAD/STEP/STP geometry similarity.
- External AI/vision provider integration.
- Persistent human validation database.
- Full production-grade BOM table parser.

The app already marks uncertain results as review items instead of silently guessing.
