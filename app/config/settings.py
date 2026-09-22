from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


IS_FROZEN = bool(getattr(sys, "frozen", False))
ROOT_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
DATA_DIR = ROOT_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = (Path.home() / "Documents" / "ProductAnalyzer" / "output") if IS_FROZEN else DATA_DIR / "output"
CACHE_DIR = DATA_DIR / "cache"


@dataclass(frozen=True)
class DemoSettings:
    catalogue_path: Path = INPUT_DIR / "PrM_Lean-Catalogue_v2s (2)-rev1.xlsx"
    pdf_paths: tuple[Path, ...] = (
        INPUT_DIR / "725958XX08_AH00.pdf",
        INPUT_DIR / "FT0120872-100_C00.pdf",
    )
    focus_product_name: str = "B - ISOLATING COCKS"
    focus_expected_count: int = 58
    confidence_review_threshold: float = 0.75
    output_dir: Path = OUTPUT_DIR


def ensure_directories() -> None:
    for path in (INPUT_DIR, OUTPUT_DIR, CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)
