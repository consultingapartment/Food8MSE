"""Шинжилгээний үр дүнг Excel (`reports/FOOD analysis.xlsx`) болгон бичнэ. Тооцоолсон утгыг шууд бичнэ
(томьёо биш): компани бүрийн томьёотой харьцааг `FOOD mse.xlsx`-ийн sheet-үүдээс үзнэ."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference, ScatterChart, Series
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.worksheet import Worksheet

from .config import LABELS
from .engine import Result
from .fundamentals import COLUMNS, DUPONT_COLUMNS
from .narrative import summarize
from .technical import TIMEFRAMES

FMT = {"pct": "0.0%;[Red]-0.0%", "x": '0.00"x"', "money": "#,##0;[Red]-#,##0", "bn": "#,##0.0;[Red]-#,##0.0",
       "days": "0", "n1": "0.0", "n2": "0.00", "int": "#,##0", "pts": "0.0", "date": "yyyy-mm-dd", None: "General"}
PALETTE = ["1F77B4", "FF7F0E", "2CA02C", "D62728", "9467BD", "8C564B", "E377C2", "7F7F7F"]
NAVY, LIGHT, GREY = "1F3864", "D9E2F3", "F2F2F2"
THIN = Side(style="thin", color="BFBFBF")
RATING_FILL = {"ХУДАЛДАН АВАХ": "C6EFCE", "ХАДГАЛАХ": "FFEB9C", "ЗАРАХ": "FFC7CE",
               "ӨНДӨР": "FFC7CE", "ДУНД": "FFEB9C", "БАГА": "C6EFCE"}


class Sheet:
    """Мөр мөрөөр бичих туслах."""

    def __init__(self, wb: Workbook, title: str, widths: Optional[list[float]] = None, tab: str | None = None):
        self.ws: Worksheet = wb.create_sheet(title[:31])
        self.row = 1
        if tab:
            self.ws.sheet_properties.tabColor = tab
        for i, w in enumerate(widths or [], 1):
            self.ws.column_dimensions[get_column_letter(i)].width = w
        self.ws.sheet_view.showGridLines = False
        self.ws.page_setup.orientation = "landscape"
        self.ws.page_setup.fitToWidth, self.ws.page_setup.fitToHeight = 1, 0
        self.ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)

    def title(self, text: str, sub: str | None = None):
        c = self.ws.cell(self.row, 1, text)
        c.font = Font(bold=True, size=14, color=NAVY)
        self.row += 1
        if sub:
            self.note(sub)

    def h2(self, text: str):
        self.row += 1
        c = self.ws.cell(self.row, 1, text)
        c.font = Font(bold=True, size=11, color="FFFFFF")
        for col in range(1, 13):
            self.ws.cell(self.row, col).fill = PatternFill("solid", fgColor=NAVY)
        self.row += 1

    def note(self, text: str, cols: int = 12, height: float | None = None):
        c = self.ws.cell(self.row, 1, text)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.font = Font(color="404040")
        self.ws.merge_cells(start_row=self.row, start_column=1, end_row=self.row, end_column=cols)
        self.ws.row_dimensions[self.row].height = height or max(15.0, 15.0 * (len(text) // 150 + 1))
        self.row += 1

    def table(self, headers: list[str], rows: list[list[Any]], fmts: list[Optional[str]] | None = None,
              fills: dict[int, dict[str, str]] | None = None) -> tuple[int, int]:
        """(толгойн мөр, сүүлийн мөр). `fills`: {багана(0-based): {утга: өнгө}}."""
        head = self.row
        for j, h in enumerate(headers, 1):
            c = self.ws.cell(head, j, h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor=NAVY)
            c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
        self.ws.row_dimensions[head].height = 45
        self.row += 1
        for i, vals in enumerate(rows):
            for j, v in enumerate(vals, 1):
                c = self.ws.cell(self.row, j, v)
                f = fmts[j - 1] if fmts and j - 1 < len(fmts) else None
                if f and isinstance(v, (int, float)):
                    c.number_format = FMT.get(f, f)
                c.border = Border(bottom=THIN)
                if i % 2:
                    c.fill = PatternFill("solid", fgColor=GREY)
                if isinstance(v, str) and len(v) > 40:
                    c.alignment = Alignment(wrap_text=True, vertical="top")
                if fills and (j - 1) in fills and v in fills[j - 1]:
                    c.fill = PatternFill("solid", fgColor=fills[j - 1][v])
                    c.font = Font(bold=True)
            self.row += 1
        return head, self.row - 1

    def blank(self, n: int = 1):
        self.row += n


def _fmt_for(kind: str) -> str:
    return {"x": "x", "pct": "pct", "money": "money", "days": "days"}.get(kind, "n2")


def build(res: Result, out: Path, images: list[Path] | None = None) -> Path:
    wb = Workbook()
    wb.remove(wb.active)
    T = res.tickers
    R = res.r
    _summary(wb, res)
    _scores(wb, res)
    _ratios(wb, res)
    _ratio_history(wb, res)
    _dupont(wb, res)
    _trends(wb, res)
    _latest(wb, res)
    _insights(wb, res)
    _insights2(wb, res)
    _breakdown(wb, res)
    _risk(wb, res)
    _valuation(wb, res)
    _graham(wb, res)
    _valuation2(wb, res)
    _ownership(wb, res)
    _forecast(wb, res)
    if any(R[t]["tech"] for t in T):
        _technical(wb, res)
    if images:
        _gallery(wb, images)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def _gallery(wb, images: list[Path]) -> None:
    """Инфографик хуудас: зураг бүрийг дарааллаар нь доош байрлуулна."""
    from openpyxl.drawing.image import Image as XLImage
    ws = wb.create_sheet("Инфографик")
    ws.sheet_properties.tabColor = "1F3864"
    ws.sheet_view.showGridLines = False
    ws["A1"] = "ИНФОГРАФИК — бүх компанийн харьцуулалт (шинжилгээний үр дүнгээр автоматаар гарсан)"
    ws["A1"].font = Font(bold=True, size=13)
    row = 3
    for p in images:
        img = XLImage(str(p))
        k = 1300 / img.width
        img.width, img.height = int(img.width * k), int(img.height * k)
        ws.add_image(img, f"A{row}")
        row += int(img.height / 20) + 3


# ------------------------------------------------------------------ 1. Дүгнэлт
def _summary(wb, res: Result):
    s = Sheet(wb, "Дүгнэлт", [22, 13, 12, 12, 12, 10, 12, 10, 9, 9, 13, 10, 16], "1F3864")
    s.title("НЭГДСЭН ДҮГНЭЛТ — ХҮНС, УНДААНЫ САЛБАРЫН 8 ХК")
    last = max(c.latest.end_date for c in res.companies.values())
    s.note(f"Тооцоолсон огноо: {res.today}. Сүүлийн тайлан: {last}. Ханшийн сүүлийн өгөгдөл: {res.as_of_prices or '—'}. "
           f"Орлого, ашиг нь сүүлийн 12 сар (LTM). Хадгаламжийн хүү {res.assumptions.deposit_rate:.0%}, "
           f"ногдол ашгийн шаардах өгөөж {res.assumptions.target_yield:.0%}. Энэ нь хөрөнгө оруулалтын зөвлөгөө биш.", 13)
    rows = []
    for t in sorted(res.tickers, key=lambda t: -(res.r[t]["score"]["total"] or -1)):
        r = res.r[t]
        rt, v, sc = r["ratios"], r["val"], r["score"]
        rev, _ = r["company"].flow(r["company"].latest, "revenue")
        rows.append([f"{t} ({r['name']})", r["company"].latest.period.label, None if rev is None else rev / 1e6,
                     rt.get("revenue_yoy"), rt.get("net_margin"), rt.get("roe"), rt.get("current_ratio"),
                     rt.get("debt_to_equity"), v.pe if v else None, v.pb if v else None,
                     v.real_discount if v else None, sc["total"], sc["rating"]])
    s.h2("НЭГДСЭН СКОРКАРД")
    s.table(["Компани", "Сүүлийн\nтайлан", "Орлого\n(тэрбум ₮)", "Орлогын\nөсөлт YoY", "Цэвэр ашгийн\nмаржин", "ROE",
             "Хөрвөх чадвар\n(Current)", "Өр/Өмч", "P/E", "P/B", "Бодит\nхямдрал", "Нийт оноо\n/100", "Зөвлөмж"],
            rows, [None, None, "bn", "pct", "pct", "pct", "x", "x", "n1", "n2", "pct", "pts", None],
            fills={12: RATING_FILL})
    s.h2("КОМПАНИ БҮРЭЭР ДҮГНЭЛТ")
    for t in res.tickers:
        for i, line in enumerate(summarize(t, res.r[t], res.assumptions)):
            c = s.ws.cell(s.row, 1, line)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if i == 0:
                c.font = Font(bold=True, color=NAVY)
            s.ws.merge_cells(start_row=s.row, start_column=1, end_row=s.row, end_column=13)
            s.ws.row_dimensions[s.row].height = 16 * (len(line) // 170 + 1)
            s.row += 1
        s.row += 1
    if res.warnings:
        s.h2("ӨГӨГДЛИЙН АНХААРУУЛГА")
        for w in res.warnings:
            s.ws.cell(s.row, 1, "• " + w)
            s.row += 1
    s.ws.freeze_panes = "A3"


# ------------------------------------------------------------------ 2. Оноо
def _scores(wb, res: Result):
    s = Sheet(wb, "Оноо", [30] + [13] * 9, "2F5597")
    s.title("100 ОНООНЫ ҮНЭЛГЭЭ", "Хэсэг бүр 0–100 оноотой, жингээр нь нэгтгэнэ. Тооцох боломжгүй хэсгийн жинг бусад хэсэгт нормчилно. "
           f"Зөвлөмж: ≥{res.assumptions.rating_buy:.0f} ХУДАЛДАН АВАХ, ≥{res.assumptions.rating_hold:.0f} ХАДГАЛАХ, бусад ЗАРАХ.")
    keys = list(res.weights._order)
    rows = []
    for k in keys:
        rows.append([LABELS[k], getattr(res.weights, k)] + [res.r[t]["score"]["components"].get(k) for t in res.tickers])
    rows.append(["НИЙТ ОНОО", sum(getattr(res.weights, k) for k in keys)] + [res.r[t]["score"]["total"] for t in res.tickers])
    rows.append(["Зөвлөмж", ""] + [res.r[t]["score"]["rating"] for t in res.tickers])
    s.blank()
    h, e = s.table(["Хэсэг", "Жин"] + res.tickers, rows, [None, "int"] + ["pts"] * len(res.tickers))
    for j in range(len(res.tickers)):
        c = s.ws.cell(e, 3 + j)
        c.fill = PatternFill("solid", fgColor=RATING_FILL.get(c.value, "FFFFFF"))
        c.font = Font(bold=True)
    s.blank()
    s.h2("ОНОО БҮРЭЛДЭХ ДҮРЭМ")
    for line in [
        "Ашигт ажиллагаа: ROE (0→20%), цэвэр ашгийн маржин (0→15%), ROA (0→10%)-ийн дундаж.",
        "Өсөлт: орлогын YoY (−10%→+20%), цэвэр ашгийн YoY (−30%→+30%), орлогын CAGR (0→20%).",
        "Хөрвөх ба төлбөрийн чадвар: эргэлтийн хөрөнгийн харьцаа (0.8→2.0), өр/өмч (1.5→0.3), хүүгийн нөхөх чадвар (1→8; хүүгүй бол 100).",
        "Эрсдэл ба чанар: Altman Z (1.81→2.99), Piotroski F (7 шалгуурын хэд нь биелсэн).",
        "Үнэлгээ: хямдралын нэгдсэн оноо (Graham 35%, Ногдол 25%, P/E 20%, P/B 20%). Ногдол ашиг: ногдлын өгөөжийн оноо.",
        "Зах зээлийн хөрвөх чадвар: чөлөөт эргэлт (5%→25%), сүүлийн 90 хоногийн арилжаатай өдөр (0→45).",
    ]:
        s.ws.cell(s.row, 1, line)
        s.row += 1
    s.blank()
    ch = BarChart()
    ch.type, ch.title, ch.height, ch.width = "col", "Нийт оноо", 8, 16
    ch.add_data(Reference(s.ws, min_col=3, max_col=2 + len(res.tickers), min_row=e - 1, max_row=e - 1), from_rows=True)
    ch.set_categories(Reference(s.ws, min_col=3, max_col=2 + len(res.tickers), min_row=h))
    ch.legend = None
    s.ws.add_chart(ch, f"A{s.row + 1}")


# ------------------------------------------------------------------ 3. Харьцаа
def _ratios(wb, res: Result):
    s = Sheet(wb, "Харьцаа", [52] + [13] * 8, "2F5597")
    s.title("ХАРЬЦААНЫ ШИНЖИЛГЭЭ — СҮҮЛИЙН ТАЙЛАН", "Орлогын мөрийг сүүлийн 12 сараар (LTM, дутуу бол жилчилсэн), дундаж үлдэгдлийг өмнөх оны эцэс ба "
           "одоогийн дундажаар тооцсон. Хоосон нүд = тооцох өгөгдөл/утга байхгүй.")
    s.blank()
    rows = [["Тайлан"] + [res.r[t]["company"].latest.period.label for t in res.tickers],
            ["Суурь"] + [res.r[t]["ratios"].get("_basis") for t in res.tickers]]
    s.table(["Үзүүлэлт"] + res.tickers, rows)
    groups = [("ХӨРВӨХ ЧАДВАР", 0, 5), ("АШИГТ АЖИЛЛАГАА", 5, 12), ("ӨРИЙН БҮТЭЦ", 12, 18), ("ЭРГЭЛТ", 18, 23), ("ӨСӨЛТ (YoY)", 23, 28)]
    for name, lo, hi in groups:
        s.h2(name)
        rws = []
        for key, label, kind in COLUMNS[lo:hi]:
            rws.append([label] + [res.r[t]["ratios"].get(key) for t in res.tickers])
        s.table(["Үзүүлэлт"] + res.tickers, rws)
        for i, (key, label, kind) in enumerate(COLUMNS[lo:hi]):
            for j in range(len(res.tickers)):
                s.ws.cell(s.row - len(rws) + i, 2 + j).number_format = FMT[_fmt_for(kind)]
    s.ws.freeze_panes = "B3"


def _ratio_history(wb, res: Result):
    s = Sheet(wb, "Харьцааны түүх", [10, 10] + [14] * len(COLUMNS), "2F5597")
    s.title("ХАРЬЦААНЫ ТҮҮХ — ТАЙЛАН БҮРЭЭР", "Шүүлтүүрээр компани сонгоно.")
    s.blank()
    heads = ["Компани", "Тайлан"] + [c[1] for c in COLUMNS]
    rows = []
    for t in res.tickers:
        for rep, rt in res.r[t]["series"]:
            rows.append([t, rep.period.label] + [rt.get(k) for k, _, _ in COLUMNS])
    h, e = s.table(heads, rows)
    for i in range(h + 1, e + 1):
        for j, (_, _, kind) in enumerate(COLUMNS):
            s.ws.cell(i, 3 + j).number_format = FMT[_fmt_for(kind)]
    s.ws.auto_filter.ref = f"A{h}:{get_column_letter(len(heads))}{e}"
    s.ws.freeze_panes = f"C{h + 1}"


# ------------------------------------------------------------------ DuPont
def _dupont(wb, res: Result):
    s = Sheet(wb, "DuPont", [10, 10] + [16] * 7, "2F5597")
    s.title("DUPONT ЗАДАРГАА — ROE-ИЙН ЭХ ҮҮСВЭР",
            "ROE = Татварын ачаалал × Хүүгийн ачаалал × EBIT маржин × Хөрөнгийн эргэлт × Өмчийн үржүүлэгч. Ижил ROE-тэй "
            "хоёр компани маржин (бизнесийн чанар), эргэлт (үр ашиг) эсвэл өрийн хөшүүрэг (эрсдэл)-ээр огт өөр байж болно.")
    s.h2("СҮҮЛИЙН ТАЙЛАН")
    rows = []
    for t in res.tickers:
        d = res.r[t]["dupont_series"][-1][1]
        rows.append([t, res.r[t]["company"].latest.period.label] + [d.get(k) for k, _, _ in DUPONT_COLUMNS])
    h, e = s.table(["Компани", "Тайлан"] + [c[1] for c in DUPONT_COLUMNS], rows)
    for i in range(h + 1, e + 1):
        for j, (_, _, kind) in enumerate(DUPONT_COLUMNS):
            s.ws.cell(i, 3 + j).number_format = FMT[_fmt_for(kind)]
    s.h2("ТҮҮХ")
    rows = [[t, rep.period.label] + [d.get(k) for k, _, _ in DUPONT_COLUMNS]
            for t in res.tickers for rep, d in res.r[t]["dupont_series"]]
    h, e = s.table(["Компани", "Тайлан"] + [c[1] for c in DUPONT_COLUMNS], rows)
    for i in range(h + 1, e + 1):
        for j, (_, _, kind) in enumerate(DUPONT_COLUMNS):
            s.ws.cell(i, 3 + j).number_format = FMT[_fmt_for(kind)]
    s.ws.auto_filter.ref = f"A{h}:{get_column_letter(9)}{e}"


# ------------------------------------------------------------------ Түүхэн хандлага
def _trends(wb, res: Result):
    years = sorted({y for t in res.tickers for y in res.r[t]["annual"]})
    s = Sheet(wb, "Түүхэн хандлага", [22] + [10] * (len(years) + 3), "2F5597")
    s.title("ТҮҮХЭН ХАНДЛАГА — ЖИЛЭЭР (Q4 буюу 12 сарын тайлантай жилүүд)",
            "Хоосон нүд = тухайн жилийн 12 сарын тайлан нэгтгэгдээгүй. CAGR = эхний ба сүүлийн жилийн орлогоор.")
    from .trends import METRICS
    spans = {}
    for key, label, kind in METRICS:
        s.h2(label)
        rows = []
        for t in res.tickers:
            ann = res.r[t]["annual"]
            row = [t] + [ann.get(y, {}).get(key) for y in years]
            if key == "revenue":
                row.append(res.r[t]["revenue_cagr"])
            rows.append(row)
        heads = ["Компани"] + [str(y) for y in years] + (["CAGR"] if key == "revenue" else [])
        h, e = s.table(heads, rows, [None] + [kind] * len(years) + ["pct"])
        spans[key] = (h, e)
    s.h2("ОРЛОГЫН ИНДЕКС (анхны жил = 100)")
    rows = [[t] + [res.r[t]["index"].get(y) for y in years] for t in res.tickers]
    h, e = s.table(["Компани"] + [str(y) for y in years], rows, [None] + ["n1"] * len(years))
    ch = LineChart()
    ch.title, ch.height, ch.width = "Орлогын индекс (анхны жил = 100)", 9, 22
    ch.y_axis.scaling.logBase = 10
    for i in range(h + 1, e + 1):
        ser = Series(Reference(s.ws, min_col=2, max_col=1 + len(years), min_row=i), title=s.ws.cell(i, 1).value)
        ser.smooth = False
        ch.series.append(ser)
    ch.display_blanks = "span"
    ch.set_categories(Reference(s.ws, min_col=2, max_col=1 + len(years), min_row=h))
    s.ws.add_chart(ch, f"A{s.row + 1}")
    s.row += 20
    s.h2("ЦЭВЭР АШГИЙН МАРЖИНЫ ХЭЛБЭЛЗЭЛ (стандарт хазайлт)")
    rows = [[t, res.r[t]["margin_vol"]] for t in res.tickers]
    s.table(["Компани", "σ (нэгж хувь)"], rows, [None, "pct"])
    s.note("Тэгш, бага σ = тогтвортой ашигт ажиллагаа; өндөр σ = мөчлөгт, урьдчилан таамаглахад хэцүү.")
    s.ws.freeze_panes = "B3"


def _latest(wb, res: Result):
    """Сүүлийн тайлангаас: хуримтлал (YTD), сүүлийн улирал, сүүлийн хагас жил — өмнөх үе ба өмнөх оны мөн үетэй, бүх компани зэрэгцээ."""
    from . import periods as P
    s = Sheet(wb, "Сүүлийн үеийн харьцуулалт", [22, 10, 11, 11, 9, 8, 11, 11, 9, 11, 9, 8, 11, 11, 9, 11, 9], "2F5597")
    s.title("СҮҮЛИЙН ТАЙЛАНГИЙН ҮЕ — ХУРИМТЛАЛ, УЛИРАЛ, ХАГАС ЖИЛ (бүх компани зэрэгцээ)",
            "Тэрбум ₮. Хуримтлал = оны эхнээс сүүлийн тайлан хүртэл. Улирал/хагас жил = хуримтлагдсан тайлангийн зөрүү. "
            "Хоосон нүд = тооцоход хэрэгтэй тайлан (Q1, Q3 заавал биш) ирүүлээгүй; зохиож бөглөөгүй. Δ = өөрчлөлт, суурь ≤ 0 бол хоосон.")
    heads = ["Компани", "Сүүлийн тайлан", "Хуримтлал", "Өмнөх оны мөн үе", "Δ", "Улирал",
             "Улирал", "Өмнөх улирал", "Δ", "Өмнөх оны мөн улирал", "Δ", "Хагас жил",
             "Хагас жил", "Өмнөх хагас жил", "Δ", "Өмнөх оны мөн хагас жил", "Δ"]
    fm = [None, None, "bn", "bn", "pct", None, "bn", "bn", "pct", "bn", "pct", None, "bn", "bn", "pct", "bn", "pct"]
    bn = lambda v: None if v is None else v / 1e6          # noqa: E731
    for key, title in (("revenue", "Борлуулалтын орлого"), ("net_income", "Цэвэр ашиг")):
        s.h2(title)
        rows = []
        for t in res.tickers:
            v = P.latest_view(res.companies[t], key)
            if not v:
                rows.append([t] + [None] * 16)
                continue
            d = lambda a, b: P.change(v.get(a), v.get(b))[0]   # noqa: E731
            rows.append([t, v["label"], bn(v["ytd"]), bn(v["ytd_py"]), d("ytd", "ytd_py"),
                         v["q_label"], bn(v["q"]), bn(v["q_prev"]), d("q", "q_prev"), bn(v["q_py"]), d("q", "q_py"),
                         v.get("h_label"), bn(v.get("h")), bn(v.get("h_prev")), d("h", "h_prev"), bn(v.get("h_py")), d("h", "h_py")])
        s.table(heads, rows, fm)
    s.ws.freeze_panes = "B3"


def _insights(wb, res: Result):
    """Онцгой үзүүлэлтүүд: ашгийн гүүр, ашгийн цэвэр байдал, өрийн үр өгөөж, Тобин Q, бүтээн байгуулалт, ханш/ашгийн зөрүү, корреляци."""
    from openpyxl.formatting.rule import ColorScaleRule
    from .insights import BRIDGE_ITEMS
    I = res.insights
    if not I:
        return
    s = Sheet(wb, "Онцгой үзүүлэлт", [22, 13, 12, 12, 12, 12, 12, 12, 12, 12, 30], "7030A0")
    s.title("ОНЦГОЙ ҮЗҮҮЛЭЛТҮҮД", "Тэрбум ₮ (өөрөөр заагаагүй бол). Бүгд тайлан, ханшийн түүхөөс тооцогдсон; хөрөнгө оруулалтын зөвлөгөө биш.")
    bn = lambda v: None if v is None else v / 1e6          # noqa: E731

    s.h2("1. АШГИЙН ГҮҮР — сүүлийн тайлангийн хуримтлагдсан цэвэр ашиг өмнөх оны мөн үеэс яагаад өөрчлөгдсөн")
    rows = []
    for t in res.tickers:
        b = I["bridge"].get(t)
        rows.append([t, None, None] + [None] * 8 if not b else
                    [t, f"{b['label']} ↔ {b['base_label']}", bn(b["start"])] + [bn(b["steps"][k]) for k in BRIDGE_ITEMS] + [bn(b["end"])])
    s.table(["Компани", "Үе", "Өмнөх ашиг"] + list(BRIDGE_ITEMS) + ["Одоогийн ашиг"], rows, [None, None] + ["bn"] * 9)
    s.note("Эерэг = ашгийг нэмсэн, сөрөг = бууруулсан. «Бусад (цэвэр)» = бусад орлого/зардал, ханшийн зөрүү, хөрөнгө данснаас хассаны олз. Нийлбэр: өмнөх ашиг + нөлөөнүүд = одоогийн ашиг.", 11)

    s.h2("2. АШГИЙН ЦЭВЭР БАЙДАЛ — ашиг үндсэн үйл ажиллагаанаас уу, нэг удаагийн зүйлээс үү")
    rows = []
    for t in res.tickers:
        p = I["purity"].get(t)
        verdict = None
        if p:
            sh = p["share"]
            verdict = ("ашиг үндсэн бус зүйлээс давамгайлж байна" if sh is not None and sh > 0.5 else
                       "ашгийн зарим хэсэг нэг удаагийн" if sh is not None and sh > 0.2 else "ашиг үндсэн үйл ажиллагаанаас")
        rows.append([t, p and p["label"], p and bn(p["pbt"]), p and bn(p["non_core"]), p and bn(p["core"]), p and p["share"], verdict])
    s.table(["Компани", "Үе", "Татвар төлөхийн өмнөх ашиг", "Нэг удаагийн/бусад", "Үндсэн ашиг", "Нэг удаагийн хувь", "Дүгнэлт"],
            rows, [None, None, "bn", "bn", "bn", "pct"])

    s.h2("3. ӨРИЙН ҮР ӨГӨӨЖ — хөрөнгийн өгөөж (ROA) ба зээлийн хүүний бодит түвшин (LTM)")
    rows = []
    for t in res.tickers:
        d = I["debt"].get(t)
        v = None if not d else ("зээлгүй" if d["debt_free"] else "өр ашиг нэмж байна" if d["spread"] > 0 else "өр ашгийг идэж байна")
        rows.append([t, d and d["roa"], d and d["rate"], d and d["spread"], d and bn(d["debt"]), v])
    s.table(["Компани", "ROA ( татвар, хүүгийн өмнөх)", "Зээлийн хүүний бодит түвшин", "Зөрүү", "Дундаж зээл (тэрбум ₮)", "Дүгнэлт"],
            rows, [None, "pct", "pct", "pct", "bn"])
    s.note("Зээлийн хүүний бодит түвшин = санхүүгийн зардал ÷ дундаж (богино + урт хугацаат) зээл. Санхүүгийн зардалд зээлийн бус хүү орсон байж болох тул ойролцоо.", 11)

    s.h2("4. ТОБИН Q — (зах зээлийн үнэлгээ + нийт өр) ÷ нийт хөрөнгө")
    rows = [[t, I["tobin"].get(t), None if I["tobin"].get(t) is None else
             ("зах зээл хөрөнгөөс нь хямд үнэлж байна" if I["tobin"][t] < 1 else "хөрөнгөөс нь үнэтэй үнэлж байна")] for t in res.tickers]
    s.table(["Компани", "Тобин Q", "Дүгнэлт"], rows, [None, "x"])

    s.h2("5. БҮТЭЭН БАЙГУУЛАЛТЫН ИНДЕКС — дуусаагүй барилга ÷ үндсэн хөрөнгө")
    rows = []
    for t in res.tickers:
        b = I["build"].get(t)
        rows.append([t, b and b["label"], b and bn(b["cip"]), b and bn(b["ppe"]), b and b["ratio"], b and b["ratio_prev"], b and bn(b["cip_change"])])
    s.table(["Компани", "Үе", "Дуусаагүй барилга", "Үндсэн хөрөнгө", "Индекс", "Өмнөх оны эцэс", "Дуусаагүй барилгын өөрчлөлт"],
            rows, [None, None, "bn", "bn", "pct", "pct", "bn"])

    s.h2("6. АШИГ БА ХАНШИЙН ЗӨРҮҮ — ханш (сүүлийн 90 хоног) ба цэвэр ашиг (LTM YoY)")
    rows = []
    for t in res.tickers:
        d = I["diverge"].get(t)
        rows.append([t, d and d["price"], d and d["earn"], d and d["gap"], d and d["verdict"]])
    s.table(["Компани", "Ханшийн өөрчлөлт", "Ашгийн өөрчлөлт", "Зөрүү (ханш − ашиг)", "Дүгнэлт"], rows, [None, "pct", "pct", "pct"])
    s.note("Зөрүү +25pp-аас дээш = «ханш түрүүлсэн»; −25pp-аас доош = «ханш хоцорсон». Ашгийн суурь ≤ 0 бол хоосон.", 11)

    pc = I.get("pricecorr") or {}
    ts = pc.get("tickers") or []
    if ts:
        s.h2("7. ХАНШИЙН КОРРЕЛЯЦИ — долоо хоногийн өгөөж, сүүлийн 52 долоо хоног")
        rows = [[a] + [pc["corr"].get((a, b)) for b in ts] for a in ts]
        h, e = s.table([""] + ts, rows, [None] + ["n2"] * len(ts))
        s.ws.conditional_formatting.add(f"B{h + 1}:{get_column_letter(1 + len(ts))}{e}",
                                        ColorScaleRule(start_type="num", start_value=-0.6, start_color="63BE7B",
                                                       mid_type="num", mid_value=0, mid_color="FFFFFF", end_type="num", end_value=0.6, end_color="F8696B"))
        s.note("Бага/сөрөг (ногоон) = хамт хөдөлдөггүй, багц төрөлжүүлэхэд тустай. Өндөр (улаан) = ижил чиглэлд хөдөлдөг.", 11)
        s.h2("8. САЛБАРЫН ИНДЕКСТЭЙ ХАРЬЦУУЛАЛТ — бусад 7-гийн тэнцүү жинтэй дундаж (52 долоо хоног)")
        rows = []
        for t in ts:
            r = pc["rel"].get(t)
            rows.append([t, r and r["return"], r and r["index"], r and r["excess"], r and r["beta"], r and r["weeks"]])
        s.table(["Компани", "Өөрийн өгөөж", "Бусад 7-гийн дундаж", "Илүү/дутуу", "β", "Долоо хоногийн тоо"], rows, [None, "pct", "pct", "pct", "n2"])
    s.ws.freeze_panes = "B3"


def _insights2(wb, res: Result):
    """Нэмэлт 17 онцгой үзүүлэлт (insights2.py)."""
    from .insights2 import HAIRCUTS, HAIRCUT_NAMES
    I = res.insights2
    if not I:
        return
    T = res.tickers
    s = Sheet(wb, "Онцгой үзүүлэлт 2", [22, 14, 14, 14, 14, 14, 14, 14, 14, 30], "7030A0")
    s.title("ОНЦГОЙ ҮЗҮҮЛЭЛТ (2) — 17 нэмэлт үзүүлэлт",
            f"Тэрбум ₮ (өөрөөр заагаагүй бол). Хадгаламжийн хүү {res.assumptions.deposit_rate * 100:.0f}%, шаардах өгөөж "
            f"{res.assumptions.required_return * 100:.0f}% (inputs/assumptions.json). Хөрөнгө оруулалтын зөвлөгөө биш.")
    bn = lambda v: None if v is None else v / 1e6          # noqa: E731
    row = lambda k, t, f: (lambda d: [t] + (f(d) if d else [None]))(I[k].get(t))   # noqa: E731

    def sec(n, title, heads, key, f, fm, note=None):
        s.h2(f"{n}. {title}")
        s.table(heads, [row(key, t, f) for t in T], fm)
        if note:
            s.note(note, 10)

    sec(1, "ТАЙЛАНГИЙН НАЙДВАРТАЙ БАЙДАЛ — Beneish M (хялбаршуулсан, мөнгөн урсгалгүй)",
        ["Компани", "Үе", "M", "Дүгнэлт", "Хуримтлал/хөрөнгө", "DSRI", "GMI", "AQI", "SGI", "Босго давсан"], "beneish",
        lambda d: [f"{d['label']} ↔ {d['base_label']}", d["m"], d["verdict"], d["tata"], d["comp"]["DSRI"], d["comp"]["GMI"],
                   d["comp"]["AQI"], d["comp"]["SGI"], ", ".join(d["flags"]) or "—"], [None, None, "n2", None, "pct", "n2", "n2", "n2", "n2"],
        "M > −1.78 = ашгийг «гоёсон» байж болзошгүй (АНУ-ын загвар, Монголд зөвхөн харьцуулах зорилготой). Мөнгөн урсгалын тайлан байхгүй тул хуримтлалыг балансаар тооцсон.")

    s.h2("2. ХУВЬЦААНД НОГДОХ ТАТАН БУУЛГАХ ӨРТӨГ — хөрөнгийн бүлэг бүрийг хасалттайгаар зарж өрөө төлсний дараа")
    rows = []
    for t in T:
        d = I["liq"].get(t)
        rows.append([t] + ([d["label"], bn(d["recoverable"]), bn(d["liabilities"]), bn(d["net"]), d["per_share"], d["price"], d["ratio"],
                            bn(d["book"])] if d else [None] * 8))
    s.table(["Компани", "Үе", "Сэргээгдэх дүн", "Нийт өр", "Цэвэр дүн", "Ногдох ₮/ш", "Ханш ₮", "Ханш ÷ өртөг", "Дансны өмч"], rows,
            [None, None, "bn", "bn", "bn", "n2", "n2", "x", "bn"])
    s.note("Сэргээгдэх хувь: " + ", ".join(f"{HAIRCUT_NAMES[k]} {v * 100:.0f}%" for k, v in HAIRCUTS.items()) +
           ". Цэвэр дүн сөрөг бол харьцаа хоосон (өр сэргээгдэх хөрөнгөөс их).", 10)

    sec(3, "НОГДОЛ АШГИЙН НӨӨЦ — хуримтлагдсан ашиг ÷ жилийн ногдол ашиг",
        ["Компани", "Үе", "Жилийн ногдол ашиг", "Хуримтлагдсан ашиг", "Нөөцийн жил", "Ногдол ашгийн хамрах", "Төлөлтийн хувь"], "divres",
        lambda d: [d["label"], bn(d["dividend"]), bn(d["retained"]), d["years"], d["cover"], d["payout"]], [None, None, "bn", "bn", "n2", "x", "pct"])

    s.h2("4. УЛИРЛЫН НӨЛӨӨТЭЙ ЖИЛИЙН АШГИЙН ТААМАГ — одоогийн хуримтлалыг түүхэн улирлын хуваарилалтаар жилчилсэн")
    rows = []
    for t in T:
        d = I["season"].get(t)
        rows.append([t] + ([d["label"], bn(d["ytd"]), "бодит" if d["done"] else "таамаг", bn(d["forecast"]), bn(d["low"]), bn(d["high"]),
                            d["share"], bn(d["naive"]), bn(d["prev_fy"]), d.get("note")] if d else [None] * 10))
    s.table(["Компани", "Үе", "Хуримтлал", "Төрөл", "Жилийн таамаг", "Доод", "Дээд", "Тухайн үеийн хувь", "Энгийн ×(12/сар)", "Өмнөх жил", "Тайлбар"], rows,
            [None, None, "bn", None, "bn", "bn", "bn", "pct", "bn", "bn"])

    sec(5, "ОРГИЛООС БУУРСАН ХЭМЖЭЭ — сүүлийн 12 сар",
        ["Компани", "Оргил ₮", "Оргилын өдөр", "Сүүлийн ₮", "Буурсан %", "«Усан доор» хоног", "Хамгийн их уналт", "Сэргэхэд хэрэгтэй өсөлт", "Бүх түүхийн оргилоос"], "drawdown",
        lambda d: [d["peak"], d["peak_day"], d["last"], d["dd"], d["under_days"], d["max_dd"], d["need"], d["dd_ath"]],
        [None, "n2", "date", "n2", "pct", "int", "pct", "pct", "pct"])

    sec(6, "ҮЙЛ АЖИЛЛАГААНЫ ХӨШҮҮРГИЙН ЗЭРЭГ — EBIT-ийн % өөрчлөлт ÷ борлуулалтын % өөрчлөлт",
        ["Компани", "LTM", "EBIT өөрчлөлт", "Борлуулалтын өөрчлөлт", "Түүхэн дундаж (жилийн)"], "dol",
        lambda d: [d["ltm"]["dol"] if d.get("ltm") else None, d["ltm"]["d_ebit"] if d.get("ltm") else None,
                   d["ltm"]["d_rev"] if d.get("ltm") else None, d.get("hist")], [None, "n2", "pct", "pct", "n2"],
        "Борлуулалт 1% өөрчлөгдөхөд ашиг хэдэн хувиар хөдөлдөг. Өндөр = тогтмол зардал их. Борлуулалтын өөрчлөлт нь 0-д ойр үед тогтворгүй.")

    sec(7, "НЭГ ₮ ХУРИМТЛУУЛСАН АШГИЙН ҮР ДҮН — зах зээлийн үнэлгээний өсөлт ÷ хуримтлагдсан ашиг",
        ["Компани", "Эхлэл", "Төгсгөл", "Жил", "Үнэлгээний өөрчлөлт", "Хуримтлагдсан ашгийн өөрчлөлт", "Үр дүн (₮)", "Эхний ханш", "Сүүлийн ханш"], "retention",
        lambda d: [d["start"], d["end"], d["years"], bn(d["d_mv"]), bn(d["d_re"]), d["ratio"], d["p0"], d["p1"]], [None, None, None, "n2", "bn", "bn", "n2", "n2", "n2"],
        "1-ээс бага = хуримтлуулсан ашиг зах зээлийн үнэлгээнд үнэ цэнэ нэмсэнгүй (ногдол ашиг, хувьцааны тооны өөрчлөлтийг тусад нь тооцоогүй).")

    sec(8, "ЗАХ ЗЭЭЛИЙН СУУЛГАСАН ӨСӨЛТ БА БОДИТ ӨСӨЛТ",
        ["Компани", "Суулгасан өсөлт", "Бодит (CAGR)", "Хугацаа (жил)", "Зөрүү (суулгасан − бодит)", "Шаардах өгөөж", "Тайлбар"], "implied",
        lambda d: [d.get("implied"), d.get("actual"), d.get("span"), d.get("gap"), d.get("required"), d.get("note")], [None, "pct", "pct", "int", "pct", "pct"],
        "Суулгасан өсөлт = шаардах өгөөж − ашгийн өгөөж (мөнхийн өсөлтийн загвараар). Бодит өсөлтөөс бага бол зах зээл өсөлтийг дутуу үнэлж байна.")

    sec(9, "ӨӨРИЙН ХӨРӨНГӨӨР ХАНГАГДАХ ӨСӨЛТ — ROE × (1 − ногдол ашгийн төлөлт)",
        ["Компани", "ROE", "Төлөлтийн хувь", "Хангагдах өсөлт", "Бодит борлуулалтын өсөлт", "Зөрүү (бодит − хангагдах)"], "sustain",
        lambda d: [d["roe"], d["payout"], d["sustainable"], d["actual"], d["gap"]], [None, "pct", "pct", "pct", "pct", "pct"],
        "Эерэг зөрүү = өсөлтийн зарим хэсгийг өр, гадны санхүүжилтээр хаасан.")

    sec(10, "ЭРГЭЛТИЙН ХӨРӨНГИЙН АЧААЛАЛ — бараа материал + авлага − өглөг",
        ["Компани", "Үе", "NWC", "Өмнөх оны мөн үе", "NWC / орлого", "Өмнөх", "NWC өсөлт", "Борлуулалтын өсөлт", "Нэмэлт ₮ тутамд NWC"], "wcap",
        lambda d: [d["label"], bn(d["nwc"]), bn(d["nwc_prev"]), d["intensity"], d["intensity_prev"], d["nwc_growth"], d["rev_growth"], d["per_extra"]],
        [None, None, "bn", "bn", "pct", "pct", "pct", "pct", "n2"])

    s.h2("11. ТАЙЛАНГИЙН ДАРААХ ХАНШИЙН ХАРИУ — тайлан зарлагдсанаас ±14 хоногийн өгөөж, салбарын (бусад 7) дундажаас илүү/дутуу")
    rows = []
    for t in T:
        d = I["reaction"].get(t)
        if not d:
            rows.append([t] + [None] * 6)
            continue
        rows.append([t, d["n"], d["hit"], d["avg_excess"], d["last"]["label"], d["last"]["surprise"], d["last"]["excess"]])
    s.table(["Компани", "Тооцсон үйл явдал", "Чиглэл таарсан хувь", "Дундаж илүү өгөөж", "Сүүлийн тайлан", "Ашгийн YoY", "Салбараас илүү өгөөж"], rows,
            [None, "int", "pct", "pct", None, "pct", "pct"])
    s.note("Тайлан зарлагдсан огноо тодорхойгүй бол үеийн дараах хуулийн хугацаагаар тооцоолсон. Жижиг түүвэр тул чиг хандлага гэж үз.", 10)

    s.h2("12. ЗАРДЛЫН «НААЛДАМХАЙ» БАЙДАЛ — борлуулалт өсөхөд ба буурахад зардлын хариу")
    rows = []
    for t in T:
        d = I["sticky"].get(t)
        rows.append([t] + ([{"year": "жил", "half": "хагас жил", "quarter": "улирал"}[d["kind"]], d["n_up"], d["n_dn"], d["beta_up"], d["beta_down"], d["sticky"]]
                           if d else [None] * 6))
    s.table(["Компани", "Давтамж", "Өссөн үе", "Буурсан үе", "Өсөхөд β", "Буурахад β", "Наалдамхай (өсөх − буурах)"], rows, [None, None, "int", "int", "n2", "n2", "n2"])
    s.note("β = зардлын % өөрчлөлт ÷ борлуулалтын % өөрчлөлт. Эерэг = борлуулалт буурахад зардал дагаж буурдаггүй.", 10)

    sec(13, "ТАТВАРЫН БОДИТ БА ХУУЛИЙН ХУВИЙН ЗӨРҮҮ (LTM)",
        ["Компани", "Татвар төлөхийн өмнөх ашиг", "Татвар", "Бодит хувь", "Хуулийн хувь", "Зөрүү", "Зөрүүгийн дүн"], "taxgap",
        lambda d: [bn(d["pbt"]), bn(d["tax"]), d["effective"], d["statutory"], d["gap"], bn(d["diff"])], [None, "bn", "bn", "pct", "pct", "pct", "bn"],
        "Хуулийн хувь = ААНОАТ 10% (6 тэрбум ₮ хүртэл), 25% (давсан хэсэг). Сөрөг зөрүү = хуулиас бага татвар төлсөн.")

    s.h2("14. БОГИНО ХУГАЦААТ ӨРИЙН ХАНА")
    rows = []
    for t in T:
        d = I["wall"].get(t)
        rows.append([t] + ([None, None, None, None, None, "зээлгүй"] if d and d.get("debt_free") else
                           [bn(d["st"]), bn(d["lt"]), d["share"], d["cover"], d["cover_inv"], None] if d else [None] * 6))
    s.table(["Компани", "Богино зээл", "Урт зээл", "Богиноны хувь", "(Мөнгө+авлага) ÷ богино", "(+бараа) ÷ богино", "Тайлбар"], rows,
            [None, "bn", "bn", "pct", "x", "x"])

    sec(15, "ХУВЬЦААНЫ ЭРСДЭЛИЙН ШАГНАЛ — ашгийн болон ногдол ашгийн өгөөж − хадгаламжийн хүү",
        ["Компани", "Ашгийн өгөөж", "Ногдол ашгийн өгөөж", "Хадгаламжийн хүү", "Ашгийн шагнал", "Ногдол ашгийн шагнал"], "erp",
        lambda d: [d["earn_yield"], d["div_yield"], d["deposit"], d["earn_prem"], d["div_prem"]], [None, "pct", "pct", "pct", "pct", "pct"],
        "Сөрөг = банкны хадгаламж хувьцаанаас илүү өгөөжтэй (хувьцааны өсөлтийн боломжийг тооцоогүй).")

    sec(16, "ЦЭВЭР БЭЛЭН МӨНГӨ ÷ ЗАХ ЗЭЭЛИЙН ҮНЭЛГЭЭ",
        ["Компани", "Бэлэн мөнгө", "Хүүтэй өр", "Цэвэр бэлэн мөнгө", "Үнэлгээний хувь", "Хувьцаанд ногдох ₮", "Ханш ₮"], "netcash",
        lambda d: [bn(d["cash"]), bn(d["debt"]), bn(d["net"]), d["ratio"], d["per_share"], d["price"]], [None, "bn", "bn", "bn", "pct", "n2", "n2"])

    sec(17, "АШГИЙН ӨСӨЛТИЙН ЦУВАА БА ТОГТВОРТОЙ БАЙДАЛ",
        ["Компани", "Давтамж", "Дараалсан өссөн үе", "Нийт харьцуулсан", "Өссөн үеийн хувь", "Цэвэр ашгийн ахиуцын σ", "Ахиуцын дундаж"], "streak",
        lambda d: [{"year": "жил", "half": "хагас жил", "quarter": "улирал"}[d["kind"]], d["streak"], d["n"], d["up_share"], d["margin_sd"], d["margin_mean"]],
        [None, None, "int", "int", "pct", "pct", "pct"])
    s.ws.freeze_panes = "B3"


def _breakdown(wb, res: Result):
    s = Sheet(wb, "Задаргаа", [24] + [15] * 7, "2F5597")
    s.title("ОРЛОГООС ЦЭВЭР АШИГ ХҮРТЭЛХ ЗАРДЛЫН ЗАДАРГАА (сүүлийн 12 сар, тэрбум ₮)",
            "Багана бүр орлогын 100%-ийг бүрдүүлдэг давхарга. 'Татвар ба бусад' = орлогын татвар болон бусад орлого/зардлын үлдэгдэл.")
    s.blank()
    names = ["Орлого", "(-) Өртөг", "(-) Борлуулалт, маркетинг", "(-) Ерөнхий удирдлага", "(-) Санхүүгийн зардал",
             "(-) Татвар ба бусад", "Цэвэр ашиг"]
    rows = [[t] + [(res.r[t]["breakdown"] or {}).get(n) for n in names] for t in res.tickers]
    s.table(["Компани"] + names, rows, [None] + ["bn"] * len(names))
    s.h2("ОРЛОГЫН ХУВИЙН ХУВААРИЛАЛТ")
    rows = []
    for t in res.tickers:
        b = res.r[t]["breakdown"]
        rows.append([t] + [None if not b or not b["Орлого"] else b[n] / b["Орлого"] for n in names[1:]])
    s.table(["Компани"] + names[1:], rows, [None] + ["pct"] * 6)


# ------------------------------------------------------------------ Эрсдэл
def _risk(wb, res: Result):
    s = Sheet(wb, "Эрсдэл", [14, 14, 14, 14, 14, 14, 14, 30, 30], "C00000")
    s.title("ЭРСДЭЛ БА ЧАНАР")
    s.h2("1. ALTMAN Z-SCORE — ТАТАН БУУГДАХ ЭРСДЭЛ")
    s.note("Z = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 1.0·X5. X1 = Ажлын капитал/Хөрөнгө, X2 = Өмч/Хөрөнгө, X3 = EBIT/Хөрөнгө, "
           "X4 = Зах зээлийн үнэлгээ/Өр, X5 = Орлого/Хөрөнгө. Босго: >2.99 аюулгүй, 1.81–2.99 сэрэмжлэх, <1.81 эрсдэлтэй (АНУ-ын "
           "олон нийтийн компанид тохируулсан тул Монголд зөвхөн харьцуулах зорилготой).", 9, 45)
    rows = []
    for t in res.tickers:
        z = res.r[t]["altman"]
        rows.append([t] + (z["x"] + [z["z"], z["zone"]] if z else [None] * 5 + [None, "тооцох өгөгдөл дутуу"]))
    s.table(["Компани", "X1", "X2", "X3", "X4", "X5", "Z-Score", "Бүс"], rows, [None] + ["n2"] * 6)
    s.h2("2. PIOTROSKI F — ТАЙЛАНГИЙН ЧАНАР (7 шалгуур; мөнгөн урсгалын тайлан нэгтгэлд байхгүй тул 2 шалгуур орхигдсон)")
    names = ["ROA > 0", "ROA өссөн", "Өр/Хөрөнгө буурсан", "Эргэлтийн хөрөнгийн харьцаа өссөн", "Хувьцаа нэмэгдээгүй",
             "Нийт ашгийн маржин өссөн", "Хөрөнгийн эргэлт өссөн"]
    rows = []
    for t in res.tickers:
        p = res.r[t]["piotroski"]
        got = {} if not p else {n: ok for n, ok in p["tests"]}
        rows.append([t] + [("✔" if got.get(n) else "✘") if got.get(n) is not None else "—" for n in names]
                    + ([f"{p['score']}/{p['of']}", p["zone"]] if p else ["—", "тооцох өгөгдөл дутуу"]))
    s.table(["Компани"] + names + ["Оноо", "Үнэлгээ"], rows)
    s.h2("3. ХҮҮГИЙН МЭДРЭМЖ — санхүүгийн зардал ×1, ×1.5, ×2, ×3 болбол цэвэр ашиг (тэрбум ₮, татварын хамгаалалтгүй)")
    rows = []
    for t in res.tickers:
        x = res.r[t]["sens"]
        rows.append([t] + ([x["finance_cost"] / 1e6] + [x["cases"][k] / 1e6 for k in (1, 1.5, 2, 3)] + [x["change_3x"], x["note"]]
                           if x else [None] * 6 + ["—"]))
    s.table(["Компани", "Санх. зардал", "ЦА ×1", "ЦА ×1.5", "ЦА ×2", "ЦА ×3", "Өөрчлөлт ×3", "Тайлбар"], rows,
            [None, "bn", "bn", "bn", "bn", "bn", "pct"])
    s.h2("4. ЭВЦЭЛДЭХ ОРЛОГО — орлогын аюулгүй зай")
    s.note("Эвцэлдэх орлого = (Борлуулалт-маркетинг + Ерөнхий удирдлага + Санхүүгийн зардал) ÷ Нийт ашгийн маржин. "
           "Аюулгүйн зай = (Орлого − Эвцэлдэх)/Орлого.", 9)
    rows = []
    for t in res.tickers:
        b = res.r[t]["break_even"]
        rows.append([t] + ([b["gross_margin"], b["fixed"] / 1e6, None if b["break_even"] is None else b["break_even"] / 1e6,
                            b["revenue"] / 1e6, b["safety"], b["note"]] if b else [None] * 5 + ["—"]))
    s.table(["Компани", "Нийт ашгийн\nмаржин", "Тогтмол зардал\n(тэрбум)", "Эвцэлдэх\nорлого (тэрбум)", "Орлого\n(тэрбум)",
             "Аюулгүйн зай", "Тайлбар"], rows, [None, "pct", "bn", "bn", "bn", "pct"])
    s.h2(f"5. АРИЛЖААНЫ ХӨРВӨХ ЧАДВАР — сүүлийн {res.assumptions.liquidity_window_days} хоног")
    rows = []
    for t in res.tickers:
        q = res.r[t]["liquidity"]
        rows.append([t] + ([q["last_day"], q["trading_days"], q["avg_value"], q["avg_qty"]] if q else [None] * 4))
    s.table(["Компани", "Сүүлийн\nарилжаа", "Арилжаатай\nөдөр", "Өдрийн дундаж\nүнийн дүн (₮)", "Өдрийн дундаж\nширхэг"],
            rows, [None, "date", "int", "int", "int"])


# ------------------------------------------------------------------ Үнэлгээ
def _valuation(wb, res: Result):
    s = Sheet(wb, "Үнэлгээ", [10] + [14] * 14, "548235")
    s.title("ҮНЭЛГЭЭНИЙ ҮЖҮҮЛЭГЧ, EV/EBIT",
            "EPS = LTM цэвэр ашиг ÷ хувьцаа; BVPS = эздийн өмч ÷ хувьцаа. EV = Зах зээлийн үнэлгээ + Хүүтэй өр − Мөнгө. "
            "EV/EBIT нь өрийг тооцдог тул өрийн түвшин өндөр компанид P/E-ээс бодит. Нэгж: тэрбум ₮ (өөрөөр заагаагүй бол).")
    s.blank()
    rows = []
    for t in res.tickers:
        v = res.r[t]["val"]
        if not v:
            rows.append([t] + [None] * 13)
            continue
        k = 1e6
        rows.append([t, v.price, v.shares, v.eps, v.bvps, v.pe, v.pb, v.market_cap / k if v.market_cap else None,
                     v.debt / k, None if v.cash is None else v.cash / k, None if v.ev is None else v.ev / k,
                     None if v.ebit is None else v.ebit / k, v.ev_ebit, v.basis])
    s.table(["Компани", "Ханш (₮)", "Хувьцаа (ш)", "EPS (₮)", "BVPS (₮)", "P/E", "P/B", "Зах зээлийн\nүнэлгээ", "Хүүтэй өр",
             "Мөнгө", "EV", "EBIT (LTM)", "EV/EBIT", "Суурь"], rows,
            [None, "n2", "int", "n2", "n2", "n1", "n2", "bn", "bn", "bn", "bn", "bn", "n1"])


def _graham(wb, res: Result):
    s = Sheet(wb, "Graham ба ногдол", [10] + [14] * 14, "548235")
    s.title("GRAHAM NUMBER БА НОГДОЛ АШИГ — ХАМТАД НЬ",
            f"Graham Number = √(22.5 × EPS × BVPS). Graham зах = (Graham − Ханш)/Graham. Ногдлын өгөөж = Ногдол ÷ Ханш; "
            f"хадгаламж {res.assumptions.deposit_rate:.0%}-тай зөрүү. Бодит үнэлгээ = Graham × (1 + зөрүү); Бодит хямдрал = 1 − Ханш/Бодит үнэлгээ. "
            "Хөрвөх чадварын эрсдэл (эзэмшлийн төвлөрөл) Graham-д орохгүй, 'Эзэмшил' хавтсанд тусад нь.")
    s.blank()
    rows = []
    for t in res.tickers:
        v = res.r[t]["val"]
        c = res.r[t]["conc"]
        rows.append([t] + ([v.price, v.eps, v.bvps, v.graham, v.graham_margin, v.dps, v.div_yield, v.div_spread,
                            v.real_value, v.real_discount, v.verdict, c["grade"] if c else None] if v else [None] * 12))
    s.table(["Компани", "Ханш (₮)", "EPS (₮)", "BVPS (₮)", "Graham\nNumber (₮)", "Graham зах", "Ногдол\n(₮/ХК)",
             "Ногдлын\nөгөөж", "Хадгаламжтай\nзөрүү", "Бодит үнэлгээ\n(₮)", "Бодит\nхямдрал", "Нэгдсэн дүгнэлт",
             "Хөрвөх чадварын\nэрсдэл"], rows,
            [None, "n2", "n2", "n2", "n2", "pct", "n2", "pct", "pct", "n2", "pct"], fills={12: RATING_FILL})
    s.ws.column_dimensions["L"].width = 36
    s.h2(f"{res.assumptions.target_yield:.0%}-ИЙН ОГТ ӨГӨӨЖӨӨР ШАЛГАХ")
    s.note("Шаардах өгөөжид хүрэх ханш = Ногдол ÷ шаардах өгөөж. Үржүүлэгч = Graham Number ÷ тэр ханш: 1-ээс хамаагүй их бол "
           "Graham Number нь зөвхөн хөрөнгийн үнээр (мөнгөн урсгалаар биш) хямд гэсэн үг.", 12)
    rows = []
    for t in res.tickers:
        v = res.r[t]["val"]
        rows.append([t] + ([v.dps, v.graham, v.price_for_target_yield, v.graham_multiple, v.yield_at_graham] if v else [None] * 5))
    s.table(["Компани", "Ногдол (₮)", "Graham (₮)", "Шаардах өгөөжид\nхүрэх ханш", "Үржүүлэгч\n(Graham/ханш)",
             "Graham ханшаар\nавбал өгөөж"], rows, [None, "n2", "n2", "n2", "n2", "pct"])


def _valuation2(wb, res: Result):
    s = Sheet(wb, "Үнэлгээ 2.0", [12, 18, 14, 14, 14, 14, 14, 14, 14], "548235")
    s.title("ХЯМДРАЛЫН НЭГДСЭН ОНОО, BCG МАТРИЦ, КОРРЕЛЯЦИ")
    a = res.assumptions
    s.h2("1. ХЯМДРАЛЫН НЭГДСЭН ОНОО (0–100)")
    s.note(f"Graham зах {a.w_graham:.0%} + Ногдол vs хадгаламж {a.w_dividend:.0%} + P/E-ийн урвуу {a.w_pe:.0%} + P/B-ийн урвуу {a.w_pb:.0%}. "
           "Ганц шалгуурын сул талыг бусад нь нөхнө. Босгыг `inputs/assumptions.json`-д өөрчилнө.", 9)
    items = sorted(((t, res.r[t]["cheap"]) for t in res.tickers if res.r[t]["cheap"]), key=lambda x: -x[1]["total"])
    rows = [[i + 1, t, c["total"], c["graham"], c["dividend"], c["pe"], c["pb"]] for i, (t, c) in enumerate(items)]
    s.table(["Эрэмбэ", "Компани", "Нэгдсэн\nоноо /100", "Graham\nхэсэг", "Ногдол\nхэсэг", "P/E\nхэсэг", "P/B\nхэсэг"], rows,
            [None, None, "pts", "pts", "pts", "pts", "pts"])
    s.h2("2. BCG МАТРИЦ — ХЭМЖЭЭ (зах зээлийн үнэлгээ) vs ӨСӨЛТ (орлогын CAGR)")
    if res.bcg:
        s.note(f"Дундаж зах зээлийн үнэлгээ {res.bcg['_mean_cap'] / 1e6:,.1f} тэрбум ₮, дундаж CAGR {res.bcg['_mean_growth']:.1%}. "
               "БУХ = том ба хурдан өсдөг; ОДОД = жижиг ба хурдан өсдөг; МӨНГӨН ҮНЭЭ = том ба удаан өсдөг; "
               "АСУУЛТЫН ТЭМДЭГ = жижиг ба удаан өсдөг.", 9)
    rows = []
    for t in res.tickers:
        v = res.r[t]["val"]
        rows.append([t, None if not v or v.market_cap is None else v.market_cap / 1e6, res.r[t]["revenue_cagr"], res.bcg.get(t, "—")])
    h, e = s.table(["Компани", "Зах зээлийн\nүнэлгээ (тэрбум ₮)", "Орлогын CAGR", "Ангилал"], rows, [None, "bn", "pct"])
    sc = ScatterChart()
    sc.title, sc.height, sc.width = "BCG: үнэлгээ (X, тэрбум ₮) ба орлогын CAGR (Y)", 9, 18
    sc.style = 13
    for i in range(h + 1, e + 1):
        if s.ws.cell(i, 2).value is None or s.ws.cell(i, 3).value is None:
            continue
        ser = Series(Reference(s.ws, min_col=3, min_row=i), Reference(s.ws, min_col=2, min_row=i), title=s.ws.cell(i, 1).value)
        color = PALETTE[len(sc.series) % len(PALETTE)]
        ser.marker.symbol, ser.marker.size = "circle", 11
        ser.marker.graphicalProperties.solidFill = color
        ser.marker.graphicalProperties.line.solidFill = color
        ser.graphicalProperties.line.noFill = True
        sc.series.append(ser)
    sc.scatterStyle = "lineMarker"
    sc.x_axis.title, sc.y_axis.title = "Зах зээлийн үнэлгээ (тэрбум ₮)", "Орлогын CAGR"
    sc.x_axis.delete = sc.y_axis.delete = False
    sc.y_axis.number_format = "0%"
    s.ws.add_chart(sc, f"H{h}")
    s.row = max(s.row, h + 20)
    s.h2("3. ОРЛОГЫН ӨСӨЛТИЙН КОРРЕЛЯЦИ — компаниуд хоорондоо хэр хамаарах вэ")
    s.note("Давхцсан ≥3 жилтэй хосыг тооцно; '—' = хангалттай өгөгдөл байхгүй. 1-д ойр = ижил чиглэлд хөдөлдөг (диверсификаци сул).", 9)
    rows = [[t] + [res.corr.get((t, u)) for u in res.tickers] for t in res.tickers]
    s.table(["Компани"] + res.tickers, rows, [None] + ["n2"] * len(res.tickers))


# ------------------------------------------------------------------ Эзэмшил
def _ownership(wb, res: Result):
    s = Sheet(wb, "Эзэмшил", [10, 14, 14, 14, 16, 14, 14, 14, 60], "7030A0")
    s.title("ХУВЬЦААНЫ ЭЗЭМШЛИЙН БҮТЭЦ, ТӨВЛӨРӨЛ",
            "≥5% эзэмшигчид (стратегийн) ба <5% эзэмшигчид (чөлөөт эргэлт). Хөрвөх чадварын эрсдэл: ӨНДӨР — чөлөөт эргэлт <10% эсвэл "
            "том эзэмшигч дунджаар ≥50% эсвэл жижиг эзэмшигч <1,000; БАГА — чөлөөт эргэлт ≥25% ба жижиг эзэмшигч ≥5,000; бусад нь ДУНД.")
    s.blank()
    rows = []
    for t in res.tickers:
        o, c = res.r[t]["own"], res.r[t]["conc"]
        m = res.inputs.market.get(t)
        rows.append([t] + ([o.as_of, m.shares if m else None, o.big_holders, o.big_pct, c["avg_big"], o.small_holders, o.small_pct,
                            c["grade"], c["reasons"]] if o else [None] * 9))
    s.table(["Компани", "Огноо", "Нийт хувьцаа", "≥5%\nэзэмшигч", "≥5%\nэзлэх хувь", "Дундаж хувь\n(нэг том\nэзэмшигч)",
             "<5%\nэзэмшигч", "Чөлөөт\nэргэлт", "Эрсдэл", "Шалтгаан"], rows,
            [None, "date", "int", "int", "pct", "pct", "int", "pct"], fills={8: RATING_FILL})
    s.ws.column_dimensions["I"].width = 12
    s.ws.column_dimensions["J"].width = 60


# ------------------------------------------------------------------ Прогноз
def _forecast(wb, res: Result):
    y = res.target_year
    s = Sheet(wb, "ЦА прогноз", [10, 10, 14, 14, 14, 14, 14, 14, 14, 14], "BF8F00")
    s.title(f"ЦЭВЭР АШГИЙН ПРОГНОЗ {y} (БҮХ ЖИЛИЙН ТҮҮХЭН ӨГӨГДЛӨӨР, тэрбум ₮)",
            "А: эерэг цэвэр ашигтай жилүүдээр ln(ЦА)–он регресс. Б: ln(Орлого) регресс × сүүлийн жилийн маржин. В: ln(Орлого) регресс × түүхэн "
            "дундаж маржин. Голч = боломжит аргуудын медиан. 2-р хагас жил = Голч × 50% (улирлын задаргаа байхгүй тул жигд). "
            f"'Үлдэх хэсэг' = Голч − {y} оны 1-р хагасын бодит дүн. Бодит дүн, зөрүү нь {y} оны жилийн тайлан гарахад автоматаар бөглөгдөнө. "
            "Энэ нь статистик экстраполяци бөгөөд компанийн зарлал, нөхцөл байдлыг тооцохгүй.")
    s.blank()
    rows = []
    for t in res.tickers:
        f = res.r[t]["forecast"]
        rows.append([t] + ([f["years"], f["a"], f["b"], f["c"], f["median"], f["h2"], f["h1_actual"], f["rest_of_year"], f["actual"],
                            f["variance"], f["variance_pct"]] if f else [None] * 11))
    s.table(["Компани", "Ашигласан\nжил", "А", "Б", "В", "ГОЛЧ\nпрогноз", "2-р хагас\n(×50%)", f"{y} 1-р\nхагас бодит",
             "Үлдэх хэсэг\n(Голч − H1)", "Бодит\nжилийн дүн", "Зөрүү", "Зөрүү %"], rows,
            [None, "int", "bn", "bn", "bn", "bn", "bn", "bn", "bn", "bn", "bn", "pct"])
    s.note("Дутуу мөр = эерэг ашигтай жил 3-аас цөөн (прогноз гаргахгүй).", 12)


# ------------------------------------------------------------------ Техник
def _technical(wb, res: Result):
    s = Sheet(wb, "Техник", [10, 12, 12, 11, 9, 9, 9, 8, 10, 10, 10, 12, 12, 12, 12, 12, 24, 9, 9, 9], "ED7D31")
    s.title("ТЕХНИК ШИНЖИЛГЭЭ — НЭГТГЭЛ",
            "MA 7/29/99, RSI(14), MACD(12,26,9), Bollinger(20,2), Gann HiLo(3), BJ HEMA (Heiken Ashi EMA 5/9/21), тулгуур/эсэргүүцэл, "
            "BOS/CHoCH, Wyckoff үе (ойролцоо эвристик). Магадлал нь дохионы тооноос гаргасан ойролцоо жин, статистик баталгаагүй.")
    if res.as_of_prices:
        s.note(f"Ханшийн сүүлийн өгөгдөл: {res.as_of_prices}.", 12)
    rows = []
    for t in res.tickers:
        for tf, tfn in TECHNICAL_TF:
            tr = res.r[t]["tech"].get(tf)
            if not tr:
                continue
            x = tr.state
            sc = x["scenario"]
            rows.append([t, tfn, x["last_day"], x["close"], x["ma7"], x["ma29"], x["ma99"], x["rsi"], x["macd"], x["macd_signal"],
                         x["bb_pctb"], x["gann"], x["bj_color"], x["smc_trend"],
                         ", ".join(f"{v:,.1f}" for v in x["support"]), ", ".join(f"{v:,.1f}" for v in x["resistance"]),
                         x["wyckoff"], sc["up"], sc["down"], sc["side"]])
    s.blank()
    s.table(["Компани", "Хугацаа", "Сүүлийн\nөдөр", "Хаалт", "MA7", "MA29", "MA99", "RSI", "MACD", "Signal", "BB %B",
             "Gann\nHiLo", "BJ HEMA", "BOS/CHoCH\nтренд", "Тулгуур", "Эсэргүүцэл", "Wyckoff", "Өсөх %", "Буурах %", "Хажуу %"],
            rows, [None, None, "date", "n2", "n2", "n2", "n2", "n1", "n2", "n2", "n2", None, None, None, None, None, None, "n1", "n1", "n1"])
    s.ws.freeze_panes = "C5"
    for t in res.tickers:
        d = res.r[t]["tech"].get("D")
        if not d:
            continue
        ws = Sheet(wb, f"ТА {t}", [11, 9, 9, 9, 9, 11, 14] + [10] * 16, "ED7D31")
        ws.title(f"{t} — өдрийн индикатор (сүүлийн {res.assumptions.tech_rows} өдөр)")
        n = res.assumptions.tech_rows
        S = d.series
        rows = []
        for i in range(len(d.bars) - 1, max(len(d.bars) - n, 0) - 1, -1):
            b = d.bars[i]
            rows.append([b.day, b.open, b.high, b.low, b.close, b.qty, b.value, S["ma7"][i], S["ma29"][i], S["ma99"][i], S["rsi"][i],
                         S["macd"][i], S["signal"][i], S["hist"][i], S["bb_mid"][i], S["bb_up"][i], S["bb_lo"][i], S["gann"][i],
                         "өсөх" if S["gann_state"][i] == 1 else "буурах" if S["gann_state"][i] == -1 else "—",
                         S["bj5"][i], S["bj9"][i], S["bj21"][i], S["bj_color"][i]])
        h, e = ws.table(["Огноо", "Нээлт", "Дээд", "Доод", "Хаалт", "Ширхэг", "Үнийн дүн", "MA7", "MA29", "MA99", "RSI", "MACD",
                         "Signal", "Hist", "BB mid", "BB дээд", "BB доод", "Gann HiLo", "Gann", "BJ EMA5", "BJ EMA9", "BJ EMA21", "BJ өнгө"],
                        rows, ["date", "n2", "n2", "n2", "n2", "int", "int"] + ["n2"] * 11 + [None] + ["n2"] * 3)
        ws.ws.freeze_panes = f"B{h + 1}"
        ws.ws.auto_filter.ref = f"A{h}:W{e}"


TECHNICAL_TF = TIMEFRAMES
