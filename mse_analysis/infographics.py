"""Инфографик: (1) үеийн харьцуулалт (жил, хагас жил, улирал), (2) 1,000₮ орлогын задаргаа, (3) хямдралын шошго,
(4) эрүүл мэндийн үзлэг, (5) улирлын цаг агаар (сарын өгөөж), (6) эзэмшлийн бүтэц.

Бүгд `Result`-аас л тооцогдоно — гараар оруулсан тоо байхгүй. matplotlib Agg.
"""
from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Optional

from . import periods as P
from .charts import BAD, BAR, GOOD, GRID, INK, MID, MUTED
from .engine import Result

ORANGE = "#e08a1e"
SOFT = "#f4f6f9"
KIND_NAME = {"year": "Жилийн", "half": "Хагас жилийн", "quarter": "Улирлын"}
NOTE = "хөрөнгө оруулалтын зөвлөгөө биш"


# ------------------------------------------------------------------ дэд функц
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _top(fig) -> float:
    """Гарчиг, дэд гарчигт зориулж дээд талд ~0.95 инч үлдээнэ."""
    return 1 - 0.95 / fig.get_size_inches()[1]


def _sub(res: Result) -> str:
    px = f"ханш {res.as_of_prices}" if res.as_of_prices else "ханш —"
    return f"{px} · тооцоолсон {res.today} · {NOTE}"


def _save(fig, out: Path, title: str, sub: str) -> Path:
    h = fig.get_size_inches()[1]
    fig.text(0.012, 1 - 0.14 / h, title, fontsize=15, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.012, 1 - 0.55 / h, sub, fontsize=9, color=MUTED, ha="left", va="top")
    from . import brand
    brand.stamp(fig)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, facecolor="white")
    _plt().close(fig)
    return out


def _pct(x: float, plus: bool = True) -> str:
    return f"{x * 100:+.0f}%" if abs(x) >= 1 and plus else f"{x * 100:+.1f}%" if plus else f"{x * 100:.1f}%"


def _bn(x: Optional[float]) -> str:
    """мянган ₮ -> тэрбум ₮"""
    return "—" if x is None else f"{x / 1e6:,.1f}"


# ------------------------------------------------------------------ 1. Жилийн динамик (бүх жил, өмнөх жилтэй нь)
def annual_trend(res: Result, out: Path) -> Path:
    plt = _plt()
    fig, axes = plt.subplots(2, 4, figsize=(16, 9))
    for ax, t in zip(axes.flat, res.tickers):
        c = res.companies[t]
        pers = sorted({p for key in ("revenue", "net_income") for p, v, _ in P.history(c, "year", key, 5) if v is not None},
                      key=lambda p: p.year)[-5:]
        ax.set_title(f"{t}  ·  {res.r[t]['name']}", loc="left", fontsize=10.5, fontweight="bold", color=INK, pad=8)
        if not pers:
            ax.text(0.5, 0.5, "жилийн тайлан алга", ha="center", va="center", color=MUTED, transform=ax.transAxes)
            ax.axis("off")
            continue
        rev = [P.value(c, p, "revenue") for p in pers]
        ni = [P.value(c, p, "net_income") for p in pers]
        w = 0.38
        xs = range(len(pers))
        ax.bar([x - w / 2 for x in xs], [(v or 0) / 1e6 for v in rev], w, color=BAR, label="Орлого", zorder=2)
        ax.bar([x + w / 2 for x in xs], [(v or 0) / 1e6 for v in ni], w, color=ORANGE, label="Цэвэр ашиг", zorder=2)
        labels = []
        for p, r_, n_ in zip(pers, rev, ni):
            dr, _ = P.change(r_, P.value(c, p.yoy(), "revenue"))
            dn, nn = P.change(n_, P.value(c, p.yoy(), "net_income"))
            a = "—" if dr is None else _pct(dr)
            b = "—" if dn is None else _pct(dn)
            labels.append(f"{p.year}\nО {a}\nА {b}")
        ax.set_xticks(list(xs))
        ax.set_xticklabels(labels, fontsize=7.8, color=INK, linespacing=1.35)
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.grid(axis="y", color=GRID, lw=0.7, zorder=0)
        ax.set_axisbelow(True)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        ax.tick_params(axis="y", labelsize=7.5, colors=MUTED, length=0)
        ax.tick_params(axis="x", length=0)
        ax.set_ylabel("тэрбум ₮", fontsize=7.5, color=MUTED)
    h, l = axes.flat[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=2, frameon=False, fontsize=9, bbox_to_anchor=(0.99, 0.985))
    fig.tight_layout(rect=(0, 0, 1, _top(fig)), h_pad=2.2, w_pad=1.5)
    return _save(fig, out, "Жилийн динамик — жил бүрийг өмнөх жилтэй нь харьцуулав",
                 "О = орлогын өөрчлөлт, А = цэвэр ашгийн өөрчлөлт (өмнөх жилтэй харьцуулсан) · «—» = өмнөх жилийн тайлан алга эсвэл суурь нь алдагдалтай · " + _sub(res))


# ------------------------------------------------------------------ 2/3. Хагас жил, улирал: 4 самбар
def _rank_panel(ax, title: str, rows: list[tuple[str, Optional[float], str, str]], cap: float) -> None:
    """rows: (тикер, өөрчлөлт, тайлбар, нэмэлт тэмдэглэгээ)."""
    ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold", color=INK, pad=10)
    have = sorted([r for r in rows if r[1] is not None], key=lambda r: r[1])
    rest = [r for r in rows if r[1] is None]
    ordered = rest + have                                          # хамгийн их нь дээд талд
    if not have:
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.7, len(rows) - 0.3)
        for y, (t, _, note, _) in enumerate(rows):
            ax.text(0.0, y, f"{t}   {note or 'өгөгдөл алга'}", va="center", ha="left", fontsize=8.3, color=MUTED, style="italic")
        ax.axis("off")
        return
    ys = range(len(ordered))
    lo = min([max(r[1], -cap) for r in have] + [0.0])
    for y, (t, d, note, extra) in zip(ys, ordered):
        if d is None:
            ax.text(0.01 * cap, y, note or "өгөгдөл алга", va="center", ha="left", fontsize=8, color=MUTED, style="italic")
            continue
        s = min(max(d, -cap), cap)
        ax.barh(y, s, color=GOOD if d >= 0 else BAD, height=0.62, zorder=2)
        txt = f"{_pct(d)}  {extra}" + (" ▸" if abs(d) > cap else "")
        ax.text((s if s >= 0 else 0) + 0.015 * cap, y, txt, va="center", ha="left", fontsize=8.3, color=INK)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([r[0] for r in ordered], fontsize=9, color=INK)
    ax.set_ylim(-0.7, len(ordered) - 0.3)
    ax.set_xlim(lo * 1.3 if lo < 0 else -0.02, cap * 1.9)
    ax.axvline(0, color=MUTED, lw=0.9, zorder=1)
    ax.grid(axis="x", color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="x", labelsize=8, colors=MUTED, length=0)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x * 100:.0f}%")


def _quarter_figure(res: Result, out: Path) -> Optional[Path]:
    """Улирал: компани бүр өөрийн хамгийн сүүлийн боломжит улирлаар (Q1/Q3 тайлан заавал биш тул нийтлэг улирал байхгүй)."""
    own = {t: P.latest_own(res.companies[t], "quarter") for t in res.tickers}
    if not any(own.values()):
        return None
    plt = _plt()
    fig, axes = plt.subplots(2, 2, figsize=(15, 8.6))
    spec = [("revenue", "Орлого", "prev", 1.0), ("revenue", "Орлого", "yoy", 1.0),
            ("net_income", "Цэвэр ашиг", "prev", 2.0), ("net_income", "Цэвэр ашиг", "yoy", 2.0)]
    for ax, (key, nm, mode, cap) in zip(axes.flat, spec):
        rows = []
        for t in res.tickers:
            c, tp = res.companies[t], own[t]
            if tp is None:
                rows.append((t, None, P.missing_reason(c, "quarter"), ""))
                continue
            cmp_ = P.compare(c, tp, key)
            k = "prev" if mode == "prev" else "yoy"
            base_p = tp.prev() if mode == "prev" else tp.yoy()
            d, note, b = cmp_["d_" + k], cmp_["n_" + k], cmp_[k]
            if d is None and note == "өгөгдөл алга":
                note = f"{tp.label}: {base_p.label} тайлан алга"
            extra = f"{tp.label} ({_bn(b)}→{_bn(cmp_['cur'])})" if d is not None else ""
            rows.append((t, d, note, extra))
        what = "өмнөх улиралтай" if mode == "prev" else "өмнөх жилийн мөн улиралтай"
        _rank_panel(ax, f"{nm}: сүүлийн боломжит улирал ({what})", rows, cap)
    fig.tight_layout(rect=(0, 0, 1, _top(fig)), h_pad=2.6, w_pad=2.4)
    sub = ("хаалт: өөрчлөлт % (хаалтад: улирал, суурь→одоо, тэрбум ₮) · ▸ = тэнхлэгээс хэтэрсэн · "
           "улирал = хуримтлагдсан тайлангийн зөрүү · " + _sub(res))
    return _save(fig, out, "Улирлын харьцуулалт — компани бүрийн сүүлийн боломжит улирал", sub)


def compare_figure(res: Result, kind: str, out: Path) -> Optional[Path]:
    if kind == "quarter":
        return _quarter_figure(res, out)
    tgt = P.target(res.companies, kind)
    if tgt is None:
        return None
    plt = _plt()
    fig, axes = plt.subplots(2, 2, figsize=(15, 8.6))
    prev, yoy = tgt.prev(), tgt.yoy()
    spec = [("revenue", "Орлого", "prev", 1.0), ("revenue", "Орлого", "yoy", 1.0),
            ("net_income", "Цэвэр ашиг", "prev", 2.0), ("net_income", "Цэвэр ашиг", "yoy", 2.0)]
    for ax, (key, nm, mode, cap) in zip(axes.flat, spec):
        base_p = prev if mode == "prev" else yoy
        rows = []
        for t in res.tickers:
            cmp_ = P.compare(res.companies[t], tgt, key)
            d, note = cmp_["d_prev" if mode == "prev" else "d_yoy"], cmp_["n_prev" if mode == "prev" else "n_yoy"]
            b = cmp_["prev" if mode == "prev" else "yoy"]
            if d is None and note == "өгөгдөл алга":
                cc = res.companies[t]
                miss = P.missing_detail(cc, tgt) if cmp_["cur"] is None else P.missing_detail(cc, base_p)
                note = miss if miss != "өгөгдөл алга" else note
            extra = "" if d is None else f"({_bn(b)}→{_bn(cmp_['cur'])})"
            rows.append((t, d, note, extra))
        what = "өмнөх үетэй" if mode == "prev" else "өмнөх жилийн мөн үетэй"
        _rank_panel(ax, f"{nm}: {tgt.label} ↔ {base_p.label}  ({what})", rows, cap)
    fig.tight_layout(rect=(0, 0, 1, _top(fig)), h_pad=2.6, w_pad=2.4)
    have = P.periods_with_data(res.companies, kind).get(tgt, [])
    miss = [t for t in res.tickers if t not in have]
    sub = ("хаалт: өөрчлөлт % (хаалтад: суурь→одоо, тэрбум ₮) · ▸ = тэнхлэгээс хэтэрсэн · "
           + (f"{tgt.label} тайлан/хуримтлал дутуу: {', '.join(miss)} · " if miss else "") + _sub(res))
    nm = KIND_NAME[kind]
    return _save(fig, out, f"{nm} харьцуулалт — {tgt.label}", sub)


# ------------------------------------------------------------------ 4. 1,000₮ орлого хаашаа явдаг вэ
SEG = [("(-) Өртөг", "Өртөг", "#5b7aa6"), ("(-) Борлуулалт, маркетинг", "Борлуулалт, маркетинг", "#8fb0d9"),
       ("(-) Ерөнхий удирдлага", "Ерөнхий удирдлага", "#b9c7dd"), ("(-) Санхүүгийн зардал", "Санхүүгийн зардал", "#d9a21b"),
       ("(-) Татвар ба бусад", "Татвар ба бусад", "#a8a29a")]


def cost_1000(res: Result, out: Path) -> Path:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(15, 7.8))
    rows = []
    for t in res.tickers:
        b = res.r[t].get("breakdown")
        if b and b.get("Орлого"):
            rev = b["Орлого"]
            rows.append((t, {k: b.get(k, 0) / rev * 1000 for k, _, _ in SEG}, b.get("Цэвэр ашиг", 0) / rev * 1000))
    rows.sort(key=lambda r: r[2])
    for y, (t, parts, ni) in enumerate(rows):
        left = 0.0
        extra_income = -min(parts[SEG[-1][0]], 0)               # «Татвар ба бусад» сөрөг бол энэ нь бусад орлого
        for k, lab, col in SEG:
            w = max(parts[k], 0)
            ax.barh(y, w, left=left, color=col, height=0.62, zorder=2, edgecolor="white", linewidth=0.8)
            if w >= 55:
                ax.text(left + w / 2, y, f"{w:.0f}", ha="center", va="center", fontsize=8.5, color="white" if k == SEG[0][0] else INK)
            left += w
        if ni >= 0:
            ax.barh(y, ni, left=left, color=GOOD, height=0.62, zorder=2, edgecolor="white", linewidth=0.8)
            ax.text(left + ni / 2 if ni >= 55 else left + ni + 8, y, f"{ni:.0f}", ha="center" if ni >= 55 else "left",
                    va="center", fontsize=9, fontweight="bold", color="white" if ni >= 55 else GOOD)
            if extra_income >= 1:
                ax.text(left + ni + (60 if ni < 55 else 8), y, f"(+{extra_income:.0f}₮ бусад орлого)", ha="left", va="center", fontsize=8, color=MUTED)
        else:
            ax.text(left + 10, y, f"алдагдал {ni:.0f}₮", ha="left", va="center", fontsize=9, fontweight="bold", color=BAD)
    ax.axvline(1000, color=INK, lw=1.1, ls="--", zorder=3)
    ax.text(1008, len(rows) - 0.35, "1,000₮ орлого", ha="left", va="bottom", fontsize=8.5, color=INK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=11, color=INK, fontweight="bold")
    ax.set_xlim(0, max(1080, max(sum(max(v, 0) for v in r[1].values()) for r in rows) + 220))
    ax.set_ylim(-0.6, len(rows) - 0.1)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=8.5, colors=MUTED)
    ax.set_xlabel("төгрөг", fontsize=8.5, color=MUTED)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in SEG] + [plt.Rectangle((0, 0), 1, 1, color=GOOD)]
    fig.legend(handles, [l for _, l, _ in SEG] + ["Цэвэр ашиг"], loc="lower center", ncol=6, frameon=False, fontsize=9,
               bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.06, 1, _top(fig)))
    last = max(c.latest.period for c in res.companies.values() if c.latest and c.latest.period.year) if res.companies else None
    return _save(fig, out, "1,000 төгрөгийн орлого хаашаа явдаг вэ?",
                 f"Сүүлийн 12 сар (LTM, дутуу бол жилчилсэн) дүнгээр, ашгийн дарааллаар · сүүлийн тайлан {last.label if last else '—'} · " + _sub(res))


# ------------------------------------------------------------------ 5. Хямдралын шошго
def price_tags(res: Result, out: Path) -> Path:
    from matplotlib.patches import Circle, FancyBboxPatch
    plt = _plt()
    items = [(t, res.r[t]["val"]) for t in res.tickers if res.r[t].get("val") and res.r[t]["val"].real_value]
    items.sort(key=lambda x: -(x[1].real_discount or -9))
    fig, axes = plt.subplots(2, 4, figsize=(15, 8.2))
    for ax in axes.flat:
        ax.axis("off")
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
    for ax, (t, v) in zip(axes.flat, items):
        disc = v.real_discount or 0
        cheap = disc > 0
        col = BAD if disc >= 0.25 else MID if cheap else MUTED
        ax.add_patch(FancyBboxPatch((0.6, 0.6), 8.8, 8.6, boxstyle="round,pad=0.05,rounding_size=0.5", fc=SOFT, ec=GRID, lw=1.2))
        ax.add_patch(Circle((1.5, 8.3), 0.28, fc="white", ec=MUTED, lw=1.2))          # үнийн шошгоны нүх
        ax.text(5, 8.1, t, ha="center", va="center", fontsize=19, fontweight="bold", color=INK)
        ax.text(5, 7.1, res.r[t]["name"], ha="center", va="center", fontsize=8.5, color=MUTED)
        ax.text(5, 5.55, f"{v.price:,.2f}".rstrip("0").rstrip(".") + "₮", ha="center", va="center", fontsize=21, fontweight="bold", color=INK)
        ax.text(5, 4.65, "зах зээлийн ханш", ha="center", va="center", fontsize=8, color=MUTED)
        ax.plot([1.4, 8.6], [4.1, 4.1], color=GRID, lw=1)
        ax.text(5, 3.3, f"бодит үнэ цэн ≈ {v.real_value:,.0f}₮", ha="center", va="center", fontsize=10, color=INK)
        if v.div_yield is not None:
            ax.text(5, 2.45, f"ногдол ашгийн өгөөж {v.div_yield * 100:.1f}%", ha="center", va="center", fontsize=8.5, color=MUTED)
        ax.add_patch(Circle((8.15, 7.7), 1.2, fc=col, ec="white", lw=2, zorder=4))
        ax.text(8.15, 7.95, f"{'-' if cheap else '+'}{abs(disc) * 100:.0f}%", ha="center", va="center", fontsize=14, fontweight="bold", color="white", zorder=5)
        ax.text(8.15, 7.2, "хямд" if cheap else "үнэтэй", ha="center", va="center", fontsize=8.5, color="white", zorder=5)
        ax.text(5, 1.3, v.verdict.capitalize() if v.verdict else "", ha="center", va="center", fontsize=7.4, color=MUTED, wrap=True)
    fig.tight_layout(rect=(0, 0.03, 1, _top(fig)))
    miss = [t for t in res.tickers if t not in {x[0] for x in items}]
    fig.text(0.5, 0.034, ("Тооцогдоогүй: " + ", ".join(miss) + " (алдагдалтай эсвэл өгөгдөл дутуу тул Graham тоо гарахгүй)") if miss else "",
             ha="center", fontsize=8.5, color=MUTED)
    fig.text(0.5, 0.012, "Бодит үнэ цэн = Graham тоо √(22.5·EPS·BVPS) × (1 + ногдлын зөрүү). «Хямд» = 1 − ханш / бодит үнэ цэн. Загварын тооцоо, баталгаа биш.",
             ha="center", fontsize=8, color=MUTED)
    return _save(fig, out, "Хямдралын шошго — ханш vs бодит үнэ цэн", _sub(res))


# ------------------------------------------------------------------ 6. Эрүүл мэндийн үзлэг
#            (нэр, түлхүүр, формат, "хэвийн" хязгаар, "анхаар" хязгаар, их нь сайн эсэх)
VITALS = [("Зүрх · ROE", "roe", "{:.0%}", 0.15, 0.05, True),
          ("Цусны эргэлт · хөрвөх чадвар", "current_ratio", "{:.2f}x", 1.5, 1.0, True),
          ("Жин · өр / өмч", "debt_to_equity", "{:.2f}x", 1.0, 2.0, False),
          ("Булчин · цэвэр ашгийн маржин", "net_margin", "{:.1%}", 0.10, 0.03, True),
          ("Өсөлт · орлого YoY", "revenue_yoy", "{:+.1%}", 0.05, 0.0, True),
          ("Дархлаа · Altman Z", "_z", "{:.1f}", 2.99, 1.81, True)]


def _status(x: Optional[float], good: float, warn: float, higher: bool) -> str:
    if x is None:
        return "n"
    if higher:
        return "g" if x >= good else "w" if x >= warn else "b"
    return "g" if x <= good else "w" if x <= warn else "b"


def health_check(res: Result, out: Path) -> Path:
    from matplotlib.patches import Circle, FancyBboxPatch
    plt = _plt()
    order = sorted(res.tickers, key=lambda t: -((res.r[t].get("score") or {}).get("total") or 0))
    fig, axes = plt.subplots(2, 4, figsize=(16, 9))
    col = {"g": GOOD, "w": MID, "b": BAD, "n": GRID}
    txt = {"g": "хэвийн", "w": "анхаар", "b": "эрсдэл", "n": "өгөгдөл алга"}
    for ax in axes.flat:
        ax.axis("off")
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 12)
    for ax, t in zip(axes.flat, order):
        r = res.r[t]
        rt = dict(r["ratios"] or {})
        rt["_z"] = (r.get("altman") or {}).get("z")
        sc = r.get("score") or {}
        ax.add_patch(FancyBboxPatch((0.2, 0.2), 9.6, 11.5, boxstyle="round,pad=0.03,rounding_size=0.4", fc="white", ec=GRID, lw=1.3))
        ax.add_patch(FancyBboxPatch((0.2, 9.9), 9.6, 1.8, boxstyle="round,pad=0.03,rounding_size=0.4", fc=SOFT, ec=GRID, lw=1.3))
        ax.text(0.7, 10.8, t, fontsize=15, fontweight="bold", color=INK, va="center")
        tot = sc.get("total")
        rate = sc.get("rating") or "—"
        rc = GOOD if rate == "ХУДАЛДАН АВАХ" else MID if rate == "ХАДГАЛАХ" else BAD if rate == "ЗАРАХ" else MUTED
        ax.text(9.4, 11.1, "—" if tot is None else f"{tot:.0f}/100", fontsize=12, fontweight="bold", color=rc, ha="right", va="center")
        ax.text(9.4, 10.4, rate, fontsize=8.5, color=rc, ha="right", va="center", fontweight="bold")
        for i, (nm, key, fmt, good, warn, higher) in enumerate(VITALS):
            x = rt.get(key)
            st = _status(x, good, warn, higher)
            y = 8.6 - i * 1.5
            ax.add_patch(Circle((0.95, y), 0.38, fc=col[st], ec="none"))
            ax.text(1.6, y + 0.2, nm, fontsize=8.2, color=INK, va="center")
            ax.text(1.6, y - 0.42, txt[st], fontsize=7.2, color=MUTED, va="center")
            ax.text(9.4, y, "—" if x is None else fmt.format(x), fontsize=11, fontweight="bold", color=INK, va="center", ha="right")
    fig.tight_layout(rect=(0, 0.035, 1, _top(fig)))
    fig.text(0.5, 0.012, "Босго: ROE ≥15% / ≥5% · хөрвөх чадвар ≥1.5 / ≥1.0 · өр/өмч ≤1.0 / ≤2.0 · маржин ≥10% / ≥3% · орлого YoY ≥5% / ≥0% · Altman Z ≥2.99 / ≥1.81 "
             "(хэвийн / анхаар, бусад нь эрсдэл). Маржин = сүүлийн тайлант үеийн (YTD); «1,000₮» зураг сүүлийн 12 сарын (LTM) тул зөрж болно. Нийт оноогоор эрэмбэлсэн.", ha="center", fontsize=8, color=MUTED)
    return _save(fig, out, "Хувьцааны эрүүл мэндийн үзлэг", _sub(res))


# ------------------------------------------------------------------ 7. Улирлын цаг агаар
def monthly_returns(bars, years: int = 10) -> dict[int, list[float]]:
    """Сар бүрийн сүүлийн хаалт -> календарийн сараар бүлэглэсэн өгөөж.
    Зөвхөн сүүлийн `years` жил; тухайн сард арилжаа байгаагүй (ханш дамжигдсан) сарыг өгөөжөөс хасна — эс бөгөөс
    нимгэн арилжаатай хувьцаанд хуурамч 0% олон гарна. Одоогийн (дуусаагүй) сарыг оруулахгүй."""
    if len(bars) < 40:
        return {}
    y1, m1 = bars[-1].day.year, bars[-1].day.month
    first = (y1 - years, m1)
    last: dict[tuple[int, int], float] = {}
    for b in bars:
        if (b.day.year, b.day.month) >= first:
            last[(b.day.year, b.day.month)] = b.close
    out: dict[int, list[float]] = {}
    for (y, m), c in last.items():
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        if (y, m) >= (y1, m1) or (py, pm) not in last:
            continue
        out.setdefault(m, []).append(c / last[(py, pm)] - 1)
    return out


def seasonality(res: Result, out: Path) -> Path:
    plt = _plt()
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("sea", [BAR, "#ffffff", ORANGE])
    tk = [t for t in res.tickers if res.inputs.prices.get(t)]
    grid, years = [], []
    for t in tk:
        mr = monthly_returns(res.inputs.prices[t])
        grid.append([median(mr[m]) if len(mr.get(m, [])) >= 3 else None for m in range(1, 13)])
        years.append(max((len(v) for v in mr.values()), default=0))
    fig, ax = plt.subplots(figsize=(15, 7.2))
    vmax = 0.12
    for i, row in enumerate(grid):
        for j, x in enumerate(row):
            if x is None:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, fc="#f1f2f4", ec="white", lw=2))
                ax.text(j + 0.5, i + 0.5, "—", ha="center", va="center", fontsize=9, color=MUTED)
            else:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, fc=cmap((max(-vmax, min(vmax, x)) + vmax) / (2 * vmax)), ec="white", lw=2))
                ax.text(j + 0.5, i + 0.5, f"{x * 100:+.1f}", ha="center", va="center", fontsize=9, color=INK)
    ax.set_xlim(0, 12)
    ax.set_ylim(len(tk), 0)
    ax.set_xticks([j + 0.5 for j in range(12)])
    ax.set_xticklabels([f"{m}-р сар" for m in range(1, 13)], fontsize=9, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(len(tk))])
    ax.set_yticklabels([f"{t}  (n={n})" for t, n in zip(tk, years)], fontsize=10, color=INK)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    for j, lab in ((0.5, "Цагаан сар (1–2-р сар)"), (6.5, "Наадам (7-р сар)")):
        ax.text(j + (0.5 if j > 1 else 1.0), len(tk) + 0.35, lab, ha="center", fontsize=8.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, _top(fig)))
    fig.text(0.5, 0.030, "Утга = сарын өгөөжийн медиан, %, сүүлийн 10 жил (сарын сүүлийн хаалтыг өмнөх сарынхтай харьцуулсан; арилжаагүй сарыг хасав). "
             "n = хамгийн олон жилийн ажиглалт.", ha="center", fontsize=8, color=MUTED)
    fig.text(0.5, 0.010, "Нэг сард 3-аас цөөн ажиглалттай бол «—». Цэнхэр = буурсан, улбар шар = өссөн. Өнгөрсөн нь ирээдүйн баталгаа биш.",
             ha="center", fontsize=8, color=MUTED)
    return _save(fig, out, "Улирлын цаг агаар — хүнсний хувьцаа аль сард өсдөг вэ?", _sub(res))


# ------------------------------------------------------------------ 8. Эзэмшлийн бүтэц
def ownership_waffle(res: Result, out: Path) -> Path:
    from matplotlib.patches import Circle
    plt = _plt()
    fig, axes = plt.subplots(2, 4, figsize=(15, 8.6))
    dark, light = "#25364f", "#b9c7dd"
    gcol = {"ӨНДӨР": BAD, "ДУНД": MID, "БАГА": GOOD}
    for ax in axes.flat:
        ax.axis("off")
        ax.set_xlim(-0.6, 10.6)
        ax.set_ylim(-2.6, 11.6)
        ax.set_aspect("equal")
    order = sorted(res.tickers, key=lambda t: -((res.r[t].get("own").big_pct) if res.r[t].get("own") else 0))
    for ax, t in zip(axes.flat, order):
        own = res.r[t].get("own")
        ax.text(0, 11.2, t, fontsize=15, fontweight="bold", color=INK, va="bottom")
        if not own:
            ax.text(5, 5, "эзэмшлийн мэдээлэл алга", ha="center", color=MUTED)
            continue
        n_big = round(own.big_pct * 100)
        for k in range(100):
            ax.add_patch(Circle((k % 10 + 0.5, 9.5 - k // 10), 0.36, fc=dark if k < n_big else light, ec="none"))
        g = (res.r[t].get("conc") or {}).get("grade", "—")
        ax.text(10, 11.2, f"төвлөрөл {g}", fontsize=9, fontweight="bold", color=gcol.get(g, MUTED), ha="right", va="bottom")
        ax.text(0, -1.0, f"●  5%-аас дээш {own.big_holders} эзэн: {own.big_pct * 100:.1f}%", fontsize=8.6, color=dark, va="center")
        ax.text(0, -1.9, f"●  {own.small_holders:,} жижиг эзэн: {own.small_pct * 100:.1f}%", fontsize=8.6, color="#7f93b3", va="center")
    fig.tight_layout(rect=(0, 0.03, 1, _top(fig)))
    as_of = max((res.r[t]["own"].as_of for t in res.tickers if res.r[t].get("own")), default=None)
    fig.text(0.5, 0.012, "Нэг цэг = нийт хувьцааны 1%. Хар = 5%-аас их хувь эзэмшигчид (шийдвэр гаргах хүч), цайвар = жижиг хувьцаа эзэмшигчид (чөлөөт эргэлт).",
             ha="center", fontsize=8, color=MUTED)
    return _save(fig, out, "Хэн хэн эзэмшдэг вэ? — 100 хувьцаа = 100 цэг", f"эзэмшлийн мэдээлэл {as_of or '—'} · " + _sub(res))


# ------------------------------------------------------------------ 8. Ашгийн гүүр
BRIDGE_SHORT = ["Нийт\nашиг", "Борл.,\nмаркет.", "Удирд.", "Санхүү", "Бусад\n(цэвэр)", "Татвар", "Бусад"]


def profit_bridge_fig(res: Result, out: Path) -> Optional[Path]:
    from .insights import BRIDGE_ITEMS
    plt = _plt()
    items = [(t, res.insights["bridge"].get(t)) for t in res.tickers]
    if not any(b for _, b in items):
        return None
    fig, axes = plt.subplots(2, 4, figsize=(16, 9))
    for ax, (t, b) in zip(axes.flat, items):
        ax.set_title(t, loc="left", fontsize=11, fontweight="bold", color=INK, pad=6)
        if not b:
            ax.text(0.5, 0.5, "өмнөх оны мөн үеийн\nтайлан алга", ha="center", va="center", color=MUTED, transform=ax.transAxes, fontsize=9)
            ax.axis("off")
            continue
        vals = [b["steps"][k] / 1e6 for k in BRIDGE_ITEMS]
        start, end = b["start"] / 1e6, b["end"] / 1e6
        run = start
        ax.bar(0, start, color=MID, width=0.62, zorder=2)
        ax.text(0, start, f"{start:,.1f}", ha="center", va="bottom" if start >= 0 else "top", fontsize=7.5, color=INK)
        for i, v in enumerate(vals, 1):
            ax.bar(i, v, bottom=run, color=GOOD if v >= 0 else BAD, width=0.62, zorder=2)
            if abs(v) >= 0.005 * max(abs(start), abs(end), 1):
                ax.text(i, run + v, f"{v:+,.1f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=7, color=INK)
            run += v
        levels = [0.0, start, end]
        acc = start
        for v in vals:
            acc += v
            levels.append(acc)
        lo, hi = min(levels), max(levels)
        pad = (hi - lo) * 0.14 or 1.0
        ax.set_ylim(lo - pad, hi + pad)
        ax.bar(len(vals) + 1, end, color=INK, width=0.62, zorder=2)
        ax.text(len(vals) + 1, end, f"{end:,.1f}", ha="center", va="bottom" if end >= 0 else "top", fontsize=7.5, color=INK)
        ax.set_xticks(range(len(vals) + 2))
        ax.set_xticklabels([b["base_label"]] + BRIDGE_SHORT + [b["label"]], fontsize=6.3, color=MUTED)
        ax.axhline(0, color=MUTED, lw=0.8)
        ax.grid(axis="y", color=GRID, lw=0.7, zorder=0)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(axis="y", labelsize=7, colors=MUTED, length=0)
    fig.tight_layout(rect=(0, 0, 1, _top(fig)), h_pad=2.4, w_pad=1.6)
    return _save(fig, out, "Ашиг яагаад өөрчлөгдсөн бэ? — ашгийн гүүр",
                 "Сүүлийн тайлангийн хуримтлагдсан цэвэр ашиг өмнөх оны мөн үеэс (тэрбум ₮) · ногоон = ашгийг нэмсэн, улаан = бууруулсан · " + _sub(res))


# ------------------------------------------------------------------ 9. Корреляци ба салбарын индекс
def correlation_fig(res: Result, out: Path) -> Optional[Path]:
    pc = res.insights.get("pricecorr") or {}
    ts = pc.get("tickers") or []
    if len(ts) < 3:
        return None
    import numpy as np
    plt = _plt()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 7.2), gridspec_kw={"width_ratios": [1.15, 1]})
    m = np.array([[np.nan if pc["corr"].get((a, b)) is None else pc["corr"][(a, b)] for b in ts] for a in ts])
    im = a1.imshow(m, cmap="RdYlGn_r", vmin=-0.6, vmax=0.6)
    a1.set_xticks(range(len(ts)))
    a1.set_xticklabels(ts, fontsize=9, color=INK)
    a1.set_yticks(range(len(ts)))
    a1.set_yticklabels(ts, fontsize=9, color=INK)
    for i in range(len(ts)):
        for j in range(len(ts)):
            if not np.isnan(m[i, j]):
                a1.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=8.5, color=INK if abs(m[i, j]) < 0.45 else "white")
    a1.set_title("Хоорондын корреляци (долоо хоногийн өгөөж, сүүлийн 52 долоо хоног)", loc="left", fontsize=10.5, fontweight="bold", color=INK, pad=10)
    for sp in a1.spines.values():
        sp.set_visible(False)
    a1.tick_params(length=0)
    fig.colorbar(im, ax=a1, fraction=0.046, pad=0.02).ax.tick_params(labelsize=8)
    rel = [(t, pc["rel"][t]) for t in ts if pc["rel"].get(t)]
    rel.sort(key=lambda x: x[1]["excess"])
    for y, (t, r) in enumerate(rel):
        a2.barh(y, r["excess"], color=GOOD if r["excess"] >= 0 else BAD, height=0.6, zorder=2)
        a2.text(max(r["excess"], 0) + 0.01, y,
                f"{r['excess'] * 100:+.0f}pp   (өөрөө {r['return'] * 100:+.0f}%, бусад {r['index'] * 100:+.0f}% · β {r['beta']:.2f})",
                va="center", ha="left", fontsize=8, color=INK)
    a2.set_yticks(range(len(rel)))
    a2.set_yticklabels([t for t, _ in rel], fontsize=9.5, color=INK, fontweight="bold")
    a2.axvline(0, color=MUTED, lw=0.9)
    lim = max([abs(r["excess"]) for _, r in rel] + [0.3])
    a2.set_xlim(-lim * 1.3, lim * 3.4)
    a2.xaxis.set_major_formatter(lambda x, _: f"{x * 100:.0f}%")
    a2.grid(axis="x", color=GRID, lw=0.7, zorder=0)
    a2.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        a2.spines[sp].set_visible(False)
    a2.tick_params(axis="x", labelsize=8, colors=MUTED, length=0)
    a2.tick_params(axis="y", length=0)
    a2.set_title("Бусад 7-гийн дунджаас илүү/дутуу (52 долоо хоногийн өгөөж)", loc="left", fontsize=10.5, fontweight="bold", color=INK, pad=10)
    fig.tight_layout(rect=(0, 0.02, 1, _top(fig)), w_pad=3)
    fig.text(0.5, 0.008, "Корреляци бага (ногоон) = хамт хөдөлдөггүй, багцыг төрөлжүүлнэ. Улаан = ижил чиглэлд хөдөлдөг. β = бусад 7-гийн дундажийн хөдөлгөөнд өөрийн хөдөлгөөний мэдрэмж.",
             ha="center", fontsize=8, color=MUTED)
    return _save(fig, out, "Аль хувьцаанууд хамт хөдөлдөг вэ? — корреляци ба салбарын индекс", _sub(res))


# ------------------------------------------------------------------ 10. Онцгой үзүүлэлтүүд
def insights_fig(res: Result, out: Path) -> Optional[Path]:
    I = res.insights
    if not I:
        return None
    plt = _plt()
    fig, axes = plt.subplots(2, 3, figsize=(16, 9.6))

    def panel(ax, title, rows, fmt, ref=None, note="", good_high=True, cap=None):
        ax.set_title(title, loc="left", fontsize=10.5, fontweight="bold", color=INK, pad=8)
        rows = [(t, v) for t, v in rows if v is not None]
        rows.sort(key=lambda x: x[1])
        if not rows:
            ax.axis("off")
            return
        for y, (t, v) in enumerate(rows):
            vv = v if cap is None else max(min(v, cap), -cap)
            ok = (v >= (ref or 0)) == good_high
            ax.barh(y, vv, color=GOOD if ok else BAD, height=0.62, zorder=2)
            ax.text(max(vv, ref or 0) + 0.015 * max(abs(x[1]) for x in rows), y, fmt(v) + (" ▸" if cap and abs(v) > cap else ""),
                    va="center", ha="left", fontsize=8, color=INK)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([t for t, _ in rows], fontsize=9, color=INK)
        ax.axvline(ref or 0, color=MUTED, lw=0.9)
        ax.grid(axis="x", color=GRID, lw=0.7, zorder=0)
        ax.set_axisbelow(True)
        lo, hi = ax.get_xlim()
        ax.set_xlim(lo - (hi - lo) * 0.05, hi + (hi - lo) * 0.22)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(axis="x", labelsize=7.5, colors=MUTED, length=0)
        ax.tick_params(axis="y", length=0)
        if note:
            ax.text(0, -0.2, note, transform=ax.transAxes, fontsize=7.6, color=MUTED, va="top")

    panel(axes[0, 0], "Ашгийн цэвэр байдал\n(нэг удаагийн/бусад зүйлийн хувь)", [(t, (I["purity"].get(t) or {}).get("share")) for t in res.tickers],
          lambda v: f"{v * 100:.0f}%", ref=0, good_high=False, cap=1.0,
          note="Татвар төлөхийн өмнөх ашгийн хэдэн хувь нь бусад орлого, ханшийн зөрүү,\nданснаас хассан олзоос ирсэн. Өндөр = ашиг үндсэн үйл ажиллагаанаас биш.")
    panel(axes[0, 1], "Өрийн үр өгөөж\n(ROA − зээлийн хүү, нэгж хувь)", [(t, (I["debt"].get(t) or {}).get("spread")) for t in res.tickers],
          lambda v: f"{v * 100:+.1f}pp", note="Эерэг = зээлсэн мөнгөөр хүүгээс илүү олж байна.\nЗээлгүй компани харагдахгүй.")
    panel(axes[0, 2], "Тобин Q\n((зах зээлийн үнэлгээ + өр) ÷ нийт хөрөнгө)", [(t, I["tobin"].get(t)) for t in res.tickers],
          lambda v: f"{v:.2f}", ref=1.0, note="1-ээс бага (ногоон) = зах зээл компанийг нийт\nхөрөнгөөс нь хямд үнэлж байна.", good_high=False)
    panel(axes[1, 0], "Бүтээн байгуулалтын индекс\n(дуусаагүй барилга ÷ үндсэн хөрөнгө)", [(t, (I["build"].get(t) or {}).get("ratio")) for t in res.tickers],
          lambda v: f"{v * 100:.1f}%", good_high=True, note="Өндөр = одоо өргөжин тэлж байна\n(ирээдүйн хүчин чадал, мөн санхүүгийн ачаалал).")
    # ашиг ба ханшийн зөрүү: хос багана
    ax = axes[1, 1]
    ax.set_title("Ханш ба ашгийн зөрүү\n(ханш 90 хоног, ашиг LTM YoY)", loc="left", fontsize=10.5, fontweight="bold", color=INK, pad=8)
    rows = [(t, I["diverge"].get(t)) for t in res.tickers if I["diverge"].get(t)]
    rows.sort(key=lambda x: (x[1]["gap"] if x[1]["gap"] is not None else -9))
    for y, (t, d) in enumerate(rows):
        pv = max(min(d["price"], 1.5), -1.5)
        ax.barh(y + 0.17, pv, height=0.32, color=MID, zorder=2)
        ax.text(max(pv, 0) + 0.04, y + 0.17, f"ханш {d['price'] * 100:+.0f}%", va="center", ha="left", fontsize=7.4, color=INK)
        if d["earn"] is not None:
            ev = max(min(d["earn"], 1.5), -1.5)
            ax.barh(y - 0.17, ev, height=0.32, color=ORANGE, zorder=2)
            ax.text(max(ev, 0) + 0.04, y - 0.17, f"ашиг {d['earn'] * 100:+.0f}%" + (" ▸" if abs(d["earn"]) > 1.5 else ""), va="center",
                    ha="left", fontsize=7.4, color=INK)
        else:
            ax.text(0, y - 0.17, " ашиг: суурь ≤ 0", va="center", fontsize=7.4, color=MUTED, style="italic")
        if d["verdict"] and d["verdict"] != "нийцэж байна":
            ax.text(1.0, y, d["verdict"], transform=ax.get_yaxis_transform(), va="center", ha="right", fontsize=7.6,
                    color=BAD if d["verdict"] == "ханш түрүүлсэн" else GOOD, fontweight="bold")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([t for t, _ in rows], fontsize=9, color=INK)
    ax.axvline(0, color=MUTED, lw=0.9)
    ax.set_xlim(-1.7, 3.0)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x * 100:.0f}%")
    ax.grid(axis="x", color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="x", labelsize=7.5, colors=MUTED, length=0)
    ax.tick_params(axis="y", length=0)
    ax.text(0, -0.2, "Ханш ашгаас 25pp-аас илүү түрүүлсэн = «ханш түрүүлсэн»\n(халсан байж магадгүй); хоцорсон = ашиг ханшид шингээгүй.",
            transform=ax.transAxes, fontsize=7.6, color=MUTED, va="top")
    # зургаа дахь самбар: уншиж ойлгох заавар
    ax = axes[1, 2]
    ax.axis("off")
    ax.text(0, 1, "Яаж унших вэ", fontsize=10.5, fontweight="bold", color=INK, va="top")
    ax.text(0, 0.9, "• Ашгийн цэвэр байдал өндөр + Тобин Q бага\n   → ашиг «нэг удаагийнх» байж болзошгүй, анхаар.\n\n"
                    "• Өрийн үр өгөөж сөрөг + бүтээн байгуулалт өндөр\n   → өргөжилт өрөөр санхүүждэг, ашиг нь хараахан гараагүй.\n\n"
                    "• Ханш түрүүлсэн + ашгийн цэвэр байдал муу\n   → ханш ашгаас илүү «мэдээлэл»-ээр хөдөлсөн.\n\n"
                    "• Ханш хоцорсон + өрийн үр өгөөж эерэг\n   → ашиг өсөж байгаа ч ханш хараахан тусгаагүй.",
            fontsize=9, color=INK, va="top", linespacing=1.5)
    fig.tight_layout(rect=(0, 0.02, 1, _top(fig)), h_pad=5.5, w_pad=3.2)
    return _save(fig, out, "Онцгой үзүүлэлтүүд — ашгийн чанар, өр, үнэлгээ, өргөжилт, ханшийн зөрүү", _sub(res))


# ------------------------------------------------------------------ бүгдийг үүсгэх
def build(res: Result, out_dir: Path) -> list[Path]:
    d = Path(out_dir)
    made: list[Optional[Path]] = [
        annual_trend(res, d / "annual.png"),
        compare_figure(res, "half", d / "halfyear.png"),
        cost_1000(res, d / "cost_1000.png"),
        price_tags(res, d / "price_tags.png"),
        health_check(res, d / "health_check.png"),
        seasonality(res, d / "seasonality.png"),
        ownership_waffle(res, d / "ownership.png"),
        profit_bridge_fig(res, d / "profit_bridge.png"),
        correlation_fig(res, d / "correlation.png"),
        insights_fig(res, d / "insights.png"),
    ]
    from . import infographics2
    made += infographics2.build(res, d)
    return [p for p in made if p]
