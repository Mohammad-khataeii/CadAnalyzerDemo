from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.models.domain import CatalogueProfile
from app.utils.text import clean_cell, normalize_part_number


CATALOGUE_HEADER_ROW = 3


class CatalogueLoader:
    """Loads the customer catalogue without changing its schema."""

    def load(self, path: Path) -> tuple[pd.DataFrame, CatalogueProfile]:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path).fillna("")
            for column in df.columns:
                df[column] = df[column].map(clean_cell)
            for column in ("PartNumber", "Master PN"):
                if column in df.columns:
                    df[column] = df[column].map(normalize_part_number)
            technical_columns = [c for c in df.columns if c.startswith("Technical attribute")]
            profile = CatalogueProfile(
                path=path,
                sheet_name="CSV",
                digit_metadata={},
                columns=list(df.columns),
                row_count=len(df),
                part_rows=int(df.get("PartNumber", pd.Series(dtype=str)).astype(bool).sum()),
                family_counts=df.get("Product Family", pd.Series(dtype=str)).value_counts().to_dict(),
                technical_columns=technical_columns,
            )
            return df, profile

        excel = pd.ExcelFile(path)
        sheet_name = excel.sheet_names[0]
        raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
        digit_row = raw.iloc[1].fillna("").tolist()
        df = pd.read_excel(path, sheet_name=sheet_name, header=CATALOGUE_HEADER_ROW)
        df = df.drop(columns=[c for c in df.columns if str(c).startswith("Unnamed")], errors="ignore")
        df = df.dropna(how="all").copy()
        for column in df.columns:
            df[column] = df[column].map(clean_cell)
        for column in ("PartNumber", "Master PN"):
            if column in df.columns:
                df[column] = df[column].map(normalize_part_number)

        digit_metadata = {
            str(df.columns[i]): clean_cell(digit_row[i + 1])
            for i in range(min(len(df.columns), max(0, len(digit_row) - 1)))
            if clean_cell(digit_row[i + 1])
        }
        technical_columns = [c for c in df.columns if c.startswith("Technical attribute")]
        profile = CatalogueProfile(
            path=path,
            sheet_name=sheet_name,
            digit_metadata=digit_metadata,
            columns=list(df.columns),
            row_count=len(df),
            part_rows=int(df.get("PartNumber", pd.Series(dtype=str)).astype(bool).sum()),
            family_counts=df.get("Product Family", pd.Series(dtype=str)).value_counts().to_dict(),
            technical_columns=technical_columns,
        )
        return df, profile
