import logging
from pathlib import Path

import pytest

from mse_financials.models import Downloaded, Period
from mse_financials.parse import parse_report
from mse_financials.pdf import ScannedPdfError, read_pdf_sheets, rows_from_lines
from mse_financials.pipeline import parse_all, warn_inconsistent

pytest.importorskip("pdfplumber")
TCK_PDF = Path(__file__).parent / "data" / "TCK_2025Q4.pdf"      # ТЧК-ийн МХБ-д ирүүлсэн ил тайлан (текст давхаргатай)


# ── мөр угсрах дүрмүүд ───────────────────────────────────────────────────────
def test_wrapped_label_with_numbers_on_middle_line():
    rows = rows_from_lines([
        "1. ХӨРӨНГӨ",
        "2.1.1.13 Богино хугацаат өр",
        "14,954,204,752.72 17,078,021,634.75",
        "төлбөрийн дүн",
    ])
    assert rows[-1][1:] == ["2.1.1.13", "Богино хугацаат өр төлбөрийн дүн", 14954204752.72, 17078021634.75]


def test_numbers_only_second_line_becomes_blank_row_and_negative_numbers():
    rows = rows_from_lines([
        "1. Борлуулалтын орлого (цэвэр) 10.00 20.00",
        "17. Бусад ашиг ( алдагдал) - 61,720,984.07 - 726,620,417.13",
        "23.1 Хөрөнгийн дахин үнэлгээний",
        "0.00 0.00",
        "нэмэгдлийн зөрүү",
        "0.00 0.00",
    ])
    assert rows[1][1:] == ["17", "Бусад ашиг ( алдагдал)", -61720984.07, -726620417.13]
    assert rows[2][1:] == ["23.1", "Хөрөнгийн дахин үнэлгээний нэмэгдлийн зөрүү", 0.0, 0.0]
    assert rows[3][1:] == ["", "", 0.0, 0.0]                       # дугаар нь хасагдсан мөр


def test_page_boundary_duplicates_are_dropped():
    rows = rows_from_lines([
        "1. Борлуулалтын орлого 1.00 2.00",
        "19. Орлогын татварын зардал 5.00 6.00",       # хуудасны төгсгөл
        "19. Орлогын татварын зардал 5.00 6.00",       # дараагийн хуудасны эхэнд яг давтагдсан мөр
        "2.1.1.10 Бусад богино",                       # хуудасны төгсгөл
        "7.00 0.00",
        "хугацаат өр төлбөр",
        "хугацаат өр төлбөр",                          # дараагийн хуудасны эхэнд нэрийн төгсгөл давтагдсан
    ])
    assert [r[1] for r in rows] == ["1", "19", "2.1.1.10"]
    assert rows[-1][2:] == ["Бусад богино хугацаат өр төлбөр", 7.0, 0.0]


def test_titles_headers_and_check_rows_are_skipped():
    rows = rows_from_lines([
        "2025 оны жилийн эцсийн тайлан", "Үзүүлэлт 1. Эхний үлдэгдэл 2. Эцсийн", "/төгрөгөөр/ үлдэгдэл /", "төгрөгөөр/",
        "1. ХӨРӨНГӨ", "1.3 НИЙТ ХӨРӨНГИЙН ДҮН 100.00 200.00",
        "1 Актив 100.00 200.00", "2 Пассив 100.00 200.00", "3 Зөрүү 0.00 0.00", "Хэвлэсэн огноо: 2026-02-24 16:57:02",
    ])
    assert [r[1] for r in rows] == ["1", "1.3"]


# ── бодит PDF ───────────────────────────────────────────────────────────────
def test_real_tck_pdf_has_two_statements_with_period_and_unit():
    sheets = read_pdf_sheets(TCK_PDF)
    assert set(sheets) == {"СБД", "ОДТ"}
    assert sheets["СБД"][0][2:] == ["Тайлант үе:", "2025.01.01-2025.12.31"]
    assert "/Төгрөг/" in sheets["СБД"][1]


@pytest.fixture(scope="module")
def tck():
    return parse_report(Downloaded("TCK", TCK_PDF, "", None))           # үе нь файл доторх огнооноос


def test_real_tck_pdf_parses_to_the_standard_template_in_thousands(tck):
    r = tck
    assert (r.period.label, str(r.end_date), r.months) == ("2025 Q4", "2025-12-31", 12)
    v = r.values
    assert v["total_assets"] == pytest.approx(114_009_471.57188)       # Эцсийн үлдэгдэл, мянган төгрөгөөр
    assert v["total_equity"] == pytest.approx(88_598_116.60381)
    assert v["total_liabilities"] == pytest.approx(25_411_354.96807)
    assert v["total_stl"] == pytest.approx(17_078_021.63475) and v["total_ltl"] == pytest.approx(8_333_333.33332)
    assert v["revenue"] == pytest.approx(112_068_354.5323) and v["net_income"] == pytest.approx(8_685_822.3575)
    assert v["profit_before_tax"] == pytest.approx(10_623_303.28211)
    assert v["other_stl"] == 0.0                                        # нэр нь хуудас дамнасан мөр
    assert r.size >= 70


def test_real_tck_pdf_passes_all_accounting_identities(tck, caplog):
    r = tck
    with caplog.at_level(logging.WARNING):
        warn_inconsistent([r], only=[r])
    assert not caplog.records


# ── скан PDF ба нэгтгэл ─────────────────────────────────────────────────────
@pytest.fixture
def scanned_pdf(tmp_path):
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    path = tmp_path / "MGLA 57220254report.pdf"
    c = canvas.Canvas(str(path))
    c.rect(50, 50, 400, 600, fill=1)            # зөвхөн дүрс, текст байхгүй
    c.showPage()
    c.save()
    return path


def test_scanned_pdf_raises_clear_error(scanned_pdf):
    with pytest.raises(ScannedPdfError, match="OCR"):
        read_pdf_sheets(scanned_pdf)


def test_scanned_pdf_is_skipped_with_warning_not_crash(scanned_pdf, caplog):
    with caplog.at_level(logging.WARNING):
        assert parse_all([Downloaded("MGLA", scanned_pdf, "", Period(2025, 4))]) == []
    assert "OCR" in caplog.text


def test_excel_beats_pdf_for_the_same_period(tmp_path, report_factory):
    xlsx = report_factory(tmp_path / "TCK 2220254report.xlsx", 114_009_471.0, 112_068_354.0, end="2025.01.01-2025.12.31")
    items = [Downloaded("TCK", TCK_PDF, "", Period(2025, 4)), Downloaded("TCK", xlsx, "", Period(2025, 4))]
    for order in (items, items[::-1]):
        (rep,) = parse_all(order)
        assert rep.source == xlsx.name


def test_pdf_alone_is_merged_when_no_excel_exists():
    (rep,) = parse_all([Downloaded("TCK", TCK_PDF, "", Period(2025, 4))])
    assert rep.source == TCK_PDF.name and rep.values["total_assets"] == pytest.approx(114_009_471.57188)


def test_integer_amounts_without_decimals_are_read():
    """Зарим компани (GAZR) дүнг аравтын орноргүй бичдэг: '30,153,766', '-6,327'. Мөрийн дугаар (1, 13) дүн биш."""
    from mse_financials.pdf import _split_numbers, rows_from_lines

    assert _split_numbers("Бусад зардал 17,210 677,185.4") == ("Бусад зардал", [17210.0, 677185.4])
    assert _split_numbers("Гадаад валютын зөрүү 61,132.4 -6,327") == ("Гадаад валютын зөрүү", [61132.4, -6327.0])
    rows = rows_from_lines(["1 ХӨРӨНГӨ", "1.1.1 Мөнгө 2,646,355 2,390,592.9", "13 Бусад 380,000 380,000"])
    assert rows[-1][1:] == ["13", "Бусад", 380000.0, 380000.0]
