import re
from datetime import date
from pathlib import Path

import pytest

from mse_financials import schedule
from mse_financials.cli import main
from mse_financials.models import Period


def test_collection_dates_are_semi_annual_and_annual():
    got = {dl.name: when for when, dl in schedule.collection_days(2026)}
    assert len(got) == 2
    assert got["Жилийн санхүүгийн тайлан"] == date(2026, 4, 1)
    assert got["Хагас жилийн тайлан"] == date(2026, 8, 15)


def test_is_collection_day():
    assert schedule.is_collection_day(date(2026, 4, 1)).name == "Жилийн санхүүгийн тайлан"
    assert schedule.is_collection_day(date(2026, 8, 15)).name == "Хагас жилийн тайлан"
    assert schedule.is_collection_day(date(2026, 8, 16)) is None
    assert schedule.is_collection_day(date(2026, 7, 20)) is None  # хуулийн хугацаа өөрөө биш


@pytest.mark.parametrize("day,expected", [
    (date(2026, 3, 31), Period(2025, 2)),   # 4/1 болоогүй -> өмнөх оны хагас жил
    (date(2026, 4, 1), Period(2025, 4)),    # 4/1 -> өмнөх оны жилийн эцсийн тайлан
    (date(2026, 8, 14), Period(2025, 4)),   # 8/15 болоогүй -> хамгийн сүүлийнх нь жилийн эцэс
    (date(2026, 8, 15), Period(2026, 2)),   # 8/15 -> тухайн оны хагас жилийн тайлан
    (date(2027, 3, 31), Period(2026, 2)),
    (date(2027, 4, 1), Period(2026, 4)),    # жилийн тайлан: тайлант жил = өмнөх жил
])
def test_latest_mandatory(day, expected):
    assert schedule.latest_mandatory(day)[0] == expected


def test_due_periods_sorted_and_only_h1_and_annual():
    periods = [p for p, _ in schedule.due_periods(date(2026, 8, 15))]
    assert periods == sorted(periods)
    assert Period(2026, 2) in periods and Period(2025, 4) in periods
    assert all(p.quarter in (2, 4) for p in periods)


def test_next_collection_wraps_to_next_year():
    assert schedule.next_collection(date(2026, 4, 1))[0] == date(2026, 8, 15)
    assert schedule.next_collection(date(2026, 8, 15))[0] == date(2027, 4, 1)
    assert schedule.next_collection(date(2026, 10, 10))[0] == date(2027, 4, 1)


def test_workflow_cron_matches_schedule():
    """collect.yml дахь cron нь schedule.py-тай үргэлж таарна (хоёр газар засахаа мартахгүйн тулд)."""
    yml = (Path(__file__).parent.parent / ".github/workflows/collect.yml").read_text("utf-8")
    crons = sorted(re.findall(r'cron:\s*"([^"]+)"', yml))
    crons = [c for c in crons if c != "0 3 1 * *"]          # keepalive-г оруулахгүй
    assert crons == sorted(schedule.cron_expressions())


def test_cli_if_due_skips_other_days(capsys, tmp_path):
    assert main(["--if-due", "--date", "2026-10-10", "--out", str(tmp_path / "r" / "x.xlsx"),
                 "--reports-dir", str(tmp_path / "m")]) == 0
    assert "цуглуулах өдөр биш" in capsys.readouterr().out
    assert not (tmp_path / "r").exists()


def test_cli_show_schedule(capsys):
    assert main(["--show-schedule", "--date", "2026-10-10"]) == 0
    out = capsys.readouterr().out
    assert "04-01" in out and "08-15" in out
    assert "Дараагийн цуглуулалт: 2027-04-01" in out
