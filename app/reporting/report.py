from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.models.domain import DemoRunResult


class ReportBuilder:
    def build(self, result: DemoRunResult, catalogue: pd.DataFrame, output_path: Path, bom_summary: dict[str, Any]) -> Path:
        profile = result.catalogue_profile
        lines: list[str] = []
        lines.append("# DEMO_ANALYSIS_REPORT")
        lines.append("")
        lines.append("## Executive summary")
        lines.append(f"FACT: The demo loaded `{profile.path.name}` from sheet `{profile.sheet_name}` with {profile.row_count} catalogue rows and {profile.part_rows} rows containing PartNumber values.")
        focus = result.demo_focus
        lines.append(f"FACT: Demo focus is `{focus.get('filter_column')}` = `{focus.get('filter_value')}`.")
        lines.append(f"ALGORITHM RESULT: The meeting target is {focus.get('expected_codes')} codes; the loaded catalogue contains {focus.get('found_codes')} focused rows, leaving a gap of {focus.get('missing_vs_expected')} versus the target.")
        lines.append(f"FACT: The demo analyzed {len(result.pdf_analyses)} supplied engineering PDF files.")
        lines.append(f"ALGORITHM RESULT: Generated {result.generated_catalogue_rows} catalogue-compatible extracted rows and {result.evidence_rows} evidence rows.")
        lines.append("")
        lines.append("## Meeting brief implemented")
        for item in focus.get("brief", []):
            lines.append(f"- FACT: {item}")
        lines.append("")
        lines.append("## Files analyzed")
        lines.extend(f"- FACT: `{a.source_pdf.name}` has {a.page_count} pages, {len(a.part_numbers)} detected part-number-like identifiers, {len(a.variants)} detected variants, and {len(a.bom_rows)} BOM/component rows." for a in result.pdf_analyses)
        lines.append("")
        lines.append("## Catalogue structure")
        lines.append("FACT: Columns preserved from the source catalogue:")
        lines.append(", ".join(profile.columns))
        lines.append("")
        lines.append("## PDF structure")
        for analysis in result.pdf_analyses:
            lines.append(f"### {analysis.source_pdf.name}")
            lines.append(f"FACT: Pages: {analysis.page_count}.")
            for field, value in analysis.fields.items():
                prefix = "UNSUPPORTED / UNKNOWN" if value in {"UNKNOWN", "NOT_FOUND", "NEEDS REVIEW"} else "FACT/INFERENCE"
                lines.append(f"- {prefix}: {field}: {value}")
            if analysis.warnings:
                lines.extend(f"- NEEDS REVIEW: {warning}" for warning in analysis.warnings)
        lines.append("")
        lines.append("## Extracted characteristics")
        for analysis in result.pdf_analyses:
            lines.append(f"- ALGORITHM RESULT: `{analysis.source_pdf.name}` -> {analysis.fields}")
        lines.append("")
        lines.append("## PDF to catalogue mapping")
        for match in result.matches:
            lines.append(f"- ALGORITHM RESULT: `{match.source_pdf}`: {match.status}; PartNumber `{match.matched_part_number or 'N/A'}`; candidates {match.candidate_count}; reason: {match.reason}")
        lines.append("")
        lines.append("## PartNumber patterns discovered")
        for row in result.rule_results.get("influence", []):
            lines.append(f"- ALGORITHM RESULT: {row['Characteristic']}: influence {row['Influence']}, support {row['Support']}, confidence {row['Confidence']}")
        lines.append("")
        lines.append("## Master PN patterns")
        master_count = catalogue.get("Master PN", pd.Series(dtype=str)).replace("", pd.NA).dropna().nunique()
        lines.append(f"ALGORITHM RESULT: {master_count} distinct Master PN values were found. Master PN is retained as a first-class catalogue field.")
        lines.append("")
        lines.append("## Product families")
        for family, count in list(profile.family_counts.items())[:20]:
            lines.append(f"- FACT: {family}: {count}")
        lines.append("")
        lines.append("## Clusters")
        for cluster in result.clusters.get("explanations", []):
            lines.append(f"- ALGORITHM RESULT: Cluster {cluster['Cluster']} has {cluster['Products']} products. Representatives: {', '.join(map(str, cluster['RepresentativeProducts']))}")
        lines.append("")
        lines.append("## Cluster explanations")
        for cluster in result.clusters.get("explanations", []):
            common = "; ".join(f"{c['Feature']}={c['Value']} ({int(c['Share']*100)}%)" for c in cluster["Common"][:5])
            lines.append(f"- ALGORITHM RESULT: Cluster {cluster['Cluster']}: {common}")
        lines.append("")
        lines.append("## Common characteristics")
        for column in profile.technical_columns:
            top = catalogue[column].replace("", pd.NA).dropna().value_counts().head(5)
            lines.append(f"- FACT: {column}: {top.to_dict()}")
        lines.append("")
        lines.append("## Most common configurations")
        tech = profile.technical_columns
        if tech:
            configs = catalogue[tech].replace("", "UNKNOWN").value_counts().head(10)
            for idx, count in configs.items():
                lines.append(f"- ALGORITHM RESULT: {idx}: {count}")
        lines.append("")
        lines.append("## BOM findings")
        lines.append(f"ALGORITHM RESULT: {bom_summary['row_count']} BOM/component-like rows were extracted from supplied PDFs.")
        lines.append(f"ALGORITHM RESULT: Most frequent components: {bom_summary['component_frequency'][:10]}")
        lines.append("")
        lines.append("## Variant findings")
        for analysis in result.pdf_analyses:
            lines.append(f"- ALGORITHM RESULT: `{analysis.source_pdf.name}` variants: {', '.join(analysis.variants[:40]) or 'NOT_FOUND'}")
        lines.append("")
        lines.append("## Similarity findings")
        for row in result.similarity:
            lines.append(f"- ALGORITHM RESULT: {row['Product']} similarity {row['Similarity']}%; reasons: {row['Reasons']}; geometric similarity: {row['GeometricSimilarity']}")
        lines.append("")
        matrix = result.rule_results.get("configuration_matrix", {})
        lines.append("## Missing combinations")
        lines.append(f"ALGORITHM RESULT: For features {matrix.get('features', [])}, expected {matrix.get('expected', 0)}, observed {matrix.get('observed', 0)}, missing {matrix.get('missing', 0)}.")
        lines.append("")
        lines.append("## Duplicate configurations")
        lines.append(f"ALGORITHM RESULT: Duplicate/ambiguous configuration records found: {len(matrix.get('duplicates', []))}.")
        lines.append("")
        lines.append("## Catalogue anomalies")
        for anomaly in result.anomalies[:80]:
            lines.append(f"- {anomaly['Severity']}: {anomaly['Type']} -> {anomaly['Evidence']}")
        lines.append("")
        lines.append("## Extraction confidence")
        all_ev = [ev for analysis in result.pdf_analyses for ev in analysis.evidence]
        avg = sum(ev.confidence for ev in all_ev) / max(1, len(all_ev))
        lines.append(f"ALGORITHM RESULT: Average confidence across recorded evidence rows is {avg:.2f}. Low/unknown fields are marked for review instead of guessed.")
        lines.append("")
        lines.append("## Fields successfully extracted")
        lines.append(", ".join(sorted({ev.field for ev in all_ev})))
        lines.append("")
        lines.append("## Fields requiring review")
        review = sorted({f for a in result.pdf_analyses for f, v in a.fields.items() if v == "NEEDS REVIEW"})
        lines.append(", ".join(review) if review else "None")
        lines.append("")
        lines.append("## Fields not available")
        unavailable = sorted({f for a in result.pdf_analyses for f, v in a.fields.items() if v in {"UNKNOWN", "NOT_FOUND"}})
        lines.append(", ".join(unavailable) if unavailable else "None")
        lines.append("")
        lines.append("## Limitations")
        lines.append("UNSUPPORTED / UNKNOWN: OCR and CAD/STEP geometry extraction are architected as replaceable interfaces but are not required for the supplied vector-text demo.")
        lines.append("UNSUPPORTED / UNKNOWN: Variant-specific handle/drain/connector mappings are partially visible in drawings and BOM text, but ambiguous items are marked for review.")
        lines.append("")
        lines.append("## What is NOT yet implemented")
        lines.append("- UNSUPPORTED / UNKNOWN: Production OCR fallback.")
        lines.append("- UNSUPPORTED / UNKNOWN: Real STEP/STP geometry similarity.")
        lines.append("- UNSUPPORTED / UNKNOWN: External AI/vision provider implementation.")
        lines.append("")
        lines.append("## Recommended next development steps")
        lines.append("1. Add OCR fallback for scanned drawings.")
        lines.append("2. Add a curated mapping table for variant-specific engineering semantics.")
        lines.append("3. Add CAD/STEP ingestion through the GeometryFeatureExtractor interface.")
        lines.append("4. Connect a human validation persistence store.")
        lines.append("")
        lines.append("## Future CAD/3D architecture")
        lines.append("INFERENCE: Use `GeometryFeatureExtractor` to read STEP/STP through Open CASCADE or CadQuery, emit geometry features, then combine technical and geometric similarity without pretending PDF drawings are CAD models.")
        lines.append("")
        lines.append("## Future AI/vision architecture")
        lines.append("INFERENCE: Keep `BaseExtractor`, `LocalExtractor`, `VisionExtractor`, and `LLMExtractor` behind the extraction layer so deterministic local extraction remains available offline.")
        lines.append("")
        lines.append("## GAP ANALYSIS")
        lines.append("| Requirement | Implemented | Evidence | Missing | Priority |")
        lines.append("|-------------|-------------|----------|---------|----------|")
        gap_rows = [
            ("PDF extraction", "Yes", "PyMuPDF native text per page plus evidence", "OCR fallback", "High"),
            ("Catalogue generation", "Yes", "catalogue_generated.csv/xlsx", "Human-reviewed persistence", "High"),
            ("Catalogue compatibility", "Yes", "Original columns preserved", "Full customer validation", "High"),
            ("Characteristic extraction", "Partial", "DN/contact/pressure/temp/title/revision", "Some variant semantics", "High"),
            ("Variant extraction", "Partial", "Detected variant labels", "Precise per-variant deltas", "High"),
            ("PartNumber mapping", "Yes", "Direct/master/characteristic matching", "More family-specific rules", "Medium"),
            ("Master PN mapping", "Yes", "Master PN retained and matched", "None for demo", "Medium"),
            ("Rule discovery", "Yes", "Influence/support/mapping table", "Statistical depth for small families", "Medium"),
            ("Clustering", "Yes", "KMeans/Hierarchical/DBSCAN engine", "UI method switching refinement", "Medium"),
            ("Family discovery", "Yes", "Family counts and cluster links", "Graph UI expansion", "Medium"),
            ("Cross-characteristic analysis", "Yes", "crosstab charts", "More Sankey/treemap screens", "Medium"),
            ("BOM analysis", "Partial", "BOM-like rows and component frequency", "Robust table parser", "High"),
            ("Anomaly detection", "Yes", "anomalies.csv and report", "Rule tuning", "Medium"),
            ("Similarity", "Yes", "technical similarity", "BOM weighting UI", "Medium"),
            ("Visualization", "Yes", "PNG and Plotly HTML charts", "Interactive embedded Plotly", "Low"),
            ("Human validation", "Partial", "Review screen and statuses", "Persistent edits database", "High"),
            ("Export", "Yes", "CSV/XLSX/JSON/Markdown", "None for demo", "Low"),
            ("3D/CAD", "Architecture only", "Explicit unavailable flag", "STEP/STP implementation", "Future"),
            ("AI vision", "Architecture only", "Optional layer documented", "Provider implementation", "Future"),
            ("Reporting", "Yes", "This report", "Customer signoff", "Low"),
        ]
        for row in gap_rows:
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
        lines.append("## FUTURE PROJECT ROADMAP")
        lines.append("### MVP/demo")
        lines.append("Complete local deterministic extraction, catalogue-compatible export, evidence review, clustering, anomalies, and report generation.")
        lines.append("### Phase 2")
        lines.append("Add OCR fallback, stronger BOM table extraction, variant-delta persistence, and validation database.")
        lines.append("### Phase 3")
        lines.append("Add optional AI/vision extractors, richer relationship graphs, and enterprise batch ingestion.")
        lines.append("### Production")
        lines.append("Add authentication, database storage, deployment packaging, audit logs, and CAD/STEP geometry analysis.")
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output_path
