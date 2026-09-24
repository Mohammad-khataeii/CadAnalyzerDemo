from __future__ import annotations

from copy import copy
import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from openpyxl import load_workbook

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
        advance("Loaded sample catalogue as schema/reference template")
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
        analysis_catalogue = generated.copy()
        demo_focus = self._build_demo_focus(catalogue, analysis_catalogue, expected_count=len(pdf_paths))
        advance("Generated catalogue rows from PDF drawings")
        rule_results = RuleDiscoveryEngine().discover(analysis_catalogue)
        advance("Discovered PDF catalogue PartNumber rules")
        clusters = ClusteringEngine().run(analysis_catalogue, method="kmeans", n_clusters=5)
        advance("Computed PDF catalogue clusters and PCA projection")
        similarity = SimilarityEngine().find_similar(analysis_catalogue)
        advance("Computed technical similarity")
        anomalies = AnomalyDetector().detect(analysis_catalogue, analyses, rule_results)
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
        output_files["focus_catalogue_csv"] = output_dir / "focus_catalogue.csv"
        output_files["focus_catalogue_xlsx"] = output_dir / "focus_catalogue.xlsx"
        generated.to_csv(output_files["catalogue_csv"], index=False)
        self._write_catalogue_workbook(output_files["catalogue_xlsx"], generated, analyses, matches, evidence, anomalies)
        analysis_catalogue.to_csv(output_files["focus_catalogue_csv"], index=False)
        analysis_catalogue.to_excel(output_files["focus_catalogue_xlsx"], index=False)
        evidence.to_csv(output_files["evidence_csv"], index=False)
        pd.DataFrame(anomalies).to_csv(output_files["anomalies_csv"], index=False)
        pd.DataFrame([row for a in analyses for row in a.bom_rows]).to_csv(output_files["bom_csv"], index=False)
        self._write_json(output_files["analysis_json"], analyses, matches, rule_results, anomalies, clusters, similarity, bom_summary, demo_focus)
        advance("Exported CSV, XLSX, and JSON outputs")
        bom_rows = [row for a in analyses for row in a.bom_rows]
        chart_builder = ChartBuilder()
        visual_title = demo_focus["filter_value"]
        chart_paths = chart_builder.build_all(analysis_catalogue, clusters, output_dir, anomalies=anomalies, evidence=evidence, bom_rows=bom_rows, rule_results=rule_results)
        chart_paths.update(chart_builder.build_demo_focus(analysis_catalogue, clusters, output_dir, len(analysis_catalogue), visual_title))
        output_files.update(chart_paths)
        output_files.update(chart_builder.build_visual_packs(output_files, output_dir, visual_title))
        advance("Generated PDF catalogue visual analytics")

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
        output_files["report"] = ReportBuilder().build(result, analysis_catalogue, output_dir / "DEMO_ANALYSIS_REPORT.md", bom_summary)
        advance("Built analysis report")
        self._progress(100, "Analysis complete")
        return result, generated, evidence

    def _progress(self, percent: int, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(percent, message)

    def _build_generated_catalogue(self, catalogue: pd.DataFrame, analyses: list[Any], matches: list[Any]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        catalogue_columns = list(catalogue.columns)
        match_by_pdf = {match.source_pdf: match for match in matches}
        for analysis in analyses:
            match = match_by_pdf.get(analysis.source_pdf.name)
            row = self._matched_catalogue_base(catalogue, match) if match else {column: "" for column in catalogue.columns}
            row["OPS Product Category"] = row.get("OPS Product Category") or "C - BRAKE CONTROL"
            has_catalogue_match = bool(match and match.matched_part_number)
            is_variant_reference = self._is_variant_reference(analysis, match)
            if has_catalogue_match and not is_variant_reference:
                row["Product Family"] = self._existing_or_known(row.get("Product Family"), analysis.fields.get("Product Family"))
                row["Product Name"] = self._existing_or_known(row.get("Product Name"), analysis.fields.get("Product Name"))
                row["Product Type"] = self._existing_or_known(row.get("Product Type"), analysis.fields.get("Product Type"))
            else:
                row["Product Family"] = self._known_or_existing(analysis.fields.get("Product Family"), row.get("Product Family"))
                row["Product Name"] = self._known_or_existing(analysis.fields.get("Product Name"), row.get("Product Name"))
                row["Product Type"] = self._known_or_existing(analysis.fields.get("Product Type"), row.get("Product Type"))
            self._map_technical_attributes(row, analysis, prefer_existing=has_catalogue_match and not is_variant_reference)
            configuration = analysis.fields.get("Configuration", "")
            if not row.get("Configurability sheet") or is_variant_reference:
                row["Configurability sheet"] = configuration if configuration and configuration != "UNKNOWN" else "PDF - REVIEW"
            part_number, master_pn = self._catalogue_part_numbers(analysis, match, is_variant_reference)
            row["PartNumber"] = part_number
            row["Master PN"] = master_pn
            row["Maturity"] = row.get("Maturity") or analysis.fields.get("Status") or "Extracted"
            row["Preferred"] = row.get("Preferred") or "Needs review"
            row["Q.,ty in 2026"] = row.get("Q.,ty in 2026", "")
            rows.append({column: row.get(column, "") for column in catalogue_columns})
        return pd.DataFrame(rows, columns=catalogue_columns)

    def _is_variant_reference(self, analysis: Any, match: Any) -> bool:
        drawing = str(analysis.fields.get("Drawing number", ""))
        return bool(match and match.matched_part_number and drawing.startswith("FT") and match.matched_part_number != drawing)

    def _catalogue_part_numbers(self, analysis: Any, match: Any, is_variant_reference: bool) -> tuple[str, str]:
        drawing = str(analysis.fields.get("Drawing number", "UNKNOWN"))
        if is_variant_reference and drawing.startswith("FT"):
            return drawing, drawing
        if match and match.matched_part_number:
            return match.matched_part_number, match.matched_master_pn or match.matched_part_number
        part_number = self._primary_part(analysis.part_numbers, drawing)
        return part_number, self._master_part(analysis.part_numbers, drawing)

    def _analysis_columns(self, analysis: Any, match: Any) -> dict[str, Any]:
        evidence = analysis.evidence
        avg_confidence = round(sum(ev.confidence for ev in evidence) / max(1, len(evidence)), 2)
        review_fields = sorted(field for field, value in analysis.fields.items() if value in {"UNKNOWN", "NOT_FOUND", "NEEDS REVIEW"})
        return {
            "Source PDF": analysis.source_pdf.name,
            "PDF Page Count": analysis.page_count,
            "Catalogue Match Status": match.status if match else "UNMATCHED",
            "Catalogue Match Reason": match.reason if match else "No match object",
            "Catalogue Candidate Count": match.candidate_count if match else 0,
            "Matched PartNumber": match.matched_part_number if match else "",
            "Matched Master PN": match.matched_master_pn if match else "",
            "Drawing number": analysis.fields.get("Drawing number", ""),
            "Drawing revision": analysis.fields.get("Drawing revision", ""),
            "Drawing title": analysis.fields.get("Drawing title", ""),
            "Extracted diameter": analysis.fields.get("Diameter", ""),
            "Extracted LED": analysis.fields.get("LED", ""),
            "Extracted pressure": analysis.fields.get("Pressure", ""),
            "Extracted mounting": analysis.fields.get("Mounting", ""),
            "Extracted configuration": analysis.fields.get("Configuration", ""),
            "Extracted status": analysis.fields.get("Status", ""),
            "Extracted drain": analysis.fields.get("Drain", ""),
            "Extracted contact": analysis.fields.get("Contact", ""),
            "Extracted handle": analysis.fields.get("Handle", ""),
            "Extracted fitting": analysis.fields.get("Fitting", ""),
            "Extracted accuracy class": analysis.fields.get("Accuracy class", ""),
            "Extracted outlet connection": analysis.fields.get("Outlet connection", ""),
            "Extracted envelope dimensions": analysis.fields.get("Envelope dimensions", ""),
            "Extracted mounting holes": analysis.fields.get("Mounting holes", ""),
            "Extracted key slot": analysis.fields.get("Key slot", ""),
            "Extracted working pressure": analysis.fields.get("Working pressure", ""),
            "Extracted working temperature": analysis.fields.get("Working temperature", ""),
            "Extracted startup temperature": analysis.fields.get("Startup temperature", ""),
            "Extracted duty cycle": analysis.fields.get("Duty cycle", ""),
            "Extracted starts per hour": analysis.fields.get("Starts per hour", ""),
            "Extracted weight": analysis.fields.get("Weight", ""),
            "Detected identifiers": ", ".join(analysis.part_numbers),
            "Detected variants": ", ".join(analysis.variants),
            "BOM row count": len(analysis.bom_rows),
            "BOM component identifiers": ", ".join(str(row.get("ComponentPartNumber", "")) for row in analysis.bom_rows[:30]),
            "Average extraction confidence": avg_confidence,
            "Fields needing review": ", ".join(review_fields),
            "PDF warnings": "; ".join(analysis.warnings),
            "Analysis note": "Generated from PDF extraction; sample Excel used only as schema/reference.",
        }

    def _write_catalogue_workbook(self, path: Path, generated: pd.DataFrame, analyses: list[Any], matches: list[Any], evidence: pd.DataFrame, anomalies: list[dict[str, Any]]) -> None:
        pdf_summary = pd.DataFrame(
            [
                {
                    "Source PDF": analysis.source_pdf.name,
                    "Pages": analysis.page_count,
                    "Drawing number": analysis.fields.get("Drawing number", ""),
                    "Drawing title": analysis.fields.get("Drawing title", ""),
                    "Product Family": analysis.fields.get("Product Family", ""),
                    "Product Name": analysis.fields.get("Product Name", ""),
                    "Product Type": analysis.fields.get("Product Type", ""),
                    "Identifiers": ", ".join(analysis.part_numbers),
                    "Variants": ", ".join(analysis.variants),
                    "BOM rows": len(analysis.bom_rows),
                    "Warnings": "; ".join(analysis.warnings),
                }
                for analysis in analyses
            ]
        )
        bom_rows = pd.DataFrame([row for analysis in analyses for row in analysis.bom_rows])
        match_rows = pd.DataFrame([match.__dict__ for match in matches])
        match_by_pdf = {match.source_pdf: match for match in matches}
        anomaly_rows = pd.DataFrame(anomalies)
        review_rows = pd.DataFrame([self._analysis_columns(analysis, match_by_pdf.get(analysis.source_pdf.name)) for analysis in analyses])
        technical_rows = self._build_technical_characteristics_frame(analyses)
        self._write_template_catalogue_sheet(path, generated)
        with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            pdf_summary.to_excel(writer, sheet_name="PDF Summary", index=False)
            review_rows.to_excel(writer, sheet_name="PDF Row Review", index=False)
            technical_rows.to_excel(writer, sheet_name="Technical Characteristics", index=False)
            evidence.to_excel(writer, sheet_name="Extraction Evidence", index=False)
            (bom_rows if not bom_rows.empty else pd.DataFrame(columns=["SourcePDF", "ComponentPartNumber", "Quantity", "Description", "Specification", "ABC class", "EvidenceText"])).to_excel(writer, sheet_name="BOM Components", index=False)
            (match_rows if not match_rows.empty else pd.DataFrame(columns=["source_pdf", "status", "matched_part_number", "matched_master_pn", "reason", "candidate_count"])).to_excel(writer, sheet_name="Matches", index=False)
            (anomaly_rows if not anomaly_rows.empty else pd.DataFrame(columns=["Type", "Severity", "Evidence"])).to_excel(writer, sheet_name="Anomalies", index=False)

    def _build_technical_characteristics_frame(self, analyses: list[Any]) -> pd.DataFrame:
        fields = [
            "Diameter",
            "LED",
            "Pressure",
            "Mounting",
            "Fitting",
            "Accuracy class",
            "Earth lug",
            "Outlet connection",
            "Envelope dimensions",
            "Mounting holes",
            "Key slot",
            "Working pressure",
            "Working temperature",
            "Startup temperature",
            "Duty cycle",
            "Starts per hour",
            "Weight",
            "Configuration",
            "Compressor detail",
        ]
        rows: list[dict[str, Any]] = []
        for analysis in analyses:
            for field in fields:
                value = analysis.fields.get(field, "")
                if not value or value in {"UNKNOWN", "NOT_FOUND", "NEEDS REVIEW"}:
                    continue
                rows.append(
                    {
                        "Source PDF": analysis.source_pdf.name,
                        "Drawing number": analysis.fields.get("Drawing number", ""),
                        "Product Name": analysis.fields.get("Product Name", ""),
                        "Product Type": analysis.fields.get("Product Type", ""),
                        "Characteristic": field,
                        "Mapped value": value,
                    }
                )
        return pd.DataFrame(rows, columns=["Source PDF", "Drawing number", "Product Name", "Product Type", "Characteristic", "Mapped value"])

    def _write_template_catalogue_sheet(self, path: Path, generated: pd.DataFrame) -> None:
        wb = load_workbook(self.settings.catalogue_path)
        ws = wb[wb.sheetnames[0]]
        header_row = 4
        first_data_row = 5
        first_catalogue_col = 2
        headers = [ws.cell(header_row, column).value for column in range(first_catalogue_col, ws.max_column + 1)]
        style_source_row = first_data_row if ws.max_row >= first_data_row else header_row
        style_by_column = {
            column: {
                "style": copy(ws.cell(style_source_row, column)._style),
                "number_format": ws.cell(style_source_row, column).number_format,
                "alignment": copy(ws.cell(style_source_row, column).alignment),
                "protection": copy(ws.cell(style_source_row, column).protection),
            }
            for column in range(first_catalogue_col, ws.max_column + 1)
        }
        if ws.max_row >= first_data_row:
            ws.delete_rows(first_data_row, ws.max_row - first_data_row + 1)
        for row_offset, record in enumerate(generated.to_dict("records"), start=first_data_row):
            for column_offset, header in enumerate(headers, start=first_catalogue_col):
                cell = ws.cell(row_offset, column_offset)
                cell.value = record.get(header, "")
                source = style_by_column[column_offset]
                cell._style = copy(source["style"])
                cell.number_format = source["number_format"]
                cell.alignment = copy(source["alignment"])
                cell.protection = copy(source["protection"])
        ws.freeze_panes = "B5"
        wb.save(path)

    def _map_technical_attributes(self, row: dict[str, Any], analysis: Any, prefer_existing: bool = False) -> None:
        choose = self._existing_or_known if prefer_existing else self._known_or_existing
        product_name = analysis.fields.get("Product Name", "")
        if product_name == "D - MANOMETERS":
            row["Technical attribute 1"] = choose(row.get("Technical attribute 1"), analysis.fields.get("Diameter")) if prefer_existing else choose(analysis.fields.get("Diameter"), row.get("Technical attribute 1"))
            row["Technical attribute 2"] = choose(row.get("Technical attribute 2"), analysis.fields.get("LED")) if prefer_existing else choose(analysis.fields.get("LED"), row.get("Technical attribute 2"))
            row["Technical attribute 3"] = choose(row.get("Technical attribute 3"), analysis.fields.get("Pressure")) if prefer_existing else choose(analysis.fields.get("Pressure"), row.get("Technical attribute 3"))
            row["Technical attribute 4"] = choose(row.get("Technical attribute 4"), analysis.fields.get("Mounting")) if prefer_existing else choose(analysis.fields.get("Mounting"), row.get("Technical attribute 4"))
            return
        if product_name == "A-BURAN COMPRESSOR":
            row["Technical attribute 1"] = self._first_known(analysis.fields.get("Outlet connection"), analysis.fields.get("Compressor detail"), row.get("Technical attribute 1"))
            row["Technical attribute 2"] = self._first_known(analysis.fields.get("Envelope dimensions"), row.get("Technical attribute 2"))
            row["Technical attribute 3"] = self._join_known(analysis.fields.get("Weight"), analysis.fields.get("Working pressure"), fallback=row.get("Technical attribute 3"))
            row["Technical attribute 4"] = self._first_known(analysis.fields.get("Mounting holes"), analysis.fields.get("Key slot"), row.get("Technical attribute 4"))
            return
        row["Technical attribute 1"] = choose(row.get("Technical attribute 1"), analysis.fields.get("Diameter")) if prefer_existing else choose(analysis.fields.get("Diameter"), row.get("Technical attribute 1"))
        row["Technical attribute 2"] = choose(row.get("Technical attribute 2"), analysis.fields.get("Drain")) if prefer_existing else choose(analysis.fields.get("Drain"), row.get("Technical attribute 2"))
        row["Technical attribute 3"] = choose(row.get("Technical attribute 3"), analysis.fields.get("Contact")) if prefer_existing else choose(analysis.fields.get("Contact"), row.get("Technical attribute 3"))
        row["Technical attribute 4"] = choose(row.get("Technical attribute 4"), analysis.fields.get("Handle")) if prefer_existing else choose(analysis.fields.get("Handle"), row.get("Technical attribute 4"))

    def _focus_catalogue(self, catalogue: pd.DataFrame) -> pd.DataFrame:
        focus_value = self.settings.focus_product_name.upper()
        if "Product Name" not in catalogue.columns:
            return catalogue.iloc[0:0].copy()
        mask = catalogue["Product Name"].astype(str).str.upper().eq(focus_value)
        return catalogue.loc[mask].copy()

    def _build_demo_focus(self, catalogue: pd.DataFrame, focus_catalogue: pd.DataFrame, expected_count: int | None = None) -> dict[str, Any]:
        technical = [c for c in catalogue.columns if c.startswith("Technical attribute")]
        preview_columns = [c for c in ["PartNumber", "Master PN", "Product Family", "Product Name", "Product Type", *technical] if c in focus_catalogue.columns]
        attribute_counts: dict[str, dict[str, int]] = {}
        for column in ["Product Type", *technical]:
            if column in focus_catalogue.columns:
                counts = focus_catalogue[column].replace("", "UNKNOWN").value_counts().head(12)
                attribute_counts[column] = {str(k): int(v) for k, v in counts.items()}
        found = int(len(focus_catalogue))
        expected = int(expected_count if expected_count is not None else found)
        return {
            "brief": [
                "Use the initial Excel catalogue as a schema/reference template only.",
                "Read the supplied PDF drawings and produce a new catalogue from those PDFs.",
                "Map extracted drawing characteristics into the catalogue-compatible Excel columns.",
                "Run requested 1st-level and 2nd-level diagrams on the PDF-generated catalogue.",
            ],
            "filter_column": "Source",
            "filter_value": "PDF-generated catalogue",
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

    def _first_known(self, *values: Any) -> str:
        for value in values:
            if value and str(value) not in {"UNKNOWN", "NOT_FOUND", "NEEDS REVIEW"}:
                return str(value)
        return ""

    def _join_known(self, *values: Any, fallback: Any = "") -> str:
        known = [str(value) for value in values if value and str(value) not in {"UNKNOWN", "NOT_FOUND", "NEEDS REVIEW"}]
        return "; ".join(known) if known else (str(fallback) if fallback else "")

    def _existing_or_known(self, existing: str | None, extracted: str | None) -> str:
        if existing and existing not in {"UNKNOWN", "NOT_FOUND"}:
            return existing
        return self._known_or_existing(extracted, existing)

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
