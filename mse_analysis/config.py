"""Шинжилгээний тогтмол утга, таамаглал, босго. Шинжилгээний дүрмийг энд л өөрчилнө."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path

TICKERS = ("APU", "TUM", "TCK", "SUU", "MFC", "GAZR", "MMX", "MGLA")

NAMES = {
    "APU": "АПУ", "TUM": "Түмэн шувуут", "TCK": "Талх чихэр", "SUU": "Сүү",
    "MFC": "Монос хүнс", "GAZR": "Газар шим үйлдвэр", "MMX": "Мах импекс", "MGLA": "Эм Жи Эл Акуа",
}

#: Үнэт цаасны төвлөрсөн хадгаламжийн төвийн ҮЦ код (ownership.csv-ийн ticker-ийг лавлахад)
SEC_CODES = {"APU": 90, "TUM": 549, "TCK": 22, "SUU": 135, "MFC": 551, "GAZR": 565, "MMX": 208, "MGLA": 572}


@dataclass
class Assumptions:
    """`inputs/assumptions.json`-оор дарж болно."""
    deposit_rate: float = 0.14            # банкны хадгаламжийн хүү (жилийн)
    target_yield: float = 0.16            # хөрөнгө оруулагчийн шаардах ногдол ашгийн өгөөж
    dividend_year: int = 2025             # inputs/market.csv дахь dps аль оны ногдол ашиг
    graham_yield: float = 0.14            # Грахамын томьёоны Y (өгөөжийн суурь). Анхдагч нь хадгаламжийн хүү
    graham_growth_cap: float = 0.05       # Грахамын g-ийн дээд хязгаар (жилийн өсөлт, 5%)
    graham_base_pe: float = 8.5           # ургалтгүй компанийн P/E
    graham_pe_pb_limit: float = 22.5      # P/E × P/B дээд хязгаар (Грахамын тоо)
    rating_buy: float = 70.0              # дүн ≥ → ХУДАЛДАН АВАХ
    rating_hold: float = 50.0             # дүн ≥ → ХАДГАЛАХ, түүнээс доош → ЗАРАХ
    ma_periods: tuple = (7, 29, 99)
    liquidity_window_days: int = 90       # арилжааны идэвх хэмжих хугацаа (хуанлийн өдөр)
    # --- Хямдралын нэгдсэн оноо (0–100): хэсэг бүрийн шугаман шатлал
    w_graham: float = 0.35
    w_dividend: float = 0.25
    w_pe: float = 0.20
    w_pb: float = 0.20
    graham_full: float = 0.2              # Ханш/Graham Number ≤ энэ бол 100 оноо
    graham_zero: float = 4.0              # ≥ энэ бол 0 оноо
    div_zero_yield: float = 0.02          # ногдлын өгөөж ≤ энэ бол 0 оноо
    div_full_ratio: float = 0.95          # өгөөж ≥ хадгаламжийн хүү × энэ бол 100 оноо
    pe_full_earnings_yield: float = 0.30  # ашгийн өгөөж (1/PE) ≥ энэ бол 100 оноо
    pb_full: float = 0.5                  # P/B ≤ энэ бол 100 оноо
    pb_zero: float = 2.0                  # P/B ≥ энэ бол 0 оноо
    forecast_min_years: int = 3           # прогноз гаргахад хамгийн багадаа хэдэн жилийн өгөгдөл
    tech_rows: int = 250                  # компани бүрийн техникийн sheet-д харуулах сүүлийн мөрийн тоо

    @classmethod
    def load(cls, path: Path | None) -> "Assumptions":
        a = cls()
        if path and Path(path).exists():
            data = json.loads(Path(path).read_text("utf-8"))
            known = {f.name for f in fields(cls)}
            unknown = set(data) - known
            if unknown:
                raise ValueError(f"assumptions.json: үл мэдэгдэх түлхүүр {sorted(unknown)}")
            for k, v in data.items():
                setattr(a, k, tuple(v) if isinstance(v, list) else v)
        return a


@dataclass
class Weights:
    """100 онооны задаргаа (нийлбэр = 100)."""
    profitability: float = 20
    growth: float = 15
    solvency: float = 15          # Хөрвөх чадвар ба төлбөрийн чадвар
    quality: float = 10           # Altman Z'' + Piotroski
    valuation: float = 20
    dividend: float = 10
    market: float = 10            # Арилжааны хөрвөх чадвар + чөлөөт эргэлт
    _order: tuple = field(default=("profitability", "growth", "solvency", "quality", "valuation", "dividend", "market"),
                          repr=False)

    def total(self) -> float:
        return sum(getattr(self, k) for k in self._order)


#: Altman Z-ийн X2: "equity" = Эздийн өмч/Хөрөнгө (өмнөх хавтасны хувилбар), "retained" = Хуримтлагдсан ашиг/Хөрөнгө (анхны Z).
ALTMAN_X2 = "equity"

LABELS = {
    "profitability": "Ашигт ажиллагаа", "growth": "Өсөлт", "solvency": "Хөрвөх ба төлбөрийн чадвар",
    "quality": "Эрсдэл ба чанар", "valuation": "Үнэлгээ", "dividend": "Ногдол ашиг", "market": "Зах зээлийн хөрвөх чадвар",
}
