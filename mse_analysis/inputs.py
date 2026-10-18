"""`inputs/` хавтасны гараар шинэчлэгддэг өгөгдөл: зах зээлийн мэдээлэл, эзэмшил, арилжааны түүх."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from .prices import Bar, load_prices


@dataclass
class Market:
    ticker: str
    price: Optional[float]            # хоосон бол арилжааны түүхийн сүүлийн хаалт
    price_date: Optional[date]
    dps: Optional[float]              # нэг хувьцаанд ногдох ногдол ашиг (төгрөг)
    dps_year: Optional[int]
    shares: Optional[float] = None    # нийт гаргасан хувьцаа (ширхэг)


@dataclass
class Ownership:
    ticker: str
    as_of: date
    big_holders: int                  # 5%-аас их хувь эзэмшигчдийн тоо
    big_pct: float                    # тэдний нийт хувь (0.8656 = 86.56%)
    small_holders: int                # 5%-аас бага хувь эзэмшигчдийн тоо
    small_pct: float                  # чөлөөт эргэлт


@dataclass
class Inputs:
    market: dict[str, Market]
    ownership: dict[str, list[Ownership]]       # хуучнаас шинэ рүү
    prices: dict[str, list[Bar]]

    def latest_ownership(self, t: str) -> Optional[Ownership]:
        rows = self.ownership.get(t) or []
        return rows[-1] if rows else None


def _f(s: str) -> Optional[float]:
    s = (s or "").strip().replace(",", "")
    return float(s) if s else None


def _d(s: str) -> Optional[date]:
    s = (s or "").strip()
    return date.fromisoformat(s) if s else None


def load_market(path: Path) -> dict[str, Market]:
    out: dict[str, Market] = {}
    if not path.exists():
        return out
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = r["ticker"].strip().upper()
            year = _f(r.get("dps_year", ""))
            out[t] = Market(t, _f(r.get("price", "")), _d(r.get("price_date", "")), _f(r.get("dps", "")),
                            int(year) if year else None, _f(r.get("shares", "")))
    return out


def load_ownership(path: Path) -> dict[str, list[Ownership]]:
    out: dict[str, list[Ownership]] = {}
    if not path.exists():
        return out
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = r["ticker"].strip().upper()
            out.setdefault(t, []).append(Ownership(
                t, date.fromisoformat(r["snapshot"]), int(float(r["big_holders"] or 0)),
                float(r["big_share"] or 0), int(float(r["small_holders"] or 0)), float(r["small_share"] or 0)))
    for rows in out.values():
        rows.sort(key=lambda o: o.as_of)
    return out


def load_inputs(directory: Path) -> Inputs:
    market = load_market(directory / "market.csv")
    ownership = load_ownership(directory / "ownership.csv")
    prices = load_prices(directory / "prices")
    for t, m in market.items():
        if m.price is None and prices.get(t):
            last = prices[t][-1]
            m.price, m.price_date = last.close, last.day
    return Inputs(market, ownership, prices)
