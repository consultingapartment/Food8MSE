"""Татах -> задлах -> нэгтгэх урсгал."""
from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from . import schedule
from .client import Client, FetchError
from .config import COMPANIES, TIMEZONE
from .discovery import find_report_links, resolve_ids
from .download import download_reports
from .excel import build_workbook, load_existing
from .models import Downloaded, ParsedReport
from .parse import parse_report, quarter_end, scan_local
from .template import BS, BY_KEY, IS

log = logging.getLogger(__name__)


def today() -> date:
    """Улаанбаатарын өнөөдрийн огноо (GitHub Actions UTC дээр ажиллахад ч зөв)."""
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(TIMEZONE)).date()
    except Exception:  # tzdata байхгүй (Windows) — локал огноо
        return date.today()


def collect(client: Client | None, tickers: list[str], reports_dir: Path,
            skip_download: bool, include_pdf: bool, since: dict[str, date] | None = None,
            failed: list[str] | None = None) -> list[Downloaded]:
    """`since`: тикер -> Excel-д нэгтгэгдсэн хамгийн сүүлийн тайлангийн огноо (түүнээс хойшхийг л авна)."""
    since = since or {}
    if skip_download:
        items = scan_local(reports_dir, tickers)
        return [i for i in items
                if not (i.ticker in since and i.period and quarter_end(i.period) <= since[i.ticker])]
    assert client is not None
    items: list[Downloaded] = []
    ids = resolve_ids(client, tickers)
    if failed is not None:
        failed += [t for t in tickers if t not in ids]
    for ticker, code in ids.items():
        log.info("%s (code=%s) тайлан татаж байна...", ticker, code)
        try:
            got = download_reports(client, ticker, code, reports_dir, include_pdf, since.get(ticker))
        except FetchError as exc:
            log.error("%s: %s", ticker, exc)
            if failed is not None:
                failed.append(ticker)
            continue
        log.info("  %d файл", len(got))
        items += got
    return items


def parse_all(items: list[Downloaded], context: list[ParsedReport] | None = None) -> list[ParsedReport]:
    """Excel файл бүрийг задалж, (тикер, тайлангийн огноо) бүрээр давхардлыг арилгана."""
    best: dict[tuple[str, date], ParsedReport] = {}
    rank: dict[tuple[str, date], tuple[bool, int]] = {}
    for item in items:
        is_pdf = item.path.suffix.lower() == ".pdf"
        try:
            rep = parse_report(item)
        except Exception as exc:  # нэг эвдэрсэн файл (эсвэл скан PDF) бүгдийг зогсоох ёсгүй
            log.warning("%s: задлах алдаа: %s", item.path.name, exc)
            continue
        if rep is None:
            log.warning("%s: Баланс/ОДТ олдсонгүй эсвэл үе тодорхойгүй", item.path.name)
            continue
        if rep.unmatched:
            log.debug("%s: загварт таараагүй мөр: %s", item.path.name, "; ".join(rep.unmatched))
        key = (rep.ticker, rep.end_date)
        score = (not is_pdf, rep.size)                      # давхар үед Excel > PDF, дараа нь илүү бүрэн хувийг авна
        if key not in best or score > rank[key]:
            best[key], rank[key] = rep, score
        if is_pdf:
            log.info("%s: PDF-ээс задаллаа — Excel хувилбар гарвал түүнийг илүүд үзнэ", item.path.name)
    reports = sorted(best.values(), key=lambda r: (r.ticker, r.end_date))
    for rep in fix_scales((context or []) + reports, targets=reports):
        log.warning("%s %s: нэгжийн засвар — %s", rep.ticker, rep.period.label, rep.scale_note)
    return reports


def _rescale(r: ParsedReport, statement: str, factor: float, name: str) -> None:
    for k, v in r.values.items():
        item = BY_KEY[k]
        if item.statement == statement and item.kind != "per_share":
            r.values[k] = v * factor
    note = f"{name} {'÷1000' if factor < 1 else '×1000'} (нэгж таарсангүй)"
    r.scale_note = f"{r.scale_note}; {note}" if r.scale_note else note


def fix_scales(reports: list[ParsedReport], targets: list[ParsedReport] | None = None) -> list[ParsedReport]:
    """Толгойн нэгж буруу (мянган төгрөг гэсэн ч бүтэн төгрөг г.м.) тайланг илрүүлж засна. Засагдсан тайлангуудыг
    буцаана. `targets` өгвөл зөвхөн тэдгээрийг засна (`reports` нь харьцуулах суурь).

    Нэг файл дотор баланс, орлогын тайлангийн нэгж ЯЛГААТАЙ байж болно (жишээ нь SUU 2024 Q4: баланс
    "мянган төгрөг" гэсэн ч бүтэн төгрөгөөр, ОДТ "төгрөг" гэж зөв) тул хоёрыг тусад нь засна:
      1. Баланс: нийт хөрөнгө нь компанийн бусад тайлангийн медианаас ~1000 дахин зөрсөн эсэх;
      2. ОДТ: орлого ÷ нийт хөрөнгө (баланс засагдсаны дараа) боломжгүй хэмжээнд (≥30 эсвэл ≤0.001) хүрсэн эсэх.
    """
    by_ticker: dict[str, list[ParsedReport]] = defaultdict(list)
    for r in reports:
        by_ticker[r.ticker].append(r)
    fixed: list[ParsedReport] = []

    def is_target(r: ParsedReport) -> bool:
        return targets is None or any(r is t for t in targets)

    for group in by_ticker.values():
        assets = [r.values["total_assets"] for r in group if r.values.get("total_assets")]
        if len(assets) >= 3:
            median = statistics.median(abs(a) for a in assets)
            for r in group:
                a = r.values.get("total_assets")
                if not (is_target(r) and a and median):
                    continue
                ratio = abs(a) / median
                factor = 1 / 1000 if 300 <= ratio <= 3000 else 1000 if 1 / 3000 <= ratio <= 1 / 300 else None
                if factor:
                    _rescale(r, BS, factor, "Баланс")
                    fixed.append(r)
        for r in group:
            a, rev = r.values.get("total_assets"), r.values.get("revenue")
            if not (is_target(r) and a and rev):
                continue
            turnover = abs(rev) / abs(a)
            factor = 1 / 1000 if turnover >= 30 else 1000 if turnover <= 0.001 else None
            if factor:
                _rescale(r, IS, factor, "ОДТ")
                if r not in fixed:
                    fixed.append(r)
    return fixed


def warn_duplicates(reports: list[ParsedReport]) -> None:
    """Нэг компанийн хоёр өөр үеийн тайлан ижил тоотой бол (ихэвчлэн компани хуучин тайлангаа буруу хавсаргасан) сануулна."""
    seen: dict[tuple, ParsedReport] = {}
    for r in sorted(reports, key=lambda r: (r.ticker, r.end_date)):
        sig = (r.ticker, r.values.get("total_assets"), r.values.get("revenue"))
        if sig[1] is None:
            continue
        if sig in seen:
            log.warning("%s %s: нийт хөрөнгө, орлого нь %s-тай бүрэн ижил — эх файл буруу/хуучин байж болзошгүй (%s)",
                        r.ticker, r.period.label, seen[sig].period.label, r.source)
        else:
            seen[sig] = r


#: (нэр, [нэмэх түлхүүрүүд], [хасах түлхүүрүүд]) — нийлбэр нь 0-тэй тэнцүү байх ёстой
IDENTITIES = (
    ("Хөрөнгө ≠ Өр + Эздийн өмч", ("total_assets",), ("total_liabilities", "total_equity")),
    ("Эргэлтийн + Эргэлтийн бус ≠ Нийт хөрөнгө", ("total_ca", "total_nca"), ("total_assets",)),
    ("Богино + Урт хугацаат өр ≠ Нийт өр", ("total_stl", "total_ltl"), ("total_liabilities",)),
    ("Орлого − Өртөг ≠ Нийт ашиг", ("revenue",), ("cogs", "gross_profit")),
    ("Татвар төлөхийн өмнөх ашиг − Татвар ≠ Татварын дараах ашиг", ("profit_before_tax",),
     ("income_tax", "profit_after_tax")),
)


def warn_inconsistent(reports: list[ParsedReport], only: list[ParsedReport] | None = None) -> None:
    """Тайлан доторх нийлбэр таарахгүй (эх файлын алдаа эсвэл буруу задалсан мөр) бол логт сануулна."""
    for r in only if only is not None else reports:
        for name, plus, minus in IDENTITIES:
            keys = plus + minus
            if any(k not in r.values for k in keys):
                continue
            diff = sum(r.values[k] for k in plus) - sum(r.values[k] for k in minus)
            if name.startswith("Орлого") or name.startswith("Татвар"):
                diff = r.values[plus[0]] - r.values[minus[0]] - r.values[minus[1]]
            tol = max(2.0, 0.001 * abs(r.values[keys[-1]]))
            if abs(diff) > tol:
                log.warning("%s %s: %s — зөрүү %s мянган төгрөг (%s)", r.ticker, r.period.label, name,
                            f"{diff:,.0f}", r.source)


def warn_missing(day: date, tickers: list[str], reports: list[ParsedReport]) -> None:
    """Хуулийн хугацаа + 14 хоног өнгөрсөн заавал тайлан ирээгүй компанийг логт сануулна."""
    due = schedule.latest_mandatory(day)
    if not due:
        return
    period, dl = due
    have = {(r.ticker, r.period) for r in reports}
    for t in tickers:
        if (t, period) not in have:
            log.warning("%s: %s (%s) тайлан ирээгүй/задрээгүй — хуулийн хугацаа %s өнгөрсөн", t, period.label,
                        dl.name, dl.due(period.year - dl.year_shift).isoformat())


def merge_new(existing: list[ParsedReport], new: list[ParsedReport], tickers: list[str]
              ) -> tuple[list[ParsedReport], int]:
    """Компани бүрийг дарааллаар шалгана: sheet-ийн сүүлийн баганын тайлан нэгтгэгдсэн эсэх, шинэ тайлан
    байвал нэмнэ. Буцаах: (нэгдсэн жагсаалт, нэмсэн тайлангийн тоо)."""
    merged = list(existing)
    added = 0
    for t in tickers:
        have = {r.end_date for r in existing if r.ticker == t}
        last = max(have, default=None)
        fresh = sorted((r for r in new if r.ticker == t and r.end_date not in have
                        and (last is None or r.end_date > last)), key=lambda r: r.end_date)   # зөвхөн сүүлийн баганаас хойших
        if last is None:
            log.info("%s: sheet хоосон — %d тайлан нэмлээ", t, len(fresh))
        elif not fresh:
            lp = next(r for r in existing if r.ticker == t and r.end_date == last)
            log.info("%s: сүүлийн тайлан %s (%s) нэгтгэгдсэн — шинэ тайлан алга", t, lp.period.label, last)
        else:
            log.info("%s: сүүлийн нэгтгэсэн %s → нэмлээ: %s", t, last, ", ".join(r.period.label for r in fresh))
        merged += fresh
        added += len(fresh)
    return merged, added


def _read_existing(out_path: Path, tickers: list[str]) -> list[ParsedReport]:
    """Байгаа Excel-ийн БҮХ компанийн sheet-ийг уншина (хэсэгчилсэн ажиллуулалтад ч бусад sheet устахгүй)."""
    try:
        existing = load_existing(out_path, list(COMPANIES) + [t for t in tickers if t not in COMPANIES])
        log.info("%s байна — %d тайлан уншлаа, шинэ тайлан хайна", out_path, len(existing))
        return existing
    except Exception as exc:
        log.warning("%s уншигдсангүй (%s) — шинээр бүтээнэ", out_path, exc)
        return []


def _last_dates(existing: list[ParsedReport], tickers: list[str]) -> dict[str, date]:
    return {t: max(r.end_date for r in existing if r.ticker == t)
            for t in tickers if any(r.ticker == t for r in existing)}


def check_updates(client: Client, tickers: list[str], since: dict[str, date],
                  include_pdf: bool = True) -> dict[str, dict]:
    """Юу ч татахгүй, бичихгүй: сайтад Excel-ийн сүүлийн баганаас ШИНЭ ямар тайлан гарсныг л жагсаана.
    Үр дүн: тикер -> {"last": огноо|None, "new": [(үеийн нэр, {"xls"|"pdf"})], "error": str|None, "unknown": тоо}."""
    result: dict[str, dict] = {}
    try:
        ids = resolve_ids(client, tickers)
    except FetchError as exc:
        return {t: {"last": since.get(t), "new": [], "error": str(exc), "unknown": 0} for t in tickers}
    for t in tickers:
        info: dict = {"last": since.get(t), "new": [], "error": None, "unknown": 0}
        result[t] = info
        code = ids.get(t)
        if code is None:
            info["error"] = "сайтаас компанийн код олдсонгүй"
            continue
        page_url = f"{client.base_url}/securities/{code}/tab/financials"
        try:
            links = find_report_links(client.text(page_url), page_url)
        except FetchError as exc:
            info["error"] = str(exc)
            continue
        groups: dict = {}
        for link in links:
            if link.kind == "pdf" and not include_pdf:
                continue
            if not link.period or not link.period.year:
                info["unknown"] += 1
                continue
            if t in since and quarter_end(link.period) <= since[t]:
                continue
            groups.setdefault(link.period, set()).add(link.kind)
        info["new"] = [(p.label, kinds) for p, kinds in sorted(groups.items())]
    return result


def check(tickers: list[str], out_path: Path, *, client: Client | None = None,
          include_pdf: bool = True) -> dict[str, dict]:
    """`--check`: Excel-ийг уншаад (өөрчлөхгүй) сайттай харьцуулна."""
    existing = _read_existing(out_path, tickers) if out_path.exists() else []
    return check_updates(client or Client(), tickers, _last_dates(existing, tickers), include_pdf)


def run(tickers: list[str], reports_dir: Path, out_path: Path, *, day: date | None = None,
        skip_download: bool = False, include_pdf: bool = True, client: Client | None = None,
        rebuild: bool = False, failed: list[str] | None = None,
        summary: dict | None = None) -> Path:
    """`out_path` Excel байвал компани бүрийн sheet-ийн сүүлийн баганыг шалгаж, зөвхөн шинэ тайланг нэмнэ.
    Байхгүй (эсвэл `rebuild`) бол бүх тайланг татаж шинээр бүтээнэ.
    `failed` жагсаалт өгвөл сайтаас татаж чадаагүй тикерүүдийг тэнд нэмнэ (дуудагч exit code-оо үүгээр шийднэ).
    `summary` dict өгвөл {"added": {тикер: [үе]}, "last": {тикер: огноо}} гэж бөглөнө (мэдэгдэлд ашиглана)."""
    day = day or today()
    reports_dir.mkdir(parents=True, exist_ok=True)
    # Байгаа файлын БҮХ компанийн sheet-ийг уншина: --tickers-ээр хэсэгчлэн ажиллуулсан ч бусад sheet устахгүй
    known = [t for t in COMPANIES if t in tickers] + [t for t in tickers if t not in COMPANIES]
    existing = _read_existing(out_path, tickers) if out_path.exists() and not rebuild else []
    sheets = [t for t in COMPANIES if t in known or any(r.ticker == t for r in existing)] + \
             [t for t in known if t not in COMPANIES]
    since = _last_dates(existing, tickers)
    client = client or (None if skip_download else Client())
    items = collect(client, tickers, reports_dir, skip_download, include_pdf, since, failed)
    new = parse_all(items, context=existing)
    merged, added = merge_new(existing, new, tickers)
    if summary is not None:
        summary["added"] = {}
        for r in merged[len(existing):]:                      # merge_new шинэ тайланг төгсгөлд нь залгадаг
            summary["added"].setdefault(r.ticker, []).append(r.period.label)
        summary["last"] = {t: max((r.end_date for r in merged if r.ticker == t), default=None) for t in tickers}
    warn_duplicates(merged)
    warn_inconsistent(merged, new)
    warn_missing(day, tickers, merged)
    if existing and not added:
        log.info("Шинэ тайлан алга — %s өөрчлөгдсөнгүй", out_path)
        return out_path
    return build_workbook(merged, sheets, out_path)
