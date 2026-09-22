# Product Analyzer

Local Python desktop POC for engineering drawing extraction, catalogue-compatible export, clustering, anomalies, similarity, and reporting.

## Run the demo pipeline

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m app.main --demo
```

Outputs are written to `data/output`.

## Launch the desktop app

```bash
.venv/bin/python -m app.main
```

The GUI is built with PySide6 and runs the supplied demo files automatically.

## Demo inputs

- `data/input/PrM_Lean-Catalogue_v2s (2)-rev1.xlsx`
- `data/input/725958XX08_AH00.pdf`
- `data/input/FT0120872-100_C00.pdf`

The generated catalogue preserves the original catalogue columns. Evidence and metadata are exported separately.

