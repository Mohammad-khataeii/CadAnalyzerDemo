from pathlib import Path

import pandas as pd

from app.catalogue.loader import CatalogueLoader
from app.catalogue.matcher import CatalogueMatcher
from app.clustering.engine import ClusteringEngine
from app.config.settings import DemoSettings
from app.pdf.analyzer import PDFAnalyzer
from app.rules.discovery import RuleDiscoveryEngine
from app.services.demo_runner import DemoRunner


def test_catalogue_loading():
    df, profile = CatalogueLoader().load(DemoSettings().catalogue_path)
    assert "PartNumber" in df.columns
    assert profile.row_count > 100
    assert "Technical attribute 1" in profile.technical_columns


def test_pdf_loading_and_part_numbers():
    pdf_path = next(path for path in DemoSettings().pdf_paths if path.exists())
    analysis = PDFAnalyzer().analyze(pdf_path)
    assert analysis.page_count >= 1
    assert analysis.part_numbers
    assert analysis.fields["Drawing number"] not in {"", "UNKNOWN", "NOT_FOUND"}


def test_catalogue_matching():
    settings = DemoSettings()
    df, _ = CatalogueLoader().load(settings.catalogue_path)
    analyses = [PDFAnalyzer().analyze(path) for path in settings.pdf_paths]
    matches = CatalogueMatcher().match(df, analyses)
    assert matches
    assert any(match.status in {"MATCH", "PREDICTED MATCH", "AMBIGUOUS"} for match in matches)


def test_rule_discovery_and_configuration_matrix():
    df, _ = CatalogueLoader().load(DemoSettings().catalogue_path)
    results = RuleDiscoveryEngine().discover(df)
    assert results["influence"]
    assert "configuration_matrix" in results


def test_clustering():
    df, _ = CatalogueLoader().load(DemoSettings().catalogue_path)
    clusters = ClusteringEngine().run(df)
    assert clusters["points"]
    assert clusters["explanations"]


def test_demo_exports(tmp_path):
    settings = DemoSettings(output_dir=tmp_path)
    progress = []
    result, generated, evidence = DemoRunner(settings, progress_callback=lambda percent, message: progress.append((percent, message))).run()
    assert len(generated) >= 2
    assert len(evidence) >= 2
    assert result.output_files["catalogue_csv"].exists()
    assert result.output_files["report"].exists()
    assert progress[0][0] == 0
    assert progress[-1][0] == 100
    assert [p for p, _ in progress] == sorted(p for p, _ in progress)
    workbook = pd.ExcelFile(result.output_files["catalogue_xlsx"])
    assert "Technical Summary" in workbook.sheet_names
    assert "Technical Characteristics" in workbook.sheet_names


def test_generated_catalogue_keeps_template_structure_and_pdf_codes(tmp_path):
    settings = DemoSettings(output_dir=tmp_path)
    template, _ = CatalogueLoader().load(settings.catalogue_path)
    _, generated, _ = DemoRunner(settings).run()
    assert list(generated.columns) == list(template.columns)

    generated_parts = set(generated["PartNumber"])
    for expected_part in {
        "FT0024835-100",
        "FT0129531-100",
        "FT0105784-100",
        "FT0027389-100",
        "FT0127469-100",
        "FT0127470-100",
    }:
        assert expected_part in generated_parts


def test_generated_catalogue_maps_additional_pdf_characteristics(tmp_path):
    settings = DemoSettings(output_dir=tmp_path)
    _, generated, _ = DemoRunner(settings).run()
    by_part = generated.set_index("PartNumber")

    assert by_part.loc["FT0027389-100", "Technical attribute 1"] == "TYPE 20 - 120°"
    assert by_part.loc["FT0127469-100", "Technical attribute 1"] == 'OUTLET 3/4" GAS UNI-ISO 228'
    assert by_part.loc["FT0127469-100", "Technical attribute 2"] == "ENVELOPE 500 x 370 x 265 mm"
    assert "WORKING PRESSURE 11 bar(g)" in by_part.loc["FT0127470-100", "Technical attribute 3"]


def test_generated_workbook_contains_aggressive_technical_characteristics(tmp_path):
    settings = DemoSettings(output_dir=tmp_path)
    result, _, _ = DemoRunner(settings).run()
    technical = pd.read_excel(result.output_files["catalogue_xlsx"], sheet_name="Technical Characteristics").fillna("")
    summary = pd.read_excel(result.output_files["catalogue_xlsx"], sheet_name="Technical Summary").fillna("")

    assert len(technical) >= 150
    assert {"material", "standard", "electrical", "pressure", "temperature"}.issubset(set(technical["Category"]))
    assert "STAINLESS STEEL" in set(technical["Mapped value"])
    assert any(technical["Mapped value"].astype(str).str.contains("IP54|IP 54", regex=True))
    assert not summary.empty
