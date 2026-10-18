"""Эрсдэл, чанар: Altman Z, Piotroski F, хүүгийн мэдрэмж, эвцэлдэх орлого, арилжааны хөрвөх чадвар."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from . import config
from .base import Company
from .fundamentals import ratios
from .prices import Bar

ZONES = ((2.99, "АЮУЛГҮЙ (Z>2.99)"), (1.81, "СЭРЭМЖЛЭХ БҮС (1.81–2.99)"), (float("-inf"), "ЭРСДЭЛТЭЙ (Z<1.81)"))


def altman(c: Company, market_cap: Optional[float]) -> Optional[dict]:
    """Z = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 1.0·X5. X4 = Зах зээлийн үнэлгээ ÷ Нийт өр. Нэгж: мянган ₮."""
    r = c.latest
    if r is None:
        return None
    ta, tl = c.v(r, "total_assets"), c.v(r, "total_liabilities")
    ca, stl = c.v(r, "total_ca"), c.v(r, "total_stl")
    eq = c.v(r, config.ALTMAN_X2 == "retained" and "retained" or "total_equity")
    ebit, _ = c.ebit_flow(r)
    rev, _ = c.flow(r, "revenue")
    if not ta or None in (ca, stl, eq, ebit, rev) or not tl or market_cap is None:
        return None
    x = [(ca - stl) / ta, eq / ta, ebit / ta, market_cap / tl, rev / ta]
    z = 1.2 * x[0] + 1.4 * x[1] + 3.3 * x[2] + 0.6 * x[3] + 1.0 * x[4]
    return {"x": x, "z": z, "zone": next(name for lim, name in ZONES if z > lim)}


def piotroski(c: Company) -> Optional[dict]:
    """Piotroski F: мөнгөн урсгалын тайлан загварт байхгүй тул CFO-той 2 шалгуурыг оруулалгүй 7 шалгуураар.
    Өмнөх оны ижил үетэй харьцуулна."""
    r = c.latest
    prev = c.prev_same(r) if r else None
    if r is None or prev is None:
        return None
    cur, old = ratios(c, r), ratios(c, prev)

    def gt(k, sign=1):
        a, b = cur.get(k), old.get(k)
        return None if a is None or b is None else (a - b) * sign > 0

    tests = [
        ("ROA > 0", None if cur["roa"] is None else cur["roa"] > 0),
        ("ROA өссөн", gt("roa")),
        ("Өр/Хөрөнгө буурсан", gt("debt_ratio", -1)),
        ("Эргэлтийн хөрөнгийн харьцаа өссөн", gt("current_ratio")),
        ("Хувьцаа нэмэгдээгүй", _no_dilution(c, r, prev)),
        ("Нийт ашгийн маржин өссөн", gt("gross_margin")),
        ("Хөрөнгийн эргэлт өссөн", gt("asset_turnover")),
    ]
    got = [t for t in tests if t[1] is not None]
    if len(got) < 4:
        return None
    score = sum(1 for _, ok in got if ok)
    return {"tests": tests, "score": score, "of": len(got),
            "zone": "ХҮЧТЭЙ" if score >= 0.8 * len(got) else "СУЛ" if score <= 0.4 * len(got) else "ДУНД"}


def _no_dilution(c: Company, r, prev) -> Optional[bool]:
    a, b = c.v(r, "share_capital"), c.v(prev, "share_capital")
    return None if a is None or b is None else a <= b * 1.001


def interest_sensitivity(c: Company) -> Optional[dict]:
    """Санхүүгийн зардал ×k болбол цэвэр ашиг (татварын хамгаалалтгүй, консерватив)."""
    r = c.latest
    ni, _ = c.flow(r, "net_income")
    fin, _ = c.flow(r, "finance_cost")
    if r is None or ni is None:
        return None
    fin = fin or 0.0
    cases = {k: ni - (k - 1) * fin for k in (1, 1.5, 2, 3)}
    chg = None if ni <= 0 else cases[3] / ni - 1
    if ni <= 0:
        note = "Алдагдалтай"
    elif fin == 0:
        note = "Санхүүгийн зардалгүй — хүүнд мэдрэмжгүй"
    elif chg >= -0.15:
        note = "Тэсвэртэй"
    elif chg >= -0.40:
        note = "Дунд зэрэг мэдрэмжтэй"
    else:
        note = "Эмзэг"
    return {"finance_cost": fin, "cases": cases, "change_3x": chg, "note": note}


def break_even(c: Company) -> Optional[dict]:
    r = c.latest
    rev, _ = c.flow(r, "revenue")
    gp, _ = c.flow(r, "gross_profit")
    if rev is None or gp is None or rev <= 0:
        return None
    sell, adm, fin = (c.flow(r, k)[0] or 0.0 for k in ("selling_exp", "admin_exp", "finance_cost"))
    fixed = sell + adm + fin
    gm = gp / rev
    if gm <= 0:
        return {"gross_margin": gm, "fixed": fixed, "break_even": None, "revenue": rev, "safety": None,
                "note": "АЛДАГДАЛТАЙ — нийт ашиг сөрөг"}
    be = fixed / gm
    safety = (rev - be) / rev
    note = ("БАТ БЭХ — орлого их буурсан ч тэсвэрлэнэ" if safety >= 0.40 else "ХЭВИЙН — дунд зэргийн аюулгүйн зайтай"
            if safety >= 0.15 else "ЭМЗЭГ — орлого бага зэрэг буурахад алдагдалд орно" if safety >= 0
            else "АЛДАГДАЛТАЙ — эвцэлдэх түвшнээс доор")
    return {"gross_margin": gm, "fixed": fixed, "break_even": be, "revenue": rev, "safety": safety, "note": note}


def trading_liquidity(bars: list[Bar], as_of: date, today: date, window_days: int) -> Optional[dict]:
    """`as_of`-оос өмнөх `window_days` хуанлийн өдрийн арилжааны идэвх. `as_of` = бүх тикерийн ханшийн хамгийн сүүлийн өдөр
    (нэг тикерийн өгөгдөл хоцорсон бол идэвх нь 0 болно)."""
    if not bars:
        return None
    end = bars[-1].day
    start = as_of - timedelta(days=window_days)
    win = [b for b in bars if start < b.day <= as_of]
    stale = (today - end).days
    n = len(win)
    return {"last_day": end, "stale_days": stale, "trading_days": n,
            "avg_value": sum(b.value for b in win) / n if n else 0.0,
            "avg_qty": sum(b.qty for b in win) / n if n else 0.0,
            "window_days": window_days}
