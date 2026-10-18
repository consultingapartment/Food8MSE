import logging
from datetime import date

from mse_financials.notify import WarningCollector, format_check, format_run, send_telegram

DAY = date(2026, 10, 12)


class Sess:
    def __init__(self, exc=None):
        self.exc, self.sent = exc, []

    def post(self, url, json=None, timeout=None):
        if self.exc:
            raise self.exc
        self.sent.append((url, json))
        return type("R", (), {"raise_for_status": lambda self: None})()


def test_no_credentials_means_no_send(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    s = Sess()
    assert send_telegram("hi", session=s) is False and s.sent == []


def test_send_uses_env_and_truncates(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TKN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    s = Sess()
    assert send_telegram("x" * 9000, session=s) is True
    url, body = s.sent[0]
    assert url == "https://api.telegram.org/botTKN/sendMessage" and body["chat_id"] == "42"
    assert len(body["text"]) <= 4000


def test_failure_never_raises_and_never_leaks_token(caplog):
    s = Sess(exc=RuntimeError("POST https://api.telegram.org/botSECRET123/sendMessage failed"))
    with caplog.at_level(logging.DEBUG):
        assert send_telegram("hi", token="SECRET123", chat_id="1", session=s) is False
    assert "SECRET123" not in caplog.text


def test_warning_collector_captures_only_warnings():
    log, h = logging.getLogger("t.notify"), WarningCollector()
    log.addHandler(h)
    log.setLevel(logging.DEBUG)
    log.info("мэдээлэл")
    log.warning("анхааруулга %s", "A")
    log.error("алдаа")
    log.removeHandler(h)
    assert h.records == ["анхааруулга A", "алдаа"]


def test_format_run_lists_added_failed_and_unchanged():
    text = format_run(DAY, {"added": {"APU": ["2026 Q2", "2026 Q3"]}, "last": {"SUU": date(2026, 3, 31)}},
                      failed=["TUM"], warnings=["w1"])
    assert "2 шинэ тайлан" in text
    assert "🆕 APU: + 2026 Q2, 2026 Q3" in text
    assert "❌ TUM" in text
    assert "w1" in text


def test_format_run_nothing_new():
    assert "шинэ тайлан алга" in format_run(DAY, {"added": {}, "last": {}}, [])


def test_format_check_marks_pdf_only_unknown_and_errors():
    result = {
        "APU": {"last": date(2026, 3, 31), "new": [("2026 Q2", {"xls"})], "error": None, "unknown": 0},
        "TCK": {"last": None, "new": [("2025 Q4", {"pdf"})], "error": None, "unknown": 2},
        "SUU": {"last": date(2026, 6, 30), "new": [], "error": None, "unknown": 0},
        "MMX": {"last": None, "new": [], "error": "HTTP 503", "unknown": 0},
    }
    text = format_check(DAY, result)
    assert "2 шинэ тайлан" in text
    assert "🆕 APU: 2026 Q2" in text
    assert "2025 Q4 (зөвхөн PDF)" in text
    assert "үе тодорхойгүй 2" in text
    assert "✓ SUU" in text and "❌ MMX: HTTP 503" in text
