"""2026 Q2-ийн шинэ маягтууд: англи шошго (АПУ), толгойгүй + дугаар нэрэнд нийлсэн (Монос хүнс),
урт sheet нэр + дугаар нэрэнд нийлсэн (Мах импекс), `nst`/`ot` sheet нэр (Түмэн шувуут)."""
from datetime import date

from openpyxl import Workbook

from mse_financials.models import Downloaded
from mse_financials.parse import parse_report


def save(path, sheets):
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    wb.save(path)
    return path


def parse(path, ticker="X"):
    return parse_report(Downloaded(ticker, path))


def test_english_statements(tmp_path):
    bs = [["APU JSC"], ["Consolidated statement of financial position"], [], ["", "", "", "Reporting date:", "2026.01.01-2026.06.30"],
          ["/tugrik/"], ["№", "Items", "", "Beginning balance", "Ending balance"],
          ["1", "ASSETS"], ["1.1", "Current assets"],
          ["1.1.1", "Cash and cash equivalents", "", "1000", "2000"],
          ["1.1.20", "Total current assets", "", "1000", "2000"],
          ["1.2", "Non-current assets"],
          ["1.2.1", "Property, plant and equipment", "", "3000", "4000"],
          ["1.2.20", "Total non-current assets", "", "3000", "4000"],
          ["1.3", "Total assets", "", "4000", "6000"],
          ["2.1.1", "Current liabilities"],
          ["2.1.1.1", "Trade payables", "", "500", "600"],
          ["2.1.1.9", "Contingent liabilities short term", "", "50", "60"],
          ["2.1.1.20", "Total current liabilities", "", "550", "660"],
          ["2.1.2", "Non-current liabilities"],
          ["2.1.2.2", "Contingent liabilities long term", "", "5", "6"],
          ["2.1.2.20", "Total non-current liabilities", "", "5", "6"],
          ["2.2", "Total liabilities", "", "555", "666"],
          ["2.3.2", "Common stock", "", "100", "100"],
          ["2.3.9", "Retained earnings", "", "3345", "5234"],
          ["2.3.20", "Total equity", "", "3445", "5334"],
          ["2.4", "Total liabilities and equity", "", "4000", "6000"]]
    inc = [["APU JSC"], [], ["Consolidated statement of Profit or loss"], [], ["", "", "", "Reporting date:", "2026.01.01-2026.06.30"],
           ["/tugrik/"], ["№", "Items", "", "Prior  year", "Current year"],
           ["1", "Revenue", "", "9000", "8000"], ["2", "Cost of sales", "", "5000", "4000"],
           ["3", "Gross profit", "", "4000", "4000"],
           ["17", "Other gain or (loss)", "", "-1", "-2000"],
           ["18", "Profit before tax", "", "3000", "2000"], ["19", "Corporation income tax", "", "300", "200"],
           ["20", "Profit after tax", "", "2700", "1800"], ["22", "Net profit", "", "2700", "1800"],
           ["23", "Other comprehensive income", "", "10", "30"],
           ["26", "Other gain or (loss)", "", "0", "7"],
           ["28", "Total other comprehensive income:", "", "2710", "1830"]]
    r = parse(save(tmp_path / "APU 9020262report.xlsx", {"BS": bs, "IS": inc, "CF": [["x"]]}), "APU")
    v = r.values
    assert (r.period.label, r.end_date) == ("2026 Q2", date(2026, 6, 30))
    assert v["cash"] == 2.0 and v["total_assets"] == 6.0          # бүтэн төгрөг -> мянган төгрөг
    assert v["share_capital"] == 0.1 and v["retained"] == 5.234 and v["total_le"] == 6.0
    assert v["st_provision"] == 0.06 and v["lt_provision"] == 0.006
    assert v["other_profit"] == -2.0 and v["oci_other_gain"] == 0.007     # "Other gain or (loss)" хоёр янзаар
    assert v["oci"] == 0.03 and v["total_comprehensive"] == 1.83
    assert v["revenue"] == 8.0 and v["net_income"] == 1.8


def test_mfc_headerless_embedded_codes_and_totals_on_group_headers(tmp_path):
    bs = [["Сангийн сайдын 2017 оны 361 дүгээр тушаал"], [], ["САНХҮҮГИЙН БАЙДЛЫН ТАЙЛАН"],
          ["Монос хүнс ХК", "", "2026 оны 07 сарын 20 өдөр"], ["(Аж ахуйн нэгжийн нэр)", "", "/төгрөгөөр/"], [],
          ["", "12-р сар 2025", "2026-01-01 -с 2026-06-30 хүртэл"], [],
          ["1 ХӨРӨНГӨ"], ["1.1 Эргэлтийн хөрөнгө"],
          ["1.1.1 Мөнгө, түүнтэй адилтгах хөрөнгө", "50000", "100000"],
          ["Бараа", "1", "2"],                                     # дэд задаргаа — алгасна
          ["Нийт 1.1 Эргэлтийн хөрөнгө", "50000", "100000"],
          ["1.2 Эргэлтийн бус хөрөнгө"], ["1.2.1 Үндсэн хөрөнгө", "300000", "300000"],
          ["Нийт 1.2 Эргэлтийн бус хөрөнгө", "300000", "300000"],
          ["Нийт 1 ХӨРӨНГӨ", "350000", "400000"],
          ["2 ӨР ТӨЛБӨР БА ЭЗДИЙН ӨМЧ"],
          ["2.1.1 Богино хугацаат өр төлбөр", "50000", "60000"],
          ["2.1.2 Дансны өглөг", "40000", "50000"], ["2.1.10 Нөөц өр төлбөр", "10000", "10000"],
          ["2.1.13 Урт хугацаат өр төлбөр", "30000", "40000"],
          ["2.1.14 Урт хугацаат зээл", "20000", "30000"], ["2.1.15 Нөөц өр төлбөр", "10000", "10000"],
          ["Нийт Өр төлбөр", "80000", "100000"],
          ["Эздийн өмч"],
          ["2.1.1 Өмч - Төрийн", "0", "0"], ["2.1.2 Өмч - Хувийн", "0", "0"], ["2.1.3 Өмч - Хувьцаат", "200000", "200000"],
          ["2.1.9 Хуримтлагдсан ашиг", "70000", "100000"],
          ["Нийт Эздийн өмч", "270000", "300000"],
          ["Нийт 2 ӨР ТӨЛБӨР БА ЭЗДИЙН ӨМЧ", "350000", "400000"], ["4 Зөрүү", "0", "0"]]
    inc = [["ОРЛОГЫН ДЭЛГЭРЭНГҮЙ ТАЙЛАН"], ["Монос хүнс ХК"], ["(Аж ахуйн нэгжийн нэр)", "", "/төгрөгөөр/"], [],
           ["", "2025-01-01 -с 2025-06-30 хүртэл", "2026-01-01 -с 2026-06-30 хүртэл"],
           ["1 Орлого үр дүн"],
           ["1.1 Борлуулалтын орлого (цэвэр)", "230000", "250000"],
           ["1.2 Борлуулсан бүтээгдэхүүний өртөг", "100000", "110000"],
           ["1.3 Нийт ашиг (алдагдал)", "130000", "140000"],
           ["1.19 Орлогын албан татвар", "8000", "4000"],
           ["1.22 Тайлант үеийн цэвэр ашиг (алдагдал)", "44000", "31000"],
           ["Нийт 1 Орлого үр дүн", "44000", "31000"]]
    r = parse(save(tmp_path / "MFC 55120262report.xlsx", {"BS": bs, "IS": inc, "CE": [["x"]]}), "MFC")
    v = r.values
    assert (r.period.label, r.end_date) == ("2026 Q2", date(2026, 6, 30))      # "-с" хэлбэрийн огнооноос
    assert v["cash"] == 100.0 and v["total_ca"] == 100.0 and v["total_nca"] == 300.0 and v["total_assets"] == 400.0
    assert v["total_stl"] == 60.0 and v["total_ltl"] == 40.0                    # гарчиг мөр дээрх нийт дүн
    assert v["st_provision"] == 10.0 and v["lt_provision"] == 10.0              # бүлгийг гарчгаар, дугаараар биш
    assert v["lt_loan"] == 30.0 and v["payable"] == 50.0
    assert v["total_liabilities"] == 100.0 and v["share_capital"] == 200.0 and v["total_equity"] == 300.0
    assert v["total_le"] == 400.0
    assert "inventory" not in v                                                  # "Бараа" дэд мөр биш
    assert v["revenue"] == 250.0 and v["cogs"] == 110.0 and v["income_tax"] == 4.0 and v["net_income"] == 31.0
    assert v["total_comprehensive"] == 31.0


def test_mmx_long_sheet_names_embedded_codes_and_equity_header_not_share_capital(tmp_path):
    bs = [["Үзүүлэлт", "1. Эхний үлдэгдэл", "2. Эцсийн үлдэгдэл /төгрөгөөр/"],
          ["1 ХӨРӨНГӨ", "0", "0"], ["1.1 Эргэлтийн хөрөнгө", "0", "0"],
          ["1.1.1 Мөнгө,түүнтэй адилтгах хөрөнгө", "23516177.29", "145226481.82"],
          ["0", "0", "0"],
          ["1.1.11 Эргэлтийн хөрөнгийн дүн", "100000", "200000"],
          ["1.3 НИЙТ ХӨРӨНГИЙН ДҮН", "100000", "200000"],
          ["2.1.1 Богино хугацаат өр төлбөр", "0", "0"],
          ["2.1.1.1 Дансны өглөг", "40000", "50000"],
          ["2.1.1.13 Богино хугацаат өр төлбөрийн дүн", "40000", "50000"],
          ["2.2 Өр төлбөрийн нийт дүн", "40000", "50000"],
          ["2.3 Эздийн өмч", "0", "0"],                                  # гарчиг: 2.3 дугаараар өмч гэж андуурч болохгүй
          ["2.3.1 Өмч:", "377820983.84", "377820983.84"],
          ["2.3.1.1    -  төрийн", "0", "0"], ["2.3.1.2           -  хувийн", "377820983.84", "377820983.84"],
          ["2.3.7 Хуримтлагдсан ашиг", "60000", "150000"],
          ["2.3.9 Эздийн өмчийн дүн", "60000", "150000"],
          ["2.4 ӨР ТӨЛБӨР БА ЭЗДИЙН ӨМЧИЙН ДҮН", "100000", "200000"]]
    inc = [["Үзүүлэлт", "1. Эхний үлдэгдэл", "2. Эцсийн үлдэгдэл /төгрөгөөр/"],
           ["1 Борлуулалтын орлого (цэвэр)", "1000000", "400000"], ["2 Борлуулсан бүтээгдэхүүний өртөг", "900000", "350000"],
           ["3 Нийт ашиг ( алдагдал)", "100000", "50000"],
           ["18 Татвар төлөхийн өмнөх ашиг (алдагдал)", "10000", "9000"],
           ["19 Орлогын татварын зардал", "1000", "900"],
           ["20.Ердийн үйл ажиллагааны татварын дараах ашиг (алдагдал)", "9000", "8100"],
           ["22.Тайлант үеийн цэвэр ашиг (алдагдал)", "9000", "8100"]]
    p = save(tmp_path / "MMX 20820262report.xlsx", {
        "Санхүү байдлын тайлан - Хагас жил": bs, "Орлогын дэлгэрэнгүй тайлан- Хагас жил": inc,
        "Өмчийн өөрчлөлтийн тайлан - Хагас жил": [["x"]], "16.5.1 Богино хугацаат өр төлбөр": [["x"]]})
    r = parse(p, "MMX")
    v = r.values
    assert (r.period.label, r.end_date) == ("2026 Q2", date(2026, 6, 30))      # огноо файлд байхгүй -> файлын нэрнээс
    assert v["cash"] == 145226.48182                                            # /төгрөгөөр/ -> мянган төгрөг
    assert v["total_assets"] == 200.0 and v["total_ca"] == 200.0 and v["total_stl"] == 50.0
    assert v["share_capital"] == 377820.98384
    assert v["profit_after_tax"] == 8.1 and v["net_income"] == 8.1 and v["income_tax"] == 0.9


def test_latin_sheet_names_nst_and_ot(tmp_path, report_factory):
    path = report_factory(tmp_path / "TUM 54920262report.xlsx", 1000, 400, end="2026.01.01-2026.06.30", sheets=("nst", "ot"))
    r = parse(path, "TUM")
    assert r is not None and r.values["total_assets"] == 1000.0 and r.values["revenue"] == 400.0
    assert r.end_date == date(2026, 6, 30)


def test_old_equity_split_rows_sum_into_share_capital(tmp_path):
    """Хуучин маягт: "Өмч" мөргүй, "Төрийн өмч/Хувийн өмч" хэсгүүдтэй (өмнө нь гарчиг мөрийн 0 орж байсан)."""
    bs = [["", "Тайлант үе:", "2025.01.01-2025.06.30"], ["", "", "", "", "/Мянган төгрөг/"],
          ["", "№", "Үзүүлэлт", "Эхний үлдэгдэл", "Эцсийн үлдэгдэл"],
          ["", "2", "ӨР ТӨЛБӨР БА ЭЗДИЙН ӨМЧ", "0", "0"], ["", "2.3", "   Эздийн өмч", "0", "0"],
          ["", "2.3.1", "      Төрийн өмч", "0", "0"], ["", "2.3.2", "      Хувийн өмч", "4000", "4000"],
          ["", "2.3.3", "      Хувьцаат өр төлбөр", "0", "0"],
          ["", "2.3.11", "   Эздийн өмчийн дүн", "5000", "5000"],
          ["", "1.3", "Нийт хөрөнгийн дүн", "5000", "5000"]]
    r = parse(save(tmp_path / "TUM 54920252report.xlsx", {"СБД": bs}), "TUM")
    assert r.values["share_capital"] == 4000.0 and r.values["total_equity"] == 5000.0
