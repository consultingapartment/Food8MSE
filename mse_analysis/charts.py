"""Бүх компанийг харьцуулсан зураг (PNG). Хоёр самбар: (1) үнэлгээ, (2) санхүүгийн харьцаа.

matplotlib-ийг зөвхөн энд, Agg backend-ээр (дэлгэцгүй орчинд) ашиглана.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from .engine import Result

INK, MUTED, GRID = "#1f2933", "#6b7785", "#e4e7eb"
BAR, GOOD, MID, BAD = "#3b6fb6", "#2f8f5b", "#d9a21b", "#c4443a"


def _g(d, k: str) -> Optional[float]:
    """dict эсвэл dataclass-аас талбар."""
    if d is None:
        return None
    return d.get(k) if isinstance(d, dict) else getattr(d, k, None)


def _score(r: dict) -> Optional[float]:
    return _g(r.get("score"), "total")


# (гарчиг, функц, формат, дээд хязгаар, лавлах шугам, өнгө-функц)
def _panels(res: Result):
    dep = res.assumptions.deposit_rate
    pct = lambda x: f"{x * 100:.0f}%" if abs(x) >= 1 else f"{x * 100:.1f}%"
    mult = lambda x: f"{x:.2f}x"
    num = lambda x: f"{x:.0f}"
    v = lambda r, k: _g(r.get("val"), k)
    rt = lambda r, k: _g(r.get("ratios"), k)
    val = [
        ("Нийт оноо (0–100)", _score, num, 100, [(res.assumptions.rating_buy, "авах"), (res.assumptions.rating_hold, "хадгалах")], "score"),
        ("P/E (үржүүлэгч, бага нь хямд)", lambda r: v(r, "pe"), mult, 30, [], None),
        ("P/B (бага нь хямд)", lambda r: v(r, "pb"), mult, 5, [(1.0, "1.0")], None),
        ("Ногдол ашгийн өгөөж", lambda r: v(r, "div_yield"), pct, 0.30, [(dep, f"хадгаламж {dep * 100:.0f}%")], None),
        ("Graham-аас хямд байх хувь", lambda r: v(r, "graham_margin"), pct, 1.0, [(0.0, "")], None),
        ("Бодит үнэ цэнийн хөнгөлөлт", lambda r: v(r, "real_discount"), pct, 1.0, [(0.0, "")], None),
    ]
    fin = [
        ("ROE (өөрийн хөрөнгийн өгөөж)", lambda r: rt(r, "roe"), pct, 0.60, [], None),
        ("Цэвэр ашгийн маржин (тайлант үе)", lambda r: rt(r, "net_margin"), pct, 0.30, [(0.0, "")], None),
        ("Хөрвөх чадвар (Current ratio)", lambda r: rt(r, "current_ratio"), mult, 5, [(1.0, "1.0")], None),
        ("Өр / Өмч", lambda r: rt(r, "debt_to_equity"), mult, 5, [(1.0, "1.0")], None),
        ("Орлогын өсөлт (YoY)", lambda r: rt(r, "revenue_yoy"), pct, 0.80, [(0.0, "")], None),
        ("Цэвэр ашгийн өсөлт (YoY)", lambda r: rt(r, "net_income_yoy"), pct, 2.0, [(0.0, "")], None),
    ]
    return val, fin


def _draw(ax, title: str, rows: list[tuple[str, Optional[float]]], fmt: Callable, cap: float,
          refs: list, kind: Optional[str], res: Result) -> None:
    got = [(t, x) for t, x in rows if x is not None]
    got.sort(key=lambda p: p[1])                                   # дээд нь хамгийн их
    ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold", color=INK, pad=16)
    if not got:
        ax.text(0.5, 0.5, "өгөгдөл алга", ha="center", va="center", color=MUTED, transform=ax.transAxes)
        ax.axis("off")
        return
    lo = min(0.0, min(max(x, -cap) for _, x in got))
    shown = [min(max(x, -cap), cap) for _, x in got]
    colors = []
    for t, x in got:
        if kind == "score":
            colors.append(GOOD if x >= res.assumptions.rating_buy else MID if x >= res.assumptions.rating_hold else BAD)
        else:
            colors.append(BAR)
    ys = range(len(got))
    ax.barh(list(ys), shown, color=colors, height=0.62, zorder=2)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([t for t, _ in got], fontsize=9, color=INK)
    for y, (t, x), s in zip(ys, got, shown):
        txt = fmt(x) + (" ▸" if abs(x) > cap else "")                # ▸ = тэнхлэгээс хэтэрсэн (хайчилсан)
        # сөрөг баганын тэмдэглэгээг тэг шугамын баруун талд (тикерийн нэртэй давхцахгүйн тулд) бичнэ
        ax.text((s if s >= 0 else 0) + 0.015 * cap, y, txt, va="center", ha="left", fontsize=8.5, color=INK)
    for x0, lab in refs:
        ax.axvline(x0, color=MUTED, lw=0.9, ls="--", zorder=1)
        if lab:
            ax.text(x0, len(got) - 0.35, lab, fontsize=7.5, color=MUTED, ha="center", va="bottom")
    ax.set_xlim(lo * 1.25 if lo < 0 else 0, cap * 1.28)
    miss = [t for t, x in rows if x is None]
    if miss:
        ax.text(1.0, -0.2, "өгөгдөл дутуу: " + ", ".join(miss), transform=ax.transAxes, ha="right", fontsize=7.5, color=MUTED)
    ax.grid(axis="x", color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="x", labelsize=8, colors=MUTED, length=0)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.set_major_formatter(lambda x, _: fmt(x))


def _figure(res: Result, title: str, panels, out: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(15, 8.4))
    for ax, (ttl, fn, fmt, cap, refs, kind) in zip(axes.flat, panels):
        rows = [(t, fn(res.r[t])) for t in res.tickers]
        _draw(ax, ttl, rows, fmt, cap, refs, kind, res)
    px = f"ханш: {res.as_of_prices}" if res.as_of_prices else "ханш: —"
    fig.suptitle(title, x=0.012, y=0.985, ha="left", fontsize=14, fontweight="bold", color=INK)
    fig.text(0.012, 0.935, f"{px} · сүүлийн тайлан: {_latest(res)} · ▸ = тэнхлэгээс хэтэрсэн утга · хөрөнгө оруулалтын зөвлөгөө биш",
             fontsize=9, color=MUTED, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.92), h_pad=2.2, w_pad=2.0)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    return out


def _latest(res: Result) -> str:
    ds = [c.latest.period for c in res.companies.values() if c.latest and c.latest.period.year]
    return max(ds, key=lambda p: (p.year, p.quarter)).label if ds else "—"


def build(res: Result, out_dir: Path) -> list[Path]:
    """`valuation.png`, `ratios.png` + инфографикууд (10 хүртэл PNG). Буцаах: Telegram-д илгээх дарааллаар."""
    from . import infographics
    val, fin = _panels(res)
    d = Path(out_dir)
    main = [
        _figure(res, f"МХБ хүнс — үнэлгээний харьцуулалт ({res.today})", val, d / "valuation.png"),
        _figure(res, f"МХБ хүнс — санхүүгийн харьцааны харьцуулалт ({res.today})", fin, d / "ratios.png"),
    ]
    info = {p.name: p for p in infographics.build(res, d)}
    order = ["annual.png", "halfyear.png", "cost_1000.png", "price_tags.png", "health_check.png",
             "seasonality.png", "ownership.png"]
    return main + [info[n] for n in order if n in info]
