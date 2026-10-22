"""Шинжилгээний үр дүнг Telegram-д илгээх: хураангуй мессеж + харьцуулсан зураг + Excel.

TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID тохируулаагүй бол юу ч илгээхгүй (алдаа гаргахгүй).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from mse_financials.notify import send_photos, send_telegram

from .engine import Result

ICON = {"ХУДАЛДАН АВАХ": "🟢", "ХАДГАЛАХ": "🟡", "ЗАРАХ": "🔴"}


def _change(res: Result, t: str) -> Optional[float]:
    bars = res.inputs.prices.get(t) or []
    return bars[-1].close / bars[-2].close - 1 if len(bars) >= 2 and bars[-2].close else None


def format_summary(res: Result) -> str:
    head = f"📈 МХБ хүнс — {res.today}" + (f" (ханш {res.as_of_prices})" if res.as_of_prices else "")
    rows = []
    for t in sorted(res.tickers, key=lambda x: -(res.r[x]["score"]["total"] or 0)):
        r = res.r[t]
        v, sc = r.get("val"), r.get("score") or {}
        ch = _change(res, t)
        price = f"{v.price:,.2f}".rstrip("0").rstrip(".") if v else "—"
        pe = f"P/E {v.pe:.1f}" if v and v.pe else "P/E —"
        tot = sc.get("total")
        rate = f"{ICON.get(sc.get('rating'), '')} {tot:.0f} {sc.get('rating')}" if tot is not None else "—"
        chs = "" if ch is None else f" ({ch * 100:+.1f}%)"
        rows.append(f"{t} {price}{chs} · {pe} · {rate}")
    lines = [head, ""] + rows
    if res.warnings:
        lines += ["", f"⚠️ Анхааруулга ({len(res.warnings)}):"] + [f"• {w[:160]}" for w in res.warnings[:6]]
    lines += ["", "Хөрөнгө оруулалтын зөвлөгөө биш."]
    return "\n".join(lines)


def _pc(x: Optional[float]) -> str:
    return "—" if x is None else f"{x * 100:+.1f}%"


def _bn(x: Optional[float]) -> str:
    return "—" if x is None else f"{x / 1e6:,.1f}"


def format_latest(res: Result) -> str:
    """Компани бүрийн сүүлийн тайлан: хуримтлал (YTD), сүүлийн улирал (эсвэл Q1/Q3 байхгүй бол хагас жил) — өмнөх үе, өмнөх оны мөн үетэй (тэрбум ₮)."""
    from . import periods as P
    lines = [f"📊 Сүүлийн тайлангийн харьцуулалт — {res.today}", "(тэрбум ₮; Δ: өмнөх үетэй / өмнөх оны мөн үетэй)", ""]
    for t in res.tickers:
        c = res.companies[t]
        head = None
        blocks = []
        for key, nm in (("revenue", "Орлого"), ("net_income", "Ашиг")):
            v = P.latest_view(c, key)
            if not v:
                continue
            head = v["label"]
            ytd = f"хуримтлал {_bn(v['ytd'])} ({_pc(P.change(v['ytd'], v['ytd_py'])[0])} YoY)"
            if v.get("q") is not None:
                seg = (f"{v['q_label']} {_bn(v['q'])} ({_pc(P.change(v['q'], v['q_prev'])[0])} / "
                       f"{_pc(P.change(v['q'], v['q_py'])[0])})")
            elif v.get("h") is not None:
                seg = (f"{v['h_label']} {_bn(v['h'])} ({_pc(P.change(v['h'], v['h_prev'])[0])} / "
                       f"{_pc(P.change(v['h'], v['h_py'])[0])})")
            else:
                seg = ""
            blocks.append(f"  {nm}: {ytd}" + (f" · {seg}" if seg else ""))
        if head:
            lines += [f"{t} — {head}"] + blocks
    lines += ["", "Хоосон («—») = тооцоход хэрэгтэй тайлан (Q1, Q3 заавал биш) ирүүлээгүй."]
    return "\n".join(lines)[:3900]


MAIN_CHARTS = {"valuation.png", "ratios.png"}


def notify(res: Result, charts: list[Path], workbook: Optional[Path]) -> bool:
    """Мессеж, дараа нь хоёр албом илгээнэ (Excel Telegram-д явахгүй: FOOD mse.xlsx, FOOD analysis.xlsx хоёр репод хадгалагдана). Мессеж явсан бол True."""
    ok = send_telegram(format_summary(res))
    if not ok:
        return False
    send_telegram(format_latest(res))                                # 2-р мессеж: сүүлийн тайлангийн харьцуулалт
    main = [c for c in charts if c.name in MAIN_CHARTS]
    info = [c for c in charts if c.name not in MAIN_CHARTS]
    if main:                                                         # 1) харьцаа, үнэлгээний харьцуулалт
        send_photos(main, caption="1) Харьцаа, үнэлгээний харьцуулсан зураг")
    if info:                                                         # 2) инфографик (Telegram албом ≤10 зураг тул хоёр албом)
        names = ("жил, хагас жил, 1,000₮ орлого, хямдрал, эрүүл мэнд, сарын өгөөж, эзэмшил, ашгийн гүүр, корреляци, онцгой үзүүлэлт",
                 "онцгой үзүүлэлт (2–4): үнэлгээний нөөц, ашгийн чанар, өсөлтийн санхүүжилт, тайлангийн дараах ханшийн хариу")
        if len(info) <= 10:
            send_photos(info, caption="2) Инфографик: " + names[0])
        else:
            send_photos(info[:10], caption="2) Инфографик (1/2): " + names[0])
            send_photos(info[10:], caption="3) Инфографик (2/2): " + names[1])
    return True
