from __future__ import annotations

from pathlib import Path
from typing import Any
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px


class ChartBuilder:
    def build_all(
        self,
        catalogue: pd.DataFrame,
        clusters: dict[str, Any],
        output_dir: Path,
        anomalies: list[dict[str, Any]] | None = None,
        evidence: pd.DataFrame | None = None,
        bom_rows: list[dict[str, Any]] | None = None,
        rule_results: dict[str, Any] | None = None,
    ) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        paths["family_frequency"] = self._bar(catalogue, "Product Family", output_dir / "family_frequency.png")
        paths["contact_handle"] = self._stacked(catalogue, "Technical attribute 3", "Technical attribute 4", output_dir / "contact_handle_matrix.png")
        paths["hierarchy_treemap"] = self._treemap(catalogue, output_dir / "catalogue_hierarchy_treemap.html")
        paths["attribute_completeness"] = self._attribute_completeness(catalogue, output_dir / "attribute_completeness.png")
        paths["maturity_by_family"] = self._maturity_by_family(catalogue, output_dir / "maturity_by_family.png")
        if rule_results:
            paths["rule_influence"] = self._rule_influence(rule_results, output_dir / "rule_influence.png")
        if anomalies:
            paths["anomaly_breakdown"] = self._anomaly_breakdown(anomalies, output_dir / "anomaly_breakdown.png")
        if evidence is not None and not evidence.empty:
            paths["extraction_confidence"] = self._extraction_confidence(evidence, output_dir / "extraction_confidence.png")
        if bom_rows:
            paths["bom_frequency"] = self._bom_frequency(bom_rows, output_dir / "bom_frequency.png")
        points = pd.DataFrame(clusters.get("points", []))
        if not points.empty:
            html = output_dir / "cluster_scatter.html"
            fig = px.scatter(points, x="PCA_X", y="PCA_Y", color="Cluster", hover_data=["PartNumber", "Product Family", "Product Type"])
            fig.write_html(html)
            paths["cluster_scatter"] = html
        return paths

    def build_demo_focus(self, catalogue: pd.DataFrame, output_dir: Path, expected_count: int) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: dict[str, Path] = {}
        paths["focus_diameter_handle"] = self._focus_stacked(
            catalogue,
            "Technical attribute 1",
            "Technical attribute 4",
            output_dir / "isolating_cocks_diameter_handle.png",
            "Isolating cocks: diameter vs handle",
        )
        paths["focus_drain_contact"] = self._stacked(
            catalogue,
            "Technical attribute 2",
            "Technical attribute 3",
            output_dir / "isolating_cocks_drain_contact.png",
        )
        paths["focus_product_type"] = self._bar(catalogue, "Product Type", output_dir / "isolating_cocks_product_type.png")
        paths["focus_coverage"] = self._focus_coverage(catalogue, output_dir / "isolating_cocks_demo_coverage.png", expected_count)
        paths["focus_characteristic_flow"] = self._focus_characteristic_flow(catalogue, output_dir / "isolating_cocks_characteristic_flow.html")
        return paths

    def _focus_coverage(self, df: pd.DataFrame, path: Path, expected_count: int) -> Path:
        found = len(df)
        gap = max(0, expected_count - found)
        labels = ["Found in catalogue", "Missing vs demo target"]
        values = [found, gap]
        colors = ["#2458d3", "#f2a541"]
        plt.figure(figsize=(8.8, 4.8))
        bars = plt.bar(labels, values, color=colors)
        plt.title("Demo scope check: isolating cock codes", fontsize=14, weight="bold", pad=14)
        plt.ylabel("Codes")
        plt.ylim(0, max(expected_count, found, 1) * 1.18)
        plt.grid(axis="y", alpha=0.22)
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2, height + 0.8, str(int(height)), ha="center", fontsize=11, weight="bold")
        plt.text(0.5, max(expected_count, found, 1) * 1.08, f"Expected from meeting brief: {expected_count}", ha="center", fontsize=10, color="#637083")
        plt.gca().spines[["top", "right", "left"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        return path

    def _focus_stacked(self, df: pd.DataFrame, row: str, col: str, path: Path, title: str) -> Path:
        if row not in df.columns or col not in df.columns or df.empty:
            return self._empty_png(path, "No focused characteristic data available")
        cross = pd.crosstab(df[row].replace("", "UNKNOWN"), df[col].replace("", "UNKNOWN"))
        cross = cross.loc[cross.sum(axis=1).sort_values().index]
        plt.figure(figsize=(11, 6.6))
        cross.plot(kind="barh", stacked=True, ax=plt.gca(), colormap="Set2")
        plt.title(title, fontsize=14, weight="bold", pad=14)
        plt.xlabel("Codes")
        plt.ylabel("")
        plt.grid(axis="x", alpha=0.22)
        plt.gca().spines[["top", "right", "left"]].set_visible(False)
        plt.legend(loc="lower right", fontsize=8)
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        return path

    def _focus_characteristic_flow(self, df: pd.DataFrame, path: Path) -> Path:
        dims = [c for c in ["Product Type", "Technical attribute 1", "Technical attribute 2", "Technical attribute 3", "Technical attribute 4"] if c in df.columns]
        if df.empty or len(dims) < 2:
            path.write_text("<html><body>No focused characteristic flow data</body></html>", encoding="utf-8")
            return path
        working = df[dims].replace("", "UNKNOWN").copy()
        fig = px.parallel_categories(
            working,
            dimensions=dims,
            title="Isolating cocks: characteristic flow",
            color_continuous_scale=px.colors.sequential.Blues,
        )
        fig.update_layout(margin=dict(t=56, l=10, r=10, b=10), font=dict(size=12))
        fig.write_html(path)
        return path

    def _treemap(self, df: pd.DataFrame, path: Path) -> Path:
        required = ["OPS Product Category", "Product Family", "Product Name", "Product Type"]
        working = df[[c for c in required if c in df.columns]].replace("", "UNKNOWN").copy()
        if working.empty:
            path.write_text("<html><body>No hierarchy data</body></html>", encoding="utf-8")
            return path
        grouped = working.value_counts().reset_index(name="Records")
        fig = px.treemap(
            grouped,
            path=[c for c in required if c in grouped.columns],
            values="Records",
            color="Records",
            color_continuous_scale="Blues",
            title="Catalogue hierarchy: category to product type",
        )
        fig.update_layout(margin=dict(t=48, l=10, r=10, b=10), font=dict(size=13))
        fig.write_html(path)
        return path

    def _attribute_completeness(self, df: pd.DataFrame, path: Path) -> Path:
        technical = [c for c in df.columns if c.startswith("Technical attribute")]
        if not technical or "Product Family" not in df.columns:
            return self._empty_png(path, "No technical attributes available")
        top_families = df["Product Family"].replace("", "UNKNOWN").value_counts().head(14).index
        matrix = []
        labels = []
        for family in top_families:
            subset = df[df["Product Family"].replace("", "UNKNOWN") == family]
            labels.append("\n".join(textwrap.wrap(str(family), 26)))
            matrix.append([(subset[col].astype(str).str.len() > 0).mean() * 100 for col in technical])
        plt.figure(figsize=(10, 7))
        ax = plt.gca()
        image = ax.imshow(matrix, cmap="PuBuGn", vmin=0, vmax=100, aspect="auto")
        ax.set_title("Technical attribute completeness by family", fontsize=14, weight="bold", pad=14)
        ax.set_xticks(range(len(technical)))
        ax.set_xticklabels([col.replace("Technical attribute ", "Attr ") for col in technical], fontsize=9)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=8)
        for y, row in enumerate(matrix):
            for x, value in enumerate(row):
                ax.text(x, y, f"{value:.0f}%", ha="center", va="center", fontsize=8, color="#102033")
        plt.colorbar(image, ax=ax, fraction=0.026, pad=0.02, label="Filled")
        ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        return path

    def _maturity_by_family(self, df: pd.DataFrame, path: Path) -> Path:
        if "Product Family" not in df.columns or "Maturity" not in df.columns:
            return self._empty_png(path, "No maturity data available")
        top = df["Product Family"].replace("", "UNKNOWN").value_counts().head(12).index
        working = df[df["Product Family"].replace("", "UNKNOWN").isin(top)].copy()
        cross = pd.crosstab(working["Product Family"].replace("", "UNKNOWN"), working["Maturity"].replace("", "UNKNOWN"))
        cross = cross.loc[cross.sum(axis=1).sort_values().index]
        plt.figure(figsize=(11, 7))
        cross.plot(kind="barh", stacked=True, ax=plt.gca(), colormap="Set2")
        plt.title("Maturity status by product family", fontsize=14, weight="bold", pad=14)
        plt.xlabel("Records")
        plt.ylabel("")
        plt.grid(axis="x", alpha=0.22)
        plt.gca().spines[["top", "right", "left"]].set_visible(False)
        plt.legend(loc="lower right", fontsize=8)
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        return path

    def _rule_influence(self, rule_results: dict[str, Any], path: Path) -> Path:
        rows = pd.DataFrame(rule_results.get("influence", []))
        if rows.empty:
            return self._empty_png(path, "No rule influence data available")
        rows = rows.sort_values(["Confidence", "Support"], ascending=True).tail(12)
        colors = rows["Influence"].map({"HIGH": "#2458d3", "MEDIUM": "#2ca58d", "LOW": "#f2a541", "NO CLEAR SIGNAL": "#8a95a6", "INSUFFICIENT DATA": "#c6ccd6"}).fillna("#8a95a6")
        plt.figure(figsize=(10, 6))
        labels = ["\n".join(textwrap.wrap(str(v), 24)) for v in rows["Characteristic"]]
        plt.barh(labels, rows["Confidence"], color=colors)
        plt.title("PartNumber rule influence confidence", fontsize=14, weight="bold", pad=14)
        plt.xlabel("Confidence")
        plt.xlim(0, 1)
        plt.grid(axis="x", alpha=0.22)
        for y, (_, row) in enumerate(rows.iterrows()):
            plt.text(row["Confidence"] + 0.015, y, f"{row['Influence']} / n={row['Support']}", va="center", fontsize=8)
        plt.gca().spines[["top", "right", "left"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        return path

    def _anomaly_breakdown(self, anomalies: list[dict[str, Any]], path: Path) -> Path:
        df = pd.DataFrame(anomalies)
        if df.empty:
            return self._empty_png(path, "No anomalies detected")
        cross = pd.crosstab(df["Type"], df["Severity"])
        cross = cross.loc[cross.sum(axis=1).sort_values().index]
        plt.figure(figsize=(11, 6))
        cross.plot(kind="barh", stacked=True, ax=plt.gca(), color=[ "#b42318", "#9a5b00", "#577399" ][: len(cross.columns)])
        plt.title("Anomaly breakdown by type and severity", fontsize=14, weight="bold", pad=14)
        plt.xlabel("Findings")
        plt.ylabel("")
        plt.grid(axis="x", alpha=0.22)
        plt.gca().spines[["top", "right", "left"]].set_visible(False)
        plt.legend(loc="lower right", fontsize=8)
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        return path

    def _extraction_confidence(self, evidence: pd.DataFrame, path: Path) -> Path:
        if not {"field", "confidence"}.issubset(evidence.columns):
            return self._empty_png(path, "No confidence data available")
        working = evidence.copy()
        working["confidence"] = pd.to_numeric(working["confidence"], errors="coerce").fillna(0)
        grouped = working.groupby("field")["confidence"].mean().sort_values()
        plt.figure(figsize=(10, 6))
        colors = ["#b42318" if v < 0.5 else "#9a5b00" if v < 0.75 else "#147a52" for v in grouped]
        plt.barh(["\n".join(textwrap.wrap(str(v), 24)) for v in grouped.index], grouped.values, color=colors)
        plt.title("Extraction confidence by field", fontsize=14, weight="bold", pad=14)
        plt.xlabel("Average confidence")
        plt.xlim(0, 1)
        plt.grid(axis="x", alpha=0.22)
        plt.gca().spines[["top", "right", "left"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        return path

    def _bom_frequency(self, bom_rows: list[dict[str, Any]], path: Path) -> Path:
        df = pd.DataFrame(bom_rows)
        if df.empty or "ComponentPartNumber" not in df.columns:
            return self._empty_png(path, "No BOM data available")
        counts = df["ComponentPartNumber"].replace("", "UNKNOWN").value_counts().head(18).sort_values()
        plt.figure(figsize=(10, 7))
        plt.barh(counts.index, counts.values, color="#2ca58d")
        plt.title("Most reused BOM/component identifiers", fontsize=14, weight="bold", pad=14)
        plt.xlabel("Occurrences across analyzed PDFs")
        plt.grid(axis="x", alpha=0.22)
        for y, value in enumerate(counts.values):
            plt.text(value + 0.03, y, str(int(value)), va="center", fontsize=8)
        plt.gca().spines[["top", "right", "left"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        return path

    def _empty_png(self, path: Path, message: str) -> Path:
        plt.figure(figsize=(8, 4))
        plt.text(0.5, 0.5, message, ha="center", va="center", fontsize=12)
        plt.axis("off")
        plt.savefig(path, dpi=160)
        plt.close()
        return path

    def _bar(self, df: pd.DataFrame, column: str, path: Path) -> Path:
        plt.figure(figsize=(11, 7))
        counts = df[column].replace("", "UNKNOWN").value_counts().head(15).sort_values()
        labels = ["\n".join(textwrap.wrap(str(label), 28)) for label in counts.index]
        colors = plt.cm.viridis([0.28 + 0.55 * i / max(1, len(counts) - 1) for i in range(len(counts))])
        bars = plt.barh(labels, counts.values, color=colors)
        plt.title(f"{column} frequency", fontsize=14, weight="bold", pad=14)
        plt.xlabel("Records")
        plt.grid(axis="x", alpha=0.22)
        for bar in bars:
            width = bar.get_width()
            plt.text(width + max(counts.values) * 0.012, bar.get_y() + bar.get_height() / 2, f"{int(width)}", va="center", fontsize=9)
        plt.gca().spines[["top", "right", "left"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        return path

    def _stacked(self, df: pd.DataFrame, row: str, col: str, path: Path) -> Path:
        cross = pd.crosstab(df[row].replace("", "UNKNOWN"), df[col].replace("", "UNKNOWN"))
        top_rows = cross.sum(axis=1).sort_values(ascending=False).head(10).index
        top_cols = cross.sum(axis=0).sort_values(ascending=False).head(8).index
        heat = cross.loc[top_rows, top_cols]
        plt.figure(figsize=(11, 6.4))
        ax = plt.gca()
        image = ax.imshow(heat.values, cmap="YlGnBu", aspect="auto")
        ax.set_title(f"{row} vs {col}", fontsize=14, weight="bold", pad=14)
        ax.set_xticks(range(len(heat.columns)))
        ax.set_xticklabels(["\n".join(textwrap.wrap(str(label), 18)) for label in heat.columns], rotation=35, ha="right", fontsize=8)
        ax.set_yticks(range(len(heat.index)))
        ax.set_yticklabels(["\n".join(textwrap.wrap(str(label), 22)) for label in heat.index], fontsize=8)
        for y in range(heat.shape[0]):
            for x in range(heat.shape[1]):
                value = int(heat.iloc[y, x])
                if value:
                    ax.text(x, y, str(value), ha="center", va="center", fontsize=8, color="#102033")
        plt.colorbar(image, ax=ax, fraction=0.026, pad=0.02, label="Records")
        ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()
        return path
