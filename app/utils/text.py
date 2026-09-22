from __future__ import annotations

import re
from typing import Iterable


def clean_cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none"}:
        return ""
    return re.sub(r"\s+", " ", text)


def normalize_part_number(value: str) -> str:
    text = clean_cell(value).upper()
    if text in {"", "N/A", "NA", "TBA"}:
        return text
    if re.fullmatch(r"\d{3}\s?\d{3}\s?\d{2}\s?\d{2}", text):
        return re.sub(r"\s+", "", text)
    return text


def compact_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = clean_cell(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def first_match(pattern: str, text: str, flags: int = re.I) -> str:
    match = re.search(pattern, text, flags)
    return clean_cell(match.group(1) if match and match.groups() else match.group(0) if match else "")

