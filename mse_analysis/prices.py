"""Арилжааны түүх: МХБ-ийн хуулбарласан текст (food_8_trade_history.txt) эсвэл цэвэр CSV уншина.

Текстийн бүтэц: тикерийн гарчиг мөр (`apu`, `MFC` ...), дараа нь `№ \tДээд\tДоод\tНээлт\tХаалт\tШирхэг\tҮнийн дүн\tОгноо`
мөрүүд (шинэ → хуучин). Нэг гарчгийн дор хоёр компани дараалан орсон байж болно (MFC-ийн дор TUM): дугаарчлал 1-ээс
дахин эхлэх үед шинэ хэсэг гэж үзэж, хэсэг бүрийг сүүлийн хаалтын ханшаар нь ойр тикерт оноож тавина.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

HEADER = re.compile(r"^[A-Za-z]{2,6}$")
ROW = re.compile(r"^\d+\t")


@dataclass(frozen=True)
class Bar:
    day: date
    open: float
    high: float
    low: float
    close: float
    qty: float
    value: float


def _num(s: str) -> float:
    s = s.strip().replace(",", "")
    return float(s) if s else 0.0


def _bar(parts: list[str]) -> Optional[Bar]:
    if len(parts) < 8:
        return None
    try:
        day = datetime.strptime(parts[7].strip(), "%Y-%m-%d").date()
        hi, lo, op, cl = (_num(p) for p in parts[1:5])
        return Bar(day, op, hi, lo, cl, _num(parts[5]), _num(parts[6]))
    except ValueError:
        return None


def _clean(bars: Iterable[Bar]) -> list[Bar]:
    """Хуучнаас шинэ рүү эрэмбэлж, огноо давхардлыг (сүүлийнхийг нь) арилгана; хаалт 0 (арилжаа болоогүй) мөрийг хасна."""
    by_day: dict[date, Bar] = {}
    for b in bars:
        if b.close > 0:
            by_day[b.day] = b
    return [by_day[d] for d in sorted(by_day)]


def parse_trade_history(text: str, ref_prices: dict[str, float] | None = None) -> dict[str, list[Bar]]:
    """Тикер -> [Bar] (хуучнаас шинэ рүү). `ref_prices`: нэг гарчгийн дор олон компани орсон үед хэсгийг
    тикерт оноох лавлах ханш (жишээ нь inputs/market.csv-ийн ханш)."""
    sections: list[tuple[str, list[Bar]]] = []         # (гарчиг, хэсгүүд)
    header = None
    cur: list[Bar] = []
    last_no = None
    groups: list[tuple[str, list[list[Bar]]]] = []
    for line in text.replace("\r", "").split("\n"):
        s = line.strip()
        if HEADER.match(s):
            header = s.upper()
            groups.append((header, [[]]))
            last_no = None
            continue
        if header is None or not ROW.match(line):
            continue
        parts = line.split("\t")
        bar = _bar(parts)
        if bar is None:
            continue
        no = int(parts[0])
        if last_no is not None and no <= last_no and groups[-1][1][-1]:
            groups[-1][1].append([])                    # дугаарчлал дахин эхэллээ -> шинэ компанийн хэсэг
        groups[-1][1][-1].append(bar)
        last_no = no
    del sections, cur

    out: dict[str, list[Bar]] = {}
    refs = ref_prices or {}
    for header, segs in groups:
        segs = [s for s in segs if s]
        if len(segs) == 1:
            out[header] = _clean(segs[0])
            continue
        free = [t for t in refs if t not in out]
        for seg in segs:
            last = max(seg, key=lambda b: b.day).close            # хэсгийн хамгийн сүүлийн хаалт
            cands = [header] + [t for t in free if t != header]
            best = min(cands, key=lambda t: abs(last - refs[t]) / refs[t] if refs.get(t) else float("inf"))
            if best == header and refs.get(header) is None and out.get(header):
                best = next((t for t in free if t not in out), header)
            out[best] = _clean(seg)
            if best in free:
                free.remove(best)
    return out


def write_csv(path: Path, bars: list[Bar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "open", "high", "low", "close", "qty", "value"])
        for b in bars:
            w.writerow([b.day.isoformat(), b.open, b.high, b.low, b.close, b.qty, b.value])


def read_csv(path: Path) -> list[Bar]:
    bars = []
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            bars.append(Bar(date.fromisoformat(row["date"]), float(row["open"]), float(row["high"]),
                            float(row["low"]), float(row["close"]), float(row.get("qty") or 0),
                            float(row.get("value") or 0)))
    return _clean(bars)


def load_prices(directory: Path) -> dict[str, list[Bar]]:
    """`inputs/prices/<TICKER>.csv` бүгдийг уншина."""
    out: dict[str, list[Bar]] = {}
    if directory.is_dir():
        for p in sorted(directory.glob("*.csv")):
            out[p.stem.upper()] = read_csv(p)
    return out
