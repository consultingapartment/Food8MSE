"""Цэвэр ашгийн прогноз: бүх түүхэн жилээр лог-шугаман регресс (3 арга) ба медиан."""
from __future__ import annotations

import math
import statistics
from typing import Optional

from .base import Company
from .trends import annual_table


def log_regress(points: list[tuple[int, float]], target: int) -> Optional[float]:
    """ln(утга) = a + b·он. Зөвхөн эерэг утгатай жилүүд; хамгийн багадаа 2 цэг."""
    pts = [(x, math.log(y)) for x, y in points if y and y > 0]
    n = len(pts)
    if n < 2:
        return None
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in pts) / sxx
    return math.exp(my + b * (target - mx))


def net_income(c: Company, target_year: int, min_years: int = 3) -> Optional[dict]:
    """A: ln(ЦА) регресс. B: ln(Орлого) регресс × сүүлийн жилийн маржин. C: … × түүхэн дундаж маржин.
    Дутуу жилүүд (тайлангүй) цэг болохгүй. Голч = боломжит аргуудын медиан. Нэгж: тэрбум ₮."""
    t = {y: d for y, d in annual_table(c).items() if y < target_year}
    ni_pts = [(y, d["net_income"]) for y, d in t.items() if d["net_income"] is not None]
    rev_pts = [(y, d["revenue"]) for y, d in t.items() if d["revenue"] is not None]
    margins = [d["net_margin"] for d in t.values() if d["net_margin"] is not None]
    if len([p for p in ni_pts if p[1] > 0]) < min_years:
        return None
    a = log_regress(ni_pts, target_year)
    rev = log_regress(rev_pts, target_year)
    last_margin = t[max(t)]["net_margin"] if t else None
    b = None if rev is None or last_margin is None else rev * last_margin
    cc = None if rev is None or not margins else rev * sum(margins) / len(margins)
    vals = [x for x in (a, b, cc) if x is not None]
    if not vals:
        return None
    mid = statistics.median(vals)
    actual = c.find(target_year, 12)
    h1 = c.find(target_year, 6)
    act = None if actual is None or c.v(actual, "net_income") is None else c.v(actual, "net_income") / 1e6
    h1v = None if h1 is None or c.v(h1, "net_income") is None else c.v(h1, "net_income") / 1e6
    return {"years": len([p for p in ni_pts if p[1] > 0]), "a": a, "b": b, "c": cc, "median": mid,
            "h2": mid * 0.5, "h1_actual": h1v, "rest_of_year": None if h1v is None else mid - h1v,
            "actual": act, "variance": None if act is None else act - mid,
            "variance_pct": None if act is None or mid == 0 else (act - mid) / mid}
