"""Онцгой үзүүлэлтүүд: ашгийн гүүр, ашгийн цэвэр байдал, өрийн үр өгөөж, Тобин Q, бүтээн байгуулалтын индекс,
ашиг ба ханшийн зөрүү, ханшийн корреляци ба салбарын индекс. Нэгж: мянган ₮ (хувь, харьцаа бусад)."""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

from .base import Company
from .prices import Bar
from .valuation import correlation

BRIDGE_ITEMS = ("Нийт ашиг", "Борлуулалт, маркетинг", "Ерөнхий удирдлага", "Санхүүгийн зардал", "Бусад (цэвэр)", "Татвар", "Бусад")


# ------------------------------------------------------------------ 1. Ашгийн гүүр
def _parts(c: Company, r) -> Optional[dict[str, float]]:
    v = c.v
    gp = v(r, "gross_profit")
    if gp is None:
        rev, cogs = v(r, "revenue"), v(r, "cogs")
        gp = None if rev is None or cogs is None else rev - cogs
    pbt, ni, tax = v(r, "profit_before_tax"), v(r, "net_income"), v(r, "income_tax")
    if gp is None or pbt is None or ni is None:
        return None
    sell, adm, fin = -(v(r, "selling_exp") or 0.0), -(v(r, "admin_exp") or 0.0), -(v(r, "finance_cost") or 0.0)
    other = pbt - (gp + sell + adm + fin)                            # бусад орлого/зардал, ханшийн зөрүү, данснаас хассан олз г.м.
    taxv = -(tax or 0.0)
    rest = ni - (pbt + taxv)                                         # зогсоосон үйл ажиллагаа г.м.
    return {"Нийт ашиг": gp, "Борлуулалт, маркетинг": sell, "Ерөнхий удирдлага": adm, "Санхүүгийн зардал": fin,
            "Бусад (цэвэр)": other, "Татвар": taxv, "Бусад": rest, "_ni": ni}


def profit_bridge(c: Company) -> Optional[dict]:
    """Сүүлийн тайлангийн хуримтлагдсан цэвэр ашиг өмнөх оны мөн үеээс яагаад өөрчлөгдсөн."""
    r = c.latest
    prev = c.prev_same(r) if r else None
    if r is None or prev is None:
        return None
    a, b = _parts(c, r), _parts(c, prev)
    if a is None or b is None:
        return None
    steps = {k: a[k] - b[k] for k in BRIDGE_ITEMS}
    return {"label": r.period.label, "base_label": prev.period.label, "start": b["_ni"], "end": a["_ni"], "steps": steps}


# ------------------------------------------------------------------ 2. Ашгийн цэвэр байдал
def earnings_purity(c: Company) -> Optional[dict]:
    r = c.latest
    if r is None:
        return None
    v = c.v
    pbt = v(r, "profit_before_tax")
    if pbt is None:
        return None
    one_off = sum(v(r, k) or 0.0 for k in ("other_income", "fx_gain", "ppe_disposal", "intangible_disposal",
                                           "investment_gain", "other_profit")) - (v(r, "other_exp") or 0.0)
    return {"label": r.period.label, "pbt": pbt, "non_core": one_off, "core": pbt - one_off,
            "share": one_off / pbt if pbt > 0 else None}


# ------------------------------------------------------------------ 3. Өрийн үр өгөөж
def debt_return(c: Company) -> Optional[dict]:
    r = c.latest
    if r is None:
        return None
    debt = (c.avg(r, "st_loan") or 0.0) + (c.avg(r, "lt_loan") or 0.0)
    assets = c.avg(r, "total_assets")
    ebit, _ = c.ebit_flow(r)
    fin, _ = c.flow(r, "finance_cost")
    if not assets or ebit is None:
        return None
    roa = ebit / assets
    if debt < 1:                                                    # мянган ₮: зээлгүй
        return {"roa": roa, "rate": None, "spread": None, "debt": 0.0, "debt_free": True}
    rate = (fin or 0.0) / debt
    return {"roa": roa, "rate": rate, "spread": roa - rate, "debt": debt, "debt_free": False}


# ------------------------------------------------------------------ 4. Тобин Q
def tobin_q(c: Company, market_cap: Optional[float]) -> Optional[float]:
    r = c.latest
    ta, tl = c.v(r, "total_assets"), c.v(r, "total_liabilities")
    if not market_cap or not ta or tl is None:
        return None
    return (market_cap + tl) / ta


# ------------------------------------------------------------------ 6. Бүтээн байгуулалтын индекс
def buildout(c: Company) -> Optional[dict]:
    r = c.latest
    if r is None:
        return None
    ppe, cip = c.v(r, "ppe"), c.v(r, "cip")
    if not ppe:
        return None
    base = c.prev_year_end(r) if r.months != 12 else c.find(r.period.year - 1, 12)
    cip0 = c.v(base, "cip") if base else None
    ppe0 = c.v(base, "ppe") if base else None
    return {"label": r.period.label, "cip": cip or 0.0, "ppe": ppe, "ratio": (cip or 0.0) / ppe,
            "ratio_prev": None if not ppe0 or cip0 is None else cip0 / ppe0, "cip_change": None if cip0 is None else (cip or 0.0) - cip0}


# ------------------------------------------------------------------ 7. Ашиг ба ханшийн зөрүү
def divergence(c: Company, bars: list[Bar], as_of: Optional[date], days: int = 90) -> Optional[dict]:
    r = c.latest
    if r is None or not bars or as_of is None:
        return None
    last = bars[-1]
    back = [b for b in bars if b.day <= last.day - timedelta(days=days)]
    if not back:
        return None
    price = last.close / back[-1].close - 1
    cur, base = c.ltm(r, "net_income"), None
    prev = c.prev_same(r)
    if prev is not None:
        base = c.ltm(prev, "net_income")
    if cur is None or base is None:                                 # LTM тооцогдохгүй бол хуримтлалын YoY
        cur, base = c.v(r, "net_income"), (c.v(prev, "net_income") if prev else None)
    earn = None if cur is None or base is None or base <= 0 else cur / base - 1
    verdict = None
    if earn is not None:
        gap = price - earn
        verdict = "ханш түрүүлсэн" if gap > 0.25 else "ханш хоцорсон" if gap < -0.25 else "нийцэж байна"
    return {"price": price, "earn": earn, "gap": None if earn is None else price - earn, "verdict": verdict,
            "days": days, "since": back[-1].day, "until": last.day}


# ------------------------------------------------------------------ 5. Корреляци ба салбарын индекс
def _weekly_returns(bars: list[Bar], start: date) -> dict[date, float]:
    wk: dict[date, float] = {}
    for b in sorted(bars, key=lambda b: b.day):
        wk[b.day - timedelta(days=b.day.weekday())] = b.close        # долоо хоногийн сүүлийн хаалт (Даваа гарагаар түлхүүрлэв)
    out = {}
    for mon, close in wk.items():
        prev = wk.get(mon - timedelta(days=7))
        if prev and mon >= start:
            out[mon] = close / prev - 1                              # зөвхөн дараалсан 2 долоо хоног арилжаалагдсан үед
    return out


def price_correlation(prices: dict[str, list[Bar]], tickers: list[str], as_of: Optional[date], weeks: int = 52,
                      min_overlap: int = 20) -> dict:
    """Долоо хоногийн өгөөжийн корреляци + тикер бүрийн салбарын индекстэй (8-ын тэнцүү жинтэй дундаж) харьцуулалт."""
    if as_of is None:
        return {"corr": {}, "rel": {}, "weeks": weeks}
    start = as_of - timedelta(weeks=weeks)
    rets = {t: _weekly_returns(prices[t], start) for t in tickers if prices.get(t)}
    corr: dict[tuple[str, str], Optional[float]] = {}
    ts = list(rets)
    for i, a in enumerate(ts):
        for b in ts[i:]:
            if a == b:
                corr[(a, b)] = 1.0
                continue
            ks = sorted(set(rets[a]) & set(rets[b]))
            val = correlation([rets[a][k] for k in ks], [rets[b][k] for k in ks]) if len(ks) >= min_overlap else None
            corr[(a, b)] = corr[(b, a)] = val
    weeks_all = sorted({k for r in rets.values() for k in r})
    index = {k: sum(r[k] for r in rets.values() if k in r) / sum(1 for r in rets.values() if k in r) for k in weeks_all}
    rel = {}
    for t, r in rets.items():
        ks = sorted(set(r) & set(index))
        if len(ks) < min_overlap:
            rel[t] = None
            continue
        others = {k: (sum(x[k] for u, x in rets.items() if u != t and k in x) / max(1, sum(1 for u, x in rets.items() if u != t and k in x)))
                  for k in ks}
        xs, ys = [others[k] for k in ks], [r[k] for k in ks]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        var = sum((x - mx) ** 2 for x in xs)
        beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var if var else None
        total = math.prod(1 + r[k] for k in ks) - 1
        idx = math.prod(1 + others[k] for k in ks) - 1
        rel[t] = {"return": total, "index": idx, "excess": total - idx, "beta": beta, "weeks": len(ks)}
    return {"corr": corr, "rel": rel, "weeks": weeks, "tickers": ts}


def compute_all(res) -> dict:
    out: dict = {"bridge": {}, "purity": {}, "debt": {}, "tobin": {}, "build": {}, "diverge": {}}
    for t in res.tickers:
        c, r = res.companies[t], res.r[t]
        out["bridge"][t] = profit_bridge(c)
        out["purity"][t] = earnings_purity(c)
        out["debt"][t] = debt_return(c)
        out["tobin"][t] = tobin_q(c, r["val"].market_cap if r.get("val") else None)
        out["build"][t] = buildout(c)
        out["diverge"][t] = divergence(c, res.inputs.prices.get(t) or [], res.as_of_prices)
    out["pricecorr"] = price_correlation(res.inputs.prices, res.tickers, res.as_of_prices)
    return out
