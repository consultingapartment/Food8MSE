"""Тайлан цуглуулах хуваарь: Жилийн эцэс (04-01) ба Хагас жил (08-15).

Эх сурвалж: Нягтлан бодох бүртгэлийн тухай хуулийн 10.3 ба МХБ-ийн "Мэдээлэл ил тод байлгах дүрэм"
  - 3.2: хагас жилийн санхүүгийн тайлан — 7 сарын 20-ны дотор (цуглуулах өдөр: 8 сарын 15)
  - 3.2: жилийн санхүүгийн тайлан (IFRS) — дараа жилийн 2 сарын 10-ны дотор (цуглуулах өдөр: 4 сарын 1)
Улирлын (Q1, Q3) тайлан нь заавал гаргах тайлан биш тул хассан.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .models import Period

GRACE_DAYS = 14  # collect_month/collect_day заагаагүй үед ашиглах анхдагч хоног


@dataclass(frozen=True)
class Deadline:
    name: str
    month: int                      # хуулийн хугацааны сар
    day: int                        # хуулийн хугацааны өдөр
    quarter: int                    # тайлангийн үе (1..4)
    year_shift: int                 # тайлант жил = ирүүлсэн жил + year_shift (жилийн тайлан: -1)
    mandatory: bool = True          # дүрмээр заавал эсэх
    collect_month: int | None = None  # тайлан цуглуулах сар
    collect_day: int | None = None    # тайлан цуглуулах өдөр

    def due(self, filing_year: int) -> date:
        return date(filing_year, self.month, self.day)

    def collect_on(self, filing_year: int) -> date:
        if self.collect_month is not None and self.collect_day is not None:
            return date(filing_year, self.collect_month, self.collect_day)
        return self.due(filing_year) + timedelta(days=GRACE_DAYS)

    def period(self, filing_year: int) -> Period:
        return Period(filing_year + self.year_shift, self.quarter)


DEADLINES = (
    Deadline("Жилийн санхүүгийн тайлан", 2, 10, 4, -1, True, 4, 1),
    Deadline("Хагас жилийн тайлан", 7, 20, 2, 0, True, 8, 15),
)


def collection_days(year: int) -> list[tuple[date, Deadline]]:
    return sorted(((d.collect_on(year), d) for d in DEADLINES), key=lambda x: x[0])


def is_collection_day(day: date) -> Deadline | None:
    for when, dl in collection_days(day.year):
        if when == day:
            return dl
    return None


def due_periods(day: date) -> list[tuple[Period, Deadline]]:
    """`day` байдлаар цуглуулах хугацаа өнгөрсөн, тайлан ирсэн байх ёстой бүх үе, хуучнаас шинэ рүү."""
    out = []
    for year in (day.year - 1, day.year):
        for dl in DEADLINES:
            if dl.collect_on(year) <= day:
                out.append((dl.period(year), dl))
    return sorted(out, key=lambda x: x[0])


def latest_mandatory(day: date) -> tuple[Period, Deadline] | None:
    items = [x for x in due_periods(day) if x[1].mandatory]
    return items[-1] if items else None


def next_collection(day: date) -> tuple[date, Deadline]:
    for year in (day.year, day.year + 1):
        for when, dl in collection_days(year):
            if when > day:
                return when, dl
    raise RuntimeError("unreachable")


def describe(day: date) -> str:
    lines = ["Тайлан цуглуулах хуваарь (Жилийн эцэс ба Хагас жил):"]
    for when, dl in collection_days(day.year):
        lines.append(
            f"  {when:%m-%d}  {dl.name:<26} хуулийн хугацаа {dl.due(day.year):%m-%d}"
            + ("" if dl.mandatory else "  (заавал биш)")
        )
    when, dl = next_collection(day)
    lines.append(f"Дараагийн цуглуулалт: {when.isoformat()} — {dl.name}")
    return "\n".join(lines)


def cron_expressions() -> list[str]:
    """GitHub Actions cron (02:00 UTC = Улаанбаатарын 10:00)."""
    return [f"0 2 {when.day} {when.month} *" for when, _ in collection_days(2001)]
