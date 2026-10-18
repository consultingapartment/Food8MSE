"""Стандарт загвар: бүх компанийн тайланг ижил мөр, ижил дарааллаар нэгтгэх мөрийн жагсаалт.

МХБ-д ирүүлдэг тайлан нь Монголын стандарт маягт (СБД/ОДТ) боловч мөрийн дугаар ("1.1.10", "22" гэх мэт)
нь компани, оноор шилжиж, нэр нь бага зэрэг ялгаатай бичигдэдэг (`ндш – ийн` / `ндш-ийн`, `дараах` / `дараахь`).
Тиймээс мөрийг НЭРЭЭР (хэвийн болгосон) таних ба зөвхөн ялгаагүй байх газар мөрийн дугаарыг нөөцөөр ашиглана.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

BS, IS = "balance", "income"

# Бичгийн алдаа/хувилбарыг нэг хэлбэрт оруулна (хэвийн болгосны дараа хэрэглэнэ).
_SPELLING = (
    ("дараахь", "дараах"), ("ноогдох", "ногдох"), ("нэмэгдэлийн", "нэмэгдлийн"),
    ("хөрөнгөорлуулалт", "хөрөнгөоруулалт"), ("хүүгийн", "хүүний"), ("борлуулсанбүтээгдэхүүний", "борлуулалтын"),
)


def norm(label: str) -> str:
    """Жижиг үсэг, зөвхөн үсэг/тоо: ' НДШ – ийн  өглөг' -> 'ндшийнөглөг'."""
    s = re.sub(r"[^0-9a-zа-яөүё]+", "", str(label).lower())
    for a, b in _SPELLING:
        s = s.replace(a, b)
    return s


@dataclass(frozen=True)
class Item:
    key: str
    label: str
    statement: str
    kind: str = "item"            # item | total | per_share
    aliases: tuple[str, ...] = ()  # нэмэлт нэр (хэвийн болгосон хэлбэрээр тулгана)
    prefixes: tuple[str, ...] = ()  # эхлэлээр таних
    group: str | None = None      # давхардсан нэртэй мөрийг ялгах бүлэг (STL, LTL)
    must: tuple[str, ...] = ()    # хэвийн болгосон нэр заавал агуулах хэсэг
    not_: tuple[str, ...] = ()    # агуулж болохгүй хэсэг
    codes: tuple[str, ...] = ()   # зөвхөн нэр өөр байж болох мөрийн дугаар (нөөц)
    names: tuple[str, ...] = field(init=False, default=())

    def __post_init__(self):
        object.__setattr__(self, "names", tuple({norm(self.label), *map(norm, self.aliases)}))


@dataclass(frozen=True)
class Section:
    label: str
    statement: str
    level: int = 2        # 1 = тайлангийн гарчиг, 2 = бүлэг (эргэлтийн хөрөнгө г.м.)


def _b(key, label, **kw):
    return Item(key, label, BS, **kw)


def _i(key, label, **kw):
    return Item(key, label, IS, **kw)


#: Мөр бүрийн дараалал нь маягтын дараалалтай ижил. Section = гарчиг мөр.
TEMPLATE: tuple[Item | Section, ...] = (
    Section("САНХҮҮГИЙН БАЙДЛЫН ТАЙЛАН (БАЛАНС) — эцсийн үлдэгдэл", BS, 1),
    Section("Эргэлтийн хөрөнгө", BS),
    _b("cash", "Мөнгө, түүнтэй адилтгах хөрөнгө"),
    _b("receivable", "Дансны авлага"),
    _b("tax_receivable", "Татвар, НДШ-ийн авлага"),
    _b("other_receivable", "Бусад авлага"),
    _b("other_fin_assets", "Бусад санхүүгийн хөрөнгө"),
    _b("inventory", "Бараа материал"),
    _b("prepaid", "Урьдчилж төлсөн зардал/тооцоо"),
    _b("other_ca", "Бусад эргэлтийн хөрөнгө"),
    _b("held_for_sale", "Борлуулах зорилгоор эзэмшиж буй эргэлтийн бус хөрөнгө",
       prefixes=("борлуулахзорилгоорэзэмшижбуйэргэлтийнбус",), not_=("өртөлбөр",)),
    _b("livestock", "Эргэлтийн сүргийн мал амьтад"),
    _b("total_ca", "Эргэлтийн хөрөнгийн дүн", kind="total", aliases=("Нийт Эргэлтийн хөрөнгө",)),
    Section("Эргэлтийн бус хөрөнгө", BS),
    _b("ppe", "Үндсэн хөрөнгө"),
    _b("intangible", "Биет бус хөрөнгө"),
    _b("biological", "Биологийн хөрөнгө"),
    _b("lt_investment", "Урт хугацаат хөрөнгө оруулалт"),
    _b("exploration", "Хайгуул ба үнэлгээний хөрөнгө"),
    _b("deferred_tax_asset", "Хойшлогдсон татварын хөрөнгө"),
    _b("investment_property", "Хөрөнгө оруулалтын зориулалттай үл хөдлөх хөрөнгө"),
    _b("rou_asset", "Ашиглах эрхтэй хөрөнгө /түрээсийн/"),
    _b("cip", "Дуусаагүй барилга"),
    _b("other_nca", "Бусад эргэлтийн бус хөрөнгө"),
    _b("goodwill", "Гүүдвилл"),
    _b("total_nca", "Эргэлтийн бус хөрөнгийн дүн", kind="total", aliases=("Нийт Эргэлтийн бус хөрөнгө",)),
    _b("total_assets", "Нийт хөрөнгийн дүн", kind="total", aliases=("Хөрөнгийн нийт дүн", "Нийт ХӨРӨНГӨ")),
    Section("Богино хугацаат өр төлбөр", BS),
    _b("payable", "Дансны өглөг"),
    _b("wages_payable", "Цалингийн өглөг"),
    _b("tax_payable", "Татварын өр"),
    _b("social_payable", "НДШ-ийн өглөг"),
    _b("st_loan", "Богино хугацаат зээл", aliases=("Банкны богино хугацаат зээл",)),
    _b("interest_payable", "Хүүний өглөг", aliases=("Зээлийн хүүгийн өглөг",)),
    _b("dividend_payable", "Ногдол ашгийн өглөг"),
    _b("deferred_income", "Урьдчилж орсон орлого"),
    _b("st_provision", "Нөөц /өр төлбөр/ (богино хугацаат)", group="STL", aliases=("Нөөц /өр төлбөр/",)),
    _b("other_stl", "Бусад богино хугацаат өр төлбөр"),
    _b("held_for_sale_liab", "Борлуулах зорилгоор эзэмшиж буй бүлэг хөрөнгөнд хамаарах өр төлбөр",
       prefixes=("борлуулахзорилгоорэзэмшижбуй",), must=("өртөлбөр",)),
    _b("total_stl", "Богино хугацаат өр төлбөрийн дүн", kind="total"),
    Section("Урт хугацаат өр төлбөр", BS),
    _b("lt_loan", "Урт хугацаат зээл"),
    _b("lt_provision", "Нөөц /өр төлбөр/ (урт хугацаат)", group="LTL", aliases=("Нөөц /өр төлбөр/",)),
    _b("deferred_tax_liab", "Хойшлогдсон татварын өр"),
    _b("grant_income", "Засгийн газрын буцалтгүй тусламжийн орлого"),
    _b("other_ltl", "Бусад урт хугацаат өр төлбөр"),
    _b("total_ltl", "Урт хугацаат өр төлбөрийн дүн", kind="total"),
    _b("total_liabilities", "Өр төлбөрийн нийт дүн", kind="total", aliases=("Нийт Өр төлбөр",)),
    Section("Эздийн өмч", BS),
    _b("share_capital", "Өмч (хувьцаат капитал)", aliases=("Өмч",), codes=("2.3",)),
    _b("treasury", "Халаасны хувьцаа"),
    _b("paid_in", "Нэмж төлөгдсөн капитал"),
    _b("revaluation", "Хөрөнгийн дахин үнэлгээний нэмэгдэл"),
    _b("fx_reserve", "Гадаад валютын хөрвүүлэлтийн нөөц"),
    _b("other_equity", "Эздийн өмчийн бусад хэсэг"),
    _b("retained", "Хуримтлагдсан ашиг"),
    _b("equity_parent", "Толгой компанийн хувьцаа эзэмшигчдэд ногдох"),
    _b("equity_nci", "Хяналтын эрхгүй хувь оролцоонд ногдох"),
    _b("total_equity", "Эздийн өмчийн дүн", kind="total", aliases=("Нийт Эздийн өмч",)),
    _b("total_le", "Өр төлбөр ба эздийн өмчийн дүн", kind="total", aliases=("Нийт ӨР ТӨЛБӨР БА ЭЗДИЙН ӨМЧ",)),

    Section("ОРЛОГЫН ДЭЛГЭРЭНГҮЙ ТАЙЛАН — тайлант үе (оны эхнээс хуримтлагдсан)", IS, 1),
    _i("revenue", "Борлуулалтын орлого (цэвэр)", aliases=("Борлуулалтын орлого",)),
    _i("cogs", "Борлуулалтын өртөг"),
    _i("gross_profit", "Нийт ашиг (алдагдал)", kind="total"),
    _i("rent_income", "Түрээсийн орлого"),
    _i("interest_income", "Хүүний орлого"),
    _i("dividend_income", "Ногдол ашгийн орлого"),
    _i("fee_income", "Эрхийн шимтгэлийн орлого"),
    _i("other_income", "Бусад орлого"),
    _i("selling_exp", "Борлуулалт, маркетингийн зардал"),
    _i("admin_exp", "Ерөнхий ба удирдлагын зардал"),
    _i("finance_cost", "Санхүүгийн зардал"),
    _i("other_exp", "Бусад зардал"),
    _i("fx_gain", "Гадаад валютын ханшийн зөрүүний олз (гарз)"),
    _i("ppe_disposal", "Үндсэн хөрөнгө данснаас хассаны олз (гарз)"),
    _i("intangible_disposal", "Биет бус хөрөнгө данснаас хассаны олз (гарз)"),
    _i("investment_gain", "Хөрөнгө оруулалт борлуулснаас үүссэн олз (гарз)",
       aliases=("Хөрөнгө оруулалт борлуулсанаас үүссэн олз (гарз)", "Хөрөнгө оруулалт борлуулсны олз (гарз)")),
    _i("associate_profit", "Толгой компанид хамаарах хараат компанийн ашиг, алдагдал"),
    _i("jv_profit", "Толгой компанид хамаарах хамтарсан үйлдвэрийн ашиг, алдагдал"),
    _i("other_profit", "Бусад ашиг (алдагдал)"),
    _i("profit_before_tax", "Татвар төлөхийн өмнөх ашиг (алдагдал)", kind="total"),
    _i("income_tax", "Орлогын татварын зардал", aliases=("Орлогын албан татвар",)),
    _i("profit_after_tax", "Татварын дараах ашиг (алдагдал)", kind="total",
       aliases=("Ердийн үйл ажиллагааны татварын дараах ашиг (алдагдал)",)),
    _i("discontinued", "Зогсоосон үйл ажиллагааны татварын дараах ашиг (алдагдал)"),
    _i("net_income", "Тайлант үеийн цэвэр ашиг (алдагдал)", kind="total"),
    _i("oci_revaluation", "Хөрөнгийн дахин үнэлгээний нэмэгдлийн зөрүү"),
    _i("oci_fx", "Гадаад валютын хөрвүүлэлтийн зөрүү"),
    _i("oci_other_gain", "Бусад олз (гарз)"),
    _i("oci_remeasure", "Ажилчдын тэтгэмжийн дахин хэмжилт"),
    _i("oci", "Бусад дэлгэрэнгүй орлогын дүн", kind="total"),
    _i("total_comprehensive", "Орлогын нийт дүн", kind="total", aliases=("Нийт дэлгэрэнгүй орлогын дүн", "Нийт Орлого үр дүн")),
)

#: Загварт оруулахгүй, дэд/давхар мөрүүд (тайланд "таараагүй" гэж гаргахгүй).
IGNORED = frozenset(map(norm, (
    "-төрийн", "-хувийн", "-хувьцаат", "Төрийн өмч", "Хувийн өмч", "Хувьцаат өр төлбөр", "Актив", "Пассив", "Зөрүү",
    "ӨР ТӨЛБӨР БА ЭЗДИЙН ӨМЧ", "Бусад дэлгэрэнгүй орлого", "Толгой компанийн хувьцаа эзэмшигчид",
    "Хяналтын эрхгүй хувь оролцоо", "Толгой компанийн хувьцаа эзэмшигчдэд ногдох",
    "Хяналтын эрхгүй хувь оролцоонд ногдох", "Нэгж хувьцаанд ногдох суурь ашиг (алдагдал)",
)))

ITEMS: tuple[Item, ...] = tuple(t for t in TEMPLATE if isinstance(t, Item))
BY_KEY = {i.key: i for i in ITEMS}

#: Бүлэг тодорхойлогч гарчиг мөрүүд (баланс). Утга нь тэг/хоосон үед л гарчиг гэж үзнэ.
GROUP_HEADERS = {
    norm("Эргэлтийн хөрөнгө"): "CA",
    norm("Эргэлтийн бус хөрөнгө"): "NCA",
    norm("БОГИНО ХУГАЦААТ ӨР ТӨЛБӨР"): "STL",
    norm("УРТ ХУГАЦААТ ӨР ТӨЛБӨР"): "LTL",
    norm("ЭЗДИЙН ӨМЧ"): "EQ",
}


def group_of(code: str) -> str | None:
    """Мөрийн дугаараас бүлэг (дугаар нь шилжсэн ч угтвар нь тогтвортой)."""
    for prefix, group in (("2.1.1", "STL"), ("2.1.2", "LTL"), ("1.1", "CA"), ("1.2", "NCA"), ("2.3", "EQ")):
        if code.startswith(prefix):
            return group
    return None


def match_item(statement: str, label: str, code: str, group: str | None) -> Item | None:
    """Мөрөнд тохирох загварын мөрийг олно (олдохгүй бол None)."""
    n = norm(label)
    code = code.strip()
    for item in ITEMS:
        if item.statement != statement:
            continue
        if item.group and group and item.group != group:
            continue
        if item.must and not all(m in n for m in item.must):
            continue
        if item.not_ and any(m in n for m in item.not_):
            continue
        if n and (n in item.names or any(n.startswith(p) for p in item.prefixes)):
            return item
        if code and code in item.codes and (not item.group or item.group == group or group is None):
            return item
    return None
