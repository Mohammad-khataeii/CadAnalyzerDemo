# Visual Output Analysis

The current catalogue has enough signal for more than frequency bars. The most useful views are:

## High-value visuals now implemented

| Visual | Output | Why it helps |
|---|---|---|
| Catalogue hierarchy treemap | `catalogue_hierarchy_treemap.html` | Shows where catalogue volume concentrates across OPS category, family, product name, and product type. |
| Attribute completeness heatmap | `attribute_completeness.png` | Makes missing technical attribute coverage obvious by product family. |
| Maturity by family | `maturity_by_family.png` | Shows released vs not released/TBA concentration by family. |
| Rule influence chart | `rule_influence.png` | Explains which attributes carry PartNumber signal and with what support. |
| Anomaly breakdown | `anomaly_breakdown.png` | Shows which anomaly classes dominate and their severity mix. |
| Extraction confidence chart | `extraction_confidence.png` | Shows which extracted fields are reliable and which need review. |
| BOM frequency chart | `bom_frequency.png` | Highlights reused component identifiers across analyzed PDFs. |
| Cluster scatter | `cluster_scatter.html` | Shows catalogue similarity structure after categorical encoding and PCA. |
| Contact/handle heatmap | `contact_handle_matrix.png` | Shows relationships between contact and handle/control-related attributes. |
| Advanced scatter cluster | `advanced_scatter_cluster.html` | Interactive scatter with cluster color and symbol encoding. |
| Hierarchical dendrogram | `cluster_dendrogram.html` | Shows product affinity as a tree; closer branches indicate higher technical similarity. |
| Affinity heatmap | `affinity_heatmap.html` | Shows pairwise technical similarity between product codes. Darker cells mean stronger affinity. |
| Bubble cluster | `cluster_bubble.html` | Shows cluster centroids, relative distance, and cluster size. |
| Colored cluster map | `cluster_colored_map.html` | Manager-friendly PCA map with colored product clusters. |
| Sankey by characteristics | `cluster_sankey.html` | Shows how product types and technical characteristics flow into clusters. |
| Cluster radar | `cluster_radar.html` | Compares clusters across completeness, variety, and concentration indicators. |

## Useful next visuals

| Visual | Data needed | Purpose |
|---|---|---|
| Family-specific configuration matrix | Catalogue technical attributes | For one family at a time, show observed/missing Diameter x Drain x Contact x Handle combinations. |
| Variant delta matrix | More robust variant extraction | Compare variants in a drawing and show exactly which characteristics differ. |
| PDF-to-catalogue match funnel | More PDFs | Counts direct match, predicted match, ambiguous, unmatched, and needs review. |
| Component-to-product network | Cleaner BOM table extraction | Reveal shared components and product platform reuse. |
| PartNumber segment explorer | More released rows per family | Visualize which PN digits/segments vary with each characteristic. |
| Review workload board | Human validation edits | Track fields accepted, edited, ignored, and still pending. |
| Time/quantity planning view | Reliable quantity columns | Connect `Q.,ty in 2026`, maturity, and family to prioritize engineering cleanup. |

## Current data signals

- The strongest hierarchy concentration is around Brake Control and Air Distribution / Isolating Cocks.
- Technical attributes are unevenly populated; completeness charts are useful because many families have sparse attributes.
- Anomaly visuals are useful immediately: the current run finds duplicate/conflicting configurations, low-confidence extraction, and missing expected combinations.
- BOM visuals are useful but should be treated as provisional until BOM table extraction is made more precise.
