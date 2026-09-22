from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from app.anomalies.detector import AnomalyDetector
from app.bom.analyzer import BOMAnalyzer
from app.catalogue.loader import CatalogueLoader
from app.catalogue.matcher import CatalogueMatcher
from app.clustering.engine import ClusteringEngine
from app.config.settings import DemoSettings, ensure_directories
from app.models.domain import DemoRunResult, Evidence
from app.pdf.analyzer import PDFAnalyzer
from app.reporting.report import ReportBuilder
from app.rules.discovery import RuleDiscoveryEngine
from app.similarity.engine import SimilarityEngine
from app.visualization.charts import ChartBuilder


class DemoRunner:
    def __init__(self, settings: DemoSettings | None = None, progress_callback: Callable[[int, str], None] | None = None) -> None:
        self.settings = settings or DemoSettings()
        self.progress_callback = progress_callback

    def run(self) -> tuple[DemoRunResult, pd.DataFrame, pd.DataFrame]:
        pdf_paths = [path for path in self.settings.pdf_paths if path.exists()]
        total_steps = 13 + len(pdf_paths)
        completed_steps = 0

        def advance(message: str) -> None:
            nonlocal completed_steps
            completed_steps += 1
            percent = min(100, round((completed_steps / total_steps) * 100))
            self._progress(percent, message)

        self._progress(0, "Preparing analysis")
        ensure_directories()
        output_dir = self.settings.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        advance("Prepared output folders")

        catalogue, profile = CatalogueLoader().load(self.settings.catalogue_path)
        focus_catalogue = self._focus_catalogue(catalogue)
        demo_focus = self._build_demo_focus(catalogue, focus_catalogue)
        advance("Loaded catalogue and isolated demo category")
        pdf_analyzer = PDFAnalyzer()
        analyses = []
        for path in pdf_paths:
            analyses.append(pdf_analyzer.analyze(path))
            advance(f"Analyzed PDF: {path.name}")

        evidence = self._build_evidence_frame(analyses)
        advance("Built extraction evidence")
        matches = CatalogueMatcher().match(catalogue, analyses)
        advance("Matched PDFs to catalogue")
        generated = self._build_generated_catalogue(catalogue, analyses, matches)
        advance("Generated catalogue-compatible rows")
        rule_results = RuleDiscoveryEngine().discover(focus_catalogue)
        advance("Discovered isolating cock PartNumber rules")
        clusters = ClusteringEngine().run(focus_catalogue, method="kmeans", n_clusters=5)
        advance("Computed isolating cock clusters and PCA projection")
        similarity = SimilarityEngine().find_similar(focus_catalogue)
        advance("Computed technical similarity")
        anomalies = AnomalyDetector().detect(focus_catalogue, analyses, rule_results)
        advance("Detected anomalies")
        bom_summary = BOMAnalyzer().summarize(analyses)
        advance("Summarized BOM/component reuse")

        output_files: dict[str, Path] = {}
        output_files["catalogue_csv"] = output_dir / "catalogue_generated.csv"
        output_files["catalogue_xlsx"] = output_dir / "catalogue_generated.xlsx"
        output_files["evidence_csv"] = output_dir / "extraction_evidence.csv"
        output_files["analysis_json"] = output_dir / "analysis_results.json"
        output_files["anomalies_csv"] = output_dir / "anomalies.csv"
        output_files["bom_csv"] = output_dir / "bom_components.csv"
        output_files["focus_catalogue_csv"] = output_dir / "isolating_cocks_catalogue.csv"
        output_files["focus_catalogue_xlsx"] = output_dir / "isolating_cocks_catalogue.xlsx"
        generated.to_csv(output_files["catalogue_csv"], index=False)
        generated.to_excel(output_files["catalogue_xlsx"], index=False)
        focus_catalogue.to_csv(output_files["focus_catalogue_csv"], index=False)
        focus_catalogue.to_excel(output_files["focus_catalogue_xlsx"], index=False)
        evidence.to_csv(output_files["evidence_csv"], index=False)
        pd.DataFrame(anomalies).to_csv(output_files["anomalies_csv"], index=False)
        pd.DataFrame([row for a in analyses for row in a.bom_rows]).to_csv(output_files["bom_csv"], index=False)
        self._write_json(output_files["analysis_json"], analyses, matches, rule_results, anomalies, clusters, similarity, bom_summary, demo_focus)
        advance("Exported CSV, XLSX, and JSON outputs")
        bom_rows = [row for a in analyses for row in a.bom_rows]
        chart_builder = ChartBuilder()
        chart_paths = chart_builder.build_all(focus_catalogue, clusters, output_dir, anomalies=anomalies, evidence=evidence, bom_rows=bom_rows, rule_results=rule_results)
        chart_paths.update(chart_builder.build_demo_focus(focus_catalogue, clusters, output_dir, self.settings.focus_expected_count))
        output_files.update(chart_paths)
        advance("Generated isolating cock visual analytics")

        result = DemoRunResult(
            catalogue_profile=profile,
            pdf_analyses=analyses,
            generated_catalogue_rows=len(generated),
            evidence_rows=len(evidence),
            demo_focus=demo_focus,
            matches=matches,
            rule_results=rule_results,
            anomalies=anomalies,
            clusters=clusters,
            similarity=similarity,
            output_files=output_files,
        )
        output_files["report"] = ReportBuilder().build(result, focus_catalogue, output_dir / "DEMO_ANALYSIS_REPORT.md", bom_summary)
        advance("Built analysis report")
        self._progress(100, "Analysis complete")
        return result, generated, evidence

    def _progress(self, percent: int, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(percent, message)

    def _build_generated_catalogue(self, catalogue: pd.DataFrame, analyses: list[Any], matches: list[Any]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        match_by_pdf = {match.source_pdf: match for match in matches}
        for analysis in analyses:
            match = match_by_pdf.get(analysis.source_pdf.name)
            row = self._matched_catalogue_base(catalogue, match) if match else {column: "" for column in catalogue.columns}
            row["OPS Product Category"] = row.get("OPS Product Category") or "C - BRAKE CONTROL"
            row["Product Family"] = self._known_or_existing(analysis.fields.get("Product Family"), row.get("Product Family"))
            row["Product Name"] = self._known_or_existing(analysis.fields.get("Product Name"), row.get("Product Name"))
            row["Product Type"] = self._known_or_existing(analysis.fields.get("Product Type"), row.get("Product Type"))
            row["Technical attribute 1"] = self._known_or_existing(analysis.fields.get("Diameter"), row.get("Technical attribute 1"))
            row["Technical attribute 2"] = self._known_or_existing(analysis.fields.get("Drain"), row.get("Technical attribute 2"))
            row["Technical attribute 3"] = self._known_or_existing(analysis.fields.get("Contact"), row.get("Technical attribute 3"))
            row["Technical attribute 4"] = self._known_or_existing(analysis.fields.get("Handle"), row.get("Technical attribute 4"))
            row["Configurability sheet"] = "EXTRACTED FROM PDF - REVIEW REQUIRED"
            row["PartNumber"] = self._primary_part(analysis.part_numbers, analysis.fields.get("Drawing number", "UNKNOWN"))
            row["Master PN"] = self._master_part(analysis.part_numbers, analysis.fields.get("Drawing number", "UNKNOWN"))
            row["Maturity"] = "EXTRACTED"
            row["Preferred"] = "NEEDS REVIEW"
            row["Q.,ty in 2026"] = ""
            rows.append(row)
        extension_rows = []
        for analysis in analyses:
            base = {column: "" for column in catalogue.columns}
            base.update(
                {
                    "OPS Product Category": "EXTRACTION METADATA",
                    "Product Family": analysis.source_pdf.name,
                    "Product Name": analysis.fields.get("Drawing title", ""),
                    "Product Type": "PDF DOCUMENT",
                    "PartNumber": analysis.fields.get("Drawing number", ""),
                    "Master PN": analysis.fields.get("Drawing number", ""),
                    "Maturity": "TRACEABILITY",
                    "Preferred": "N/A",
                }
            )
            extension_rows.append(base)
        return pd.DataFrame(rows + extension_rows, columns=catalogue.columns)

    def _focus_catalogue(self, catalogue: pd.DataFrame) -> pd.DataFrame:
        focus_value = self.settings.focus_product_name.upper()
        if "Product Name" not in catalogue.columns:
            return catalogue.iloc[0:0].copy()
        mask = catalogue["Product Name"].astype(str).str.upper().eq(focus_value)
        return catalogue.loc[mask].copy()

    def _build_demo_focus(self, catalogue: pd.DataFrame, focus_catalogue: pd.DataFrame) -> dict[str, Any]:
        technical = [c for c in catalogue.columns if c.startswith("Technical attribute")]
        preview_columns = [c for c in ["PartNumber", "Master PN", "Product Family", "Product Name", "Product Type", *technical] if c in focus_catalogue.columns]
        attribute_counts: dict[str, dict[str, int]] = {}
        for column in ["Product Type", *technical]:
            if column in focus_catalogue.columns:
                counts = focus_catalogue[column].replace("", "UNKNOWN").value_counts().head(12)
                attribute_counts[column] = {str(k): int(v) for k, v in counts.items()}
        found = int(len(focus_catalogue))
        expected = int(self.settings.focus_expected_count)
        return {
            "brief": [
                "Review engineering-mapped drawings and the source catalogue.",
                "Focus on Product Name column value B - ISOLATING COCKS.",
                "Validate the expected 58-code demo scope against the loaded Excel file.",
                "Extract characteristics from attached PDF drawings and map them into catalogue-compatible Excel rows.",
                "Show cluster and cross-characteristic visuals for the focused product set.",
            ],
            "filter_column": "Product Name",
            "filter_value": self.settings.focus_product_name,
            "expected_codes": expected,
            "found_codes": found,
            "missing_vs_expected": max(0, expected - found),
            "technical_columns": technical,
            "attribute_counts": attribute_counts,
            "records": focus_catalogue[preview_columns].to_dict("records") if preview_columns else [],
        }

    def _primary_part(self, part_numbers: list[str], fallback: str) -> str:
        if "XX" in fallback:
            return fallback
        for part in part_numbers:
            if "XX" not in part and part not in {"TBA", "N/A"}:
                return part
        return fallback

    def _master_part(self, part_numbers: list[str], fallback: str) -> str:
        for part in part_numbers:
            if "XX" in part:
                return part
        if fallback.startswith("FT") and fallback.endswith("-100"):
            return fallback[:-3] + "XXX"
        return fallback

    def _matched_catalogue_base(self, catalogue: pd.DataFrame, match: Any) -> dict[str, Any]:
        if not match or not match.matched_part_number:
            return {column: "" for column in catalogue.columns}
        rows = catalogue[catalogue["PartNumber"] == match.matched_part_number]
        if rows.empty:
            return {column: "" for column in catalogue.columns}
        return rows.iloc[0].to_dict()

    def _known_or_existing(self, extracted: str | None, existing: str | None) -> str:
        if extracted and extracted not in {"UNKNOWN", "NOT_FOUND"}:
            return extracted
        return existing or extracted or "UNKNOWN"

    def _build_evidence_frame(self, analyses: list[Any]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for analysis in analyses:
            for ev in analysis.evidence:
                rows.append(ev.__dict__)
            for field, value in analysis.fields.items():
                if value in {"UNKNOWN", "NOT_FOUND", "NEEDS REVIEW"}:
                    rows.append(Evidence(field, value, analysis.source_pdf.name, 0, "Field not unambiguously available in deterministic extraction.", 0.25, "status_marker", "NEEDS REVIEW").__dict__)
        return pd.DataFrame(rows)

    def _write_json(self, path: Path, analyses: list[Any], matches: list[Any], rule_results: dict[str, Any], anomalies: list[dict[str, Any]], clusters: dict[str, Any], similarity: list[dict[str, Any]], bom_summary: dict[str, Any], demo_focus: dict[str, Any]) -> None:
        payload = {
            "demo_focus": demo_focus,
            "pdfs": [
                {
                    "source_pdf": a.source_pdf.name,
                    "page_count": a.page_count,
                    "fields": a.fields,
                    "part_numbers": a.part_numbers,
                    "variants": a.variants,
                    "warnings": a.warnings,
                }
                for a in analyses
            ],
            "matches": [m.__dict__ for m in matches],
            "rules": rule_results,
            "anomalies": anomalies,
            "clusters": clusters,
            "similarity": similarity,
            "bom": bom_summary,
        }
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
