import pytest

from mse_financials.template import IGNORED, ITEMS, TEMPLATE, group_of, match_item, norm


def test_norm_strips_punctuation_and_spelling_variants():
    assert norm(" НДШ – ийн  өглөг") == norm("НДШ-ийн өглөг") == "ндшийнөглөг"
    assert norm("Татварын дараахь ашиг (алдагдал)") == norm("Татварын дараах ашиг ( алдагдал )")
    assert norm("Борлуулсан бүтээгдэхүүний өртөг") == norm("Борлуулалтын өртөг")


def test_spelling_fix_does_not_corrupt_borluulalt():
    """'орлуулалт' -> 'оруулалт' засвар 'борлуулалт' дотор орж болохгүй (өмнө нь орж байсан алдаа)."""
    assert "борлуулалт" in norm("Борлуулалтын орлого")


def test_template_keys_unique_and_labels_non_empty():
    keys = [i.key for i in ITEMS]
    assert len(keys) == len(set(keys)) and all(i.label for i in ITEMS)
    assert sum(1 for t in TEMPLATE if not hasattr(t, "key")) >= 5


@pytest.mark.parametrize("statement,label,code,group,key", [
    ("balance", "Нөөц  /өр төлбөр/", "2.1.1.9", "STL", "st_provision"),
    ("balance", "Нөөц /өр төлбөр/", "2.1.2.2", "LTL", "lt_provision"),
    ("balance", "Борлуулах зорилгоор эзэмшиж буй эргэлтийн бус хөрөнгө (борлуулах бүлэг хөрөнгө)", "1.1.9", "CA", "held_for_sale"),
    ("balance", "Борлуулах зорилгоор эзэмшиж буй эргэлтийн бус хөрөнгө ( борлуулах бүлэг хөрөнгө )- нд хамаарах өр төлбөр",
     "2.1.1.11", "STL", "held_for_sale_liab"),
    ("balance", "Эздийн өмч", "2.3", "EQ", "share_capital"),      # хуучин маягт: нэр өөр, дугаараар таних
    ("balance", "Өмч", "2.3", "EQ", "share_capital"),
    ("balance", "Нийт хөрөнгийн дүн", "1.3", None, "total_assets"),
    ("balance", "Эргэлтийн хөрөнгө", "1.1", None, None),           # гарчиг — мөр биш
    ("income", "Татварын дараахь ашиг (алдагдал)", "22", None, "profit_after_tax"),
    ("income", "Борлуулсан бүтээгдэхүүний өртөг", "2", None, "cogs"),
    ("income", "Хүүгийн орлого", "5", None, "interest_income"),
    ("income", "Тайлант үеийн цэвэр ашиг ( алдагдал)", "24", None, "net_income"),
])
def test_match_item(statement, label, code, group, key):
    item = match_item(statement, label, code, group)
    assert (item.key if item else None) == key


def test_match_respects_statement():
    assert match_item("income", "Дансны авлага", "", None) is None


def test_group_of_code_prefix():
    assert [group_of(c) for c in ("2.1.1.9", "2.1.2.2", "1.1.4", "1.2.1", "2.3.5", "1.3")] == \
           ["STL", "LTL", "CA", "NCA", "EQ", None]


def test_ignored_labels_are_normalised():
    assert norm("-хувийн") in IGNORED and norm("Хувийн өмч") in IGNORED
