from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys


IS_FROZEN = bool(getattr(sys, "frozen", False))
ROOT_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
DATA_DIR = ROOT_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
USER_DATA_DIR = Path.home() / "Documents" / "ProductAnalyzer"
OUTPUT_DIR = (USER_DATA_DIR / "output") if IS_FROZEN else DATA_DIR / "output"
CACHE_DIR = (USER_DATA_DIR / "cache") if IS_FROZEN else DATA_DIR / "cache"
TECHNICAL_DESIGNS_DIR = Path.home() / "Desktop" / "TechnicalDesigns"


def default_pdf_paths() -> tuple[Path, ...]:
    technical_designs = (
        TECHNICAL_DESIGNS_DIR / "FT0024835-100_A03.pdf",
        TECHNICAL_DESIGNS_DIR / "1-498149_B03.pdf",
        TECHNICAL_DESIGNS_DIR / "FT0105784-100-smns_B01.pdf",
        TECHNICAL_DESIGNS_DIR / "FT0027389-100_L00_F2.pdf",
        TECHNICAL_DESIGNS_DIR / "FT0127469-100.pdf",
        TECHNICAL_DESIGNS_DIR / "FT0127470-100.pdf",
    )
    if any(path.exists() for path in technical_designs):
        return technical_designs
    return (
        INPUT_DIR / "725958XX08_AH00.pdf",
        INPUT_DIR / "FT0120872-100_C00.pdf",
    )


@dataclass(frozen=True)
class DemoSettings:
    catalogue_path: Path = INPUT_DIR / "PrM_Lean-Catalogue_v2s (2)-rev1.xlsx"
    pdf_paths: tuple[Path, ...] = field(default_factory=default_pdf_paths)
    focus_product_name: str = "D - MANOMETERS"
    focus_expected_count: int = 19
    confidence_review_threshold: float = 0.75
    output_dir: Path = OUTPUT_DIR


def ensure_directories() -> None:
    writable_paths = (OUTPUT_DIR, CACHE_DIR)
    if not IS_FROZEN:
        writable_paths = (INPUT_DIR, *writable_paths)
    for path in writable_paths:
        path.mkdir(parents=True, exist_ok=True)
