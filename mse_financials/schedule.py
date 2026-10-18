"""Тайлан цуглуулах хуваарь: хуулийн хугацаа + 14 хоног.

Эх сурвалж: МХБ-ийн "Мэдээлэл ил тод байлгах дүрэм" (Disclosure and Transparency Rules)
  - 3.2: хагас жилийн санхүүгийн тайлан — тайлант үеэс дараагийн сарын 20-ны дотор
  - 3.2: жилийн санхүүгийн тайлан (IFRS) — дараа жилийн 2 сарын 10-ны дотор
Улирлын (Q1, Q3) тайланг дүрмээр тусад нь заагаагүй; ихэнх компани сайн дураар ирүүлдэг
тул тооцоолсон хугацаа (`mandatory=False`)-аар оруулсан. Хэрэггүй бол жагсаалтаас хасаж,
`.github/workflows/collect.yml` дахь cron мөрийг мөн хасна.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .models import Period

GRACE_DAYS = 14  # хуулийн хугацаанаас хойш хүлээх хоног (хоцорсон ирүүлэлтэд зай өгнө)


@dataclass(frozen=True)
class Deadline:
    name: str
    month: int          # ирүүлэх сар
    day: int            # ирүүлэх өдөр
    quarter: int        # тайлангийн үе (1..4)
    year_shift: int     # тайлант жил = ирүүлсэн жил + year_shift (жилийн тайлан: -1)
    mandatory: bool     # дүрмээр заавал эсэх

    def due(self, filing_year: int) -> date:
        return date(filing_year, self.month, self.day)

    def collect_on(self, filing_year: int) -> date:
        return self.due(filing_year) + timedelta(days=GRACE_DAYS)

    def period(self, filing_year: int) -> Period:
        return Period(filing_year + self.year_shift, self.quarter)


DEADLINES = (
    Deadline("Жилийн санхүүгийн тайлан", 2, 10, 4, -1, True),
    Deadline("1-р улирлын тайлан", 4, 30, 1, 0, False),
    Deadline("Хагас жилийн тайлан", 7, 20, 2, 0, True),
    Deadline("3-р улирлын тайлан", 10, 30, 3, 0, False),
)


def collection_days(year: int) -> list[tuple[date, Deadline]]:
    return sorted(((d.collect_on(year), d) for d in DEADLINES), key=lambda x: x[0])


def is_collection_day(day: date) -> Deadline | None:
    for when, dl in collection_days(day.year):
        if when == day:
            return dl
    return None


def due_periods(day: date) -> list[tuple[Period, Deadline]]:
    """`day` байдлаар (хугацаа + 14 хоног) өнгөрсөн, тайлан ирсэн байх ёстой бүх үе, хуучнаас шинэ рүү."""
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
    lines = [f"Тайлан цуглуулах хуваарь (хуулийн хугацаа + {GRACE_DAYS} хоног):"]
    for when, dl in collection_days(day.year):
        lines.append(f"  {when:%m-%d}  {dl.name:<26} хуулийн хугацаа {dl.due(day.year):%m-%d}"
                     + ("" if dl.mandatory else "  (заавал биш)"))
    when, dl = next_collection(day)
    lines.append(f"Дараагийн цуглуулалт: {when.isoformat()} — {dl.name}")
    return "\n".join(lines)


def cron_expressions() -> list[str]:
    """GitHub Actions cron (02:00 UTC = Улаанбаатарын 10:00)."""
    return [f"0 2 {when.day} {when.month} *" for when, _ in collection_days(2001)]
