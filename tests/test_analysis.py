"""mse_analysis: цэвэр функцүүд, нэгтгэл ба гаралтын Excel. Сүлжээ ашиглахгүй."""
from __future__ import annotations

import math
from datetime import date
from pathlib import Path

import pytest
from openpyxl import load_workbook

from mse_analysis import concentration, forecast, risk, scoring, technical, valuation
from mse_analysis.base import Company
from mse_analysis.cli import import_trades, main
from mse_analysis.config import Assumptions, Weights
from mse_analysis.inputs import Market, Ownership
from mse_analysis.prices import Bar
from mse_financials.models import ParsedReport, Period

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("ликвид", "урсамтгай", "олонжуулагч", "уусгалт", "msiaa")


def bars(closes, start=date(2025, 1, 1)):
    out = []
    for i, c in enumerate(closes):
        d = date.fromordinal(start.toordinal() + i)
        out.append(Bar(d, c, c * 1.01, c * 0.99, c, 100, 100 * c))
    return out


def report(year, months, **v):
    base = {"total_assets": 1000.0, "total_equity": 600.0, "total_liabilities": 400.0, "total_ca": 500.0, "total_stl": 200.0,
            "cash": 100.0, "revenue": 1000.0, "cogs": 600.0, "gross_profit": 400.0, "selling_exp": 100.0, "admin_exp": 100.0,
            "finance_cost": 20.0, "profit_before_tax": 200.0, "net_income": 180.0}
    base.update(v)
    q = months // 3
    return ParsedReport("TST", Period(year, q), date(year, months, 28 if months == 2 else 30), months, values=base)


# ------------------------------------------------------------------ индикатор
def test_sma_ema_basic():
    assert technical.sma([1, 2, 3, 4], 2) == [None, 1.5, 2.5, 3.5]
    e = technical.ema([1, 2, 3], 3)                       # α = 0.5
    assert e == [1, 1.5, 2.25]


def test_rsi_extremes():
    up = technical.rsi([float(i) for i in range(1, 40)])
    assert up[-1] == 100.0
    down = technical.rsi([float(i) for i in range(40, 1, -1)])
    assert down[-1] == 0.0
    assert up[13] is None and up[14] == 100.0


def test_macd_lengths_and_sign():
    closes = [float(i) for i in range(1, 80)]
    line, sig, hist = technical.macd(closes)
    assert len(line) == len(sig) == len(hist) == len(closes)
    assert line[-1] > 0


def test_bollinger_flat_series_has_zero_width():
    mid, up, lo = technical.bollinger([5.0] * 30)
    assert mid[-1] == up[-1] == lo[-1] == 5.0


def test_gann_hilo_flips_with_trend():
    b = bars([10, 11, 12, 13, 14, 15, 16, 15, 12, 9, 7, 5, 4])
    state, line = technical.gann_hilo(b)
    assert state[8] == 1 or state[7] == 1 and state[-1] == -1
    assert state[-1] == -1 and line[-1] is not None


def test_resample_weekly_and_monthly():
    b = bars([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], start=date(2025, 1, 6))     # Даваа-с эхэлнэ
    w = technical.resample(b, "W")
    assert [x.close for x in w] == [7, 10]                     # 1-р долоо хоног Даваа–Ням (7 өдөр), дараа нь 3 өдөр
    assert w[0].open == 1 and w[0].high == max(x.high for x in b[:7]) and w[0].qty == 700
    assert len(technical.resample(b, "M")) == 1


def test_analyze_needs_enough_bars():
    assert technical.analyze("X", bars([1.0] * 10), "D") is None
    r = technical.analyze("X", bars([100 + (i % 7) for i in range(200)]), "D")
    assert r and 0 <= r.state["rsi"] <= 100
    sc = r.state["scenario"]
    assert math.isclose(sc["up"] + sc["down"] + sc["side"], 100.0)


# ------------------------------------------------------------------ үнэлгээ
def test_graham_number():
    assert valuation.graham_number(10, 100) == pytest.approx(150.0)
    assert valuation.graham_number(-1, 100) is None
    assert valuation.graham_number(10, 0) is None


def test_value_matches_formulas():
    c = Company("TST", [report(2024, 12), report(2025, 12, net_income=200.0, total_equity=700.0)])
    a = Assumptions()
    m = Market("TST", 1.0, date(2026, 1, 1), 0.1, 2025, shares=1_000_000.0)       # EPS = 200*1000/1e6 = 0.2
    v = valuation.value(c, m, a)
    assert v.eps == pytest.approx(0.2) and v.bvps == pytest.approx(0.7)
    assert v.graham == pytest.approx(math.sqrt(22.5 * 0.2 * 0.7))
    assert v.graham_margin == pytest.approx((v.graham - 1.0) / v.graham)
    assert v.div_yield == pytest.approx(0.1) and v.div_spread == pytest.approx(0.1 - a.deposit_rate)
    assert v.real_value == pytest.approx(v.graham * (1 + v.div_spread))
    assert v.real_discount == pytest.approx(1 - 1.0 / v.real_value)
    assert v.price_for_target_yield == pytest.approx(0.1 / a.target_yield)
    assert v.pe == pytest.approx(5.0) and v.pb == pytest.approx(1 / 0.7)


def test_loss_making_company_has_no_graham():
    c = Company("TST", [report(2025, 12, net_income=-5.0)])
    v = valuation.value(c, Market("TST", 1.0, None, None, None, shares=1e6), Assumptions())
    assert v.graham is None and v.pe is None and v.graham_margin is None
    assert "ТООЦОХГҮЙ" in v.verdict


def test_cheapness_is_bounded_and_monotonic():
    a = Assumptions()
    c = Company("TST", [report(2025, 12)])
    cheap = valuation.value(c, Market("TST", 0.1, None, 0.05, 2025, shares=1e6), a)
    dear = valuation.value(c, Market("TST", 50.0, None, 0.0, 2025, shares=1e6), a)
    s1, s2 = valuation.cheapness(cheap, a)["total"], valuation.cheapness(dear, a)["total"]
    assert 0 <= s2 < s1 <= 100


def test_bcg_and_correlation():
    assert valuation.bcg_class(10, 0.2, 5, 0.1).startswith("БУХ")
    assert valuation.bcg_class(1, 0.2, 5, 0.1).startswith("ОДОД")
    assert valuation.bcg_class(10, 0.0, 5, 0.1).startswith("МӨНГӨН")
    assert valuation.bcg_class(1, 0.0, 5, 0.1).startswith("АСУУЛТЫН")
    assert valuation.correlation([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert valuation.correlation([1, 2], [1, 2]) is None


# ------------------------------------------------------------------ эрсдэл
def test_altman_known_value():
    c = Company("TST", [report(2025, 12)])
    z = risk.altman(c, market_cap=800.0)
    x1, x2, x3, x4, x5 = 300 / 1000, 600 / 1000, 220 / 1000, 800 / 400, 1000 / 1000
    assert z["z"] == pytest.approx(1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5)
    assert z["zone"].startswith("АЮУЛГҮЙ")


def test_interest_sensitivity_and_break_even():
    c = Company("TST", [report(2025, 12)])
    s = risk.interest_sensitivity(c)
    assert s["cases"][1] == 180 and s["cases"][3] == 180 - 2 * 20
    b = risk.break_even(c)
    assert b["break_even"] == pytest.approx((100 + 100 + 20) / 0.4)
    assert b["safety"] == pytest.approx((1000 - 550) / 1000)


def test_piotroski_needs_previous_year():
    assert risk.piotroski(Company("TST", [report(2025, 12)])) is None
    p = risk.piotroski(Company("TST", [report(2024, 12, net_income=100.0), report(2025, 12)]))
    assert p and p["of"] >= 4 and 0 <= p["score"] <= p["of"]


def test_trading_liquidity_window():
    b = bars([10.0] * 200, start=date(2026, 1, 1))
    q = risk.trading_liquidity(b, b[-1].day, date(2026, 10, 17), 90)
    assert q["trading_days"] == 90 and q["stale_days"] == (date(2026, 10, 17) - b[-1].day).days
    assert risk.trading_liquidity([], date(2026, 1, 1), date(2026, 1, 1), 90) is None


def own(big_n, big, small_n, small):
    return Ownership("T", date(2026, 6, 30), big_n, big, small_n, small)


@pytest.mark.parametrize("o,grade", [
    (own(3, 0.9275, 16701, 0.0725), "ӨНДӨР"),     # SUU: чөлөөт эргэлт <10%
    (own(1, 0.70, 18596, 0.30), "ӨНДӨР"),         # MFC: нэг эзэмшигч 70%
    (own(2, 0.7969, 631, 0.2031), "ӨНДӨР"),       # MGLA: жижиг эзэмшигч цөөн
    (own(4, 0.6986, 10020, 0.3014), "БАГА"),      # MMX
    (own(3, 0.8656, 38567, 0.1344), "ДУНД"),      # APU
])
def test_concentration_grades(o, grade):
    assert concentration.assess(o)["grade"] == grade


# ------------------------------------------------------------------ прогноз, оноо
def test_log_regress_recovers_exponential():
    pts = [(2020 + i, 100 * 1.1 ** i) for i in range(5)]
    assert forecast.log_regress(pts, 2026) == pytest.approx(100 * 1.1 ** 6)
    assert forecast.log_regress([(2020, 5.0)], 2026) is None
    assert forecast.log_regress([(2020, -1.0), (2021, -2.0)], 2026) is None


def test_forecast_needs_three_positive_years_and_fills_actual():
    rs = [report(y, 12, revenue=1000.0 * 1.1 ** (y - 2020), net_income=100.0 * 1.1 ** (y - 2020)) for y in range(2020, 2025)]
    c = Company("TST", rs)
    f = forecast.net_income(c, 2025)
    assert f["years"] == 5 and f["actual"] is None
    assert f["h2"] == pytest.approx(f["median"] / 2)
    c2 = Company("TST", rs + [report(2025, 12, net_income=150000.0)])
    assert forecast.net_income(c2, 2025)["actual"] == pytest.approx(150000.0 / 1e6)
    assert forecast.net_income(Company("TST", rs[:2]), 2025) is None


def test_linear_scale_is_clipped_and_two_directional():
    assert valuation.linear(5, 0, 10) == 50
    assert valuation.linear(-5, 0, 10) == 0 and valuation.linear(50, 0, 10) == 100
    assert valuation.linear(0.3, 1.5, 0.3) == 100          # бага байх тусам сайн
    assert valuation.linear(None, 0, 1) is None


def test_weights_sum_to_100():
    assert Weights().total() == 100


def test_rating_thresholds_and_missing_components_are_renormalised():
    a, w = Assumptions(), Weights()
    full = {"ratios": {"current_ratio": 2.0, "debt_to_equity": 0.3}, "no_interest": True, "altman": None, "piotroski": None, "cheap": {"total": 90, "dividend": 90},
            "free_float": None, "liquidity": None, "revenue_cagr": None}
    r = scoring.rate(full, a, w)
    # зөвхөн 3 хэсэг тооцогдсон: (100×15 + 90×20 + 90×10) ÷ 45
    assert r["total"] == pytest.approx((1500 + 1800 + 900) / 45) and r["rating"] == "ХУДАЛДАН АВАХ"
    assert r["missing"]
    full["cheap"] = {"total": 0, "dividend": 0}
    full["ratios"] = {"current_ratio": 0.5, "debt_to_equity": 2.0}
    assert scoring.rate(full, a, w)["rating"] == "ЗАРАХ"


def test_assumptions_reject_unknown_keys(tmp_path):
    p = tmp_path / "a.json"
    p.write_text('{"deposit_rate": 0.1, "oops": 1}')
    with pytest.raises(ValueError):
        Assumptions.load(p)
    p.write_text('{"deposit_rate": 0.1}')
    assert Assumptions.load(p).deposit_rate == 0.1


# ------------------------------------------------------------------ арилжааны түүх
TRADES = """apu
Ханш\tАрилжигдсан
\tДээд\tДоод\tНээлт\tХаалт\tШирхэг\tҮнийн дүн\tОгноо
1\t110\t100\t101\t105\t10\t1,050\t2026-07-02
2\t100\t95\t96\t99\t5\t495\t2026-07-01
"""


def test_import_trades_merges_with_existing(tmp_path):
    inputs = tmp_path / "inputs"
    (inputs / "prices").mkdir(parents=True)
    (inputs / "market.csv").write_text("ticker,price,price_date,shares,dps,dps_year\nAPU,105,2026-07-02,1000,1,2025\n")
    txt = tmp_path / "t.txt"
    txt.write_text(TRADES, "utf-8")
    assert import_trades(txt, inputs)[0].startswith("APU: 2 өдөр")
    txt.write_text(TRADES.replace("2026-07-02", "2026-07-03").replace("2026-07-01", "2026-07-02"), "utf-8")
    assert "3 өдөр" in import_trades(txt, inputs)[0]


# ------------------------------------------------------------------ бүхэлд нь (репо дахь бодит файлтай)
needs_data = pytest.mark.skipif(not (ROOT / "reports" / "FOOD mse.xlsx").exists(), reason="reports/FOOD mse.xlsx алга")


@needs_data
def test_end_to_end_workbook(tmp_path):
    out = tmp_path / "a.xlsx"
    assert main(["--reports", str(ROOT / "reports" / "FOOD mse.xlsx"), "--inputs", str(ROOT / "inputs"),
                 "--out", str(out), "--date", "2026-10-17", "--charts", str(tmp_path / "png")]) == 0
    wb = load_workbook(out)
    for name in ("Дүгнэлт", "Оноо", "Харьцаа", "Харьцааны түүх", "DuPont", "Түүхэн хандлага", "Задаргаа", "Эрсдэл", "Үнэлгээ",
                 "Graham ба ногдол", "Үнэлгээ 2.0", "Эзэмшил", "ЦА прогноз", "Техник", "ТА APU"):
        assert name in wb.sheetnames, name
    ws = wb["Дүгнэлт"]
    rows = [r for r in ws.iter_rows(min_row=6, max_row=13, values_only=True)]
    assert {r[0].split()[0] for r in rows} == {"APU", "TUM", "TCK", "SUU", "MFC", "GAZR", "MMX", "MGLA"}
    assert all(r[12] in ("ХУДАЛДАН АВАХ", "ХАДГАЛАХ", "ЗАРАХ") for r in rows)
    scores = [r[11] for r in rows]
    assert scores == sorted(scores, reverse=True) and all(0 <= s <= 100 for s in scores)
    # нэр томьёоны хориг
    for sheet in wb:
        for row in sheet.iter_rows(values_only=True):
            for v in row:
                if isinstance(v, str):
                    low = v.lower()
                    assert not any(f in low for f in FORBIDDEN), (sheet.title, v)


@needs_data
def test_cli_subset_and_errors(tmp_path):
    base = ["--reports", str(ROOT / "reports" / "FOOD mse.xlsx"), "--inputs", str(ROOT / "inputs"), "--out", str(tmp_path / "s.xlsx"),
            "--charts", str(tmp_path / "png")]       # хэзээ ч жинхэнэ reports/charts-ийг дарахгүй
    assert main(base + ["--tickers", "APU", "SUU", "--no-technical"]) == 0
    wb = load_workbook(tmp_path / "s.xlsx")
    assert "Техник" not in wb.sheetnames and "ТА APU" not in wb.sheetnames
    assert main(base + ["--tickers", "TTL"]) == 1                                  # TTL ≠ TCK
    assert main(["--reports", str(tmp_path / "none.xlsx"), "--out", str(tmp_path / "x.xlsx")]) == 1


# ------------------------------------------------------------------ live (open.mse.mn): задлагчийн механик
# АНХААР: HTML жишээ нь БОДИТ хуудас биш, бүтцийг дуурайсан зохиомол. Бодит хуудсыг GitHub Actions дээр шалгана.
HTML = """<table><thead><tr><th>Огноо</th><th>Нээлтийн ханш</th><th>Хаалтын ханш</th><th>Өдрийн хязгаар</th>
<th>Ширхэг</th><th>Үнийн дүн</th><th>Хэлцэл</th></tr></thead><tbody>
<tr><td>2026-10-16</td><td>1,100.00</td><td>1,110.50</td><td>1,095.00 - 1,120.00</td><td>1,000</td><td>1,110,500.00</td><td>3</td></tr>
<tr><td>2026-10-15</td><td>1,097.00</td><td>1,099.00</td><td>1,095.00 - 1,100.00</td><td>14,474</td><td>15,897,712.00</td><td>9</td></tr>
<tr><td>2026-10-14</td><td>0</td><td>0</td><td>0 - 0</td><td>0</td><td>0</td><td>0</td></tr>
</tbody></table>"""


def test_live_parse_history_reads_table():
    from mse_analysis import live
    bars = live.parse_history(HTML)
    assert [b.day for b in bars] == [date(2026, 10, 15), date(2026, 10, 16)]
    b = bars[-1]
    assert (b.open, b.close, b.low, b.high, b.qty, b.value) == (1100.0, 1110.5, 1095.0, 1120.0, 1000.0, 1110500.0)
    assert live.parse_history("<p>no table</p>") == []


def test_live_fetch_uses_security_urls(tmp_path):
    from mse_analysis import live

    class FakeClient:
        def __init__(self): self.urls = []
        def text(self, u): self.urls.append(u); return HTML
        def sleep(self): pass
    c = FakeClient()
    h = live.fetch(tmp_path / "raw", date(2026, 10, 16), c)
    assert set(h) == set(live.SECURITY_IDS) and h["TUM"][-1].close == 1110.5
    assert "https://open.mse.mn/securities/549/tab/tradeinfo?startDate=2026-08-17&endDate=2026-10-16" in c.urls
    assert (tmp_path / "raw" / "APU.html").exists()


def test_live_apply_merges_history_and_updates_market(tmp_path):
    from mse_analysis import live
    from mse_analysis.prices import read_csv
    (tmp_path / "prices").mkdir()
    (tmp_path / "market.csv").write_text("ticker,price,price_date,shares,dps,dps_year\nAPU,967.14,2026-07-20,1000,130,2025\nTUM,370,2026-07-20,1,1,2025\n")
    (tmp_path / "prices" / "APU.csv").write_text("date,open,high,low,close,qty,value\n2026-10-15,1,1,1,1,1,1\n")
    h = {"APU": live.parse_history(HTML)}
    assert "+1 шинэ өдөр" in live.apply(h, tmp_path)[0]
    text = (tmp_path / "market.csv").read_text()
    assert "APU,1110.5,2026-10-16,1000,130,2025" in text and "TUM,370,2026-07-20" in text
    bars = read_csv(tmp_path / "prices" / "APU.csv")
    assert [b.close for b in bars] == [1099.0, 1110.5]


def test_fetch_prices_fails_cleanly_without_touching_files(tmp_path, monkeypatch):
    from mse_analysis import live
    (tmp_path / "market.csv").write_text("ticker,price,price_date,shares,dps,dps_year\nAPU,1,2026-07-20,1,1,2025\n")
    monkeypatch.setattr(live, "fetch", lambda raw, today, client=None: {})
    assert main(["--reports", str(ROOT / "reports" / "FOOD mse.xlsx"), "--inputs", str(tmp_path), "--fetch-prices", "--charts", str(tmp_path / "png")]) == 1
    assert "APU,1,2026-07-20" in (tmp_path / "market.csv").read_text()


# ------------------------------------------------------------------ зураг, Telegram
def test_charts_build_two_pngs(tmp_path):
    from datetime import date as _d
    from mse_analysis import charts
    from mse_analysis.engine import compute
    res = compute(ROOT / "reports" / "FOOD mse.xlsx", ROOT / "inputs", _d(2026, 10, 19), with_technical=False)
    out = charts.build(res, tmp_path)
    assert [p.name for p in out] == ["valuation.png", "ratios.png", "annual.png", "halfyear.png", "cost_1000.png",
                                     "price_tags.png", "health_check.png", "seasonality.png", "ownership.png"]
    assert all(p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and p.stat().st_size > 20000 for p in out)


def test_notify_summary_and_sends(tmp_path, monkeypatch):
    from datetime import date as _d
    from mse_analysis import notify as n
    from mse_analysis.engine import compute
    res = compute(ROOT / "reports" / "FOOD mse.xlsx", ROOT / "inputs", _d(2026, 10, 19), with_technical=False)
    text = n.format_summary(res)
    assert text.startswith("📈 МХБ хүнс — 2026-10-19") and "APU" in text and "P/E" in text and "зөвлөгөө биш" in text
    assert len(text) < 3900 and "MSIAA" not in text
    sent = []
    monkeypatch.setattr(n, "send_telegram", lambda t: sent.append("text") or True)
    monkeypatch.setattr(n, "send_photos", lambda ps, caption="": sent.append(f"album{len(list(ps))}") or True)
    x = tmp_path / "a.xlsx"
    x.write_bytes(b"x")
    names = ["valuation.png", "ratios.png", "annual.png", "halfyear.png", "cost_1000.png"]
    assert n.notify(res, [tmp_path / nm for nm in names], x) is True
    assert sent == ["text", "album2", "album3"]               # Excel Telegram-д явахгүй               # 1) харьцаа/үнэлгээ, 2) инфографик — тусдаа албом
    monkeypatch.setattr(n, "send_telegram", lambda t: False)       # токен байхгүй: юу ч илгээхгүй
    sent.clear()
    assert n.notify(res, [], x) is False and sent == []


def test_send_file_uses_photo_or_document_endpoint(tmp_path):
    from mse_financials.notify import send_file

    class S:
        calls = []
        def post(self, url, **kw):
            S.calls.append(url)
            class R:
                def raise_for_status(self): pass
            return R()
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    assert send_file(f, photo=True, token="T", chat_id="1", session=S()) is True
    assert send_file(f, token="T", chat_id="1", session=S()) is True
    assert S.calls[0].endswith("/sendPhoto") and S.calls[1].endswith("/sendDocument")
    assert send_file(f, token="", chat_id="") is False


def test_send_photos_album_chunks_of_ten(tmp_path):
    from mse_financials.notify import send_photos

    class S:
        calls = []
        def post(self, url, **kw):
            S.calls.append((url, len(kw["files"])))
            class R:
                def raise_for_status(self): pass
            return R()
    fs = []
    for i in range(12):
        f = tmp_path / f"{i}.png"
        f.write_bytes(b"x")
        fs.append(f)
    assert send_photos(fs, "c", token="T", chat_id="1", session=S()) is True
    assert [c[1] for c in S.calls] == [10, 2] and all(c[0].endswith("/sendMediaGroup") for c in S.calls)
    assert send_photos(fs, token="", chat_id="") is False


# ------------------------------------------------------------------ үеийн харьцуулалт (жил, хагас жил, улирал)
def test_periods_flows_and_comparisons():
    from mse_analysis import periods as P
    from datetime import date as _d
    from mse_analysis.engine import compute
    res = compute(ROOT / "reports" / "FOOD mse.xlsx", ROOT / "inputs", _d(2026, 10, 19), with_technical=False)
    c = res.companies["TUM"]
    h1, fy = P.value(c, P.Per("half", 2025, 1), "revenue"), P.value(c, P.Per("year", 2025, 0), "revenue")
    h2 = P.value(c, P.Per("half", 2025, 2), "revenue")
    assert h2 == fy - h1                                              # H2 = FY − H1
    assert P.Per("half", 2026, 1).prev() == P.Per("half", 2025, 2) and P.Per("quarter", 2026, 1).prev() == P.Per("quarter", 2025, 4)
    assert P.Per("quarter", 2026, 2).yoy() == P.Per("quarter", 2025, 2)
    # TCK-д 2026 оны тайлан алга → тооцохгүй (зохиож бөглөхгүй), шалтгааныг нэрлэнэ
    assert P.value(res.companies["TCK"], P.Per("half", 2026, 1), "revenue") is None
    assert "2026 оны тайлан алга" in P.missing_detail(res.companies["TCK"], P.Per("half", 2026, 1))
    g = res.companies["GAZR"]
    assert P.value(g, P.Per("half", 2025, 1), "revenue") == pytest.approx(23375174.60881, abs=0.01) and P.value(g, P.Per("half", 2025, 2), "revenue") is not None
    assert P.change(5, 0) == (None, "алдагдлаас ашигт шилжсэн") and P.change(-1, -2) == (None, "алдагдалтай хэвээр")
    assert abs(P.change(110, 100)[0] - 0.1) < 1e-9
    tgt = P.target(res.companies, "half")
    assert tgt == P.Per("half", 2026, 1)


def test_monthly_returns_skips_untraded_months():
    from datetime import date as _d
    from mse_analysis.infographics import monthly_returns
    from mse_analysis.prices import Bar
    bars = []
    for y in (2024, 2025, 2026):
        for m in range(1, 13):
            if (y, m) >= (2026, 11):
                break
            if y == 2025 and m == 3:
                continue                                              # 3-р сард арилжаа байхгүй
            bars += [Bar(_d(y, m, d), 100.0 + m, 100.0 + m, 100.0 + m, 100.0 + m, 1, 1) for d in range(1, 29)]
    mr = monthly_returns(bars)
    assert len(mr[3]) == 2 and len(mr[4]) == 2                       # 2025 оны 3, 4-р сарын өгөөж хасагдсан
    assert all(len(v) >= 2 for v in mr.values())
