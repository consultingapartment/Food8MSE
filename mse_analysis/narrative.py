"""Тоон үзүүлэлтээс гарсан компани бүрийн дүгнэлт (дүрэмд суурилсан, загварчилсан өгүүлбэр)."""
from __future__ import annotations

from typing import Optional

from .config import LABELS


def pct(x: Optional[float], d: int = 1, sign: bool = False) -> str:
    return "—" if x is None else f"{x * 100:+.{d}f}%" if sign else f"{x * 100:.{d}f}%"


def num(x: Optional[float], d: int = 2) -> str:
    return "—" if x is None else f"{x:,.{d}f}"


def bn(x_thousand: Optional[float]) -> str:
    """мянган ₮ -> тэрбум ₮"""
    return "—" if x_thousand is None else f"{x_thousand / 1e6:,.1f}"


def summarize(t: str, r: dict, a) -> list[str]:
    """Компанийн 5–6 өгүүлбэр. `r` = engine-ийн үр дүн."""
    c, rt, v = r["company"], r["ratios"], r["val"]
    last = c.latest
    out: list[str] = []
    rev, basis = c.flow(last, "revenue")
    ni, _ = c.flow(last, "net_income")
    tail = "сүүлийн 12 сар" if basis == "LTM" else "жилчилсэн"
    out.append(f"{r['name']} ({t}) — {last.period.label} тайлан. Орлого ({tail}) {bn(rev)} тэрбум ₮, "
               f"өмнөх оны ижил үеэс {pct(rt.get('revenue_yoy'), 1, True)}; цэвэр ашиг {bn(ni)} тэрбум ₮ "
               f"(цэвэр ашгийн маржин {pct(rt.get('net_margin'))}).")
    out.append(f"Ашигт ажиллагаа: нийт ашгийн маржин {pct(rt.get('gross_margin'))}, ROE {pct(rt.get('roe'))}, "
               f"ROA {pct(rt.get('roa'))}.")
    cr, de = rt.get("current_ratio"), rt.get("debt_to_equity")
    liq = "сайн" if (cr or 0) >= 2 else "хэвийн" if (cr or 0) >= 1 else "сул"
    lev = "бага" if (de is not None and de < 0.5) else "дунд" if (de is not None and de < 1.0) else "өндөр"
    out.append(f"Хөрвөх чадвар {liq} (эргэлтийн хөрөнгийн харьцаа {num(cr)}), өрийн түвшин {lev} (өр/өмч {num(de)}).")
    if v:
        g = f"Graham-аар {pct(v.graham_margin, 0)} хямд" if (v.graham_margin or 0) > 0 else (
            f"Graham-аар {pct(-v.graham_margin, 0)} үнэтэй" if v.graham_margin is not None else "Graham тооцогдохгүй")
        out.append(f"Үнэлгээ: P/E {num(v.pe, 1)}, P/B {num(v.pb)}, EV/EBIT {num(v.ev_ebit, 1)}; {g}. "
                   f"Ногдлын өгөөж {pct(v.div_yield)} (хадгаламж {pct(a.deposit_rate, 0)}-тай {pct(v.div_spread, 1, True)} зөрүү). "
                   f"Дүгнэлт: {v.verdict}.")
    risks = []
    if r["altman"]:
        risks.append(f"Altman Z {num(r['altman']['z'])} — {r['altman']['zone']}")
    if r["break_even"] and r["break_even"]["safety"] is not None:
        risks.append(f"эвцэлдэх орлогын аюулгүйн зай {pct(r['break_even']['safety'], 0)}")
    if r["conc"]:
        risks.append(f"эзэмшлийн хөрвөх чадварын эрсдэл {r['conc']['grade']}")
    if risks:
        out.append("Эрсдэл: " + "; ".join(risks) + ".")
    s = r["score"]
    if s["total"] is not None:
        comp = {k: x for k, x in s["components"].items() if x is not None}
        best = max(comp, key=comp.get)
        worst = min(comp, key=comp.get)
        out.append(f"Нийт оноо {s['total']:.0f}/100 — {s['rating']}. Хамгийн хүчтэй тал: {LABELS[best].lower()} "
                   f"({comp[best]:.0f}), хамгийн сул тал: {LABELS[worst].lower()} ({comp[worst]:.0f}).")
    return out
