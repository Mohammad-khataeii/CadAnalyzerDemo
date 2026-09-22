from __future__ import annotations

from pathlib import Path
from typing import Any
import textwrap

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import pdist
from sklearn.metrics.pairwise import cosine_similarity


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
            self._cluster_scatter_preview(points, html.with_suffix(".png"), "Cluster PCA scatter", symbol_labels=False)
            paths["cluster_scatter"] = html
        return paths

    def build_demo_focus(self, catalogue: pd.DataFrame, clusters: dict[str, Any], output_dir: Path, expected_count: int) -> dict[str, Path]:
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
        paths["visual_quantity_bubbles"] = self._visual_quantity_bubbles(catalogue, output_dir / "visual_quantity_bubbles.png")
        paths["visual_distribution_panel"] = self._visual_distribution_panel(catalogue, output_dir / "visual_distribution_panel.png")
        paths["visual_cluster_story"] = self._visual_cluster_story(catalogue, clusters, output_dir / "visual_cluster_story.png")
        paths.update(self._advanced_cluster_charts(catalogue, clusters, output_dir))
        return paths

    def _advanced_cluster_charts(self, df: pd.DataFrame, clusters: dict[str, Any], output_dir: Path) -> dict[str, Path]:
        working, matrix, features = self._cluster_matrix(df, clusters)
        if working.empty or len(working) < 2 or matrix.shape[1] == 0:
            return {}
        paths: dict[str, Path] = {}
        paths["advanced_scatter_cluster"] = self._advanced_scatter_cluster(working, output_dir / "advanced_scatter_cluster.html")
        paths["cluster_colored_map"] = self._cluster_colored_map(working, output_dir / "cluster_colored_map.html")
        paths["cluster_bubble"] = self._cluster_bubble(working, output_dir / "cluster_bubble.html")
        paths["cluster_sankey"] = self._cluster_sankey(working, output_dir / "cluster_sankey.html")
        paths["cluster_radar"] = self._cluster_radar(working, features, output_dir / "cluster_radar.html")
        paths["affinity_heatmap"] = self._affinity_heatmap(working, matrix, output_dir / "affinity_heatmap.html")
        paths["cluster_dendrogram"] = self._cluster_dendrogram(working, matrix, output_dir / "cluster_dendrogram.html")
        return paths

    def _cluster_matrix(self, df: pd.DataFrame, clusters: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
        points = pd.DataFrame(clusters.get("points", []))
        if points.empty or "PartNumber" not in points or "PartNumber" not in df:
            return pd.DataFrame(), pd.DataFrame(), []
        features = [c for c in clusters.get("features", []) if c in df.columns]
        if not features:
            features = [c for c in ["Product Family", "Product Name", "Product Type", "Technical attribute 1", "Technical attribute 2", "Technical attribute 3", "Technical attribute 4"] if c in df.columns]
        keep = ["PartNumber", "Master PN", *features]
        enriched = points.merge(df[[c for c in keep if c in df.columns]], on="PartNumber", how="left", suffixes=("", "_Catalogue"))
        for column in features:
            catalogue_column = f"{column}_Catalogue"
            if catalogue_column in enriched.columns:
                enriched[column] = enriched[column].where(enriched[column].astype(str).str.len() > 0, enriched[catalogue_column])
                enriched = enriched.drop(columns=[catalogue_column])
        enriched[features] = enriched[features].replace("", "UNKNOWN").fillna("UNKNOWN")
        matrix = pd.get_dummies(enriched[features], prefix=features, dtype=float)
        return enriched, matrix, features

    def _advanced_scatter_cluster(self, df: pd.DataFrame, path: Path) -> Path:
        fig = px.scatter(
            df,
            x="PCA_X",
            y="PCA_Y",
            color="Cluster",
            symbol="Cluster",
            hover_data=["PartNumber", "Master PN", "Product Type", "Technical attribute 1", "Technical attribute 2", "Technical attribute 3", "Technical attribute 4"],
            title="Scatter plot with generated clusters",
        )
        fig.update_traces(marker=dict(size=10, line=dict(width=0.8, color="white")))
        fig.update_layout(margin=dict(t=58, l=20, r=20, b=20), font=dict(size=12))
        fig.write_html(path)
        self._cluster_scatter_preview(df, path.with_suffix(".png"), "Scatter plot with generated clusters", symbol_labels=True)
        return path

    def _cluster_colored_map(self, df: pd.DataFrame, path: Path) -> Path:
        fig = px.scatter(
            df,
            x="PCA_X",
            y="PCA_Y",
            color="Cluster",
            hover_name="PartNumber",
            hover_data=["Product Type", "Technical attribute 1", "Technical attribute 2", "Technical attribute 3", "Technical attribute 4"],
            title="Colored cluster map",
        )
        fig.update_traces(marker=dict(size=15, opacity=0.82, line=dict(width=1, color="white")))
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        fig.update_layout(margin=dict(t=58, l=20, r=20, b=20), plot_bgcolor="#f4f7fb", font=dict(size=12))
        fig.write_html(path)
        self._cluster_scatter_preview(df, path.with_suffix(".png"), "Manager view: colored cluster map", symbol_labels=False)
        return path

    def _cluster_bubble(self, df: pd.DataFrame, path: Path) -> Path:
        rows = []
        for cluster, group in df.groupby("Cluster"):
            rows.append(
                {
                    "Cluster": str(cluster),
                    "PCA_X": group["PCA_X"].mean(),
                    "PCA_Y": group["PCA_Y"].mean(),
                    "Products": len(group),
                    "Dominant diameter": group.get("Technical attribute 1", pd.Series(dtype=str)).replace("", "UNKNOWN").mode().iat[0],
                    "Dominant type": group.get("Product Type", pd.Series(dtype=str)).replace("", "UNKNOWN").mode().iat[0],
                    "Examples": ", ".join(group["PartNumber"].head(6).astype(str)),
                }
            )
        bubbles = pd.DataFrame(rows)
        fig = px.scatter(
            bubbles,
            x="PCA_X",
            y="PCA_Y",
            size="Products",
            color="Cluster",
            text="Cluster",
            hover_data=["Products", "Dominant type", "Dominant diameter", "Examples"],
            title="Bubble cluster by size and distance",
            size_max=72,
        )
        fig.update_traces(textposition="middle center", marker=dict(opacity=0.78, line=dict(width=1, color="white")))
        fig.update_layout(margin=dict(t=58, l=20, r=20, b=20), font=dict(size=12))
        fig.write_html(path)
        self._bubble_preview(bubbles, path.with_suffix(".png"))
        return path

    def _cluster_sankey(self, df: pd.DataFrame, path: Path) -> Path:
        dims = [c for c in ["Product Type", "Technical attribute 1", "Technical attribute 2", "Technical attribute 3"] if c in df.columns]
        if not dims:
            path.write_text("<html><body>No Sankey dimensions available</body></html>", encoding="utf-8")
            return path
        working = df[[*dims, "Cluster"]].replace("", "UNKNOWN").copy()
        working["Cluster"] = "Cluster " + working["Cluster"].astype(str)
        node_labels: list[str] = []
        node_index: dict[str, int] = {}
        links: dict[tuple[str, str], int] = {}

        def node(label: str) -> int:
            if label not in node_index:
                node_index[label] = len(node_labels)
                node_labels.append(label)
            return node_index[label]

        for row in working.to_dict("records"):
            chain = [str(row[d]) for d in dims] + [str(row["Cluster"])]
            for source, target in zip(chain, chain[1:]):
                node(source)
                node(target)
                links[(source, target)] = links.get((source, target), 0) + 1
        fig = go.Figure(
            data=[
                go.Sankey(
                    arrangement="snap",
                    node=dict(label=node_labels, pad=14, thickness=16, line=dict(color="#cbd5e1", width=0.5)),
                    link=dict(
                        source=[node_index[s] for s, _ in links],
                        target=[node_index[t] for _, t in links],
                        value=list(links.values()),
                    ),
                )
            ]
        )
        fig.update_layout(title_text="Sankey: characteristics flowing into clusters", margin=dict(t=58, l=20, r=20, b=20), font=dict(size=11))
        fig.write_html(path)
        self._sankey_preview(links, path.with_suffix(".png"))
        return path

    def _cluster_radar(self, df: pd.DataFrame, features: list[str], path: Path) -> Path:
        categories = ["Completeness", "Drain variety", "Contact variety", "Handle variety", "Type concentration"]
        fig = go.Figure()
        for cluster, group in df.groupby("Cluster"):
            technical = [c for c in features if c.startswith("Technical attribute") and c in group.columns]
            completeness = float((group[technical].replace("UNKNOWN", pd.NA).notna().mean().mean() if technical else 0) * 100)
            drain_variety = self._normalized_unique(group, "Technical attribute 2")
            contact_variety = self._normalized_unique(group, "Technical attribute 3")
            handle_variety = self._normalized_unique(group, "Technical attribute 4")
            type_concentration = self._top_share(group, "Product Type") * 100
            values = [completeness, drain_variety, contact_variety, handle_variety, type_concentration]
            fig.add_trace(go.Scatterpolar(r=values + [values[0]], theta=categories + [categories[0]], fill="toself", name=f"Cluster {cluster}"))
        fig.update_layout(
            title="Cluster radar comparison",
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            margin=dict(t=58, l=35, r=35, b=25),
            font=dict(size=12),
        )
        fig.write_html(path)
        self._radar_preview(df, features, path.with_suffix(".png"))
        return path

    def _affinity_heatmap(self, df: pd.DataFrame, matrix: pd.DataFrame, path: Path) -> Path:
        similarity = cosine_similarity(matrix)
        labels = df["PartNumber"].astype(str).tolist()
        fig = px.imshow(
            similarity,
            x=labels,
            y=labels,
            color_continuous_scale="Blues",
            zmin=0,
            zmax=1,
            title="Affinity heatmap by technical similarity",
            aspect="auto",
        )
        fig.update_layout(margin=dict(t=58, l=80, r=20, b=90), font=dict(size=9))
        fig.write_html(path)
        self._affinity_heatmap_preview(df, similarity, path.with_suffix(".png"))
        return path

    def _cluster_dendrogram(self, df: pd.DataFrame, matrix: pd.DataFrame, path: Path) -> Path:
        labels = df["PartNumber"].astype(str).tolist()
        dense = matrix.to_numpy(dtype=float)
        if len(dense) < 3:
            path.write_text("<html><body>At least three products are required for a dendrogram</body></html>", encoding="utf-8")
            return path
        distances = pdist(dense, metric="cosine")
        link = linkage(distances, method="average")
        fig = ff.create_dendrogram(dense, labels=labels, orientation="left", linkagefun=lambda _: link)
        fig.update_layout(title="Hierarchical dendrogram by technical affinity", margin=dict(t=58, l=120, r=20, b=30), font=dict(size=10), height=980)
        fig.write_html(path)
        self._dendrogram_preview(link, labels, path.with_suffix(".png"))
        return path

    def _visual_quantity_bubbles(self, df: pd.DataFrame, path: Path) -> Path:
        columns = [
            ("Product Type", "Product type"),
            ("Technical attribute 1", "Diameter"),
            ("Technical attribute 2", "Drain"),
            ("Technical attribute 4", "Handle"),
        ]
        rows: list[dict[str, Any]] = []
        for column, label in columns:
            if column not in df.columns:
                continue
            for value, count in df[column].replace("", "UNKNOWN").value_counts().head(5).items():
                rows.append({"Group": label, "Value": str(value), "Count": int(count)})
        if not rows:
            return self._empty_png(path, "No quantity distributions available")

        visual = pd.DataFrame(rows)
        group_order = list(dict.fromkeys(visual["Group"]))
        colors = ["#2458d3", "#2ca58d", "#f2a541", "#b84a62", "#536dfe"]
        fig, axes = plt.subplots(2, 2, figsize=(13, 8))
        axes_flat = list(axes.ravel())
        max_count = max(visual["Count"].max(), 1)
        for ax, group in zip(axes_flat, group_order):
            subset = visual[visual["Group"] == group].sort_values("Count", ascending=True).reset_index(drop=True)
            labels = ["\n".join(textwrap.wrap(str(value), 20)) for value in subset["Value"]]
            y_positions = np.arange(len(subset))
            sizes = 450 + 2200 * subset["Count"] / max_count
            ax.scatter(subset["Count"], y_positions, s=sizes, color=colors[: len(subset)], alpha=0.78, edgecolor="white", linewidth=1.5, zorder=3)
            ax.hlines(y_positions, 0, subset["Count"], color="#d9e1ec", linewidth=2, zorder=1)
            for x_value, y_value, count in zip(subset["Count"], y_positions, subset["Count"]):
                ax.text(x_value, y_value, str(int(count)), ha="center", va="center", color="white", fontsize=9, weight="bold")
            ax.set_yticks(y_positions)
            ax.set_yticklabels(labels, fontsize=8)
            ax.set_xlim(0, max_count * 1.18)
            ax.set_title(group, fontsize=12, weight="bold")
            ax.grid(axis="x", alpha=0.18)
            ax.spines[["top", "right", "left"]].set_visible(False)
        for ax in axes_flat[len(group_order) :]:
            ax.axis("off")
        fig.suptitle("Visual quantity bubbles: dominant product characteristics", fontsize=16, weight="bold")
        plt.tight_layout()
        plt.savefig(path, dpi=170)
        plt.close()
        return path

    def _visual_distribution_panel(self, df: pd.DataFrame, path: Path) -> Path:
        columns = [
            ("Product Type", "Product type distribution"),
            ("Technical attribute 1", "Diameter distribution"),
            ("Technical attribute 2", "Drain distribution"),
            ("Technical attribute 4", "Handle distribution"),
        ]
        available = [(column, title) for column, title in columns if column in df.columns]
        if not available:
            return self._empty_png(path, "No distribution data available")
        fig, axes = plt.subplots(2, 2, figsize=(13, 8))
        axes_flat = list(axes.ravel())
        palette = ["#2458d3", "#2ca58d", "#f2a541", "#b84a62", "#536dfe", "#64748b"]
        for ax, (column, title) in zip(axes_flat, available):
            counts = df[column].replace("", "UNKNOWN").value_counts().head(6).sort_values()
            labels = ["\n".join(textwrap.wrap(str(label), 18)) for label in counts.index]
            bars = ax.barh(labels, counts.values, color=palette[: len(counts)])
            ax.set_title(title, fontsize=12, weight="bold")
            ax.grid(axis="x", alpha=0.18)
            ax.spines[["top", "right", "left"]].set_visible(False)
            for bar in bars:
                width = bar.get_width()
                ax.text(width + max(counts.values) * 0.02, bar.get_y() + bar.get_height() / 2, str(int(width)), va="center", fontsize=8)
        for ax in axes_flat[len(available) :]:
            ax.axis("off")
        fig.suptitle("Manager visual layer: quantity distributions", fontsize=16, weight="bold")
        plt.tight_layout()
        plt.savefig(path, dpi=170)
        plt.close()
        return path

    def _visual_cluster_story(self, df: pd.DataFrame, clusters: dict[str, Any], path: Path) -> Path:
        points = pd.DataFrame(clusters.get("points", []))
        if points.empty:
            return self._empty_png(path, "No cluster story available")
        explanations = clusters.get("explanations", [])
        fig = plt.figure(figsize=(13, 7.5))
        grid = fig.add_gridspec(1, 2, width_ratios=[1.2, 0.8])
        ax = fig.add_subplot(grid[0, 0])
        colors = plt.cm.Set2(np.linspace(0, 1, max(2, points["Cluster"].nunique())))
        for idx, (cluster, group) in enumerate(points.groupby("Cluster")):
            ax.scatter(group["PCA_X"], group["PCA_Y"], s=150, alpha=0.84, label=f"Cluster {cluster}", color=colors[idx], edgecolor="white", linewidth=1.2)
            ax.text(group["PCA_X"].mean(), group["PCA_Y"].mean(), f"C{cluster}\n{len(group)}", ha="center", va="center", fontsize=10, weight="bold", color="#162033")
        ax.set_title("Natural product groups", fontsize=14, weight="bold")
        ax.set_xlabel("Similarity axis X")
        ax.set_ylabel("Similarity axis Y")
        ax.grid(alpha=0.18)
        ax.legend(loc="best", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)

        ax_text = fig.add_subplot(grid[0, 1])
        ax_text.axis("off")
        ax_text.set_title("What each cluster means", fontsize=14, weight="bold", loc="left")
        y = 0.9
        for cluster in explanations[:5]:
            common = [
                item
                for item in cluster.get("Common", [])
                if item.get("Feature") not in {"Product Family", "Product Name"}
            ][:3]
            title = f"Cluster {cluster.get('Cluster')} - {cluster.get('Products')} codes"
            body = "\n".join(
                textwrap.wrap(
                    "; ".join(f"{item['Feature'].replace('Technical attribute ', 'Attr ')}={item['Value']}" for item in common) or "Mixed configuration",
                    38,
                )
            )
            ax_text.text(0.02, y, title, fontsize=10.5, weight="bold", color="#162033", transform=ax_text.transAxes)
            ax_text.text(0.02, y - 0.045, body, fontsize=8.2, color="#637083", transform=ax_text.transAxes, linespacing=1.25)
            y -= 0.18
        fig.suptitle("Visual cluster story: from quantities to product families", fontsize=16, weight="bold")
        plt.tight_layout()
        plt.savefig(path, dpi=170)
        plt.close()
        return path

    def _cluster_scatter_preview(self, df: pd.DataFrame, path: Path, title: str, symbol_labels: bool) -> Path:
        plt.figure(figsize=(10.5, 6.5))
        ax = plt.gca()
        colors = plt.cm.Set2(np.linspace(0, 1, max(2, df["Cluster"].nunique())))
        markers = ["o", "^", "s", "D", "P", "X", "v"]
        for idx, (cluster, group) in enumerate(df.groupby("Cluster")):
            marker = markers[idx % len(markers)] if symbol_labels else "o"
            ax.scatter(group["PCA_X"], group["PCA_Y"], s=115 if symbol_labels else 190, marker=marker, color=colors[idx], alpha=0.86, label=f"Cluster {cluster}", edgecolor="white", linewidth=1)
        ax.set_title(title, fontsize=14, weight="bold", pad=12)
        ax.set_xlabel("PCA X")
        ax.set_ylabel("PCA Y")
        ax.grid(alpha=0.2)
        ax.legend(loc="best", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=165)
        plt.close()
        return path

    def _bubble_preview(self, bubbles: pd.DataFrame, path: Path) -> Path:
        if bubbles.empty:
            return self._empty_png(path, "No bubble data available")
        plt.figure(figsize=(10.5, 6.5))
        ax = plt.gca()
        sizes = 900 + 3600 * bubbles["Products"] / max(1, bubbles["Products"].max())
        scatter = ax.scatter(bubbles["PCA_X"], bubbles["PCA_Y"], s=sizes, c=np.arange(len(bubbles)), cmap="Set2", alpha=0.76, edgecolor="white", linewidth=1.4)
        for _, row in bubbles.iterrows():
            ax.text(row["PCA_X"], row["PCA_Y"], f"C{row['Cluster']}\n{row['Products']}", ha="center", va="center", fontsize=10, weight="bold", color="#162033")
        x_min, x_max = float(bubbles["PCA_X"].min()), float(bubbles["PCA_X"].max())
        y_min, y_max = float(bubbles["PCA_Y"].min()), float(bubbles["PCA_Y"].max())
        x_pad = max(0.25, (x_max - x_min) * 0.12)
        y_pad = max(0.22, (y_max - y_min) * 0.18)
        ax.set_xlim(x_min - x_pad, x_max + x_pad)
        ax.set_ylim(y_min - y_pad, y_max + y_pad)
        ax.set_title("Bubble cluster: size = number of codes", fontsize=14, weight="bold", pad=12)
        ax.set_xlabel("Cluster position X")
        ax.set_ylabel("Cluster position Y")
        ax.grid(alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=165)
        plt.close()
        return path

    def _sankey_preview(self, links: dict[tuple[str, str], int], path: Path) -> Path:
        if not links:
            return self._empty_png(path, "No flow data available")
        top = pd.DataFrame([{"Flow": f"{source} -> {target}", "Codes": value} for (source, target), value in links.items()])
        top = top.sort_values("Codes").tail(14)
        plt.figure(figsize=(11, 7))
        labels = ["\n".join(textwrap.wrap(flow, 42)) for flow in top["Flow"]]
        bars = plt.barh(labels, top["Codes"], color="#2458d3")
        plt.title("Sankey preview: strongest characteristic flows", fontsize=14, weight="bold", pad=12)
        plt.xlabel("Codes")
        plt.grid(axis="x", alpha=0.2)
        for bar in bars:
            width = bar.get_width()
            plt.text(width + max(top["Codes"]) * 0.02, bar.get_y() + bar.get_height() / 2, str(int(width)), va="center", fontsize=8)
        plt.gca().spines[["top", "right", "left"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=165)
        plt.close()
        return path

    def _radar_preview(self, df: pd.DataFrame, features: list[str], path: Path) -> Path:
        categories = ["Completeness", "Drain variety", "Contact variety", "Handle variety", "Type concentration"]
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]
        fig, ax = plt.subplots(figsize=(7.8, 7.8), subplot_kw=dict(polar=True))
        for cluster, group in df.groupby("Cluster"):
            technical = [c for c in features if c.startswith("Technical attribute") and c in group.columns]
            completeness = float((group[technical].replace("UNKNOWN", pd.NA).notna().mean().mean() if technical else 0) * 100)
            values = [
                completeness,
                self._normalized_unique(group, "Technical attribute 2"),
                self._normalized_unique(group, "Technical attribute 3"),
                self._normalized_unique(group, "Technical attribute 4"),
                self._top_share(group, "Product Type") * 100,
            ]
            values += values[:1]
            ax.plot(angles, values, linewidth=2, label=f"Cluster {cluster}")
            ax.fill(angles, values, alpha=0.12)
        ax.set_title("Cluster radar comparison", fontsize=14, weight="bold", pad=24)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=9)
        ax.set_ylim(0, 100)
        ax.legend(loc="upper right", bbox_to_anchor=(1.28, 1.12), fontsize=8)
        plt.tight_layout()
        plt.savefig(path, dpi=165)
        plt.close()
        return path

    def _affinity_heatmap_preview(self, df: pd.DataFrame, similarity: np.ndarray, path: Path) -> Path:
        labels = df["PartNumber"].astype(str).tolist()
        plt.figure(figsize=(10, 8))
        ax = plt.gca()
        image = ax.imshow(similarity, cmap="Blues", vmin=0, vmax=1, aspect="auto")
        tick_step = max(1, len(labels) // 8)
        ticks = list(range(0, len(labels), tick_step))
        ax.set_xticks(ticks)
        ax.set_xticklabels([labels[i] for i in ticks], rotation=45, ha="right", fontsize=6)
        ax.set_yticks(ticks)
        ax.set_yticklabels([labels[i] for i in ticks], fontsize=6)
        ax.set_title("Affinity heatmap by technical similarity", fontsize=14, weight="bold", pad=12)
        plt.colorbar(image, ax=ax, fraction=0.026, pad=0.02, label="Similarity")
        ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=165)
        plt.close()
        return path

    def _dendrogram_preview(self, link: np.ndarray, labels: list[str], path: Path) -> Path:
        plt.figure(figsize=(11, 9))
        dendrogram(link, labels=labels, orientation="left", leaf_font_size=7, color_threshold=None)
        plt.title("Hierarchical dendrogram by technical affinity", fontsize=14, weight="bold", pad=12)
        plt.xlabel("Distance")
        plt.tight_layout()
        plt.savefig(path, dpi=165)
        plt.close()
        return path

    def _normalized_unique(self, df: pd.DataFrame, column: str) -> float:
        if column not in df.columns or df.empty:
            return 0.0
        count = df[column].replace("", "UNKNOWN").nunique()
        return min(100.0, float(count / max(1, len(df))) * 100)

    def _top_share(self, df: pd.DataFrame, column: str) -> float:
        if column not in df.columns or df.empty:
            return 0.0
        counts = df[column].replace("", "UNKNOWN").value_counts(normalize=True)
        return float(counts.iloc[0]) if not counts.empty else 0.0

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
        self._flow_preview(working, dims, path.with_suffix(".png"))
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
        self._treemap_preview(grouped, path.with_suffix(".png"))
        return path

    def _flow_preview(self, df: pd.DataFrame, dims: list[str], path: Path) -> Path:
        if df.empty or len(dims) < 2:
            return self._empty_png(path, "No characteristic flow data available")
        chains = df[dims].astype(str).agg(" -> ".join, axis=1).value_counts().head(12).sort_values()
        fig = plt.figure(figsize=(13, 7.5))
        grid = fig.add_gridspec(1, 2, width_ratios=[0.9, 1.1])
        ax = fig.add_subplot(grid[0, 0])
        ax_legend = fig.add_subplot(grid[0, 1])
        path_ids = [f"Path {idx + 1:02d}" for idx in range(len(chains))]
        bars = ax.barh(path_ids, chains.values, color="#2ca58d")
        ax.set_title("Most common configuration paths", fontsize=13, weight="bold", pad=10)
        ax.set_xlabel("Codes")
        ax.grid(axis="x", alpha=0.2)
        for bar in bars:
            width = bar.get_width()
            ax.text(width + max(chains.values) * 0.03, bar.get_y() + bar.get_height() / 2, str(int(width)), va="center", fontsize=8)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax_legend.axis("off")
        ax_legend.set_title("Path legend", fontsize=13, weight="bold", loc="left", pad=10)
        y = 0.96
        for path_id, chain, count in zip(path_ids[::-1], chains.index[::-1], chains.values[::-1]):
            wrapped = "\n".join(textwrap.wrap(str(chain), 54))
            ax_legend.text(0.0, y, f"{path_id}  ({int(count)} code{'s' if int(count) != 1 else ''})", fontsize=8.4, weight="bold", color="#162033", transform=ax_legend.transAxes)
            ax_legend.text(0.0, y - 0.035, wrapped, fontsize=7.2, color="#637083", transform=ax_legend.transAxes, linespacing=1.15)
            y -= 0.078 + 0.025 * wrapped.count("\n")
            if y < 0.03:
                break
        fig.suptitle("Characteristic flow preview", fontsize=15, weight="bold")
        plt.tight_layout()
        plt.savefig(path, dpi=165)
        plt.close()
        return path

    def _treemap_preview(self, grouped: pd.DataFrame, path: Path) -> Path:
        if grouped.empty:
            return self._empty_png(path, "No hierarchy data available")
        label_column = "Product Type" if "Product Type" in grouped.columns else grouped.columns[0]
        top = grouped.groupby(label_column)["Records"].sum().sort_values().tail(16)
        plt.figure(figsize=(11, 7))
        labels = ["\n".join(textwrap.wrap(str(label), 34)) for label in top.index]
        bars = plt.barh(labels, top.values, color="#2458d3")
        plt.title("Catalogue hierarchy preview: largest product groups", fontsize=14, weight="bold", pad=12)
        plt.xlabel("Records")
        plt.grid(axis="x", alpha=0.2)
        for bar in bars:
            width = bar.get_width()
            plt.text(width + max(top.values) * 0.02, bar.get_y() + bar.get_height() / 2, str(int(width)), va="center", fontsize=8)
        plt.gca().spines[["top", "right", "left"]].set_visible(False)
        plt.tight_layout()
        plt.savefig(path, dpi=165)
        plt.close()
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
