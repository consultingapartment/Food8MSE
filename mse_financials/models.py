"""Өгөгдлийн бүтцүүд."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional


@dataclass(frozen=True, order=True)
class Period:
    """Тайлангийн үе. year=0 бол үе тодорхойгүй (tag нь файлын нэр)."""

    year: int
    quarter: int
    tag: str = ""

    @property
    def label(self) -> str:
        return f"{self.year} Q{self.quarter}" if self.year else self.tag

    @property
    def compact(self) -> str:
        return f"{self.year}Q{self.quarter}" if self.year else self.tag


@dataclass(frozen=True)
class ReportLink:
    """Хуудаснаас олдсон тайлангийн файлын холбоос."""

    url: str
    period: Optional[Period] = None
    text: str = ""
    filed: str = ""  # хуудсан дээрх ирүүлсэн огноо (YYYY-MM-DD)

    @property
    def kind(self) -> str:
        """'pdf' эсвэл 'xls' (xls/xlsx) — холбоосын өргөтгөлөөр."""
        return "pdf" if self.url.lower().split("?")[0].endswith(".pdf") else "xls"


@dataclass
class Downloaded:
    ticker: str
    path: Path
    url: str = ""
    period: Optional[Period] = None
    new: bool = False  # энэ ажиллуулалтаар шинээр татагдсан эсэх
    filed: str = ""


@dataclass
class ParsedReport:
    """Нэг тайлангаас задалсан, стандарт загварын түлхүүрээр индексжсэн утгууд."""

    ticker: str
    period: Period
    end_date: date
    months: int                          # хамрах хугацаа (3/6/9/12); ОДТ нь оны эхнээс хуримтлагдсан
    values: dict[str, float] = field(default_factory=dict)  # түлхүүр -> утга (мянган төгрөг; EPS — төгрөг)
    source: str = ""
    filed: str = ""                      # МХБ-д ирүүлсэн огноо (YYYY-MM-DD); хуудсаас татсан үед л мэдэгдэнэ
    scale_note: str = ""                 # нэгжийн засвар хийсэн бол тайлбар
    unmatched: list[str] = field(default_factory=list)  # загварт таараагүй, утгатай мөрүүд

    @property
    def size(self) -> int:
        return len(self.values)
