"""Харьцааны шинжилгээ, DuPont, өсөлт: тайлан (багана) бүрээр. Бүх харьцаа бутархай (0.12 = 12%)."""
from __future__ import annotations

from typing import Optional

from mse_financials.models import ParsedReport

from .base import Company, div, sub

#: (түлхүүр, нэр, формат) — Excel-ийн багана ба тайлбарын дараалал
COLUMNS = [
    # Хөрвөх чадвар
    ("current_ratio", "Эргэлтийн хөрөнгийн харьцаа (Current Ratio)", "x"),
    ("quick_ratio", "Шуурхай хөрвөх чадлын харьцаа (Quick Ratio)", "x"),
    ("cash_ratio", "Мөнгөний харьцаа (Cash Ratio)", "x"),
    ("working_capital", "Эргэлтийн хөрөнгө − Богино өр (мянган ₮)", "money"),
    ("wc_to_assets", "Цэвэр эргэлтийн хөрөнгө / Нийт хөрөнгө", "pct"),
    # Ашигт ажиллагаа
    ("gross_margin", "Нийт ашгийн маржин", "pct"),
    ("operating_margin", "Үйл ажиллагааны ашгийн маржин", "pct"),
    ("ebit_margin", "EBIT маржин", "pct"),
    ("net_margin", "Цэвэр ашгийн маржин", "pct"),
    ("roa", "Хөрөнгийн өгөөж (ROA)", "pct"),
    ("roe", "Өмчийн өгөөж (ROE)", "pct"),
    ("roce", "Ашигласан хөрөнгийн өгөөж (ROCE)", "pct"),
    # Өрийн бүтэц
    ("debt_ratio", "Өр / Нийт хөрөнгө", "pct"),
    ("debt_to_equity", "Өр / Эздийн өмч", "x"),
    ("equity_ratio", "Эздийн өмч / Нийт хөрөнгө", "pct"),
    ("net_debt", "Цэвэр хүүтэй өр (мянган ₮)", "money"),
    ("net_debt_to_ebit", "Цэвэр хүүтэй өр / EBIT", "x"),
    ("interest_coverage", "Хүүгийн нөхөх чадвар (EBIT / Санхүүгийн зардал)", "x"),
    # Эргэлт
    ("asset_turnover", "Хөрөнгийн эргэлт", "x"),
    ("inventory_days", "Бараа материалын эргэлтийн хоног", "days"),
    ("receivable_days", "Авлагын эргэлтийн хоног", "days"),
    ("payable_days", "Өглөгийн эргэлтийн хоног", "days"),
    ("cash_cycle", "Мөнгөн мөчлөг (хоног)", "days"),
    # Өсөлт (өмнөх оны ижил үетэй харьцуулсан)
    ("revenue_yoy", "Орлогын өсөлт (YoY)", "pct"),
    ("gross_profit_yoy", "Нийт ашгийн өсөлт (YoY)", "pct"),
    ("net_income_yoy", "Цэвэр ашгийн өсөлт (YoY)", "pct"),
    ("assets_yoy", "Нийт хөрөнгийн өсөлт (YoY)", "pct"),
    ("equity_yoy", "Эздийн өмчийн өсөлт (YoY)", "pct"),
]

DUPONT_COLUMNS = [
    ("tax_burden", "Татварын ачаалал (Цэвэр ашиг / Татварын өмнөх ашиг)", "x"),
    ("interest_burden", "Хүүгийн ачаалал (Татварын өмнөх ашиг / EBIT)", "x"),
    ("ebit_margin", "EBIT маржин", "pct"),
    ("net_margin", "Цэвэр ашгийн маржин", "pct"),
    ("asset_turnover", "Хөрөнгийн эргэлт", "x"),
    ("equity_multiplier", "Өмчийн үржүүлэгч (Дундаж хөрөнгө / Дундаж өмч)", "x"),
    ("roe", "ROE = Маржин × Эргэлт × Өмчийн үржүүлэгч", "pct"),
]


def _growth(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    """Өсөлтийн хувь. Өмнөх утга ≤ 0 үед утга учиргүй тул None."""
    if cur is None or prev is None or prev <= 0:
        return None
    return cur / prev - 1


def ratios(c: Company, r: ParsedReport) -> dict[str, Optional[float]]:
    v = lambda k: c.v(r, k)           # noqa: E731
    ca, stl = v("total_ca"), v("total_stl")
    cash = v("cash")
    other_liquid = (v("receivable") or 0) + (v("tax_receivable") or 0) + (v("other_receivable") or 0) \
        + (v("other_fin_assets") or 0)
    ta, eq, tl = v("total_assets"), v("total_equity"), v("total_liabilities")
    rev, gp, ni = v("revenue"), v("gross_profit"), v("net_income")
    op = None if gp is None else gp - (v("selling_exp") or 0) - (v("admin_exp") or 0)
    ebit = c.ebit(r)

    rev_f, basis = c.flow(r, "revenue")
    cogs_f, _ = c.flow(r, "cogs")
    ni_f, _ = c.flow(r, "net_income")
    ebit_f, _ = c.ebit_flow(r)
    avg_ta, avg_eq = c.avg(r, "total_assets"), c.avg(r, "total_equity")
    fin = v("finance_cost") or 0.0

    debt = c.interest_debt(r)
    net_debt = None if cash is None else debt - cash
    prev = c.prev_same(r)
    pv = lambda k: c.v(prev, k)       # noqa: E731

    out: dict[str, Optional[float]] = {
        "current_ratio": div(ca, stl),
        "quick_ratio": div(None if ca is None else cash + other_liquid if cash is not None else None, stl),
        "cash_ratio": div(cash, stl),
        "working_capital": sub(ca, stl),
        "wc_to_assets": div(sub(ca, stl), ta),
        "gross_margin": div(gp, rev),
        "operating_margin": div(op, rev),
        "ebit_margin": div(ebit, rev),
        "net_margin": div(ni, rev),
        "roa": div(ni_f, avg_ta),
        "roe": div(ni_f, avg_eq),
        "roce": div(ebit_f, None if ta is None or stl is None else ta - stl),
        "debt_ratio": div(tl, ta),
        "debt_to_equity": div(tl, eq) if (eq or 0) > 0 else None,
        "equity_ratio": div(eq, ta),
        "net_debt": net_debt,
        "net_debt_to_ebit": div(net_debt, ebit_f) if (ebit_f or 0) > 0 else None,
        "interest_coverage": div(ebit, fin) if fin > 0 else None,
        "asset_turnover": div(rev_f, avg_ta),
        "inventory_days": _days(c.avg(r, "inventory"), cogs_f),
        "receivable_days": _days(c.avg(r, "receivable"), rev_f),
        "payable_days": _days(c.avg(r, "payable"), cogs_f),
        "revenue_yoy": _growth(rev, pv("revenue")) if prev else None,
        "gross_profit_yoy": _growth(gp, pv("gross_profit")) if prev else None,
        "net_income_yoy": _growth(ni, pv("net_income")) if prev else None,
        "assets_yoy": _growth(ta, pv("total_assets")) if prev else None,
        "equity_yoy": _growth(eq, pv("total_equity")) if prev else None,
    }
    inv_d, rec_d, pay_d = out["inventory_days"], out["receivable_days"], out["payable_days"]
    out["cash_cycle"] = None if None in (inv_d, rec_d, pay_d) else inv_d + rec_d - pay_d
    out["_basis"] = basis                                           # type: ignore[assignment]
    return out


def _days(avg_balance: Optional[float], flow: Optional[float]) -> Optional[float]:
    x = div(avg_balance, flow) if (flow or 0) > 0 else None
    return None if x is None else x * 365


def dupont(c: Company, r: ParsedReport) -> dict[str, Optional[float]]:
    ni_f, _ = c.flow(r, "net_income")
    pbt_f, _ = c.flow(r, "profit_before_tax")
    ebit_f, _ = c.ebit_flow(r)
    rev_f, basis = c.flow(r, "revenue")
    avg_ta, avg_eq = c.avg(r, "total_assets"), c.avg(r, "total_equity")
    out = {
        "tax_burden": div(ni_f, pbt_f),
        "interest_burden": div(pbt_f, ebit_f),
        "ebit_margin": div(ebit_f, rev_f),
        "net_margin": div(ni_f, rev_f),
        "asset_turnover": div(rev_f, avg_ta),
        "equity_multiplier": div(avg_ta, avg_eq),
        "roe": div(ni_f, avg_eq),
    }
    out["_basis"] = basis                                           # type: ignore[assignment]
    return out


def series(c: Company) -> list[tuple[ParsedReport, dict]]:
    return [(r, ratios(c, r)) for r in c.reports]


def dupont_series(c: Company) -> list[tuple[ParsedReport, dict]]:
    return [(r, dupont(c, r)) for r in c.reports]


def cagr(values: list[tuple[int, float]], min_years: int = 2) -> Optional[float]:
    """[(он, утга)] -> жилийн дундаж өсөлт (CAGR). Эхний/сүүлийн утга эерэг, хамгийн багадаа `min_years` жил."""
    pts = sorted(values)
    if len(pts) < 2:
        return None
    (y0, a), (y1, b) = pts[0], pts[-1]
    if y1 - y0 < min_years or a <= 0 or b <= 0:
        return None
    return (b / a) ** (1 / (y1 - y0)) - 1
