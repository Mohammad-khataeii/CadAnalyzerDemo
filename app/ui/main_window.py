from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QBrush, QColor, QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:  # pragma: no cover - optional runtime dependency in some packages
    QWebEngineView = None

from app.services.demo_runner import DemoRunner
from app.config.settings import DemoSettings


PALETTE = {
    "bg": "#f5f7fb",
    "panel": "#ffffff",
    "panel_alt": "#f8fafc",
    "border": "#d9e1ec",
    "text": "#162033",
    "muted": "#637083",
    "accent": "#2458d3",
    "accent_soft": "#e8efff",
    "green": "#147a52",
    "green_soft": "#e5f6ef",
    "amber": "#9a5b00",
    "amber_soft": "#fff3d6",
    "red": "#b42318",
    "red_soft": "#fee4df",
}


class ProductAnalyzerWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Product Analyzer - Engineering Catalogue POC")
        self.resize(1560, 940)
        self.result = None
        self.generated: pd.DataFrame | None = None
        self.evidence: pd.DataFrame | None = None
        self.current_settings = DemoSettings()
        self.selected_catalogue_path: Path = self.current_settings.catalogue_path
        self.selected_pdf_paths: list[Path] = list(self.current_settings.pdf_paths)
        self.stack = QStackedWidget()
        self.nav = QListWidget()
        self.pages: dict[str, QWidget] = {}
        self.page_bodies: dict[str, QVBoxLayout] = {}
        self._build_ui()
        self._run_demo()

    def _build_ui(self) -> None:
        self.setStyleSheet(self._stylesheet())
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 14, 18)
        sidebar_layout.setSpacing(12)
        brand = QLabel("Product Analyzer")
        brand.setObjectName("Brand")
        subtitle = QLabel("Engineering catalogue automation")
        subtitle.setObjectName("SidebarSubtitle")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(subtitle)
        self.nav.setObjectName("Navigation")
        self.nav.setFixedWidth(260)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        sidebar_layout.addWidget(self.nav, 1)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        for name in [
            "Dashboard",
            "PDF Import",
            "Extraction Review",
            "Generated Catalogue",
            "Product Explorer",
            "Clusters",
            "Family Explorer",
            "Characteristic Analysis",
            "Part Number Rules",
            "Anomalies",
            "Similar Products",
            "BOM Analysis",
            "Reports",
            "Settings",
        ]:
            self._add_page(name)

        toolbar = self.addToolBar("Demo")
        toolbar.setMovable(False)
        run_action = QAction("Run demo", self)
        run_action.triggered.connect(self._run_demo)
        toolbar.addAction(run_action)
        choose_catalogue = QAction("Choose catalogue", self)
        choose_catalogue.triggered.connect(self._choose_catalogue)
        toolbar.addAction(choose_catalogue)
        choose_pdfs = QAction("Choose PDFs", self)
        choose_pdfs.triggered.connect(self._choose_pdfs)
        toolbar.addAction(choose_pdfs)
        run_selected = QAction("Analyze selected files", self)
        run_selected.triggered.connect(self._run_selected_files)
        toolbar.addAction(run_selected)
        open_output = QAction("Open output folder", self)
        open_output.triggered.connect(self._open_output_folder)
        toolbar.addAction(open_output)

    def _add_page(self, name: str) -> None:
        item = QListWidgetItem(name)
        self.nav.addItem(item)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 22, 24, 22)
        page_layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("PageHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(name)
        title.setObjectName("PageTitle")
        description = QLabel(self._page_description(name))
        description.setObjectName("PageDescription")
        description.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(description)
        page_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(16)
        scroll.setWidget(body)
        page_layout.addWidget(scroll, 1)

        help_row = QHBoxLayout()
        help_row.setContentsMargins(0, 0, 0, 0)
        help_row.addStretch(1)
        help_button = QPushButton("?")
        help_button.setObjectName("HelpButton")
        help_button.setFixedSize(38, 38)
        help_button.setToolTip(f"What this page shows: {name}")
        help_button.clicked.connect(lambda checked=False, page_name=name: self._show_page_help(page_name))
        help_row.addWidget(help_button, 0, Qt.AlignRight | Qt.AlignBottom)
        page_layout.addLayout(help_row)

        self.stack.addWidget(page)
        self.pages[name] = page
        self.page_bodies[name] = body_layout
        if self.nav.count() == 1:
            self.nav.setCurrentRow(0)

    def _run_demo(self) -> None:
        self.current_settings = DemoSettings()
        self.selected_catalogue_path = self.current_settings.catalogue_path
        self.selected_pdf_paths = list(self.current_settings.pdf_paths)
        self._run_with_settings(self.current_settings)

    def _run_selected_files(self) -> None:
        if not self.selected_catalogue_path.exists():
            QMessageBox.warning(self, "Catalogue required", "Choose a valid Excel catalogue before running analysis.")
            return
        if not self.selected_pdf_paths:
            QMessageBox.warning(self, "PDFs required", "Choose at least one engineering PDF before running analysis.")
            return
        settings = DemoSettings(
            catalogue_path=self.selected_catalogue_path,
            pdf_paths=tuple(self.selected_pdf_paths),
            output_dir=DemoSettings().output_dir,
        )
        self.current_settings = settings
        self._run_with_settings(settings)

    def _run_with_settings(self, settings: DemoSettings) -> None:
        progress = QProgressDialog("Preparing analysis", None, 0, 100, self)
        progress.setWindowTitle("Analyzing files")
        progress.setWindowModality(Qt.ApplicationModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        def update_progress(percent: int, message: str) -> None:
            progress.setLabelText(f"{message}\n{percent}%")
            progress.setValue(percent)
            QApplication.processEvents()

        try:
            self.result, self.generated, self.evidence = DemoRunner(settings, progress_callback=update_progress).run()
            self._populate_pages()
            progress.setValue(100)
            QApplication.processEvents()
            progress.close()
        except Exception as exc:
            progress.close()
            QMessageBox.critical(self, "Analysis failed", str(exc))
            raise

    def _choose_catalogue(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose catalogue Excel file",
            str(self.selected_catalogue_path.parent if self.selected_catalogue_path else Path.home()),
            "Catalogue files (*.xlsx *.xls *.csv);;Excel files (*.xlsx *.xls);;CSV files (*.csv);;All files (*)",
        )
        if path:
            self.selected_catalogue_path = Path(path)
            self._refresh_import_page_if_ready()

    def _choose_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose engineering PDF files",
            str(self.selected_pdf_paths[0].parent if self.selected_pdf_paths else Path.home()),
            "PDF files (*.pdf);;All files (*)",
        )
        if paths:
            self.selected_pdf_paths = [Path(path) for path in paths]
            self._refresh_import_page_if_ready()

    def _clear_selected_files(self) -> None:
        self.selected_pdf_paths = []
        self._refresh_import_page_if_ready()

    def _refresh_import_page_if_ready(self) -> None:
        if "PDF Import" not in self.page_bodies:
            return
        self._clear_page("PDF Import")
        if self.result is not None:
            self._pdf_import()

    def _clear_page(self, name: str) -> None:
        layout = self.page_bodies[name]
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _populate_pages(self) -> None:
        assert self.result is not None
        for name in self.page_bodies:
            self._clear_page(name)
        self._dashboard()
        self._pdf_import()
        self._review()
        self._generated_catalogue()
        self._product_explorer()
        self._clusters()
        self._family()
        self._characteristics()
        self._rules()
        self._anomalies()
        self._similar()
        self._bom()
        self._reports()
        self._settings()

    def _dashboard(self) -> None:
        r = self.result
        focus = r.demo_focus
        needs_review = sum(1 for a in r.pdf_analyses for v in a.fields.values() if v in {"NEEDS REVIEW", "UNKNOWN", "NOT_FOUND"})
        metrics = [
            ("Demo category", focus.get("filter_value", "UNKNOWN"), "Column value isolated for this demo"),
            ("Target codes", focus.get("expected_codes", 0), "Meeting brief scope"),
            ("Found codes", focus.get("found_codes", 0), "Rows found in loaded Excel"),
            ("Gap", focus.get("missing_vs_expected", 0), "Expected minus loaded rows"),
            ("PDFs analyzed", len(r.pdf_analyses), "Native text extraction plus evidence"),
            ("Catalogue records", r.catalogue_profile.row_count, "Rows loaded from the source Excel"),
            ("Generated rows", r.generated_catalogue_rows, "Catalogue-compatible demo output"),
            ("Evidence rows", r.evidence_rows, "Traceability records"),
            ("Clusters", len(r.clusters.get("explanations", [])), "K-Means with PCA projection"),
            ("Needs review", needs_review, "Fields not guessed"),
            ("Anomalies", len(r.anomalies), "Rule and extraction checks"),
        ]
        self._add_metric_grid("Dashboard", metrics, columns=3)

        self._add_section("Dashboard", "Demo brief", "This app run is configured around the exact isolating-cock demo scope from the engineering meeting.")
        self._add_table("Dashboard", [{"Step": index + 1, "Implemented demo requirement": item} for index, item in enumerate(focus.get("brief", []))], max_height=240)

        chart_row = QSplitter(Qt.Horizontal)
        chart_row.addWidget(self._chart_card("Demo scope check", r.output_files.get("focus_coverage")))
        chart_row.addWidget(self._chart_card("Isolating cock product type", r.output_files.get("focus_product_type")))
        chart_row.setSizes([1, 1])
        self.page_bodies["Dashboard"].addWidget(chart_row)

        match_rows = [m.__dict__ for m in r.matches]
        self._add_section("Dashboard", "PDF to catalogue mapping", "Direct and inferred matching states from the current demo run.")
        self._add_table("Dashboard", match_rows, max_height=220)

    def _pdf_import(self) -> None:
        self._upload_panel("PDF Import")
        rows = []
        for analysis in self.result.pdf_analyses:
            rows.append(
                {
                    "PDF": analysis.source_pdf.name,
                    "Pages": analysis.page_count,
                    "Detected identifiers": len(analysis.part_numbers),
                    "Variants": ", ".join(analysis.variants[:16]),
                    "Warnings": "; ".join(analysis.warnings) or "None",
                }
            )
        self._add_metric_grid(
            "PDF Import",
            [
                ("Input PDFs", len(rows), "Supplied engineering drawings"),
                ("BOM rows", sum(len(a.bom_rows) for a in self.result.pdf_analyses), "Component-like rows extracted"),
                ("Variants", sum(len(a.variants) for a in self.result.pdf_analyses), "Variant tokens detected"),
            ],
            columns=3,
        )
        self._add_table("PDF Import", rows)

    def _review(self) -> None:
        assert self.evidence is not None
        review_count = int((self.evidence.get("status", "") == "NEEDS REVIEW").sum()) if "status" in self.evidence else 0
        self._add_metric_grid("Extraction Review", [("Evidence rows", len(self.evidence), "Every accepted field keeps evidence"), ("Needs review", review_count, "Human validation queue")], columns=2)
        self.page_bodies["Extraction Review"].addWidget(self._chart_card("Extraction confidence by field", self.result.output_files.get("extraction_confidence")))
        self._add_table("Extraction Review", self.evidence.to_dict("records"))

    def _generated_catalogue(self) -> None:
        assert self.generated is not None
        self._add_metric_grid(
            "Generated Catalogue",
            [
                ("Rows", len(self.generated), "Generated catalogue plus metadata rows"),
                ("Columns", len(self.generated.columns), "Original catalogue structure retained"),
                ("Review flags", int((self.generated == "NEEDS REVIEW").sum().sum()), "Values left for engineer validation"),
            ],
            columns=3,
        )
        cat_split = QSplitter(Qt.Horizontal)
        cat_split.addWidget(self._chart_card("Attribute completeness", self.result.output_files.get("attribute_completeness")))
        cat_split.addWidget(self._chart_card("Maturity by family", self.result.output_files.get("maturity_by_family")))
        cat_split.setSizes([1, 1])
        self.page_bodies["Generated Catalogue"].addWidget(cat_split)
        self._add_table("Generated Catalogue", self.generated.to_dict("records"))

    def _product_explorer(self) -> None:
        assert self.generated is not None
        focus_rows = self.result.demo_focus.get("records", [])
        fields = ["PartNumber", "Master PN", "Product Family", "Product Name", "Product Type", "Technical attribute 1", "Technical attribute 2", "Technical attribute 3", "Technical attribute 4"]
        rows = [{key: row.get(key, "") for key in fields if key in row} for row in focus_rows]
        self._add_metric_grid(
            "Product Explorer",
            [
                ("Focused products", len(rows), "Isolating cock catalogue rows"),
                ("Expected codes", self.result.demo_focus.get("expected_codes", 0), "Meeting brief target"),
                ("Review fields", int((self.generated == "NEEDS REVIEW").sum().sum()), "Editable validation targets"),
            ],
            columns=3,
        )
        self._add_section("Product Explorer", "Isolating cock catalogue rows", "Focused view of the source Excel rows used for this demo, including master PN and technical characteristics.")
        self._add_table("Product Explorer", rows)
        self._add_section("Product Explorer", "AI-mapped drawing examples", "Rows generated from the attached PDF drawings into the original Excel structure.")
        generated_rows = self.generated[[c for c in fields if c in self.generated.columns]].to_dict("records")
        self._add_table("Product Explorer", generated_rows, max_height=260)

    def _upload_panel(self, page_name: str) -> None:
        panel = self._panel()
        panel.setObjectName("UploadPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        top = QHBoxLayout()
        title = QLabel("File upload")
        title.setObjectName("PanelTitle")
        top.addWidget(title)
        top.addStretch(1)
        choose_catalogue = QPushButton("Choose catalogue")
        choose_catalogue.clicked.connect(self._choose_catalogue)
        choose_pdfs = QPushButton("Choose PDFs")
        choose_pdfs.clicked.connect(self._choose_pdfs)
        run = QPushButton("Analyze selected files")
        run.setObjectName("PrimaryButton")
        run.clicked.connect(self._run_selected_files)
        clear = QPushButton("Clear PDFs")
        clear.setObjectName("SecondaryButton")
        clear.clicked.connect(self._clear_selected_files)
        top.addWidget(choose_catalogue)
        top.addWidget(choose_pdfs)
        top.addWidget(run)
        top.addWidget(clear)
        layout.addLayout(top)

        files = QGridLayout()
        files.setHorizontalSpacing(12)
        files.setVerticalSpacing(8)
        files.addWidget(self._file_chip("Catalogue", self.selected_catalogue_path, self.selected_catalogue_path.exists()), 0, 0)
        pdf_summary = f"{len(self.selected_pdf_paths)} PDF selected" if len(self.selected_pdf_paths) == 1 else f"{len(self.selected_pdf_paths)} PDFs selected"
        pdf_ok = all(path.exists() for path in self.selected_pdf_paths) and bool(self.selected_pdf_paths)
        files.addWidget(self._file_chip("PDF set", Path(pdf_summary), pdf_ok, detail=", ".join(path.name for path in self.selected_pdf_paths[:4]) + (" ..." if len(self.selected_pdf_paths) > 4 else "")), 0, 1)
        layout.addLayout(files)
        hint = QLabel("Select a catalogue workbook and one or more engineering PDFs, then run analysis. Outputs are regenerated in the configured output folder.")
        hint.setObjectName("SectionDescription")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.page_bodies[page_name].addWidget(panel)

    def _file_chip(self, label: str, path: Path, ok: bool, detail: str | None = None) -> QFrame:
        chip = QFrame()
        chip.setObjectName("FileChipOk" if ok else "FileChipMissing")
        layout = QVBoxLayout(chip)
        layout.setContentsMargins(14, 12, 14, 12)
        label_widget = QLabel(label)
        label_widget.setObjectName("MetricLabel")
        name_widget = QLabel(path.name)
        name_widget.setObjectName("FileName")
        name_widget.setWordWrap(True)
        detail_widget = QLabel(detail or str(path))
        detail_widget.setObjectName("FilePath")
        detail_widget.setWordWrap(True)
        layout.addWidget(label_widget)
        layout.addWidget(name_widget)
        layout.addWidget(detail_widget)
        return chip

    def _clusters(self) -> None:
        explanations = self.result.clusters.get("explanations", [])
        self._add_metric_grid(
            "Clusters",
            [
                ("Cluster count", len(explanations), "K-Means on isolating cocks"),
                ("Products clustered", len(self.result.clusters.get("points", [])), "Focused catalogue records with PartNumber"),
                ("Features", len(self.result.clusters.get("features", [])), "Encoded categorical characteristics"),
            ],
            columns=3,
        )
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._web_chart_card("Cluster PCA scatter", self.result.output_files.get("cluster_scatter")))
        splitter.addWidget(self._cluster_summary_panel(explanations))
        splitter.setSizes([900, 460])
        self.page_bodies["Clusters"].addWidget(splitter)
        self._add_section("Clusters", "Clustered products", "Point data behind the embedded scatter plot.")
        self._add_table("Clusters", self.result.clusters.get("points", []), max_height=360)

    def _family(self) -> None:
        product_type_counts = self.result.demo_focus.get("attribute_counts", {}).get("Product Type", {})
        rows = [{"Product Type": k, "Count": v} for k, v in product_type_counts.items()]
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._chart_card("Isolating cock product type", self.result.output_files.get("focus_product_type")))
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._label("Product type distribution", "PanelTitle"))
        layout.addWidget(self._mini_bars(rows[:12], "Product Type", "Count"))
        splitter.addWidget(panel)
        splitter.setSizes([780, 520])
        self.page_bodies["Family Explorer"].addWidget(splitter)
        self.page_bodies["Family Explorer"].addWidget(self._web_chart_card("Focused characteristic flow", self.result.output_files.get("focus_characteristic_flow")))
        self._add_table("Family Explorer", rows, max_height=360)

    def _characteristics(self) -> None:
        rows = []
        source = pd.DataFrame(self.result.demo_focus.get("records", []))
        for column in self.result.catalogue_profile.technical_columns:
            counts = source[column].value_counts().to_dict() if column in source else {}
            rows.append({"Characteristic": column, "Generated values": counts})
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._chart_card("Diameter vs handle clusters", self.result.output_files.get("focus_diameter_handle")))
        splitter.addWidget(self._chart_card("Drain vs contact matrix", self.result.output_files.get("focus_drain_contact")))
        splitter.addWidget(self._chart_card("Attribute completeness", self.result.output_files.get("attribute_completeness")))
        splitter.addWidget(self._characteristic_panel(rows))
        splitter.setSizes([560, 560, 560, 420])
        self.page_bodies["Characteristic Analysis"].addWidget(splitter)
        self.page_bodies["Characteristic Analysis"].addWidget(self._web_chart_card("Characteristic flow", self.result.output_files.get("focus_characteristic_flow")))
        self._add_table("Characteristic Analysis", rows, max_height=330)

    def _rules(self) -> None:
        influence = self.result.rule_results.get("influence", [])
        matrix = self.result.rule_results.get("configuration_matrix", {})
        self._add_metric_grid(
            "Part Number Rules",
            [
                ("Rule candidates", len(influence), "Characteristic influence checks"),
                ("Observed configs", matrix.get("observed", 0), "Observed matrix rows"),
                ("Missing configs", matrix.get("missing", 0), "Expected minus observed combinations"),
            ],
            columns=3,
        )
        self._add_table("Part Number Rules", influence, max_height=360)
        self.page_bodies["Part Number Rules"].addWidget(self._chart_card("Rule influence", self.result.output_files.get("rule_influence")))
        self._add_json_panel("Part Number Rules", "Configuration matrix", matrix)

    def _anomalies(self) -> None:
        rows = self.result.anomalies
        severity_counts = {s: sum(1 for r in rows if r.get("Severity") == s) for s in ["HIGH", "MEDIUM", "LOW"]}
        self._add_metric_grid(
            "Anomalies",
            [
                ("High", severity_counts["HIGH"], "Potential catalogue conflicts"),
                ("Medium", severity_counts["MEDIUM"], "Review recommended"),
                ("Low", severity_counts["LOW"], "Weak-signal findings"),
            ],
            columns=3,
        )
        self.page_bodies["Anomalies"].addWidget(self._chart_card("Anomaly breakdown", self.result.output_files.get("anomaly_breakdown")))
        self._add_table("Anomalies", rows)

    def _similar(self) -> None:
        self._add_metric_grid("Similar Products", [("Candidates", len(self.result.similarity), "Technical similarity only"), ("Geometry", "Unavailable", "CAD/STEP placeholder kept explicit")], columns=2)
        self._add_table("Similar Products", self.result.similarity)

    def _bom(self) -> None:
        rows = []
        for analysis in self.result.pdf_analyses:
            rows.extend(analysis.bom_rows)
        shared = len({row.get("ComponentPartNumber") for row in rows if row.get("ComponentPartNumber")})
        self._add_metric_grid("BOM Analysis", [("BOM rows", len(rows), "Extracted component-like rows"), ("Unique components", shared, "Distinct component PartNumbers")], columns=2)
        self.page_bodies["BOM Analysis"].addWidget(self._chart_card("BOM component frequency", self.result.output_files.get("bom_frequency")))
        self._add_table("BOM Analysis", rows)

    def _reports(self) -> None:
        report_path = self.result.output_files["report"]
        controls = QHBoxLayout()
        open_button = QPushButton("Open report")
        open_button.clicked.connect(lambda: QDesktopServices.openUrl(report_path.resolve().as_uri()))
        output_button = QPushButton("Open output folder")
        output_button.clicked.connect(self._open_output_folder)
        controls.addWidget(open_button)
        controls.addWidget(output_button)
        controls.addStretch(1)
        wrapper = QWidget()
        wrapper.setLayout(controls)
        self.page_bodies["Reports"].addWidget(wrapper)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setObjectName("ReportViewer")
        text.setText(report_path.read_text(encoding="utf-8"))
        text.setMinimumHeight(620)
        self.page_bodies["Reports"].addWidget(text)

    def _settings(self) -> None:
        output_dir = Path(self.result.output_files["report"]).parent if self.result else Path("data/output")
        settings = [
            ("Demo input mode", "Bundled/source files in data/input are loaded automatically."),
            ("Demo focus", f"{self.result.demo_focus.get('filter_column')} = {self.result.demo_focus.get('filter_value')} / expected {self.result.demo_focus.get('expected_codes')} codes."),
            ("Output folder", str(output_dir)),
            ("AI providers", "Disabled for this offline deterministic demo."),
            ("CAD geometry", "Architecture placeholder only; no fake geometric similarity is reported."),
        ]
        for title, body in settings:
            self.page_bodies["Settings"].addWidget(self._info_card(title, body))

    def _add_metric_grid(self, page_name: str, metrics: list[tuple[str, Any, str]], columns: int = 4) -> None:
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for index, (label, value, caption) in enumerate(metrics):
            grid.addWidget(self._metric_card(label, value, caption), index // columns, index % columns)
        wrapper = QWidget()
        wrapper.setLayout(grid)
        self.page_bodies[page_name].addWidget(wrapper)

    def _metric_card(self, label: str, value: Any, caption: str) -> QFrame:
        card = self._panel()
        card.setObjectName("MetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        label_widget = QLabel(label)
        label_widget.setObjectName("MetricLabel")
        value_widget = QLabel(str(value))
        value_widget.setObjectName("MetricValue")
        caption_widget = QLabel(caption)
        caption_widget.setObjectName("MetricCaption")
        caption_widget.setWordWrap(True)
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)
        layout.addWidget(caption_widget)
        return card

    def _chart_card(self, title: str, path: Path | None) -> QFrame:
        card = self._panel()
        layout = QVBoxLayout(card)
        layout.addWidget(self._label(title, "PanelTitle"))
        if path and Path(path).exists():
            image = QLabel()
            image.setAlignment(Qt.AlignCenter)
            pixmap = QPixmap(str(path))
            image.setPixmap(pixmap.scaled(620, 430, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            image.setMinimumHeight(360)
            layout.addWidget(image, 1)
        else:
            layout.addWidget(self._empty_state("Chart not generated yet."))
        return card

    def _web_chart_card(self, title: str, path: Path | None) -> QFrame:
        card = self._panel()
        layout = QVBoxLayout(card)
        layout.addWidget(self._label(title, "PanelTitle"))
        path_obj = Path(path) if path else None
        if QWebEngineView and path_obj and path_obj.exists() and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            view = QWebEngineView()
            view.setMinimumHeight(520)
            view.load(QUrl.fromLocalFile(str(path_obj.resolve())))
            layout.addWidget(view, 1)
        elif path_obj and path_obj.exists():
            layout.addWidget(self._empty_state(f"Interactive chart is available at {path_obj.name}. Open it from the output folder."))
        else:
            layout.addWidget(self._empty_state("Cluster chart not generated yet."))
        return card

    def _cluster_summary_panel(self, explanations: list[dict[str, Any]]) -> QFrame:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._label("Cluster explanations", "PanelTitle"))
        for cluster in explanations:
            common = cluster.get("Common", [])[:4]
            lines = [f"{item['Feature']}: {item['Value']} ({int(item['Share'] * 100)}%)" for item in common]
            body = "\n".join(lines + [f"Representatives: {', '.join(map(str, cluster.get('RepresentativeProducts', [])[:3]))}"])
            layout.addWidget(self._info_card(f"Cluster {cluster.get('Cluster')} - {cluster.get('Products')} products", body))
        layout.addStretch(1)
        return panel

    def _characteristic_panel(self, rows: list[dict[str, Any]]) -> QFrame:
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._label("Generated characteristic values", "PanelTitle"))
        for row in rows:
            layout.addWidget(self._info_card(row["Characteristic"], str(row["Generated values"])))
        layout.addStretch(1)
        return panel

    def _mini_bars(self, rows: list[dict[str, Any]], label_key: str, value_key: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        max_value = max([int(row[value_key]) for row in rows] or [1])
        for row in rows:
            line = QFrame()
            line_layout = QHBoxLayout(line)
            line_layout.setContentsMargins(0, 4, 0, 4)
            label = QLabel(str(row[label_key]))
            label.setMinimumWidth(220)
            bar = QFrame()
            bar.setObjectName("MiniBar")
            bar.setFixedHeight(14)
            bar.setMinimumWidth(max(16, int(220 * int(row[value_key]) / max_value)))
            count = QLabel(str(row[value_key]))
            count.setObjectName("Muted")
            line_layout.addWidget(label)
            line_layout.addWidget(bar)
            line_layout.addWidget(count)
            line_layout.addStretch(1)
            layout.addWidget(line)
        return widget

    def _add_json_panel(self, page_name: str, title: str, value: Any) -> None:
        text = QTextEdit()
        text.setReadOnly(True)
        text.setObjectName("CodePanel")
        text.setText(str(value))
        text.setMinimumHeight(190)
        panel = self._panel()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._label(title, "PanelTitle"))
        layout.addWidget(text)
        self.page_bodies[page_name].addWidget(panel)

    def _add_section(self, page_name: str, title: str, description: str) -> None:
        section = QFrame()
        section.setObjectName("SectionBlock")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.addWidget(self._label(title, "SectionTitle"))
        desc = QLabel(description)
        desc.setObjectName("SectionDescription")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self.page_bodies[page_name].addWidget(section)

    def _add_table(self, page_name: str, rows: list[dict[str, Any]], max_height: int | None = None) -> None:
        table = QTableWidget()
        table.setObjectName("DataTable")
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setWordWrap(False)
        table.setShowGrid(True)
        keys = self._ordered_keys(rows)
        table.setColumnCount(len(keys))
        table.setHorizontalHeaderLabels(keys)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, key in enumerate(keys):
                item = QTableWidgetItem(str(row.get(key, "")))
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                item.setForeground(QBrush(QColor(PALETTE["text"])))
                self._tint_item(item, key, row.get(key, ""))
                table.setItem(r, c, item)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(42)
        if max_height:
            table.setMaximumHeight(max_height)
        else:
            table.setMinimumHeight(360)
        self.page_bodies[page_name].addWidget(table, 1)

    def _tint_item(self, item: QTableWidgetItem, key: str, value: Any) -> None:
        text = str(value).upper()
        if "NEEDS REVIEW" in text or text in {"UNKNOWN", "NOT_FOUND"}:
            item.setBackground(QBrush(QColor(PALETTE["amber_soft"])))
            item.setForeground(QBrush(QColor(PALETTE["amber"])))
        if key == "Severity" and text == "HIGH":
            item.setBackground(QBrush(QColor(PALETTE["red_soft"])))
            item.setForeground(QBrush(QColor(PALETTE["red"])))
        elif key == "Severity" and text == "MEDIUM":
            item.setBackground(QBrush(QColor(PALETTE["amber_soft"])))
            item.setForeground(QBrush(QColor(PALETTE["amber"])))
        elif key == "status" and text == "ACCEPTED":
            item.setBackground(QBrush(QColor(PALETTE["green_soft"])))
            item.setForeground(QBrush(QColor(PALETTE["green"])))

    def _ordered_keys(self, rows: list[dict[str, Any]]) -> list[str]:
        if not rows:
            return []
        preferred = [
            "PDF",
            "SourcePDF",
            "PartNumber",
            "Product",
            "Master PN",
            "Product Family",
            "Product Name",
            "Product Type",
            "Field",
            "field",
            "value",
            "Value",
            "Confidence",
            "confidence",
            "Severity",
            "Type",
            "Cluster",
        ]
        keys = list(rows[0].keys())
        for row in rows[1:]:
            for key in row:
                if key not in keys:
                    keys.append(key)
        return [key for key in preferred if key in keys] + [key for key in keys if key not in preferred]

    def _info_card(self, title: str, body: str) -> QFrame:
        card = self._panel()
        card.setObjectName("InfoCard")
        layout = QVBoxLayout(card)
        title_widget = QLabel(title)
        title_widget.setObjectName("InfoTitle")
        body_widget = QLabel(body)
        body_widget.setObjectName("InfoBody")
        body_widget.setWordWrap(True)
        layout.addWidget(title_widget)
        layout.addWidget(body_widget)
        return card

    def _empty_state(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("EmptyState")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setMinimumHeight(220)
        return label

    def _panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        return panel

    def _label(self, text: str, object_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(True)
        return label

    def _open_output_folder(self) -> None:
        if self.result and "report" in self.result.output_files:
            folder = Path(self.result.output_files["report"]).parent
        else:
            folder = Path("data/output").resolve()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _show_page_help(self, name: str) -> None:
        message = QMessageBox(self)
        message.setWindowTitle(f"{name} help")
        message.setText("What this page is showing")
        message.setInformativeText(self._page_help(name))
        message.setStandardButtons(QMessageBox.Ok)
        message.exec()

    def _page_description(self, name: str) -> str:
        descriptions = {
            "Dashboard": "Demo overview for the isolating-cock scope, PDF extraction, matching, review queue, and focused analytics.",
            "PDF Import": "Drawing-level ingestion status, detected identifiers, variants, warnings, and component extraction counts.",
            "Extraction Review": "Evidence-backed characteristic decisions. Low-confidence values stay visible for engineer validation.",
            "Generated Catalogue": "Catalogue-compatible output using the source Excel columns and terminology.",
            "Product Explorer": "Focused isolating-cock rows from the source catalogue plus PDF-mapped demo rows.",
            "Clusters": "Interactive isolating-cock product clusters with PCA projection, explanations, and representative PartNumbers.",
            "Family Explorer": "Focused product-type distribution and characteristic flow for isolating cocks.",
            "Characteristic Analysis": "Cross-characteristic relationships for diameter, drain, contact, handle, and product type.",
            "Part Number Rules": "Discovered PartNumber influence signals, support counts, and configuration matrix results.",
            "Anomalies": "Duplicate, conflict, missing-configuration, low-confidence, and mapping-risk findings.",
            "Similar Products": "Technical similarity results with explicit CAD geometry placeholder.",
            "BOM Analysis": "Component-like rows extracted from drawing BOM/table text.",
            "Reports": "Generated markdown analysis report with facts, inferences, limitations, and gap analysis.",
            "Settings": "Demo-mode runtime paths and future integration boundaries.",
        }
        return descriptions.get(name, "")

    def _page_help(self, name: str) -> str:
        help_text = {
            "Dashboard": (
                "Shows the whole demo status in one place.\n\n"
                "It confirms the focus category, target code count, rows found in Excel, missing gap, PDFs analyzed, generated rows, clusters, review fields, and anomalies.\n\n"
                "Use this page to explain the demo story quickly: source Excel loaded, isolating cocks filtered, drawings mapped, charts generated."
            ),
            "PDF Import": (
                "Shows which drawing PDFs are being analyzed.\n\n"
                "For each PDF it lists page count, detected part numbers, variants, warnings, and extracted BOM/component-like rows.\n\n"
                "Use the buttons here to choose a catalogue file, choose PDFs, clear PDFs, or run analysis on selected files."
            ),
            "Extraction Review": (
                "Shows the evidence behind extracted fields.\n\n"
                "Each row links a field value to the source PDF, page number, evidence text, confidence score, extraction method, and review status.\n\n"
                "Use this page to see what the app extracted directly and what needs engineer validation."
            ),
            "Generated Catalogue": (
                "Shows the Excel-compatible output generated from the PDF drawings.\n\n"
                "The table keeps the original catalogue column structure, adds mapped technical attributes, and flags uncertain values as NEEDS REVIEW.\n\n"
                "The charts summarize completeness and maturity for the focused catalogue data."
            ),
            "Product Explorer": (
                "Shows the focused isolating-cock product rows from the source Excel.\n\n"
                "It lists PartNumber, Master PN, product hierarchy, product type, diameter, drain, contact, and handle attributes.\n\n"
                "The lower table shows the PDF-mapped rows generated by the app for comparison."
            ),
            "Clusters": (
                "Shows product clusters for isolating cocks only.\n\n"
                "The scatter plot projects catalogue rows into two dimensions using encoded product attributes, then groups similar configurations.\n\n"
                "The summary explains each cluster using its most common attributes and representative PartNumbers."
            ),
            "Family Explorer": (
                "Shows how the focused isolating-cock rows are distributed by product type.\n\n"
                "The bar chart and count list show which product types dominate the category.\n\n"
                "The flow chart connects product type, diameter, drain, contact, and handle to show common configuration paths."
            ),
            "Characteristic Analysis": (
                "Shows cross-relationships between technical characteristics.\n\n"
                "Diameter vs handle highlights handle patterns by size; drain vs contact shows how drain options combine with contacts.\n\n"
                "The value panel lists the most common values for each technical attribute in the focused demo category."
            ),
            "Part Number Rules": (
                "Shows which characteristics appear to influence PartNumber patterns.\n\n"
                "Support means how many rows contain the characteristic; confidence estimates how strongly values map to observed part-number segments.\n\n"
                "The configuration matrix compares expected vs observed combinations and flags missing or duplicate configurations."
            ),
            "Anomalies": (
                "Shows data issues and review risks found during analysis.\n\n"
                "Examples include duplicate configurations, conflicting characteristics, missing expected combinations, PDFs not found in the catalogue, and low-confidence fields.\n\n"
                "Severity tells whether the issue is high, medium, or low priority."
            ),
            "Similar Products": (
                "Shows catalogue rows that are technically similar based on shared attributes.\n\n"
                "Similarity is calculated from product family, product name, product type, and technical attributes.\n\n"
                "CAD geometry is explicitly marked unavailable so the demo does not pretend to compare 3D shapes."
            ),
            "BOM Analysis": (
                "Shows component-like rows extracted from the PDF drawing text.\n\n"
                "It lists component identifiers, quantities when visible, descriptions, specifications, ABC class, and evidence text.\n\n"
                "The chart highlights the most frequently reused component identifiers across the analyzed PDFs."
            ),
            "Reports": (
                "Shows the generated markdown report for the current analysis run.\n\n"
                "The report records facts, algorithm results, extracted characteristics, mappings, clusters, anomalies, limitations, and next steps.\n\n"
                "Use Open report or Open output folder to access the exported files."
            ),
            "Settings": (
                "Shows runtime configuration for this demo.\n\n"
                "It lists the input mode, focused category, expected code count, output folder, AI-provider status, and CAD-geometry boundary.\n\n"
                "This page is mainly for explaining what is active now and what is intentionally not implemented yet."
            ),
        }
        return help_text.get(name, "Shows the data and outputs for this page.")

    def _stylesheet(self) -> str:
        return f"""
        QMainWindow {{ background: {PALETTE['bg']}; }}
        #Sidebar {{ background: #101827; border-right: 1px solid #0b1220; }}
        #Brand {{ color: #ffffff; font-size: 22px; font-weight: 800; }}
        #SidebarSubtitle {{ color: #aab5c6; font-size: 12px; }}
        #Navigation {{ background: transparent; border: none; color: #d6deeb; outline: 0; font-size: 14px; }}
        #Navigation::item {{ padding: 10px 12px; margin: 2px 0; border-radius: 6px; }}
        #Navigation::item:selected {{ background: #254171; color: #ffffff; }}
        #Navigation::item:hover {{ background: #1b2c48; }}
        QToolBar {{ background: {PALETTE['panel']}; border-bottom: 1px solid {PALETTE['border']}; spacing: 8px; padding: 6px; }}
        QToolButton, QPushButton {{ background: {PALETTE['accent']}; color: #ffffff; border: none; border-radius: 6px; padding: 8px 12px; font-weight: 600; }}
        QPushButton:hover, QToolButton:hover {{ background: #1f49ad; }}
        #HelpButton {{ background: #101827; color: #ffffff; border: 1px solid #2d3f5f; border-radius: 19px; padding: 0; font-size: 18px; font-weight: 900; }}
        #HelpButton:hover {{ background: #2458d3; border: 1px solid #2458d3; }}
        #SecondaryButton {{ background: #edf2f8; color: {PALETTE['text']}; border: 1px solid {PALETTE['border']}; }}
        #SecondaryButton:hover {{ background: #dfe8f5; }}
        #PrimaryButton {{ background: #123fb7; }}
        #PageTitle {{ color: {PALETTE['text']}; font-size: 28px; font-weight: 800; }}
        #PageDescription, #SectionDescription, #Muted {{ color: {PALETTE['muted']}; font-size: 13px; }}
        #Panel, #MetricCard, #InfoCard, #SectionBlock, #UploadPanel {{ background: {PALETTE['panel']}; border: 1px solid {PALETTE['border']}; border-radius: 8px; }}
        #SectionBlock {{ background: #fbfdff; }}
        #UploadPanel {{ border: 1px solid #bfd0ea; background: #f8fbff; }}
        #FileChipOk {{ background: #eef8f3; border: 1px solid #bfe6d2; border-radius: 8px; }}
        #FileChipMissing {{ background: #fff7e8; border: 1px solid #f3d49b; border-radius: 8px; }}
        #FileName {{ color: {PALETTE['text']}; font-size: 15px; font-weight: 800; }}
        #FilePath {{ color: {PALETTE['muted']}; font-size: 12px; }}
        #MetricLabel {{ color: {PALETTE['muted']}; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
        #MetricValue {{ color: {PALETTE['text']}; font-size: 30px; font-weight: 800; }}
        #MetricCaption {{ color: {PALETTE['muted']}; font-size: 12px; }}
        #PanelTitle, #SectionTitle {{ color: {PALETTE['text']}; font-size: 17px; font-weight: 800; }}
        #InfoTitle {{ color: {PALETTE['text']}; font-weight: 800; }}
        #InfoBody {{ color: {PALETTE['muted']}; font-size: 12px; }}
        #EmptyState {{ background: {PALETTE['panel_alt']}; color: {PALETTE['muted']}; border: 1px dashed {PALETTE['border']}; border-radius: 8px; }}
        #MiniBar {{ background: {PALETTE['accent']}; border-radius: 4px; }}
        #DataTable {{ background: {PALETTE['panel']}; color: {PALETTE['text']}; alternate-background-color: #f8fbff; border: 1px solid {PALETTE['border']}; border-radius: 8px; gridline-color: #edf1f7; selection-background-color: #dce8ff; selection-color: {PALETTE['text']}; }}
        QHeaderView::section {{ background: #eef3fb; color: {PALETTE['text']}; border: none; border-right: 1px solid {PALETTE['border']}; padding: 7px; font-weight: 800; }}
        QTableWidget::item {{ padding: 7px; color: {PALETTE['text']}; }}
        QTableWidget::item:selected {{ background: #dce8ff; color: {PALETTE['text']}; }}
        QTableCornerButton::section {{ background: #eef3fb; border: none; }}
        QTextEdit {{ background: {PALETTE['panel']}; color: {PALETTE['text']}; border: 1px solid {PALETTE['border']}; border-radius: 8px; padding: 10px; }}
        #CodePanel {{ font-family: Menlo, Consolas, monospace; font-size: 12px; }}
        """


def run_app() -> int:
    app = QApplication([])
    app.setStyle("Fusion")
    app.setFont(QFont("Inter", 10))
    window = ProductAnalyzerWindow()
    window.show()
    return app.exec()
