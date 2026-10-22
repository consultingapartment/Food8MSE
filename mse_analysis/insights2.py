"""Нэмэлт онцгой үзүүлэлтүүд (17): тайлангийн найдвартай байдал, татан буулгах өртөг, ногдол ашгийн нөөц,
улирлын нөлөөтэй жилийн таамаг, ханшийн уналт, үйл ажиллагааны хөшүүрэг, хуримтлуулсан ашгийн үр дүн,
зах зээлийн суулгасан өсөлт, өөрийн хөрөнгөөр хангагдах өсөлт, эргэлтийн хөрөнгийн ачаалал, тайлангийн дараах ханшийн хариу,
зардлын наалдамхай байдал, татварын зөрүү, богино хугацаат өрийн хана, хувьцааны эрсдэлийн шагнал, цэвэр бэлэн мөнгө, өсөлтийн цуваа.
Нэгж: мянган ₮ (хувь, харьцаа, ширхэг бусад)."""
from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Optional

from . import periods as P
from .base import Company, div
from .config import Assumptions
from .prices import Bar

#: Татан буулгах үеийн хөрөнгийн бүлэг бүрийн сэргээгдэх хувь (таамаглал; энд л өөрчилнө)
HAIRCUTS = {"cash": 1.0, "receivable": 0.8, "other_receivable": 0.5, "tax_receivable": 0.5, "inventory": 0.6, "biological": 0.7,
            "held_for_sale": 0.8, "investment_property": 0.6, "lt_investment": 0.5, "ppe": 0.5, "cip": 0.5}
HAIRCUT_NAMES = {"cash": "Бэлэн мөнгө", "receivable": "Авлага", "other_receivable": "Бусад авлага", "tax_receivable": "Татварын авлага",
                 "inventory": "Бараа материал", "biological": "Биологийн хөрөнгө", "held_for_sale": "Борлуулах хөрөнгө",
                 "investment_property": "Хөрөнгө оруулалтын үл хөдлөх", "lt_investment": "Урт хугацаат хөрөнгө оруулалт",
                 "ppe": "Үндсэн хөрөнгө", "cip": "Дуусаагүй барилга"}


def _g(x: Optional[float]) -> float:
    return 0.0 if x is None else x


def _close_on_or_before(bars: list[Bar], day: date) -> Optional[float]:
    best = None
    for b in bars:
        if b.day <= day:
            best = b.close
        else:
            break
    return best


# ------------------------------------------------------------------ 1. Тайлангийн найдвартай байдлын индекс (Beneish-ийн хялбаршуулсан)
def beneish(c: Company) -> Optional[dict]:
    r = c.latest
    p = c.prev_same(r) if r else None
    if r is None or p is None:
        return None
    v = c.v
    try:
        rev, rev0 = v(r, "revenue"), v(p, "revenue")
        gp, gp0 = v(r, "gross_profit"), v(p, "gross_profit")
        rec, rec0 = v(r, "receivable"), v(p, "receivable")
        ta, ta0 = v(r, "total_assets"), v(p, "total_assets")
        ca, ca0 = v(r, "total_ca"), v(p, "total_ca")
        ppe, ppe0 = v(r, "ppe"), v(p, "ppe")
        tl, tl0 = v(r, "total_liabilities"), v(p, "total_liabilities")
        cl, cl0 = v(r, "total_stl"), v(p, "total_stl")
        cash, cash0 = v(r, "cash"), v(p, "cash")
        stl, stl0 = v(r, "st_loan"), v(p, "st_loan")
        tx, tx0 = v(r, "tax_payable"), v(p, "tax_payable")
        sga, sga0 = _g(v(r, "selling_exp")) + _g(v(r, "admin_exp")), _g(v(p, "selling_exp")) + _g(v(p, "admin_exp"))
    except Exception:
        return None
    need = (rev, rev0, gp, gp0, ta, ta0, ca, ca0, tl, tl0, cl, cl0)
    if any(x is None for x in need) or not all((rev, rev0, ta, ta0)):
        return None
    ppe, ppe0, rec, rec0 = _g(ppe), _g(ppe0), _g(rec), _g(rec0)
    gm, gm0 = gp / rev, gp0 / rev0
    comp = {
        "DSRI": div(rec / rev, rec0 / rev0) if rec0 else 1.0,
        "GMI": div(gm0, gm) if gm > 0 else None,
        "AQI": div(1 - (ca + ppe) / ta, 1 - (ca0 + ppe0) / ta0),
        "SGI": rev / rev0,
        "SGAI": div(sga / rev, sga0 / rev0) if sga0 else 1.0,
        "LVGI": div(tl / ta, tl0 / ta0),
    }
    if any(x is None for x in comp.values()):
        return None
    d_ca, d_cash = ca - ca0, _g(cash) - _g(cash0)
    d_cl, d_std, d_tax = cl - cl0, _g(stl) - _g(stl0), _g(tx) - _g(tx0)
    tata = ((d_ca - d_cash) - (d_cl - d_std - d_tax)) / ta               # балансын аргаар тооцсон хуримтлал (мөнгөн урсгалын тайланг ашиглаагүй)
    m = (-4.84 + 0.920 * comp["DSRI"] + 0.528 * comp["GMI"] + 0.404 * comp["AQI"] + 0.892 * comp["SGI"] + 0.115 * 1.0
         - 0.172 * comp["SGAI"] + 4.679 * tata - 0.327 * comp["LVGI"])
    verdict = "анхаарах" if m > -1.78 else "хэвийн"
    flags = [k for k, lim in (("DSRI", 1.3), ("GMI", 1.2), ("AQI", 1.25), ("SGI", 1.5), ("LVGI", 1.2)) if comp[k] > lim]
    return {"label": r.period.label, "base_label": p.period.label, "m": m, "verdict": verdict, "tata": tata, "comp": comp, "flags": flags}


# ------------------------------------------------------------------ 2. Хувьцаанд ногдох татан буулгах өртөг
def liquidation(c: Company, price: Optional[float], shares: Optional[float]) -> Optional[dict]:
    r = c.latest
    tl = c.v(r, "total_liabilities") if r else None
    if r is None or tl is None:
        return None
    parts = {k: _g(c.v(r, k)) * h for k, h in HAIRCUTS.items()}
    net = sum(parts.values()) - tl
    book = c.v(r, "total_equity")
    per = None if not shares else net * 1000 / shares
    return {"label": r.period.label, "recoverable": sum(parts.values()), "liabilities": tl, "net": net, "per_share": per, "price": price,
            "ratio": None if not per or per <= 0 or not price else price / per, "book": book, "parts": parts}


# ------------------------------------------------------------------ 3. Ногдол ашгийн нөөцийн жил
def dividend_reserve(c: Company, dps: Optional[float], shares: Optional[float]) -> Optional[dict]:
    r = c.latest
    if r is None or not dps or not shares:
        return None
    total = dps * shares / 1000                                           # мянган ₮
    ret = c.v(r, "retained")
    ni, _ = c.flow(r, "net_income")
    years = None if ret is None or ret <= 0 else ret / total
    return {"label": r.period.label, "dividend": total, "retained": ret, "years": years,
            "cover": None if ni is None else ni / total, "payout": None if not ni or ni <= 0 else total / ni}


# ------------------------------------------------------------------ 4. Улирлын нөлөөг тооцсон жилийн таамаг
def seasonal_forecast(c: Company) -> Optional[dict]:
    r = c.latest
    if r is None:
        return None
    key = "net_income"
    cur = c.v(r, key)
    if cur is None:
        return None
    if r.months == 12:
        return {"label": r.period.label, "ytd": cur, "done": True, "forecast": cur, "low": cur, "high": cur, "share": 1.0, "n": 0,
                "naive": cur, "prev_fy": c.v(c.find(r.period.year - 1, 12), key) if c.find(r.period.year - 1, 12) else None}
    shares = []
    for y in range(r.period.year - 8, r.period.year):
        a, f = c.find(y, r.months), c.find(y, 12)
        if a and f:
            x, z = c.v(a, key), c.v(f, key)
            if x is not None and z is not None and z > 0 and x > 0:
                shares.append(x / z)
    if len(shares) < 2 or cur <= 0:
        return {"label": r.period.label, "ytd": cur, "done": False, "forecast": None, "low": None, "high": None, "share": None,
                "n": len(shares), "naive": cur * 12 / r.months, "prev_fy": None,
                "note": "алдагдалтай" if cur <= 0 else "түүхэн улирлын нөлөөг тооцох өгөгдөл (≥2 жил) дутуу"}
    mean = sum(shares) / len(shares)
    prev = c.find(r.period.year - 1, 12)
    return {"label": r.period.label, "ytd": cur, "done": False, "forecast": cur / mean, "low": cur / max(shares), "high": cur / min(shares),
            "share": mean, "n": len(shares), "naive": cur * 12 / r.months, "prev_fy": c.v(prev, key) if prev else None}


# ------------------------------------------------------------------ 5. Оргилоос буурсан хэмжээ ("усан доор")
def drawdown(bars: list[Bar], days: int = 365) -> Optional[dict]:
    if len(bars) < 20:
        return None
    last = bars[-1]
    win = [b for b in bars if b.day > last.day - timedelta(days=days)]
    peak = max(win, key=lambda b: b.close)
    ath = max(bars, key=lambda b: b.close)
    mdd = 0.0
    hi = 0.0
    for b in win:
        hi = max(hi, b.close)
        mdd = min(mdd, b.close / hi - 1)
    dd = last.close / peak.close - 1
    return {"peak": peak.close, "peak_day": peak.day, "last": last.close, "last_day": last.day, "dd": dd,
            "under_days": (last.day - peak.day).days if dd < 0 else 0, "max_dd": mdd,
            "need": peak.close / last.close - 1 if last.close else None, "ath": ath.close, "ath_day": ath.day,
            "dd_ath": last.close / ath.close - 1}


# ------------------------------------------------------------------ 6. Үйл ажиллагааны хөшүүрэг
def _ebit_ltm(c: Company, r) -> Optional[float]:
    pbt, fin = c.ltm(r, "profit_before_tax"), c.ltm(r, "finance_cost")
    return None if pbt is None else pbt + (fin or 0.0)


def op_leverage(c: Company) -> Optional[dict]:
    r = c.latest
    if r is None:
        return None
    out: dict = {"ltm": None, "hist": None, "pairs": []}
    p = c.prev_same(r)
    if p is not None:
        e1, e0 = _ebit_ltm(c, r), _ebit_ltm(c, p)
        r1, r0 = c.ltm(r, "revenue"), c.ltm(p, "revenue")
        if None not in (e1, e0, r1, r0) and e0 > 0 and r0 > 0 and abs(r1 / r0 - 1) >= 0.02:
            out["ltm"] = {"dol": (e1 / e0 - 1) / (r1 / r0 - 1), "d_ebit": e1 / e0 - 1, "d_rev": r1 / r0 - 1}
    fys = sorted(c.annual(), key=lambda x: x.period.year)
    for a, b in zip(fys, fys[1:]):
        if b.period.year != a.period.year + 1:
            continue
        e0, e1 = c.ebit(a), c.ebit(b)
        r0, r1 = c.v(a, "revenue"), c.v(b, "revenue")
        if None in (e0, e1, r0, r1) or e0 <= 0 or r0 <= 0 or abs(r1 / r0 - 1) < 0.02:
            continue
        out["pairs"].append((b.period.year, (e1 / e0 - 1) / (r1 / r0 - 1)))
    out["pairs"] = out["pairs"][-4:]
    if out["pairs"]:
        out["hist"] = statistics.median(x for _, x in out["pairs"])
    return out if out["ltm"] or out["hist"] is not None else None


# ------------------------------------------------------------------ 7. Хуримтлуулсан ашгийн үр дүн (Баффетийн тест)
def retention_test(c: Company, bars: list[Bar], shares: Optional[float], target_days: int = 1095) -> Optional[dict]:
    r = c.latest
    if r is None or not bars or not shares:
        return None
    cands = [a for a in c.annual() if (r.end_date - a.end_date).days >= 700]
    if not cands:
        return None
    start = min(cands, key=lambda a: abs((r.end_date - a.end_date).days - target_days))
    p0 = _close_on_or_before(bars, start.end_date)
    p1 = bars[-1].close
    re1, re0 = c.v(r, "retained"), c.v(start, "retained")
    if p0 is None or re1 is None or re0 is None:
        return None
    d_mv = (p1 - p0) * shares / 1000
    d_re = re1 - re0
    return {"start": start.period.label, "end": r.period.label, "years": (r.end_date - start.end_date).days / 365.25,
            "d_mv": d_mv, "d_re": d_re, "ratio": d_mv / d_re if d_re > 0 else None, "p0": p0, "p1": p1}


# ------------------------------------------------------------------ 8. Зах зээлийн суулгасан өсөлт
def implied_growth(c: Company, market_cap: Optional[float], req: float) -> Optional[dict]:
    r = c.latest
    if r is None or not market_cap:
        return None
    e0, _ = c.flow(r, "net_income")
    if e0 is None:
        return None
    if e0 <= 0:
        return {"implied": None, "actual": None, "note": "алдагдалтай"}
    g = (market_cap * req - e0) / (market_cap + e0)                       # P = E0(1+g)/(r−g)
    fys = [a for a in sorted(c.annual(), key=lambda a: a.period.year) if (c.v(a, "net_income") or 0) > 0]
    actual, span = None, None
    if len(fys) >= 2:
        b = fys[-1]
        a = next((x for x in fys if x.period.year == b.period.year - 3), None) or next(
            (x for x in fys if x.period.year == b.period.year - 2), None) or next((x for x in fys if x.period.year == b.period.year - 1), None)
        if a is not None:
            span = b.period.year - a.period.year
            actual = (c.v(b, "net_income") / c.v(a, "net_income")) ** (1 / span) - 1
    return {"implied": g, "actual": actual, "span": span, "gap": None if actual is None else g - actual, "required": req}


# ------------------------------------------------------------------ 9. Өөрийн хөрөнгөөр хангагдах өсөлт
def sustainable_growth(c: Company, dps: Optional[float], shares: Optional[float]) -> Optional[dict]:
    r = c.latest
    if r is None:
        return None
    ni, _ = c.flow(r, "net_income")
    eq = c.avg(r, "total_equity")
    if ni is None or not eq or eq <= 0:
        return None
    roe = ni / eq
    total_div = (dps or 0.0) * (shares or 0.0) / 1000
    payout = min(max(total_div / ni, 0.0), 1.0) if ni > 0 else None
    sus = None if payout is None else roe * (1 - payout)
    p = c.prev_same(r)
    r1 = c.ltm(r, "revenue")
    r0 = c.ltm(p, "revenue") if p else None
    act = None if not r1 or not r0 or r0 <= 0 else r1 / r0 - 1
    return {"roe": roe, "payout": payout, "sustainable": sus, "actual": act, "gap": None if sus is None or act is None else act - sus}


# ------------------------------------------------------------------ 10. Эргэлтийн хөрөнгийн ачаалал
def _nwc(c: Company, r) -> float:
    return _g(c.v(r, "inventory")) + _g(c.v(r, "receivable")) - _g(c.v(r, "payable"))


def working_capital(c: Company) -> Optional[dict]:
    r = c.latest
    p = c.prev_same(r) if r else None
    if r is None or p is None:
        return None
    rev1, rev0 = c.ltm(r, "revenue"), c.ltm(p, "revenue")
    if not rev1 or not rev0 or rev0 <= 0:
        return None
    n1, n0 = _nwc(c, r), _nwc(c, p)
    return {"label": r.period.label, "nwc": n1, "nwc_prev": n0, "intensity": n1 / rev1, "intensity_prev": n0 / rev0,
            "nwc_growth": None if n0 <= 0 else n1 / n0 - 1, "rev_growth": rev1 / rev0 - 1,
            "per_extra": (n1 - n0) / (rev1 - rev0) if rev1 - rev0 > 0 else None}


# ------------------------------------------------------------------ 11. Тайлангийн дараах ханшийн хариу
def _est_event_day(r) -> date:
    y = r.period.year
    return {12: date(y + 1, 2, 10), 3: date(y, 4, 30), 6: date(y, 7, 20), 9: date(y, 10, 30)}.get(r.months, r.end_date + timedelta(days=45))


def earnings_reaction(c: Company, prices: dict[str, list[Bar]], window: int = 14, last_n: int = 6) -> Optional[dict]:
    bars = prices.get(c.ticker) or []
    if not bars:
        return None
    others = {t: b for t, b in prices.items() if t != c.ticker and b}
    events = []
    for r in c.reports[-last_n * 2:]:
        if not r.period.year:
            continue
        filed = None
        try:
            filed = date.fromisoformat(r.filed) if r.filed else None
        except ValueError:
            filed = None
        day, est = (filed, False) if filed else (_est_event_day(r), True)
        start = day - timedelta(days=1 if filed else window)
        end = day + timedelta(days=window)
        if end > bars[-1].day or start < bars[0].day:
            continue
        p0, p1 = _close_on_or_before(bars, start), _close_on_or_before(bars, end)
        if not p0 or not p1:
            continue
        ret = p1 / p0 - 1
        rs = []
        for b in others.values():
            a0, a1 = _close_on_or_before(b, start), _close_on_or_before(b, end)
            if a0 and a1:
                rs.append(a1 / a0 - 1)
        excess = ret - sum(rs) / len(rs) if rs else None
        prev = c.prev_same(r)
        ni, ni0 = c.v(r, "net_income"), c.v(prev, "net_income") if prev else None
        sur, _ = P.change(ni, ni0)
        events.append({"label": r.period.label, "day": day, "estimated": est, "surprise": sur, "ret": ret, "excess": excess})
    events = events[-last_n:]
    if not events:
        return None
    pairs = [e for e in events if e["surprise"] is not None and e["excess"] is not None]
    hit = None if not pairs else sum(1 for e in pairs if (e["surprise"] > 0) == (e["excess"] > 0)) / len(pairs)
    ex = [e["excess"] for e in events if e["excess"] is not None]
    return {"events": events, "hit": hit, "n": len(pairs), "avg_excess": sum(ex) / len(ex) if ex else None, "window": window,
            "last": events[-1]}


# ------------------------------------------------------------------ 12/17. Үеийн цуваа (улирал → хагас жил → жил)
def _series(c: Company) -> tuple[str, list[tuple[P.Per, dict]]]:
    best = ("year", [])
    for kind in ("quarter", "half", "year"):
        rows = []
        for p in sorted(P.periods_with_data({"x": c}, kind, "revenue"), key=lambda q: (q.year, q.n)):
            d = {k: P.value(c, p, k) for k in ("revenue", "net_income", "cogs", "selling_exp", "admin_exp")}
            dy = {k: P.value(c, p.yoy(), k) for k in d}
            if d["revenue"] is not None:
                rows.append((p, {"cur": d, "py": dy}))
        if len(rows) >= 4:
            return kind, rows[-12:]
        if len(rows) > len(best[1]):
            best = (kind, rows[-12:])
    return best


def _cost(d: dict) -> Optional[float]:
    if d["cogs"] is None:
        return None
    return abs(d["cogs"]) + abs(d["selling_exp"] or 0.0) + abs(d["admin_exp"] or 0.0)


def cost_stickiness(c: Company) -> Optional[dict]:
    """Борлуулалт өсөхөд зардал хэдэн хувиар өсөж, буурахад хэдэн хувиар буурдаг. Үеийг улирал → хагас жил → жилээр сонгоно."""
    best = None
    for kind in ("quarter", "half", "year"):
        up, dn = [], []
        for p in sorted(P.periods_with_data({"x": c}, kind, "revenue"), key=lambda q: (q.year, q.n))[-12:]:
            cur = {k: P.value(c, p, k) for k in ("revenue", "cogs", "selling_exp", "admin_exp")}
            py = {k: P.value(c, p.yoy(), k) for k in cur}
            c1, c0 = _cost(cur), _cost(py)
            r1, r0 = cur["revenue"], py["revenue"]
            if None in (c1, c0, r1, r0) or r0 <= 0 or c0 <= 0:
                continue
            dr, dc = r1 / r0 - 1, c1 / c0 - 1
            if abs(dr) < 0.005:
                continue
            (up if dr > 0 else dn).append((abs(dr), abs(dc) * (1 if dc * dr > 0 else -1)))
        n = len(up) + len(dn)
        if best is None or (bool(up and dn), n) > (bool(best["up"] and best["dn"]), best["n"]):
            best = {"kind": kind, "up": up, "dn": dn, "n": n}
        if up and dn and n >= 4:
            break
    if not best or best["n"] == 0:
        return None
    f = lambda xs: None if not xs else sum(x for _, x in xs) / sum(a for a, _ in xs)     # noqa: E731
    bu, bd = f(best["up"]), f(best["dn"])
    return {"kind": best["kind"], "n_up": len(best["up"]), "n_dn": len(best["dn"]), "beta_up": bu, "beta_down": bd,
            "sticky": None if bu is None or bd is None else bu - bd}


# ------------------------------------------------------------------ 13. Татварын зөрүү
def tax_gap(c: Company, a: Assumptions) -> Optional[dict]:
    r = c.latest
    if r is None:
        return None
    pbt, _ = c.flow(r, "profit_before_tax")
    tax, _ = c.flow(r, "income_tax")
    if pbt is None or pbt <= 0 or tax is None:
        return None
    expected = a.tax_low * min(pbt, a.tax_threshold) + a.tax_high * max(pbt - a.tax_threshold, 0.0)
    tax = abs(tax)
    return {"pbt": pbt, "tax": tax, "effective": tax / pbt, "statutory": expected / pbt, "gap": tax / pbt - expected / pbt,
            "diff": tax - expected}


# ------------------------------------------------------------------ 14. Богино хугацаат өрийн хана
def debt_wall(c: Company) -> Optional[dict]:
    r = c.latest
    if r is None:
        return None
    st, lt = _g(c.v(r, "st_loan")), _g(c.v(r, "lt_loan"))
    cash, rec, inv = _g(c.v(r, "cash")), _g(c.v(r, "receivable")), _g(c.v(r, "inventory"))
    if st + lt < 1:
        return {"debt_free": True, "st": 0.0, "lt": 0.0}
    return {"debt_free": False, "st": st, "lt": lt, "share": st / (st + lt), "cover": None if st < 1 else (cash + rec) / st,
            "cover_inv": None if st < 1 else (cash + rec + inv) / st, "cash": cash}


# ------------------------------------------------------------------ 15. Хувьцааны эрсдэлийн шагнал
def equity_premium(c: Company, market_cap: Optional[float], div_yield: Optional[float], deposit: float) -> Optional[dict]:
    r = c.latest
    if r is None or not market_cap:
        return None
    ni, _ = c.flow(r, "net_income")
    ey = None if ni is None else ni / market_cap
    return {"earn_yield": ey, "div_yield": div_yield, "deposit": deposit,
            "earn_prem": None if ey is None else ey - deposit, "div_prem": None if div_yield is None else div_yield - deposit}


# ------------------------------------------------------------------ 16. Цэвэр бэлэн мөнгө
def net_cash(c: Company, market_cap: Optional[float], shares: Optional[float], price: Optional[float]) -> Optional[dict]:
    r = c.latest
    if r is None or not market_cap:
        return None
    cash = c.v(r, "cash")
    if cash is None:
        return None
    net = cash - c.interest_debt(r)
    return {"cash": cash, "debt": c.interest_debt(r), "net": net, "ratio": net / market_cap,
            "per_share": None if not shares else net * 1000 / shares, "price": price}


# ------------------------------------------------------------------ 17. Өсөлтийн цуваа ба ашгийн тогтвортой байдал
def growth_streak(c: Company) -> Optional[dict]:
    kind, rows = _series(c)
    if len(rows) < 2:
        return None
    growth = []
    for p, d in rows:
        ni, ni0 = d["cur"]["net_income"], d["py"]["net_income"]
        if ni is not None and ni0 is not None:
            growth.append((p, ni > ni0))
    streak = 0
    for _, up in reversed(growth):
        if not up:
            break
        streak += 1
    margins = [d["cur"]["net_income"] / d["cur"]["revenue"] for _, d in rows[-8:]
               if d["cur"]["net_income"] is not None and d["cur"]["revenue"]]
    sd = statistics.pstdev(margins) if len(margins) >= 3 else None
    return {"kind": kind, "streak": streak, "n": len(growth), "up_share": None if not growth else sum(1 for _, u in growth if u) / len(growth),
            "margin_sd": sd, "margin_mean": sum(margins) / len(margins) if margins else None}


# ------------------------------------------------------------------ нэгтгэл
def compute_all(res) -> dict:
    a: Assumptions = res.assumptions
    out: dict = {k: {} for k in ("beneish", "liq", "divres", "season", "drawdown", "dol", "retention", "implied", "sustain", "wcap",
                                  "reaction", "sticky", "taxgap", "wall", "erp", "netcash", "streak")}
    for t in res.tickers:
        c, r = res.companies[t], res.r[t]
        v = r.get("val")
        m = res.inputs.market.get(t)
        bars = res.inputs.prices.get(t) or []
        cap, shares, price = (v.market_cap, v.shares, v.price) if v else (None, None, None)
        dps = m.dps if m else None
        out["beneish"][t] = beneish(c)
        out["liq"][t] = liquidation(c, price, shares)
        out["divres"][t] = dividend_reserve(c, dps, shares)
        out["season"][t] = seasonal_forecast(c)
        out["drawdown"][t] = drawdown(bars)
        out["dol"][t] = op_leverage(c)
        out["retention"][t] = retention_test(c, bars, shares)
        out["implied"][t] = implied_growth(c, cap, a.required_return)
        out["sustain"][t] = sustainable_growth(c, dps, shares)
        out["wcap"][t] = working_capital(c)
        out["reaction"][t] = earnings_reaction(c, res.inputs.prices)
        out["sticky"][t] = cost_stickiness(c)
        out["taxgap"][t] = tax_gap(c, a)
        out["wall"][t] = debt_wall(c)
        out["erp"][t] = equity_premium(c, cap, v.div_yield if v else None, a.deposit_rate)
        out["netcash"][t] = net_cash(c, cap, shares, price)
        out["streak"][t] = growth_streak(c)
    return out
