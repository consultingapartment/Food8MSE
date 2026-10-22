"""Нэмэлт 17 онцгой үзүүлэлтийн инфографик (3 зураг): `insights2.py`-ийн үр дүнг самбар болгон харуулна."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from .charts import BAD, BAR, GOOD, GRID, INK, MID, MUTED
from .engine import Result
from .infographics import ORANGE, _plt, _save, _sub, _top


def _style(ax, xlim_pad: float = 0.25) -> None:
    ax.axvline(0, color=MUTED, lw=0.9)
    ax.grid(axis="x", color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo - (hi - lo) * 0.04, hi + (hi - lo) * xlim_pad)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="x", labelsize=7.5, colors=MUTED, length=0)
    ax.tick_params(axis="y", length=0)


def _title(ax, text: str) -> None:
    ax.set_title(text, loc="left", fontsize=10.5, fontweight="bold", color=INK, pad=8)


def _missing(ax, tickers: list[str], why: str) -> None:
    if tickers:
        ax.text(0, -0.2, f"Тооцогдоогүй: {', '.join(tickers)} ({why})", transform=ax.transAxes, fontsize=7.4, color=MUTED, va="top",
                style="italic")


def panel(ax, title: str, rows: list[tuple[str, Optional[float], str]], *, ref: float = 0.0, good_high: Optional[bool] = True,
          cap: Optional[float] = None, note: str = "", why: str = "өгөгдөл дутуу", all_tickers: Optional[list[str]] = None,
          fmt: Optional[Callable[[float], str]] = None, xpad: float = 0.25) -> None:
    """Хэвтээ баганан самбар. rows = (тикер, утга, шошго). good_high=None бол ногоон/улаан биш (саарал-цэнхэр)."""
    _title(ax, title)
    have = [(t, v, s) for t, v, s in rows if v is not None]
    miss = [t for t in (all_tickers or [r[0] for r in rows]) if t not in {x[0] for x in have}]
    if not have:
        ax.axis("off")
        ax.text(0, 0.5, "өгөгдөл алга", color=MUTED, transform=ax.transAxes)
        return
    have.sort(key=lambda x: x[1])
    span = max(abs(v) for _, v, _ in have) or 1.0
    for y, (t, v, s) in enumerate(have):
        vv = v if cap is None else max(min(v, cap), -cap)
        color = BAR if good_high is None else (GOOD if (v >= ref) == good_high else BAD)
        ax.barh(y, vv - ref, left=ref, color=color, height=0.62, zorder=2)
        ax.text(max(vv, ref) + 0.02 * span, y, s + (" ▸" if cap is not None and abs(v) > cap else ""), va="center", ha="left",
                fontsize=7.8, color=INK)
    ax.set_yticks(range(len(have)))
    ax.set_yticklabels([t for t, _, _ in have], fontsize=9, color=INK)
    _style(ax, xpad)
    if ref:
        ax.axvline(ref, color=MUTED, lw=0.9)
    if fmt:
        ax.xaxis.set_major_formatter(lambda x, _: fmt(x))
    if note:
        ax.text(0, -0.2 if not miss else -0.3, note, transform=ax.transAxes, fontsize=7.6, color=MUTED, va="top")
    _missing(ax, miss, why)


def pair_panel(ax, title: str, rows: list[tuple[str, Optional[float], Optional[float]]], names: tuple[str, str], *, cap: float = 1.0,
               note: str = "", why: str = "өгөгдөл дутуу", all_tickers: Optional[list[str]] = None) -> None:
    """Хос баганан самбар (хувиар): тикер бүрт хоёр утга."""
    _title(ax, title)
    have = [r for r in rows if r[1] is not None or r[2] is not None]
    miss = [t for t in (all_tickers or [r[0] for r in rows]) if t not in {x[0] for x in have}]
    if not have:
        ax.axis("off")
        ax.text(0, 0.5, "өгөгдөл алга", color=MUTED, transform=ax.transAxes)
        return
    for y, (t, a, b) in enumerate(have):
        for off, v, col in ((0.17, a, MID), (-0.17, b, ORANGE)):
            if v is None:
                continue
            vv = max(min(v, cap), -cap)
            ax.barh(y + off, vv, height=0.32, color=col, zorder=2)
            ax.text(max(vv, 0) + 0.02 * cap, y + off, f"{v * 100:+.0f}%" + (" ▸" if abs(v) > cap else ""), va="center", ha="left",
                    fontsize=7.4, color=INK)
    ax.set_yticks(range(len(have)))
    ax.set_yticklabels([t for t, _, _ in have], fontsize=9, color=INK)
    _style(ax, 0.3)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x * 100:.0f}%")
    ax.barh([], [])
    ax.legend(handles=[plt_patch(MID, names[0]), plt_patch(ORANGE, names[1])], fontsize=7.4, frameon=False, loc="upper right",
              bbox_to_anchor=(1.0, -0.09), ncol=2, borderaxespad=0.0, handlelength=1.2, columnspacing=1.0)
    if note:
        ax.text(0, -0.2 if not miss else -0.3, note, transform=ax.transAxes, fontsize=7.6, color=MUTED, va="top")
    _missing(ax, miss, why)


def plt_patch(color: str, label: str):
    from matplotlib.patches import Patch
    return Patch(color=color, label=label)


def _guide(ax, title: str, text: str) -> None:
    ax.axis("off")
    ax.text(0, 1, title, fontsize=10.5, fontweight="bold", color=INK, va="top")
    ax.text(0, 0.9, text, fontsize=8.4, color=INK, va="top", linespacing=1.45)


def _fig(res: Result):
    plt = _plt()
    fig, axes = plt.subplots(2, 3, figsize=(16, 9.4))
    return fig, axes


def _finish(fig, out: Path, title: str, res: Result) -> Path:
    fig.tight_layout(rect=(0, 0.02, 1, _top(fig)), h_pad=6.0, w_pad=3.2)
    return _save(fig, out, title, _sub(res))


# ------------------------------------------------------------------ А. Үнэлгээний нөөц, ханшийн эрсдэл
def valuation_safety(res: Result, out: Path) -> Path:
    I, T = res.insights2, res.tickers
    fig, axes = _fig(res)
    g = lambda k, f: [(t, *f(I[k].get(t))) for t in T]           # noqa: E731

    def liq(d):
        return (d["ratio"], f"{d['ratio']:.1f}×") if d and d.get("ratio") is not None else (None, "")
    panel(axes[0, 0], "Татан буулгах өртөг\n(ханш ÷ хувьцаанд ногдох татан буулгах өртөг)", g("liq", liq), ref=1.0, good_high=False, cap=8,
          all_tickers=T, why="татан буулгах цэвэр өртөг сөрөг",
          note="Хөрөнгийг хасалттайгаар (мөнгө 100%, авлага 80%, бараа 60%, үндсэн хөрөнгө 50%)\nзарж өрөө төлсний дараах үлдэгдэл. 1-ээс бага = ханш түүнээс доогуур.")

    def res_(d):
        return (None, "") if not d or d.get("years") is None else (min(d["years"], 40), f"{d['years']:.1f} жил · төлөлт {d['payout'] * 100:.0f}%"
                                                                    if d.get("payout") is not None else f"{d['years']:.1f} жил")
    panel(axes[0, 1], "Ногдол ашгийн нөөц\n(хуримтлагдсан ашиг ÷ жилийн ногдол ашиг)", g("divres", res_), good_high=True, cap=40, all_tickers=T,
          note="Ногдол ашгийг одоогийн түвшинд хэдэн жил хуримтлагдсан ашгаасаа\nтөлж чадах вэ. Урт = нөөц зузаан.")

    def dd(d):
        return (None, "") if not d else (d["dd"], f"{d['dd'] * 100:.1f}% · {d['under_days']} хоног")
    panel(axes[0, 2], "Оргилоос буурсан хэмжээ\n(сүүлийн 12 сар; «усан доор» хоног)", g("drawdown", dd), good_high=True, all_tickers=T,
          note="0% = одоо оргил дээр. Урт «усан доор» = оргилдоо удаан хүрээгүй.", fmt=lambda x: f"{x * 100:.0f}%")

    def erp(d):
        if not d or d.get("earn_prem") is None:
            return None, ""
        dv = "" if d.get("div_prem") is None else f" · ногдол {d['div_prem'] * 100:+.1f}pp"
        return d["earn_prem"], f"ашиг {d['earn_prem'] * 100:+.1f}pp{dv}"
    panel(axes[1, 0], "Хувьцааны эрсдэлийн шагнал\n(ашгийн өгөөж − 14% хадгаламж)", g("erp", erp), good_high=True, all_tickers=T,
          note="Ашгийн өгөөж = LTM цэвэр ашиг ÷ зах зээлийн үнэлгээ. Сөрөг = банкны\nхадгаламж хувьцаанаас илүү өгөөжтэй.", fmt=lambda x: f"{x * 100:.0f}pp")

    def nc(d):
        return (None, "") if not d else (d["ratio"], f"{d['ratio'] * 100:+.0f}%")
    panel(axes[1, 1], "Цэвэр бэлэн мөнгө ÷ зах зээлийн үнэлгээ\n((мөнгө − хүүтэй өр) ÷ үнэлгээ)", g("netcash", nc), good_high=True, cap=1.0,
          all_tickers=T, note="Эерэг = үнийн хэдэн хувийг цэвэр мөнгө бүрдүүлж байна.\nСөрөг = хувьцаа өрөөр «тэжээгдсэн».", fmt=lambda x: f"{x * 100:.0f}%")

    rows = []
    for t in T:
        d = I["implied"].get(t)
        rows.append((t, d.get("implied") if d else None, d.get("actual") if d else None))
    pair_panel(axes[1, 2], "Зах зээлийн суулгасан ба бодит өсөлт\n(ашиг, жилийн %)", rows, ("суулгасан (15%)", "бодит (3 жил CAGR)"),
               cap=1.0, all_tickers=T, why="алдагдалтай",
               note="Суулгасан өсөлт нь бодит өсөлтөөс бага бол зах зээл өсөлтийг\nдутуу үнэлж байна (эсрэгээр бол халуун).")
    return _finish(fig, out, "Онцгой үзүүлэлт (2) — үнэлгээний нөөц, ногдол ашиг, ханшийн эрсдэл", res)


# ------------------------------------------------------------------ Б. Ашгийн чанар, үйл ажиллагааны эрсдэл
def earnings_quality(res: Result, out: Path) -> Path:
    I, T = res.insights2, res.tickers
    fig, axes = _fig(res)
    g = lambda k, f: [(t, *f(I[k].get(t))) for t in T]           # noqa: E731

    def bn(d):
        return (None, "") if not d else (d["m"], f"M {d['m']:.2f}" + (" ⚠" if d["flags"] else ""))
    panel(axes[0, 0], "Тайлангийн найдвартай байдал\n(Beneish M, хялбаршуулсан; хэт их = ашиг «гоёсон»)", g("beneish", bn), ref=-1.78, good_high=False,
          all_tickers=T, why="өмнөх оны мөн үеийн тайлан байхгүй",
          note="−1.78-аас дээш = анхаарах. ⚠ = авлага, нийт ашгийн маржин, хөрөнгийн чанар,\nборлуулалтын өсөлт, өрийн ачаалал аль нэг нь босго давсан.")

    def dol(d):
        if not d:
            return None, ""
        if d.get("ltm"):
            return d["ltm"]["dol"], f"{d['ltm']['dol']:.1f}× (LTM)"
        return (d["hist"], f"{d['hist']:.1f}× (түүхэн)") if d.get("hist") is not None else (None, "")
    panel(axes[0, 1], "Үйл ажиллагааны хөшүүрэг\n(EBIT-ийн % өөрчлөлт ÷ борлуулалтын % өөрчлөлт)", g("dol", dol), ref=1.5, good_high=False, cap=5,
          all_tickers=T, note="Борлуулалт 1% өөрчлөгдөхөд ашиг хэдэн хувиар хөдөлдөг. 1.5-аас\nдээш = тогтмол зардал их, борлуулалт унавал ашиг хурдан унана.")

    def st(d):
        return (None, "") if not d or d.get("sticky") is None else (d["sticky"], f"{d['sticky']:+.2f}")
    panel(axes[0, 2], "Зардлын «наалдамхай» байдал\n(өсөхөд хариу − буурахад хариу)", g("sticky", st), good_high=False, cap=2.5, all_tickers=T,
          why="борлуулалт буурсан үе байхгүй",
          note="Эерэг = борлуулалт буурахад зардал дагаж буурдаггүй (ашиг хурдан муудна).\nСөрөг = зардлаа хурдан тохируулдаг.")

    def tg(d):
        return (None, "") if not d else (d["gap"], f"{d['effective'] * 100:.1f}% vs хууль {d['statutory'] * 100:.1f}%")
    panel(axes[1, 0], "Татварын бодит ба хуулийн хувийн зөрүү\n(pp)", g("taxgap", tg), good_high=None, all_tickers=T, why="алдагдалтай/тайлан дутуу",
          note="Хуулийн хувь = ААНОАТ 10% / 25% (6 тэрбум ₮ хүртэл 10%).\nЗөрүү их = хойшлогдсон татвар, хасагдах зардал, ашгийн чанарыг шалгах.", fmt=lambda x: f"{x * 100:.0f}pp")

    def gs(d):
        if not d:
            return None, ""
        sd = "" if d.get("margin_sd") is None else f" · σ {d['margin_sd'] * 100:.1f}pp"
        return d["streak"], f"{d['streak']} үе{sd}"
    panel(axes[1, 1], "Ашгийн өсөлтийн цуваа\n(дараалан өмнөх оноос өссөн үе; σ = маржины хэлбэлзэл)", g("streak", gs), good_high=True, all_tickers=T,
          note="Үе = тухайн компанийн тайлангийн давтамж (улирал/хагас жил/жил).\nσ бага = ашгийн маржин тогтвортой.")

    def sf(d):
        if not d or d.get("forecast") is None or not d.get("prev_fy"):
            return None, ""
        ch = d["forecast"] / d["prev_fy"] - 1
        return ch, f"{d['forecast'] / 1e6:,.1f} тэр.₮ ({ch * 100:+.0f}%)" + (" ✓" if d["done"] else "")
    panel(axes[1, 2], "Улирлын нөлөөтэй жилийн ашгийн таамаг\n(өмнөх жилтэй харьцуулсан %)", g("season", sf), good_high=True, cap=2.0, all_tickers=T,
          why="түүхэн өгөгдөл дутуу / алдагдалтай",
          note="Одоогийн хуримтлалыг өмнөх жилүүдийн улирлын хуваарилалтаар жилчилсэн.\n✓ = жилийн эцсийн бодит ашиг.", fmt=lambda x: f"{x * 100:.0f}%")
    return _finish(fig, out, "Онцгой үзүүлэлт (3) — ашгийн чанар, үйл ажиллагааны эрсдэл, таамаг", res)


# ------------------------------------------------------------------ В. Өсөлт, өр, хариу
def growth_and_reaction(res: Result, out: Path) -> Path:
    I, T = res.insights2, res.tickers
    fig, axes = _fig(res)
    g = lambda k, f: [(t, *f(I[k].get(t))) for t in T]           # noqa: E731

    def rt(d):
        return (None, "") if not d else (d["ratio"], f"{d['ratio']:.2f}₮ ({d['years']:.1f} жил)")
    panel(axes[0, 0], "Нэг ₮ хуримтлуулсан ашгийн үр дүн\n(зах зээлийн үнэлгээний өсөлт ÷ хуримтлагдсан ашиг)", g("retention", rt), ref=1.0,
          good_high=True, cap=2.5, all_tickers=T, why="ханш/өгөгдөл дутуу",
          note="Хуримтлуулсан 1₮ ашиг тутамд зах зээлийн үнэлгээ хэдэн ₮-өөр өссөн.\n1-ээс бага = ашгийг дахин хөрөнгө оруулахад үнэ цэнэ нэмсэнгүй.")

    rows = []
    for t in T:
        d = I["sustain"].get(t)
        rows.append((t, d.get("sustainable") if d else None, d.get("actual") if d else None))
    pair_panel(axes[0, 1], "Өөрийн хөрөнгөөр хангагдах өсөлт ба бодит өсөлт\n(ROE × (1 − ногдол ашгийн хувь) vs борлуулалтын өсөлт)", rows,
               ("хангагдах", "бодит борлуулалт"), cap=1.0, all_tickers=T,
               note="Бодит өсөлт хангагдах өсөлтөөс өндөр = зөрүүг өр, санхүүжилтээр хаасан.")

    def wc(d):
        if not d or d.get("nwc_growth") is None:
            return None, ""
        gap = d["nwc_growth"] - d["rev_growth"]
        return gap, f"{d['nwc_growth'] * 100:+.0f}% / {d['rev_growth'] * 100:+.0f}%"
    panel(axes[0, 2], "Эргэлтийн хөрөнгийн ачаалал\n(NWC өсөлт − борлуулалтын өсөлт, pp)", g("wcap", wc), good_high=False, cap=1.5, all_tickers=T,
          why="өгөгдөл дутуу",
          note="Шошго: NWC өсөлт / борлуулалтын өсөлт.\nNWC = бараа + авлага − өглөг. Эерэг = мөнгө гацсан.", fmt=lambda x: f"{x * 100:.0f}pp", xpad=0.5)

    def dw(d):
        if not d:
            return None, ""
        if d.get("debt_free"):
            return 0.0, "зээлгүй"
        return d["share"], f"{d['share'] * 100:.0f}% · хаах чадвар " + ("—" if d["cover"] is None else f"{d['cover']:.1f}×")
    panel(axes[1, 0], "Богино хугацаат өрийн хана\n(богино өр ÷ нийт зээл)", g("wall", dw), good_high=False, all_tickers=T,
          note="Хаах чадвар = (мөнгө + авлага) ÷ богино өр. 1-ээс бага бол\nбогино өрийг хөрвөх хөрөнгөөр хаах боломжгүй.",
          fmt=lambda x: f"{x * 100:.0f}%", xpad=0.9)

    # тайлангийн дараах ханшийн хариу: гэнэтийн зөрүү (ашгийн YoY) ↔ салбараас илүү/дутуу өгөөж
    ax = axes[1, 1]
    _title(ax, "Тайлангийн дараах ханшийн хариу\n(ашгийн YoY ↔ ханш салбараас илүү/дутуу, ±14 хоног)")
    pts = []
    for t in T:
        d = I["reaction"].get(t)
        if not d:
            continue
        for e in d["events"]:
            if e["surprise"] is not None and e["excess"] is not None:
                pts.append((t, max(min(e["surprise"], 1.0), -1.0), e["excess"], e["estimated"]))
    if pts:
        for t, x, y, est in pts:
            ok = (x > 0) == (y > 0)
            ax.scatter([x], [y], s=34, color=GOOD if ok else BAD, alpha=0.75, zorder=3, marker="o" if not est else "D")
        ax.axhline(0, color=MUTED, lw=0.9)
        ax.axvline(0, color=MUTED, lw=0.9)
        ax.grid(color=GRID, lw=0.7, zorder=0)
        ax.xaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")
        ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")
        ax.tick_params(labelsize=7.5, colors=MUTED)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        hits = [f"{t} {I['reaction'][t]['hit'] * 100:.0f}%" for t in T if I["reaction"].get(t) and I["reaction"][t].get("hit") is not None]
        ax.text(0, -0.2, "Ногоон = ханш ашгийн чиглэлд хариу өгсөн. Алмаз = зарлагдсан\nогноо тодорхойгүй (тооцоолсон). Чиглэл таарсан хувь:\n" + ", ".join(hits[:4]) + "\n" + ", ".join(hits[4:]),
                transform=ax.transAxes, fontsize=7.6, color=MUTED, va="top")
    else:
        ax.axis("off")
        ax.text(0, 0.5, "өгөгдөл алга", color=MUTED, transform=ax.transAxes)

    _guide(axes[1, 2], "Яаж унших вэ",
           "• Үр дүн < 1 + хангагдах өсөлт бага\n   → ашгаа дахин хөрөнгө оруулахад үр ашиг муу.\n\n"
           "• Эргэлтийн хөрөнгийн ачаалал өндөр + богино өрийн\n   хана өндөр → бэлэн мөнгө гацсан, өр дахин санхүүжих\n   шаардлагатай, эрсдэл өндөр.\n\n"
           "• Ханшийн хариу ашгийн чиглэлд тогтмол таарвал\n   тайлан ханшид хурдан шингэдэг; таарахгүй бол\n   мэдээлэл ханшид урьдчилан шингэсэн.\n\n"
           "• Бүх харьцаа нийтэд ил тайлан, ханшийн түүхөөс.")
    return _finish(fig, out, "Онцгой үзүүлэлт (4) — өсөлтийн санхүүжилт, өр, тайлангийн дараах ханшийн хариу", res)


def build(res: Result, out_dir: Path) -> list[Path]:
    d = Path(out_dir)
    if not res.insights2:
        return []
    return [valuation_safety(res, d / "insights2_valuation.png"),
            earnings_quality(res, d / "insights3_quality.png"),
            growth_and_reaction(res, d / "insights4_growth.png")]
