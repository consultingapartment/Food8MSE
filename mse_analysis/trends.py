"""Түүхэн хандлага: жилийн цуваа, индексжүүлсэн өсөлт, CAGR, цэвэр ашгийн маржины хэлбэлзэл, орлогоос ашиг хүртэлх задаргаа."""
from __future__ import annotations

import math
from typing import Optional

from .base import Company, div
from .fundamentals import cagr

METRICS = [
    ("revenue", "Борлуулалтын орлого (тэрбум ₮)", "bn"),
    ("net_income", "Цэвэр ашиг (тэрбум ₮)", "bn"),
    ("gross_margin", "Нийт ашгийн маржин", "pct"),
    ("net_margin", "Цэвэр ашгийн маржин", "pct"),
    ("roe", "ROE (цэвэр ашиг ÷ жилийн эцсийн өмч)", "pct"),
    ("total_assets", "Нийт хөрөнгө (тэрбум ₮)", "bn"),
]


def annual_table(c: Company) -> dict[int, dict[str, Optional[float]]]:
    """Жил -> үзүүлэлт (зөвхөн Q4 буюу 12 сарын тайлантай жилүүд)."""
    out: dict[int, dict[str, Optional[float]]] = {}
    for r in c.annual():
        rev, ni, gp, eq, ta = (c.v(r, k) for k in ("revenue", "net_income", "gross_profit", "total_equity", "total_assets"))
        out[r.period.year] = {
            "revenue": None if rev is None else rev / 1e6,
            "net_income": None if ni is None else ni / 1e6,
            "gross_margin": div(gp, rev), "net_margin": div(ni, rev),
            "roe": div(ni, eq) if (eq or 0) > 0 else None,
            "total_assets": None if ta is None else ta / 1e6,
        }
    return out


def revenue_cagr(c: Company) -> Optional[float]:
    t = annual_table(c)
    return cagr([(y, d["revenue"]) for y, d in t.items() if d["revenue"] is not None])


def index_series(c: Company) -> dict[int, float]:
    """Орлогын индекс (анхны жил = 100)."""
    pts = sorted((y, d["revenue"]) for y, d in annual_table(c).items() if d["revenue"])
    if not pts or pts[0][1] <= 0:
        return {}
    base = pts[0][1]
    return {y: v / base * 100 for y, v in pts}


def margin_volatility(c: Company) -> Optional[float]:
    """Цэвэр ашгийн маржины стандарт хазайлт (хувийн нэгжээр, 0.05 = 5 нэгж хувь). Хамгийн багадаа 3 жил."""
    ms = [d["net_margin"] for d in annual_table(c).values() if d["net_margin"] is not None]
    if len(ms) < 3:
        return None
    mu = sum(ms) / len(ms)
    return math.sqrt(sum((m - mu) ** 2 for m in ms) / len(ms))


def breakdown(c: Company) -> Optional[dict[str, float]]:
    """Орлого → цэвэр ашиг (тэрбум ₮, сүүлийн 12 сар)."""
    r = c.latest
    if r is None:
        return None
    f = lambda k: c.flow(r, k)[0] or 0.0            # noqa: E731
    rev = c.flow(r, "revenue")[0]
    if rev is None:
        return None
    cogs, sell, adm, fin, ni = f("cogs"), f("selling_exp"), f("admin_exp"), f("finance_cost"), f("net_income")
    other = rev - cogs - sell - adm - fin - ni
    k = 1e6
    return {"Орлого": rev / k, "(-) Өртөг": cogs / k, "(-) Борлуулалт, маркетинг": sell / k,
            "(-) Ерөнхий удирдлага": adm / k, "(-) Санхүүгийн зардал": fin / k,
            "(-) Татвар ба бусад": other / k, "Цэвэр ашиг": ni / k}
