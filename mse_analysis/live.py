"""МХБ-ийн нээлттэй өгөгдлийн сайт (open.mse.mn)-аас тухайн өдрийн арилжааны мэдээллийг татна.

Хаяг: `https://open.mse.mn/securities/{id}/tab/tradeinfo` — "Арилжааны мэдээлэл" дэд таб (Үндсэн харагдах байдал).
Тухайн өдрийн нээлт, хаалтын ханшийг шууд авч одоо байгаа түүхтэй нэгтгэнэ.
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

from mse_financials.client import Client

from .config import TICKERS
from .prices import Bar, read_csv, write_csv

log = logging.getLogger("mse_analysis.live")

BASE = "https://open.mse.mn"
#: Тикер -> open.mse.mn дахь үнэт цаасны дугаар
SECURITY_IDS = {"APU": 90, "TUM": 549, "TCK": 22, "SUU": 135, "MFC": 551, "GAZR": 565, "MMX": 208, "MGLA": 572}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def url_for(ticker: str, today: Optional[date] = None, days: int = 60) -> str:
    u = f"{BASE}/securities/{SECURITY_IDS[ticker]}/tab/tradeinfo"
    if today:
        u += f"?startDate={(today - timedelta(days=days)).isoformat()}&endDate={today.isoformat()}"
    return u


class _Rows(HTMLParser):
    """HTML-ийн <tr> бүрийн <td>/<th> нүднүүдийн текстийг цуглуулна."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: Optional[list[str]] = None
        self._cell: Optional[list[str]] = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _num(s: str) -> Optional[float]:
    s = s.replace(",", "").replace("\xa0", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_history(html: str, today: date) -> list[Bar]:
    """'Арилжааны мэдээлэл' дэд табын 2 баганатай хүснэгтээс тухайн өдрийн ханшийг задлана."""
    p = _Rows()
    p.feed(html)
    
    info: dict[str, float] = {}
    for cells in p.rows:
        if len(cells) >= 2:
            k = cells[0].strip().lower()
            v = _num(cells[1])
            if v is not None:
                info[k] = v

    cl = None
    op = None
    for k, v in info.items():
        if "хаалтын ханш" in k and "өмнөх" not in k:
            cl = v
        elif "нээлтийн ханш" in k:
            op = v

    if not cl or cl <= 0:
        return []

    if not op:
        op = cl

    bar = Bar(
        day=today,
        open=op,
        high=max(op, cl),
        low=min(op, cl),
        close=cl,
        qty=0.0,
        value=0.0
    )
    return [bar]


def fetch(raw_dir: Optional[Path], today: date, client: Optional[Client] = None) -> dict[str, list[Bar]]:
    """8 тикерийн хуудсыг татаж задлана. Тикер -> [Bar]."""
    client = client or Client(base_url=BASE, timeout=40)
    out: dict[str, list[Bar]] = {}
    for t in TICKERS:
        if t not in SECURITY_IDS:
            continue
        try:
            html = client.text(url_for(t, today))
        except Exception as e:
            log.warning("%s: татаж чадсангүй: %s", t, e)
            continue
        if raw_dir:
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / f"{t}.html").write_text(html, "utf-8")
        
        bars = parse_history(html, today)
        log.info("%s: сүүлийн хаалт %s", t, f"{bars[0].close:g} ({bars[0].day})" if bars else "—")
        if bars:
            out[t] = bars
        client.sleep()
    return out


# ------------------------------------------------------------------ inputs/-д бичих
def apply(history: dict[str, list[Bar]], inputs: Path) -> list[str]:
    """`prices/<T>.csv`-д шинэ өдрүүдийг нэгтгэж, `market.csv` дахь ханш/огноог сүүлийн хаалтаар шинэчилнэ."""
    import csv

    path = inputs / "market.csv"
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        fields = rd.fieldnames or []
        rows = list(rd)
    done = []
    for r in rows:
        t = r["ticker"].strip().upper()
        new = history.get(t)
        if not new:
            continue
        pp = inputs / "prices" / f"{t}.csv"
        bars = {b.day: b for b in (read_csv(pp) if pp.exists() else [])}
        added = sum(1 for b in new if b.day not in bars)
        bars.update({b.day: b for b in new})
        merged = [bars[d] for d in sorted(bars)]
        write_csv(pp, merged)
        last = merged[-1]
        r["price"] = f"{last.close:g}"
        r["price_date"] = last.day.isoformat()
        done.append(f"{t} {last.close:g} ({last.day}), +{added} шинэ өдөр")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return done
