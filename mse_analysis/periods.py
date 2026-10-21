"""Жил, хагас жил, улирлын урсгал ба өмнөх үетэй харьцуулалт.

Тайлангийн орлогын мөр нь оны эхнээс хуримтлагдсан (YTD: 3, 6, 9, 12 сар). Тиймээс:
  улирал Q = YTD(3Q сар) − YTD(3(Q−1) сар); хагас жил H1 = YTD(6), H2 = YTD(12) − YTD(6); жил = YTD(12).
Хоёр хуримтлагдсан тайлан (жишээ нь 3 ба 6 сар) байхгүй бол тухайн улирлын утга тооцогдохгүй (None) — зохиож бөглөхгүй.
Нэгж: мянган төгрөг.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .base import Company

KINDS = ("year", "half", "quarter")


@dataclass(frozen=True)
class Per:
    kind: str           # "year" | "half" | "quarter"
    year: int
    n: int              # жил: 0, хагас жил: 1|2, улирал: 1..4

    @property
    def label(self) -> str:
        return f"{self.year}" if self.kind == "year" else f"{self.year} H{self.n}" if self.kind == "half" else f"{self.year} Q{self.n}"

    def prev(self) -> "Per":
        """Өмнөх үе (жил → өмнөх жил, H1 → өмнөх оны H2, Q1 → өмнөх оны Q4)."""
        if self.kind == "year":
            return Per("year", self.year - 1, 0)
        top = 2 if self.kind == "half" else 4
        return Per(self.kind, self.year - 1, top) if self.n == 1 else Per(self.kind, self.year, self.n - 1)

    def yoy(self) -> "Per":
        """Өмнөх оны мөн үе."""
        return Per(self.kind, self.year - 1, self.n)


def _ytd(c: Company, year: int, months: int, key: str) -> Optional[float]:
    if months == 0:
        return 0.0
    r = c.find(year, months)
    return None if r is None else c.v(r, key)


def value(c: Company, p: Per, key: str) -> Optional[float]:
    """Тухайн үеийн дүн (мянган ₮) эсвэл тооцох өгөгдөл дутуу бол None."""
    span = {"year": (12, 0), "half": (6 * p.n, 6 * (p.n - 1)), "quarter": (3 * p.n, 3 * (p.n - 1))}[p.kind]
    end, start = span
    a, b = _ytd(c, p.year, end, key), _ytd(c, p.year, start, key)
    return None if a is None or b is None else a - b


def change(cur: Optional[float], base: Optional[float]) -> tuple[Optional[float], str]:
    """(өөрчлөлт %, тайлбар). Суурь ≤ 0 бол хувь утга учиргүй тул None ба үгээр тайлбарлана."""
    if cur is None or base is None:
        return None, "өгөгдөл алга"
    if base > 0:
        return cur / base - 1, ""
    if cur > 0:
        return None, "алдагдлаас ашигт шилжсэн"
    return None, "алдагдалтай хэвээр"


def periods_with_data(companies: dict[str, Company], kind: str, key: str = "revenue") -> dict[Per, list[str]]:
    """Үе -> тэр үеийн утга тооцогдох тикерүүд."""
    years = {r.period.year for c in companies.values() for r in c.reports if r.period.year}
    out: dict[Per, list[str]] = {}
    ns = {"year": [0], "half": [1, 2], "quarter": [1, 2, 3, 4]}[kind]
    for y in sorted(years):
        for n in ns:
            p = Per(kind, y, n)
            have = [t for t, c in companies.items() if value(c, p, key) is not None]
            if have:
                out[p] = have
    return out


def target(companies: dict[str, Company], kind: str) -> Optional[Per]:
    """Харьцуулах үе: хамгийн сүүлийн үе, гэхдээ ядаж хоёр компанид өгөгдөлтэй байх."""
    cand = periods_with_data(companies, kind)
    ok = [p for p, have in cand.items() if len(have) >= 2]
    return max(ok, key=lambda p: (p.year, p.n)) if ok else None


def compare(c: Company, p: Per, key: str) -> dict:
    """{'cur', 'prev', 'yoy', 'd_prev', 'd_yoy', 'n_prev', 'n_yoy'} (d_* = өөрчлөлт %, n_* = тайлбар)."""
    cur = value(c, p, key)
    prev, yoy = value(c, p.prev(), key), value(c, p.yoy(), key)
    d_prev, n_prev = change(cur, prev)
    d_yoy, n_yoy = change(cur, yoy)
    return {"cur": cur, "prev": prev, "yoy": yoy, "d_prev": d_prev, "d_yoy": d_yoy, "n_prev": n_prev, "n_yoy": n_yoy}


def history(c: Company, kind: str, key: str, last_n: int = 6) -> list[tuple[Per, Optional[float], Optional[float]]]:
    """Сүүлийн үеүдийн цуваа: [(үе, утга, өмнөх жилийн мөн үеэс өөрчлөлт %)]. Утгагүй үеийг алгасна (жил/хагас жилийн цувааны завсар орхино)."""
    cand = periods_with_data({"x": c}, kind, key)
    pers = sorted(cand, key=lambda p: (p.year, p.n))[-last_n:]
    out = []
    for p in pers:
        cur = value(c, p, key)
        d, _ = change(cur, value(c, p.yoy(), key))
        out.append((p, cur, d))
    return out


def latest_own(c: Company, kind: str, key: str = "revenue") -> Optional[Per]:
    """Тухайн компанийн өөрийн хамгийн сүүлийн боломжит үе (утга тооцогдох)."""
    cand = periods_with_data({"x": c}, kind, key)
    top = max((r.period.year for r in c.reports if r.period.year), default=0)
    cand = {p: v for p, v in cand.items() if p.year >= top - 1}      # хуучирсан (жишээ нь 10 жилийн өмнөх) үеийг сүүлийнх гэж үзэхгүй
    return max(cand, key=lambda p: (p.year, p.n)) if cand else None


def missing_reason(c: Company, kind: str) -> str:
    """Улирлын утга яагаад тооцогдохгүй байгааг үгээр тайлбарлана."""
    top = max((r.period.year for r in c.reports if r.period.year), default=0)
    if kind == "quarter" and not any(r.months in (3, 9) for r in c.reports if r.period.year >= top - 1):
        return "Q1/Q3 тайлан ирүүлдэггүй (заавал биш)"
    return "хуримтлагдсан тайлан дутуу"


def missing_detail(c: Company, p: Per) -> str:
    """Үеийн утга тооцоход дутуу байгаа хуримтлагдсан тайлан (жишээ нь «2025 оны 12 сарын тайлан алга»)."""
    end, start = {"year": (12, 0), "half": (6 * p.n, 6 * (p.n - 1)), "quarter": (3 * p.n, 3 * (p.n - 1))}[p.kind]
    miss = [m for m in (end, start) if m and c.find(p.year, m) is None]
    if not miss:
        return "өгөгдөл алга"
    if c.reports and not any(r.period.year == p.year for r in c.reports):
        return f"{p.year} оны тайлан алга"
    return ", ".join(f"{p.year} оны {m} сарын тайлан алга" for m in miss)
