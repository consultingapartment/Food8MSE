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


MAIN_CHARTS = {"valuation.png", "ratios.png"}


def notify(res: Result, charts: list[Path], workbook: Optional[Path]) -> bool:
    """Мессеж, дараа нь хоёр албом илгээнэ (Excel Telegram-д явахгүй: FOOD mse.xlsx, FOOD analysis.xlsx хоёр репод хадгалагдана). Мессеж явсан бол True."""
    ok = send_telegram(format_summary(res))
    if not ok:
        return False
    main = [c for c in charts if c.name in MAIN_CHARTS]
    info = [c for c in charts if c.name not in MAIN_CHARTS]
    if main:                                                         # 1) харьцаа, үнэлгээний харьцуулалт
        send_photos(main, caption="1) Харьцаа, үнэлгээний харьцуулсан зураг")
    if info:                                                         # 2) инфографик (тусдаа албом)
        send_photos(info, caption="2) Инфографик: жил, хагас жил, 1,000₮ орлого, хямдрал, эрүүл мэнд, улирлын өгөөж, эзэмшил")
    return True
