"""Бүх шинжилгээг нэг дор тооцоолж `Result` болгоно. Excel бичих нь `workbook.py`-д."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from . import concentration, forecast, risk, scoring, technical, trends, valuation
from .base import Company, load_companies
from .config import NAMES, TICKERS, Assumptions, Weights
from .fundamentals import dupont_series, ratios, series
from .inputs import Inputs, load_inputs


@dataclass
class Result:
    today: date
    assumptions: Assumptions
    weights: Weights
    companies: dict[str, Company]
    inputs: Inputs
    tickers: list[str]
    r: dict[str, dict] = field(default_factory=dict)       # тикер -> үр дүн
    corr: dict[tuple[str, str], Optional[float]] = field(default_factory=dict)
    bcg: dict[str, str] = field(default_factory=dict)
    target_year: int = 0
    as_of_prices: Optional[date] = None
    warnings: list[str] = field(default_factory=list)
    insights: dict = field(default_factory=dict)
    insights2: dict = field(default_factory=dict)


def compute(reports: Path, inputs_dir: Path, today: date, a: Assumptions | None = None, w: Weights | None = None,
            tickers: list[str] | None = None, with_technical: bool = True) -> Result:
    a, w = a or Assumptions(), w or Weights()
    inp = load_inputs(inputs_dir)
    comps = load_companies(reports, tickers or list(TICKERS))
    tks = [t for t in (tickers or TICKERS) if t in comps]
    res = Result(today, a, w, comps, inp, tks)
    for t in set(tickers or TICKERS) - set(tks):
        res.warnings.append(f"{t}: тайлан олдсонгүй — шинжилгээнээс хасав")
    last_days = [inp.prices[t][-1].day for t in tks if inp.prices.get(t)]
    res.as_of_prices = max(last_days) if last_days else None
    res.target_year = max((c.latest.period.year for c in comps.values()), default=today.year)

    for t in tks:
        c = comps[t]
        m = inp.market.get(t)
        own = inp.latest_ownership(t)
        r: dict = {"company": c, "name": NAMES.get(t, t)}
        r["ratios"] = ratios(c, c.latest)
        r["series"] = series(c)
        r["dupont_series"] = dupont_series(c)
        r["val"] = valuation.value(c, m, a) if m else None
        r["cheap"] = valuation.cheapness(r["val"], a) if r["val"] else None
        r["altman"] = risk.altman(c, r["val"].market_cap if r["val"] else None)
        r["piotroski"] = risk.piotroski(c)
        r["sens"] = risk.interest_sensitivity(c)
        r["break_even"] = risk.break_even(c)
        r["no_interest"] = (c.flow(c.latest, "finance_cost")[0] or 0) == 0
        r["annual"] = trends.annual_table(c)
        r["revenue_cagr"] = trends.revenue_cagr(c)
        r["index"] = trends.index_series(c)
        r["margin_vol"] = trends.margin_volatility(c)
        r["breakdown"] = trends.breakdown(c)
        r["forecast"] = forecast.net_income(c, res.target_year, a.forecast_min_years)
        r["own"] = own
        r["conc"] = concentration.assess(own) if own else None
        r["free_float"] = own.small_pct if own else None
        bars = inp.prices.get(t) or []
        r["liquidity"] = (risk.trading_liquidity(bars, res.as_of_prices, today, a.liquidity_window_days)
                          if bars and res.as_of_prices else None)
        r["tech"] = {}
        if with_technical and bars:
            for tf, _ in technical.TIMEFRAMES:
                tr = technical.analyze(t, bars, tf)
                if tr:
                    r["tech"][tf] = tr
        res.r[t] = r

    for t in tks:
        res.r[t]["score"] = scoring.rate(res.r[t], a, w)

    # корреляци: жилийн орлогын өсөлт
    growth: dict[str, dict[int, float]] = {}
    for t in tks:
        ann = res.r[t]["annual"]
        growth[t] = {y: ann[y]["revenue"] / ann[y - 1]["revenue"] - 1 for y in ann
                     if y - 1 in ann and ann[y]["revenue"] and ann[y - 1]["revenue"]}
    for i, x in enumerate(tks):
        for y in tks[i:]:
            years = sorted(set(growth[x]) & set(growth[y]))
            res.corr[(x, y)] = res.corr[(y, x)] = (
                1.0 if x == y else valuation.correlation([growth[x][k] for k in years], [growth[y][k] for k in years])
                if len(years) >= 3 else None)

    # BCG
    pts = [(t, res.r[t]["val"].market_cap, res.r[t]["revenue_cagr"]) for t in tks if res.r[t]["val"]]
    ok = [(t, cap, g) for t, cap, g in pts if cap is not None and g is not None]
    if ok:
        mc = sum(c for _, c, _ in ok) / len(ok)
        mg = sum(g for _, _, g in ok) / len(ok)
        res.bcg = {t: valuation.bcg_class(c, g, mc, mg) for t, c, g in ok}
        res.bcg["_mean_cap"], res.bcg["_mean_growth"] = mc, mg      # type: ignore[assignment]

    from . import insights
    res.insights = insights.compute_all(res)
    from . import insights2
    res.insights2 = insights2.compute_all(res)

    # өгөгдлийн сануулга
    for t in tks:
        c, r = comps[t], res.r[t]
        if r["ratios"].get("_basis") != "LTM":
            res.warnings.append(f"{t}: LTM тооцох өгөгдөл дутуу — жилчилсэн (YTD × 12 ÷ сар) ашиглав")
        if t not in inp.market:
            res.warnings.append(f"{t}: inputs/market.csv-д ханш/ногдол алга — үнэлгээ тооцоогүй")
        if t not in inp.prices:
            res.warnings.append(f"{t}: арилжааны түүх алга — техник шинжилгээ хийгдсэнгүй")
        elif r["liquidity"] and r["liquidity"]["stale_days"] > 30:
            res.warnings.append(f"{t}: ханшийн сүүлийн өгөгдөл {r['liquidity']['last_day']} ({r['liquidity']['stale_days']} хоногийн өмнө)")
    return res
