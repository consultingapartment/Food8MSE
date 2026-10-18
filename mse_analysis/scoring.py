"""100 онооны үнэлгээ ба зөвлөмж. Бүх босгыг энд л тодорхойлно."""
from __future__ import annotations

from typing import Optional

from .config import LABELS, Assumptions, Weights
from .valuation import linear


def _avg(xs: list[Optional[float]]) -> Optional[float]:
    v = [x for x in xs if x is not None]
    return sum(v) / len(v) if v else None


def components(r: dict, a: Assumptions) -> dict[str, Optional[float]]:
    """`r` = engine-ийн нэг компанийн үр дүн. Хэсэг бүр 0–100 (тооцох боломжгүй бол None)."""
    rt = r["ratios"] or {}
    cov = rt.get("interest_coverage")
    no_interest = r["no_interest"]
    solv = [
        linear(rt.get("current_ratio"), 0.8, 2.0),
        linear(rt.get("debt_to_equity"), 1.5, 0.3) if rt.get("debt_to_equity") is not None else 0.0,
        100.0 if no_interest else linear(cov, 1.0, 8.0),
    ]
    alt, pio = r["altman"], r["piotroski"]
    qual = [linear(alt["z"], 1.81, 2.99) if alt else None,
            None if not pio else pio["score"] / pio["of"] * 100]
    chp = r["cheap"] or {}
    float_pct = r["free_float"]
    liq = r["liquidity"]
    market = [linear(float_pct, 0.05, 0.25), None if not liq else linear(liq["trading_days"], 0, 45)]
    return {
        "profitability": _avg([linear(rt.get("roe"), 0, 0.20), linear(rt.get("net_margin"), 0, 0.15),
                               linear(rt.get("roa"), 0, 0.10)]),
        "growth": _avg([linear(rt.get("revenue_yoy"), -0.10, 0.20), linear(rt.get("net_income_yoy"), -0.30, 0.30),
                        linear(r["revenue_cagr"], 0.0, 0.20)]),
        "solvency": _avg(solv),
        "quality": _avg(qual),
        "valuation": chp.get("total"),
        "dividend": chp.get("dividend"),
        "market": _avg(market),
    }


def rate(r: dict, a: Assumptions, w: Weights) -> dict:
    comp = components(r, a)
    used = {k: getattr(w, k) for k in w._order if comp.get(k) is not None}
    wsum = sum(used.values())
    total = sum(comp[k] * wt for k, wt in used.items()) / wsum if wsum else None
    rating = None if total is None else "ХУДАЛДАН АВАХ" if total >= a.rating_buy else "ХАДГАЛАХ" if total >= a.rating_hold else "ЗАРАХ"
    return {"components": comp, "weights": {k: getattr(w, k) for k in w._order}, "total": total, "rating": rating,
            "missing": [LABELS[k] for k in w._order if comp.get(k) is None]}
