import json
import logging

import pytest

from mse_financials import ocr, vision
from mse_financials.pdf import ScannedPdfError

R = lambda c, a, b: (c, [a, b])        # noqa: E731
# SUU 2025 оны жилийн тайлангийн (скан) бодит тоо; өмнөх баганын «Эргэлтийн бус хөрөнгийн дүн» нь эх тайландаа 48.3 сая ₮-өөр буруу
BS = [
    R("1", 0, 0), R("1.1", 0, 0), R("1.1.1", 1618713781.59, 5648167151.68), R("1.1.2", 5068411414.68, 7716966244.13),
    R("1.1.3", 67324982.41, 8813588.00), R("1.1.4", 2701476556.20, 7847123705.37), R("1.1.5", 0, 0),
    R("1.1.6", 32781243399.65, 45970636810.60), R("1.1.7", 10886748343.77, 15508544929.41), R("1.1.8", 0, 0),
    R("1.1.9", 48300000.00, 4200000.00), R("1.1.10", 413426716.80, 229206889.87),
    R("1.1.11", 53585645195.10, 82933659319.06),
    R("1.2.1", 80328363752.81, 82396769149.03), R("1.2.2", 158086271.69, 1189603408.68),
    R("1.2.3", 1132304782.44, 958151615.12), R("1.2.4", 0, 0), R("1.2.5", 0, 0), R("1.2.6", 0, 0),
    R("1.2.7", 489680034.27, 489680034.27), R("1.2.8", 15598564277.63, 21734447952.87),
    R("1.2.9", 5853209309.65, 11959904382.24), R("1.2.10", 103608508428.49, 118728556542.21),
    R("1.3", 157145853623.59, 201662215861.27),
    R("2.1.1.1", 4228619796.48, 15896555427.95), R("2.1.1.2", 1408806469.07, 1236335568.55),
    R("2.1.1.3", 1667872641.36, 1527422955.67), R("2.1.1.4", 1126131046.80, 649619933.90),
    R("2.1.1.5", 25886509287.53, 29234821709.44), R("2.1.1.6", 256441307.11, 300169616.26),
    R("2.1.1.7", 3300247229.51, 6904780.29), R("2.1.1.8", 72126504.40, 70376608.78), R("2.1.1.9", 0, 0),
    R("2.1.1.10", 24081452681.15, 36588222319.70), R("2.1.1.11", 0, 0), R("2.1.1.12", 0, 0),
    R("2.1.1.13", 62028206963.41, 85510428920.54),
    R("2.1.2.1", 23987897627.12, 36586771180.24), R("2.1.2.2", 0, 0), R("2.1.2.3", 401486714.13, 589184923.13),
    R("2.1.2.4", 1459505825.09, 1042465299.48), R("2.1.2.5", 8891609341.74, 7671776040.65),
    R("2.1.2.6", 34740499508.08, 45890197443.50), R("2.2", 96768706471.49, 131400626364.04),
    R("2.3", 34400000.00, 34400000.00), R("2.3.1", 0, 0), R("2.3.2", 34400000.00, 34400000.00), R("2.3.3", 0, 0),
    R("2.3.4", -86784.70, -86784.70), R("2.3.5", 60101311.76, 60101311.76), R("2.3.6", 0, 0), R("2.3.7", 0, 0),
    R("2.3.8", 0, 0), R("2.3.9", 60282732625.04, 70167174970.17), R("2.3.10", 0, 0),
    R("2.3.11", 60377147152.10, 70261589497.23), R("2.4", 157145853623.59, 201662215861.27),
]
IS = [
    R("1", 192399370626.41, 221437853418.98), R("2", 134849708271.99, 155728115125.83),
    R("3", 57549662354.42, 65709738293.15), R("4", 60654545.40, 60654545.41), R("5", 47518386.05, 15078567.51),
    R("6", 0, 0), R("7", 0, 0), R("8", 2714205468.77, 3579407357.01), R("9", 12512796776.82, 14183178768.80),
    R("10", 20017258579.47, 31187701081.48), R("11", 4950808308.09, 7469238883.45), R("12", 157488641.49, 110861482.23),
    R("13", -138679198.44, -448564382.41), R("14", -1500267199.58, -1614930099.88), R("15", 0, 0), R("16", 0, 0),
    R("17", 0, 0), R("18", 21094742050.75, 14350404064.83), R("19", 3270811875.35, 1667935938.00),
    R("20", 17823930175.40, 12682468126.83), R("21", 0, 0), R("22", 17823930175.40, 12682468126.83),
    R("23", 0, 0), R("23.1", 0, 0), R("23.2", 0, 0), R("23.3", 0, 0), R("24", 17823930175.40, 12682468126.83),
    R("25", 0, 0),
]


def reply():
    body = {"balance": [{"code": c, "values": v} for c, v in BS], "income": [{"code": c, "values": v} for c, v in IS]}
    return {"content": [{"type": "text", "text": "```json\n" + json.dumps(body) + "\n```"}]}


class Sess:
    def __init__(self, payload):
        self.payload, self.sent = payload, []

    def post(self, url, json=None, timeout=None, headers=None):
        self.sent.append((url, json, headers))
        payload = self.payload
        return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: payload})()


@pytest.fixture(autouse=True)
def fake_pages(monkeypatch):
    monkeypatch.setattr(vision, "_page_images", lambda path, dpi=150: ["AAAA"])


def test_no_key_means_no_vision(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert not vision.available() and vision.read_records(tmp_path / "x.pdf") is None


def test_records_are_read_from_model_json_and_key_stays_in_header(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "SECRET")
    s = Sess(reply())
    recs = vision.read_records(tmp_path / "x.pdf", session=s)
    assert recs[0] == ("1", [0.0, 0.0]) and len(recs) == len(BS) + len(IS)
    url, body, headers = s.sent[0]
    assert headers["x-api-key"] == "SECRET" and "SECRET" not in json.dumps(body)


def test_build_sheets_accepts_source_error_in_prior_column_only_when_not_strict():
    with pytest.raises(ScannedPdfError):
        ocr.build_sheets(BS + IS)                                  # эх тайлангийн 2024 багана 48.3 сая ₮-өөр зөрүүтэй
    sheets = ocr.build_sheets(BS + IS, strict_prev=False)
    assert sheets["ОДТ"][1][4] == 221437853418.98


def test_scanned_pdf_falls_back_to_vision_and_passes_sum_checks(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(ocr, "tesseract_path", lambda: None)
    s = Sess(reply())
    real = vision.read_records
    monkeypatch.setattr(vision, "read_records", lambda path, **kw: real(path, session=s))
    with caplog.at_level(logging.WARNING):
        sheets = ocr.ocr_sheets(tmp_path / "x.pdf")
    assert sheets["СБД"] and "харааны загвараар" in caplog.text


def test_vision_numbers_that_fail_sum_checks_are_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(ocr, "tesseract_path", lambda: None)
    bad = reply()
    data = json.loads(bad["content"][0]["text"].strip("`json\n"))
    data["income"][0]["values"][1] += 1_000_000                    # орлогыг буруу уншсан
    bad = {"content": [{"type": "text", "text": json.dumps(data)}]}
    real = vision.read_records
    monkeypatch.setattr(vision, "read_records", lambda path, **kw: real(path, session=Sess(bad)))
    with pytest.raises(ScannedPdfError, match="нийлбэрийн шалгалтад унав"):
        ocr.ocr_sheets(tmp_path / "x.pdf")
