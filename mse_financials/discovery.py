"""open.mse.mn хуудаснаас тикер -> companyCode болон тайлангийн холбоос олох."""
from __future__ import annotations

import html as htmllib
import logging
import posixpath
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .config import KNOWN_IDS
from .models import Period, ReportLink

log = logging.getLogger(__name__)

FILE_RE = re.compile(r"\.(xlsx?|pdf)(?:$|[?#])", re.I)
#: Хүснэгтийн мөр: "2026 2 2026-07-28 ..." -> (2026, 2)
PERIOD_RE = re.compile(r"(?<!\d)(20\d{2})\D{1,12}?([1-4])(?!\d)")
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")


def parse_securities(page_html: str) -> dict[str, int]:
    """/securities хуудаснаас {тикер: companyCode}. Зөвхөн хувьцааны (#stocks) ангилал I-III."""
    soup = BeautifulSoup(page_html, "html.parser")
    out: dict[str, int] = {}
    for tab in ("class1", "class2", "class3"):
        for row in soup.select(f"#stocks #{tab} table tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            link = cells[1].find("a")
            m = re.search(r"/securities/(\d+)", link.get("href", "")) if link else None
            symbol = link.get_text(strip=True) if link else ""
            if m and symbol:
                out.setdefault(symbol, int(m.group(1)))
    return out


def resolve_ids(client, tickers: list[str]) -> dict[str, int]:
    """Тикер бүрийн companyCode. Сайтаас олдохгүй бол KNOWN_IDS-ээс авна."""
    try:
        found = parse_securities(client.text("/securities"))
    except Exception as exc:  # сүлжээ/бүтцийн алдаа — нөөц жагсаалт руу шилжинэ
        log.warning("/securities уншиж чадсангүй (%s) — KNOWN_IDS ашиглана", exc)
        found = {}
    ids = {}
    for t in tickers:
        code = found.get(t) or KNOWN_IDS.get(t)
        if code is None:
            log.error("%s: companyCode олдсонгүй", t)
            continue
        if t in found and t in KNOWN_IDS and found[t] != KNOWN_IDS[t]:
            log.warning("%s: сайтын ID (%s) нь KNOWN_IDS (%s)-оос ялгаатай — сайтынхыг ашиглана",
                        t, found[t], KNOWN_IDS[t])
        ids[t] = code
    return ids


def _normalize(url: str) -> str:
    p = urlparse(url)
    path = posixpath.normpath(p.path.replace("//", "/"))
    return p._replace(path=path, fragment="").geturl()


def find_report_links(page_html: str, page_url: str) -> list[ReportLink]:
    """Санхүүгийн тайлангийн файлын холбоосууд (аудитын дүгнэлтийг оруулахгүй).

    Үеийг файлын нэрээс биш хүснэгтийн мөрөөс (Он | Улирал | Огноо) авдаг тул
    `90_finance_report_xls_6a68....xlsx` шиг hash нэртэй файлууд ч зөв таарна.
    """
    soup = BeautifulSoup(page_html, "html.parser")
    found: dict[str, ReportLink] = {}
    seen_paths: set[str] = set()

    def add(raw: str, text: str = "", row_text: str | None = None) -> None:
        raw = htmllib.unescape(raw).strip()
        if not raw or raw.startswith(("javascript:", "#", "mailto:")):
            return
        period, filed = None, ""
        if row_text and (m := PERIOD_RE.search(row_text)):
            period = Period(int(m.group(1)), int(m.group(2)))
        if row_text and (d := DATE_RE.search(row_text)):
            filed = d.group(1)
        is_report = bool(re.search(r"finance[_/]", raw, re.I))
        if not is_report and period is None:
            return  # аудитын дүгнэлт эсвэл хамааралгүй файл
        url = _normalize(urljoin(page_url, raw))
        key = url.split("?")[0].strip()
        if key in seen_paths:
            return  # аль хэдийн олдсон: үеийг нь дарж бичихгүй
        seen_paths.add(key)
        found[url] = ReportLink(url=url, period=period, text=text, filed=filed)

    for tag in soup.find_all(True):
        text = tag.get_text(" ", strip=True)[:120] if tag.name == "a" else ""
        tr = tag.find_parent("tr")
        row_text = tr.get_text(" ", strip=True) if tr else None
        for attr, val in tag.attrs.items():
            for v in (val if isinstance(val, list) else [val]):
                if not isinstance(v, str):
                    continue
                if FILE_RE.search(v):
                    add(v, text, row_text)
                elif attr.startswith("data-") and ("{" in v or "[" in v):
                    for u in re.findall(r"[\w/\\:.\-%]+\.(?:xlsx?|pdf)", htmllib.unescape(v), re.I):
                        add(u.replace("\\/", "/"), "", row_text)
    # script/текст доторх холбоос (хамгийн сүүлд: хүснэгтээс олдсоныг дарахгүй)
    for u in re.findall(r"""["'(]([^"'()]+?\.(?:xlsx?|pdf))(?:\?[^"'()]*)?["')]""", page_html, re.I):
        add(u.replace("\\/", "/"))
    return list(found.values())
