"""Харьцааны шинжилгээ: компанийн sheet-ийн доор Excel ТОМЬЁОгоор бичигдэнэ (шинэ тайлан нэмэгдэхэд өөрөө тооцогдоно).

Томьёо нь тухайн sheet-ийн дээд талын мөрүүдийг (Баланс, Орлогын тайлан) лавлана. Тооцооллын дүрэм:
  * Орлогын тайлангийн мөр нь оны эхнээс хуримтлагдсан тул жилийн түвшинд хөрвүүлнэ: × 12 ÷ хамрах сар.
  * Дундаж үлдэгдэл = (өмнөх оны Q4-ийн үлдэгдэл + тайлант үеийн эцсийн үлдэгдэл) ÷ 2.
    Өмнөх оны Q4 байхгүй бол тайлант үеийн эцсийн үлдэгдлийг ашиглана.
  * Нэг оролцогч нь хоосон бол харьцаа хоосон үлдэнэ (0 гэж тооцохгүй).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

PCT, TIMES, DAYS, MONEY = "0.0%;[Red]-0.0%", '0.00"x"', "0", "#,##0;[Red]-#,##0"
FIRST_ROW_NOTE = ("Орлогын мөр нь оны эхнээс хуримтлагдсан → жилийн түвшинд хөрвүүлнэ (× 12 ÷ хамрах сар). "
                  "Дундаж = өмнөх оны Q4 ба тайлант үеийн эцсийн үлдэгдлийн дундаж (өмнөх оны Q4 байхгүй бол эцсийн).")


@dataclass(frozen=True)
class Ctx:
    """Нэг баганад томьёо бүтээхэд хэрэгтэй хаягууд."""
    col: str                      # багана (жишээ нь "C")
    last: str                     # сүүлийн баганын үсэг
    row_of: dict[str, int]        # загварын түлхүүр -> мөр
    calc: dict[str, int]          # энэ блокийн тооцоолсон мөр (avg_ta, ann, ...) -> мөр

    def c(self, key: str) -> Optional[str]:
        """Загварын мөрийн энэ баганын нүд (мөр байхгүй бол None)."""
        return f"{self.col}{self.row_of[key]}" if key in self.row_of else None

    def k(self, key: str) -> Optional[str]:
        return f"{self.col}{self.calc[key]}" if key in self.calc else None

    def rng(self, key: str) -> Optional[str]:
        return f"$B{self.row_of[key]}:${self.last}{self.row_of[key]}" if key in self.row_of else None

    @property
    def dates(self) -> str:
        return f"$B$4:${self.last}$4"


Spec = tuple  # (id, label, format, builder(ctx) -> (formula_body, [нүд...]) | None)


def _guard(body: str, cells: list[Optional[str]]) -> Optional[str]:
    """Бүх нүд тоо байвал л тооцоолно, үгүй бол хоосон."""
    if any(c is None for c in cells):
        return None
    cond = ",".join(f"ISNUMBER({c})" for c in cells)
    return f'=IF(AND({cond}),IFERROR({body},""),"")'


def _avg(key: str) -> Callable[[Ctx], Optional[str]]:
    def build(x: Ctx) -> Optional[str]:
        end, rng = x.c(key), x.rng(key)
        if end is None:
            return None
        prev = f"INDEX({rng},MATCH(DATE(YEAR({x.col}$4)-1,12,31),{x.dates},0))"
        return f'=IF(ISNUMBER({end}),IFERROR(IF({prev}="",{end},({end}+{prev})/2),{end}),"")'
    return build


def _ratio(num: str, den: str, num_keys: tuple[str, ...], den_keys: tuple[str, ...] = (),
           calc_num: tuple[str, ...] = (), calc_den: tuple[str, ...] = (), scale: str = "") -> Callable:
    """num/den: {0},{1}... нь (num_keys + calc_num) ба (den_keys + calc_den)-ийн нүдээр орлогдоно."""
    def build(x: Ctx) -> Optional[str]:
        n = [x.c(k) for k in num_keys] + [x.k(k) for k in calc_num]
        d = [x.c(k) for k in den_keys] + [x.k(k) for k in calc_den]
        if any(v is None for v in n + d):
            return None
        body = f"({num.format(*n)})/({den.format(*d)})" + scale
        return _guard(body, n + d)
    return build


def _growth(key: str) -> Callable[[Ctx], Optional[str]]:
    def build(x: Ctx) -> Optional[str]:
        cur, rng = x.c(key), x.rng(key)
        if cur is None:
            return None
        base = f"INDEX({rng},MATCH(DATE(YEAR({x.col}$4)-1,MONTH({x.col}$4),DAY({x.col}$4)),{x.dates},0))"
        return f'=IF(ISNUMBER({cur}),IFERROR(IF({base}>0,{cur}/{base}-1,""),""),"")'
    return build


def _ccc(x: Ctx) -> Optional[str]:
    cells = [x.k("dio"), x.k("dso"), x.k("dpo")]
    return None if any(c is None for c in cells) else _guard(f"{cells[0]}+{cells[1]}-{cells[2]}", cells)


def _days_impl(avg: str, flow_key: str) -> Callable:
    def build(x: Ctx) -> Optional[str]:
        a, f, ann = x.k(avg), x.c(flow_key), x.k("ann")
        return None if None in (a, f, ann) else _guard(f"{a}/({f}*{ann})*365", [a, f, ann])
    return build


def _times(avg: str, flow_key: str) -> Callable:
    def build(x: Ctx) -> Optional[str]:
        a, f, ann = x.k(avg), x.c(flow_key), x.k("ann")
        return None if None in (a, f, ann) else _guard(f"{f}*{ann}/{a}", [a, f, ann])
    return build


def _ann_flow(flow_key: str, avg: str) -> Callable:
    def build(x: Ctx) -> Optional[str]:
        a, f, ann = x.k(avg), x.c(flow_key), x.k("ann")
        return None if None in (a, f, ann) else _guard(f"{f}*{ann}/{a}", [a, f, ann])
    return build


def _ann(x: Ctx) -> Optional[str]:
    return f'=IF(ISNUMBER({x.col}$6),IFERROR(12/{x.col}$6,""),"")'


def _dupont(x: Ctx) -> Optional[str]:
    cells = [x.k("nm"), x.k("at"), x.k("em")]
    return None if None in cells else _guard(f"{cells[0]}*{cells[1]}*{cells[2]}", cells)


def _interest_cover(x: Ctx) -> Optional[str]:
    pbt, fc = x.c("profit_before_tax"), x.c("finance_cost")
    return None if None in (pbt, fc) else _guard(f"({pbt}+ABS({fc}))/ABS({fc})", [pbt, fc])


def _working_capital(x: Ctx) -> Optional[str]:
    ca, stl = x.c("total_ca"), x.c("total_stl")
    return None if None in (ca, stl) else _guard(f"({ca}-{stl})/1000", [ca, stl])


def _quick(x: Ctx) -> Optional[str]:
    ca, inv, stl = x.c("total_ca"), x.c("inventory"), x.c("total_stl")
    return None if None in (ca, inv, stl) else _guard(f"({ca}-{inv})/{stl}", [ca, inv, stl])


#: (бүлгийн гарчиг | None, [(id, нэр, формат, builder)])
GROUPS: tuple = (
    ("Тооцооны туслах мөрүүд", [
        ("ann", "Жилийн коэффициент (12 ÷ хамрах сар)", "0.00", _ann),
        ("avg_ta", "Дундаж нийт хөрөнгө, мянган төгрөг", MONEY, _avg("total_assets")),
        ("avg_eq", "Дундаж эздийн өмч, мянган төгрөг", MONEY, _avg("total_equity")),
        ("avg_inv", "Дундаж бараа материал, мянган төгрөг", MONEY, _avg("inventory")),
        ("avg_rec", "Дундаж дансны авлага, мянган төгрөг", MONEY, _avg("receivable")),
        ("avg_pay", "Дундаж дансны өглөг, мянган төгрөг", MONEY, _avg("payable")),
    ]),
    ("1. Ашигт ажиллагаа", [
        ("gm", "Нийт ашгийн маржин = Нийт ашиг ÷ Орлого", PCT, _ratio("{0}", "{0}", ("gross_profit",), ("revenue",))),
        ("cogs_pct", "Борлуулалтын өртгийн харьцаа = Өртөг ÷ Орлого", PCT, _ratio("{0}", "{0}", ("cogs",), ("revenue",))),
        ("sell_pct", "Борлуулалт, маркетингийн зардлын харьцаа", PCT, _ratio("{0}", "{0}", ("selling_exp",), ("revenue",))),
        ("admin_pct", "Ерөнхий, удирдлагын зардлын харьцаа", PCT, _ratio("{0}", "{0}", ("admin_exp",), ("revenue",))),
        ("nm", "Цэвэр ашгийн маржин = Цэвэр ашиг ÷ Орлого", PCT, _ratio("{0}", "{0}", ("net_income",), ("revenue",))),
        ("roa", "Хөрөнгийн өгөөж (ROA, жилийн) = Цэвэр ашиг ÷ Дундаж хөрөнгө", PCT,
         _ratio("{0}*{1}", "{0}", ("net_income",), (), ("ann",), ("avg_ta",))),
        ("roe", "Өмчийн өгөөж (ROE, жилийн) = Цэвэр ашиг ÷ Дундаж өмч", PCT,
         _ratio("{0}*{1}", "{0}", ("net_income",), (), ("ann",), ("avg_eq",))),
    ]),
    ("2. DuPont задаргаа (ROE = Маржин × Эргэц × Хөшүүрэг)", [
        ("at", "Хөрөнгийн эргэц = Орлого (жилийн) ÷ Дундаж хөрөнгө", TIMES, _times("avg_ta", "revenue")),
        ("em", "Санхүүгийн хөшүүрэг = Дундаж хөрөнгө ÷ Дундаж өмч", TIMES,
         _ratio("{0}", "{0}", (), (), ("avg_ta",), ("avg_eq",))),
        ("roe_dp", "ROE (DuPont; дээрх ROE-тэй ижил байх ёстой)", PCT, _dupont),
    ]),
    ("3. Хөрвөх чадвар", [
        ("cur", "Эргэлтийн хөрөнгийн харьцаа (Current Ratio) = Эргэлтийн хөрөнгө ÷ Богино хугацаат өр", TIMES,
         _ratio("{0}", "{0}", ("total_ca",), ("total_stl",))),
        ("quick", "Хурдавчилсан харьцаа = (Эргэлтийн хөрөнгө − Бараа материал) ÷ Богино хугацаат өр", TIMES, _quick),
        ("cash_r", "Мөнгөн харьцаа = Мөнгө ÷ Богино хугацаат өр", TIMES, _ratio("{0}", "{0}", ("cash",), ("total_stl",))),
        ("wc", "Ажлын капитал, сая төгрөг", MONEY, _working_capital),
    ]),
    ("4. Өр төлбөрийн даац", [
        ("de", "Өр ÷ Өмч", TIMES, _ratio("{0}", "{0}", ("total_liabilities",), ("total_equity",))),
        ("da", "Өр ÷ Нийт хөрөнгө", PCT, _ratio("{0}", "{0}", ("total_liabilities",), ("total_assets",))),
        ("icr", "Хүүгийн даац = (Татварын өмнөх ашиг + Санхүүгийн зардал) ÷ Санхүүгийн зардал", TIMES, _interest_cover),
    ]),
    ("5. Эргэлт (хүнс, ундааны салбарын онцлог)", [
        ("inv_t", "Бараа материалын эргэц = Өртөг (жилийн) ÷ Дундаж бараа материал", TIMES, _ann_flow("cogs", "avg_inv")),
        ("dio", "Бараа материал хадгалагдах хоног (DIO)", DAYS, _days_impl("avg_inv", "cogs")),
        ("rec_t", "Авлагын эргэц = Орлого (жилийн) ÷ Дундаж авлага", TIMES, _ann_flow("revenue", "avg_rec")),
        ("dso", "Авлага цуглуулах хоног (DSO)", DAYS, _days_impl("avg_rec", "revenue")),
        ("pay_t", "Өглөгийн эргэц = Өртөг (жилийн) ÷ Дундаж өглөг", TIMES, _ann_flow("cogs", "avg_pay")),
        ("dpo", "Өглөг төлөх хоног (DPO)", DAYS, _days_impl("avg_pay", "cogs")),
        ("ccc", "Мөнгөн эргэлтийн мөчлөг (CCC) = DIO + DSO − DPO", DAYS, _ccc),
    ]),
    ("6. Өсөлт (өмнөх оны ижил үеэс, YoY)", [
        ("g_rev", "Орлогын өсөлт", PCT, _growth("revenue")),
        ("g_gp", "Нийт ашгийн өсөлт", PCT, _growth("gross_profit")),
        ("g_ni", "Цэвэр ашгийн өсөлт (өмнөх үе ашигтай үед)", PCT, _growth("net_income")),
    ]),
)
