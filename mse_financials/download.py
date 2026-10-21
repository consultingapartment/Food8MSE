"""Тайлангийн файл татах. Манифест (url -> файл) хадгалж, дахин татахгүй."""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse

from .client import Client, FetchError
from .discovery import find_report_links
from .models import Downloaded, ReportLink
from .parse import quarter_end

log = logging.getLogger(__name__)
MANIFEST = "manifest.json"


def sniff_ext(content: bytes, fallback: str) -> str:
    """Агуулгаас төрлийг тодорхойлно (зарим '.xls' холбоос үнэндээ PDF байдаг)."""
    if content[:4] == b"%PDF":
        return ".pdf"
    if content[:2] == b"PK":
        return ".xlsx"
    if content[:4] == b"\xd0\xcf\x11\xe0":
        return ".xls"
    return fallback


def _stem(ticker: str, link: ReportLink, counter: dict[str, int]) -> str:
    base = re.sub(r"[\\/:*?\"<>|\s]+", "", unquote(Path(urlparse(link.url).path).stem))
    tag = link.period.compact if link.period else base
    key = f"{tag}.{link.kind}"
    counter[key] = counter.get(key, 0) + 1
    suffix = f"_{counter[key]}" if counter[key] > 1 else ""
    return f"{ticker}_{tag}{suffix}" + ("_pdf" if link.kind == "pdf" else "")


def download_reports(client: Client, ticker: str, code: int, dest: Path,
                     include_pdf: bool = True, since: date | None = None) -> list[Downloaded]:
    """`since` өгвөл тэр огнооноос хойших үеийн тайланг л татна (аль хэдийн нэгтгэснийг дахин татахгүй)."""
    folder = dest / ticker
    folder.mkdir(parents=True, exist_ok=True)
    manifest_path = folder / MANIFEST
    manifest: dict[str, str] = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}

    page_url = f"{client.base_url}/securities/{code}/tab/financials"
    page = client.text(page_url)
    links = find_report_links(page, page_url)
    if not links:
        debug = dest / "_debug"
        debug.mkdir(exist_ok=True)
        (debug / f"{ticker}.html").write_text(page, "utf-8")
        log.warning("%s: файлын холбоос олдсонгүй — хуудсыг %s/%s.html хадгаллаа", ticker, debug, ticker)
        return []

    out: list[Downloaded] = []
    counter: dict[str, int] = {}
    # Excel хувилбартай үеийн PDF-ийг татахгүй (Excel найдвартай, PDF/OCR удаан, алдаатай). Excel холбоос нь үнэндээ
    # PDF байвал (sniff_ext) тэр үе PDF-ээр л үлдэнэ.
    has_excel = {l.period for l in links if l.kind != "pdf" and l.period}
    got_pdf_as_excel: set = set()
    links = sorted(links, key=lambda l: l.kind == "pdf")            # Excel эхэлж, PDF сүүлд
    for link in links:
        if link.kind == "pdf" and not include_pdf:
            continue
        if link.kind == "pdf" and link.period in has_excel and link.period not in got_pdf_as_excel:
            log.debug("%s %s: Excel хувилбартай тул PDF татсангүй", ticker, link.period.label)
            continue
        if since and link.period and quarter_end(link.period) <= since:
            continue
        stem = _stem(ticker, link, counter)
        cached = manifest.get(link.url)
        if cached and (folder / cached).exists():
            out.append(Downloaded(ticker, folder / cached, link.url, link.period, filed=link.filed))
            continue
        try:
            resp = client.get(link.url)
        except FetchError as exc:
            log.warning("  алгаслаа: %s", exc)
            if link.kind != "pdf" and link.period:
                got_pdf_as_excel.add(link.period)                     # Excel татагдсангүй — PDF-ээр нөхнө
            continue
        ext = sniff_ext(resp.content, Path(urlparse(link.url).path).suffix.lower() or ".xls")
        path = folder / (stem + ext)
        path.write_bytes(resp.content)
        manifest[link.url] = path.name
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), "utf-8")
        out.append(Downloaded(ticker, path, link.url, link.period, new=True, filed=link.filed))
        if link.kind != "pdf" and ext == ".pdf" and link.period:
            got_pdf_as_excel.add(link.period)                         # "Excel" нь PDF болж таарсан — жинхэнэ PDF-ийг ч татна
        client.sleep()
    return out
