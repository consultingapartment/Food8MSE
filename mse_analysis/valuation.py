"""Үнэлгээ: P/E, P/B, EV/EBIT, Graham Number, ногдол ашгийн өгөөж, бодит хямдрал, нэгдсэн оноо, BCG матриц."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .base import Company, div
from .config import Assumptions
from .inputs import Market


def clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def linear(x: Optional[float], zero_at: float, full_at: float) -> Optional[float]:
    """x = zero_at үед 0, full_at үед 100 оноо (хоёр чиглэлд ажиллана); хязгаараас гарвал таслана."""
    if x is None or zero_at == full_at:
        return None
    return clip((x - zero_at) / (full_at - zero_at) * 100)


@dataclass
class Valuation:
    ticker: str
    basis: str                         # LTM / Жилчилсэн
    price: Optional[float]
    shares: Optional[float]
    eps: Optional[float]               # ₮
    bvps: Optional[float]              # ₮
    market_cap: Optional[float]        # мянган ₮
    pe: Optional[float]
    pb: Optional[float]
    ebit: Optional[float]              # мянган ₮ (LTM)
    debt: Optional[float]              # хүүтэй өр, мянган ₮
    cash: Optional[float]
    ev: Optional[float]
    ev_ebit: Optional[float]
    graham: Optional[float]            # Graham Number, ₮
    graham_margin: Optional[float]     # (GN − Ханш)/GN
    dps: Optional[float]
    div_yield: Optional[float]
    div_spread: Optional[float]        # ногдлын өгөөж − хадгаламжийн хүү
    real_value: Optional[float]        # Бодит үнэлгээ = GN × (1 + зөрүү)
    real_discount: Optional[float]     # 1 − Ханш/Бодит үнэлгээ
    price_for_target_yield: Optional[float]   # шаардах өгөөжид хүрэх ханш = Ногдол ÷ 16%
    graham_multiple: Optional[float]   # Graham Number ÷ тэр ханш
    yield_at_graham: Optional[float]   # Graham Number-ээр авбал ногдлын өгөөж
    verdict: str = ""
    note: str = ""


def graham_number(eps: Optional[float], bvps: Optional[float], limit: float = 22.5) -> Optional[float]:
    if eps is None or bvps is None or eps <= 0 or bvps <= 0:
        return None
    return math.sqrt(limit * eps * bvps)


def value(c: Company, m: Market, a: Assumptions) -> Optional[Valuation]:
    r = c.latest
    if r is None:
        return None
    ni, basis = c.flow(r, "net_income")
    eq = c.v(r, "total_equity")
    sh = m.shares
    price = m.price
    eps = None if ni is None or not sh else ni * 1000 / sh
    bvps = None if eq is None or not sh else eq * 1000 / sh
    cap = None if price is None or not sh else price * sh / 1000
    ebit, _ = c.ebit_flow(r)
    debt, cash = c.interest_debt(r), c.v(r, "cash")
    ev = None if cap is None or cash is None else cap + debt - cash
    gn = graham_number(eps, bvps)
    gm = None if gn is None or price is None else (gn - price) / gn
    dps = m.dps
    y = div(dps, price)
    spread = None if y is None else y - a.deposit_rate
    real = None if gn is None or spread is None else gn * (1 + spread)
    real_disc = None if real is None or price is None or real <= 0 else 1 - price / real
    p_target = None if not dps else dps / a.target_yield
    pe = div(price, eps) if (eps or 0) > 0 else None
    pb = div(price, bvps) if (bvps or 0) > 0 else None
    v = Valuation(
        c.ticker, basis, price, sh, eps, bvps, cap, pe, pb, ebit, debt, cash, ev,
        div(ev, ebit) if (ebit or 0) > 0 else None, gn, gm, dps, y, spread, real, real_disc, p_target,
        div(gn, p_target), div(dps, gn))
    v.verdict, v.note = verdict(v, a)
    return v


def verdict(v: Valuation, a: Assumptions) -> tuple[str, str]:
    """Graham ба ногдлын хоёр шалгуурын нэгдсэн дүгнэлт."""
    if v.graham_margin is None:
        return "ГРАХАМ ТООЦОХГҮЙ", "Цэвэр ашиг эсвэл эздийн өмч сөрөг тул Graham Number тооцогдохгүй."
    cheap = v.graham_margin > 0
    pay = v.div_spread is not None and v.div_spread >= -0.02
    if cheap and pay:
        return "ХЯМД БА НОГДОЛ ХАНГАЛТТАЙ", "Хөрөнгийн үнэлгээгээр хямд, ногдлын өгөөж хадгаламжид ойр."
    if cheap:
        return "ҮНЭЛГЭЭ ХЯМД, ГЭВЧ НОГДОЛ СУЛ", "Graham-аар хямд боловч ногдлын өгөөж хадгаламжаас доогуур."
    if pay:
        return "ҮНЭТЭЙ, ГЭВЧ НОГДОЛ ӨНДӨР", "Graham-аар үнэтэй ч ногдлын өгөөж өндөр."
    return "ҮНЭТЭЙ БА НОГДОЛ СУЛ", "Хоёр шалгуураар хоёулангаар сул."


def cheapness(v: Valuation, a: Assumptions) -> dict[str, Optional[float]]:
    """Хямдралын нэгдсэн оноо (0–100) ба хэсгүүд. Дутуу хэсгийг 0 гэж үзнэ (тооцох боломжгүй = хямд биш)."""
    ratio = None if v.graham is None or v.price is None else v.price / v.graham
    parts = {
        "graham": linear(ratio, a.graham_zero, a.graham_full),
        "dividend": linear(v.div_yield, a.div_zero_yield, a.deposit_rate * a.div_full_ratio),
        "pe": None if v.pe is None else linear(1 / v.pe, 0.0, a.pe_full_earnings_yield),
        "pb": None if v.pb is None else linear(v.pb, a.pb_zero, a.pb_full),
    }
    w = {"graham": a.w_graham, "dividend": a.w_dividend, "pe": a.w_pe, "pb": a.w_pb}
    total = sum(w[k] * (parts[k] or 0.0) for k in w) / sum(w.values())
    # P/E хоосон (алдагдалтай) бол ашгийн өгөөж 0 → 0 оноо, P/B-тэй адил
    parts["total"] = total
    return parts


# ------------------------------------------------------------------ BCG
def bcg_class(cap: Optional[float], growth: Optional[float], mean_cap: float, mean_growth: float) -> str:
    """Зах зээлийн үнэлгээ (хэмжээ) ба орлогын CAGR (өсөлт)-ийн дундажтай харьцуулсан 4 ангилал."""
    if cap is None or growth is None:
        return "Тодорхойгүй"
    big, fast = cap >= mean_cap, growth >= mean_growth
    return {(True, True): "БУХ (том, хурдан өсдөг)", (False, True): "ОДОД (жижиг, хурдан өсдөг)",
            (True, False): "МӨНГӨН ҮНЭЭ (том, удаан өсдөг)", (False, False): "АСУУЛТЫН ТЭМДЭГ (жижиг, удаан өсдөг)"}[(big, fast)]


def correlation(xs: list[float], ys: list[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)
