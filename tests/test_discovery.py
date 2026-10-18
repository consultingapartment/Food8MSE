from mse_financials.discovery import find_report_links, parse_securities
from mse_financials.models import Period

PAGE_URL = "https://open.mse.mn/securities/90/tab/financials"
H = "https://issuers.mse.mn//uploads"

FINANCE_HTML = f"""
<table>
 <tr><td>2026</td><td>2</td><td>2026-07-28</td>
     <td><a href="{H}/finance_reports/90_finance_report_pdf_6a68.pdf">PDF</a></td>
     <td><a href="{H}/finance_reports/90_finance_report_xls_6a68.xlsx">XLS</a></td></tr>
 <tr><td>2025</td><td>2</td><td>2025-07-21</td>
     <td><a href="{H}/finance_reports/ 90 20252report.xls">XLS</a></td></tr>
 <tr><td>2015</td><td>4</td><td>2016-04-15</td>
     <td><a href="{H}/finance_reports/../../uploads/finance/9020154report.xls">XLS</a></td></tr>
</table>
<table>
 <tr><td>PwC Audit</td><td>2026-04-08</td>
     <td><a href="{H}/audit_concl_files/90_177563audit.pdf">file</a></td></tr>
 <tr><td>Онч аудит</td><td>2026-04-10</td>
     <td><a href="{H}/files/20260508083528_69fd2fd093dab.pdf">file</a></td></tr>
</table>
<script>var x = "{H}/finance_reports/90_finance_report_xls_6a68.xlsx";</script>
"""


def by_name(links):
    return {link.url.rsplit("/", 1)[-1]: link for link in links}


def test_period_comes_from_table_row_not_filename():
    links = by_name(find_report_links(FINANCE_HTML, PAGE_URL))
    assert links["90_finance_report_xls_6a68.xlsx"].period == Period(2026, 2)
    assert links["90_finance_report_pdf_6a68.pdf"].kind == "pdf"
    assert links["90_finance_report_xls_6a68.xlsx"].kind == "xls"


def test_audit_files_are_skipped():
    urls = [link.url for link in find_report_links(FINANCE_HTML, PAGE_URL)]
    assert not any("audit" in u.lower() for u in urls)
    assert not any("20260508083528" in u for u in urls)


def test_script_duplicate_does_not_override_row_period():
    links = find_report_links(FINANCE_HTML, PAGE_URL)
    xlsx = [x for x in links if x.url.endswith("6a68.xlsx")]
    assert len(xlsx) == 1 and xlsx[0].period == Period(2026, 2)


def test_odd_urls_are_normalised():
    links = find_report_links(FINANCE_HTML, PAGE_URL)
    old = [x for x in links if x.url.endswith("9020154report.xls")]
    assert old and "../" not in old[0].url and "//uploads" not in old[0].url.split("://", 1)[1]
    assert any(x.url.endswith(" 90 20252report.xls") and x.period == Period(2025, 2) for x in links)


def test_parse_securities_reads_stock_tables():
    html = """<div id="stocks"><div id="class1"><table>
      <tr><td>1</td><td><a href="/securities/90">APU</a></td><td>АПУ ХК</td></tr>
      <tr><td>2</td><td><a href="/securities/549">TUM</a></td><td>Түмэн</td></tr></table></div>
      <div id="class2"><table><tr><td>1</td><td><a href="/securities/22">TCK</a></td><td>x</td></tr></table></div></div>
      <div id="bonds"><table><tr><td>1</td><td><a href="/securities/1">BOND</a></td><td>x</td></tr></table></div>"""
    assert parse_securities(html) == {"APU": 90, "TUM": 549, "TCK": 22}
