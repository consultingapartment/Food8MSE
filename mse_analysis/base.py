"""Тайлангийн өгөгдлийн хандалт: компани бүрийн тайлангийн цуваа, оны түвшний (LTM / жилчилсэн) урсгал, дундаж үлдэгдэл.

Нэгж: мянган төгрөг. Орлогын тайлангийн мөр нь оны эхнээс хуримтлагдсан (YTD), балансын мөр нь тайлант огнооны үлдэгдэл.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mse_financials.config import COMPANIES
from mse_financials.excel import load_existing
from mse_financials.models import ParsedReport

LTM = "LTM"                       # сүүлийн 12 сар = өмнөх оны жил + энэ оны YTD − өмнөх оны YTD
ANNUALIZED = "Жилчилсэн"          # LTM тооцох өгөгдөл дутуу үед YTD × 12 ÷ сар


def div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """Аль нэг нь хоосон эсвэл хуваагч 0 бол None."""
    if a is None or b is None or b == 0:
        return None
    return a / b


def sub(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return None if a is None or b is None else a - b


@dataclass
class Company:
    ticker: str
    reports: list[ParsedReport]           # хуучнаас шинэ рүү

    # ------------------------------------------------------------------ хайлт
    def find(self, year: int, months: int) -> Optional[ParsedReport]:
        return next((r for r in self.reports if r.period.year == year and r.months == months), None)

    def prev_same(self, r: ParsedReport) -> Optional[ParsedReport]:
        """Өмнөх оны ижил үеийн тайлан."""
        return self.find(r.period.year - 1, r.months)

    def prev_year_end(self, r: ParsedReport) -> Optional[ParsedReport]:
        return self.find(r.period.year - 1, 12)

    @property
    def latest(self) -> Optional[ParsedReport]:
        return self.reports[-1] if self.reports else None

    def annual(self) -> list[ParsedReport]:
        return [r for r in self.reports if r.months == 12]

    # ------------------------------------------------------------------ утга
    @staticmethod
    def v(r: Optional[ParsedReport], key: str) -> Optional[float]:
        """Мөрийн утга. Тайланд байхгүй мөр = 0 (хоосон нүд), харин ТОМ дүн (нийт хөрөнгө г.м) байхгүй бол None."""
        if r is None:
            return None
        if key in r.values:
            return r.values[key]
        return None if key in _MUST_EXIST else 0.0

    def ltm(self, r: ParsedReport, key: str) -> Optional[float]:
        """ОДТ-ийн мөрийн сүүлийн 12 сарын дүн. Өгөгдөл дутуу бол None."""
        cur = self.v(r, key)
        if cur is None:
            return None
        if r.months == 12:
            return cur
        fy, prev = self.prev_year_end(r), self.prev_same(r)
        if fy is None or prev is None:
            return None
        a, b = self.v(fy, key), self.v(prev, key)
        return None if a is None or b is None else a + cur - b

    def flow(self, r: ParsedReport, key: str) -> tuple[Optional[float], str]:
        """Оны түвшний урсгал + үндэслэл (LTM, эс бөгөөс жилчилсэн)."""
        x = self.ltm(r, key)
        if x is not None:
            return x, LTM
        cur = self.v(r, key)
        return (None if cur is None else cur * 12 / r.months), ANNUALIZED

    def avg(self, r: ParsedReport, key: str) -> Optional[float]:
        """Дундаж үлдэгдэл = (өмнөх оны эцэс + одоогийн) ÷ 2; өмнөх оны эцэс байхгүй бол одоогийн."""
        cur = self.v(r, key)
        if cur is None:
            return None
        prev = self.v(self.prev_year_end(r), key) if r.months != 12 or self.prev_year_end(r) else None
        return cur if prev is None else (cur + prev) / 2

    def ebit(self, r: ParsedReport) -> Optional[float]:
        """Татвар, хүүгийн өмнөх ашиг (YTD) = Татвар төлөхийн өмнөх ашиг + Санхүүгийн зардал."""
        pbt = self.v(r, "profit_before_tax")
        return None if pbt is None else pbt + (self.v(r, "finance_cost") or 0.0)

    def ebit_flow(self, r: ParsedReport) -> tuple[Optional[float], str]:
        pbt, basis = self.flow(r, "profit_before_tax")
        fin, _ = self.flow(r, "finance_cost")
        return (None if pbt is None else pbt + (fin or 0.0)), basis

    def interest_debt(self, r: ParsedReport) -> float:
        """Хүүтэй өр = богино + урт хугацаат зээл."""
        return (self.v(r, "st_loan") or 0.0) + (self.v(r, "lt_loan") or 0.0)


#: Байхгүй бол 0 гэж үзэж болохгүй (тайлан бүрэн уншигдаагүй гэсэн үг) дүнгүүд
_MUST_EXIST = {"total_assets", "total_ca", "total_stl", "total_liabilities", "total_equity", "revenue",
               "net_income", "profit_before_tax", "gross_profit", "cogs"}


def load_companies(path: Path, tickers: tuple[str, ...] | list[str] | None = None) -> dict[str, Company]:
    """`FOOD mse.xlsx` -> {тикер: Company}. Тайлангүй компани орохгүй."""
    tickers = list(tickers or COMPANIES)
    reports = load_existing(path, tickers)
    out: dict[str, Company] = {}
    for t in tickers:
        rs = sorted((r for r in reports if r.ticker == t), key=lambda r: r.end_date)
        if rs:
            out[t] = Company(t, rs)
    return out
