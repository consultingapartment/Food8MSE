"""Скан хийсэн (зөвхөн зурагтай) PDF тайланг OCR-оор уншина.

Сангийн сайдын 2017 оны 361 дүгээр тушаалын маягтад зориулсан. Монгол хэлний OCR сан шаардахгүй:
мөрийн ДУГААР ба ТОО (латин цифр)-ыг л `tesseract` (eng)-ээр уншиж, мөрийн нэрийг дугаараар нь стандарт
хүснэгтээс авна. Тоо бүр 2 аравтын орноор төгсдөг тул цифрийг нь аваад 100-д хуваана (таслал/цэгийн OCR алдаа
нөлөөлөхгүй).

БУРУУ ТОО ОРОХООС САЙТАР САНАХ: Баланс, ОДТ-ийн нийлбэрийн бүх шалгалт (дэд мөрийн нийлбэр = дүн, хөрөнгө =
өр + өмч, нийт ашиг = орлого − өртөг, ...) ХОЁР баганад хоёуланд нь биелэхгүй бол `ScannedPdfError` шиднэ.
Шаардлагатай програм: `tesseract` (Ubuntu: `apt install tesseract-ocr`), `numpy`.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from .pdf import ScannedPdfError

log = logging.getLogger(__name__)

NUMTOK = re.compile(r"^[-—–]?[\d,.]+$")
AMOUNT = re.compile(r"[.,]\d{2}$")                    # дүн нь үргэлж 2 аравтын орноор төгсдөг ("2025", "31" жил/өдрийг хасна)
CODE = re.compile(r"^(\d+(?:\.\d+)*)\.?$")
DPIS = (300,)
TOL = 0.05                                            # нийлбэрийн шалгалтын зөвшөөрөх зөрүү (төгрөг)

# Стандарт маягтын мөрийн дугаар -> нэр (текст PDF-ээс авсан; загварын `match_item` нэрээр таньдаг)
BS_LABELS = {
    "1.1.1": "Мөнгө,түүнтэй адилтгах хөрөнгө", "1.1.2": "Дансны авлага", "1.1.3": "Татвар, НДШ – ийн авлага",
    "1.1.4": "Бусад авлага", "1.1.5": "Бусад санхүүгийн хөрөнгө", "1.1.6": "Бараа материал",
    "1.1.7": "Урьдчилж төлсөн зардал/тооцоо", "1.1.8": "Бусад эргэлтийн хөрөнгө",
    "1.1.9": "Борлуулах зорилгоор эзэмшиж буй эргэлтийн бус хөрөнгө (борлуулах бүлэг хөрөнгө)",
    "1.1.11": "Эргэлтийн хөрөнгийн дүн",
    "1.2.1": "Үндсэн хөрөнгө", "1.2.2": "Биет бус хөрөнгө", "1.2.3": "Биологийн хөрөнгө",
    "1.2.4": "Урт хугацаат хөрөнгө оруулалт", "1.2.5": "Хайгуул ба үнэлгээний хөрөнгө",
    "1.2.6": "Хойшлогдсон татварын хөрөнгө", "1.2.7": "Хөрөнгө оруулалтын зориулалттай үл хөдлөх хөрөнгө",
    "1.2.8": "Бусад эргэлтийн бус хөрөнгө", "1.2.9": "Дуусаагүй барилга", "1.2.10": "Эргэлтийн бус хөрөнгийн дүн",
    "1.3": "НИЙТ ХӨРӨНГИЙН ДҮН",
    "2.1.1.1": "Дансны өглөг", "2.1.1.2": "Цалингийн өглөг", "2.1.1.3": "Татварын өр", "2.1.1.4": "НДШ - ийн өглөг",
    "2.1.1.5": "Богино хугацаат зээл", "2.1.1.6": "Хүүний өглөг", "2.1.1.7": "Ногдол ашгийн өглөг",
    "2.1.1.8": "Урьдчилж орсон орлого", "2.1.1.9": "Нөөц /өр төлбөр/", "2.1.1.10": "Бусад богино хугацаат өр төлбөр",
    "2.1.1.11": "Борлуулах зорилгоор эзэмшиж буй эргэлтийн бус хөрөнгө (борлуулах бүлэг хөрөнгө)-нд хамаарах өр төлбөр",
    "2.1.1.13": "Богино хугацаат өр төлбөрийн дүн",
    "2.1.2.1": "Урт хугацаат зээл", "2.1.2.2": "Нөөц /өр төлбөр/", "2.1.2.3": "Хойшлогдсон татварын өр",
    "2.1.2.4": "Бусад урт хугацаат өр төлбөр", "2.1.2.6": "Урт хугацаат өр төлбөрийн дүн",
    "2.2": "Өр төлбөрийн нийт дүн", "2.4": "ӨР ТӨЛБӨР БА ЭЗДИЙН ӨМЧИЙН ДҮН",
}
#: Өмчийн хэсэг: скан дээрх маягт (2.3.1 төрийн, 2.3.2 хувийн, 2.3.3 хувьцаат, 2.3.4 халаасны ...) -> загварын дугаар, нэр
EQUITY_B = (
    ("2.3", "2.3.1", "Өмч:"), ("2.3.4", "2.3.2", "Халаасны хувьцаа"), ("2.3.5", "2.3.3", "Нэмж төлөгдсөн капитал"),
    ("2.3.6", "2.3.4", "Хөрөнгийн дахин үнэлгээний нэмэгдэл"), ("2.3.7", "2.3.5", "Гадаад валютын хөрвүүлэлтийн нөөц"),
    ("2.3.8", "2.3.6", "Эздийн өмчийн бусад хэсэг"), ("2.3.9", "2.3.7", "Хуримтлагдсан ашиг"),
    ("2.3.11", "2.3.9", "Эздийн өмчийн дүн"),
)
BS_ONLY_SCAN_CODES = {"1", "1.1", "1.2", "1.1.10", "2.1.1.12", "2.1.2.5", "2.3.1", "2.3.2", "2.3.3", "2.3.10"}
IS_ROWS = (
    ("1", "Борлуулалтын орлого (цэвэр)"), ("2", "Борлуулсан бүтээгдэхүүний өртөг"), ("3", "Нийт ашиг ( алдагдал)"),
    ("4", "Түрээсийн орлого"), ("5", "Хүүний орлого"), ("6", "Ногдол ашгийн орлого"),
    ("7", "Эрхийн шимтгэлийн орлого"), ("8", "Бусад орлого"), ("9", "Борлуулалт, маркетингийн зардал"),
    ("10", "Ерөнхий ба удирдлагын зардал"), ("11", "Санхүүгийн зардал"), ("12", "Бусад зардал"),
    ("13", "Гадаад валютын ханшийн зөрүүний олз (гарз)"), ("14", "Үндсэн хөрөнгө данснаас хассаны олз (гарз)"),
    ("15", "Биет бус хөрөнгө данснаас хассаны олз (гарз)"), ("16", "Хөрөнгө оруулалт борлуулснаас үүссэн олз (гарз)"),
    ("17", "Бусад ашиг ( алдагдал)"), ("18", "Татвар төлөхийн өмнөх ашиг (алдагдал)"),
    ("19", "Орлогын татварын зардал"), ("20", "Ердийн үйл ажиллагааны татварын дараах ашиг (алдагдал)"),
    ("21", "Зогсоосон үйл ажиллагааны татварын дараах ашиг (алдагдал)"), ("22", "Тайлант үеийн цэвэр ашиг ( алдагдал)"),
    ("23", "Бусад дэлгэрэнгүй орлого"), ("23.1", "Хөрөнгийн дахин үнэлгээний нэмэгдлийн зөрүү"),
    ("23.2", "Гадаад валютын хөрвүүлэлтийн зөрүү"), ("23.3", "Бусад олз (гарз)"),
    ("24", "Нийт дэлгэрэнгүй орлогын дүн"), ("25", "Нэгж хувьцаанд ногдох суурь ашиг (алдагдал)"),
)
IS_CODES = [c for c, _ in IS_ROWS]
BS_KNOWN = set(BS_LABELS) | BS_ONLY_SCAN_CODES | {c for c, _, _ in EQUITY_B}

Record = tuple[Optional[str], list[float]]            # (мөрийн дугаар | None, [эхний, эцсийн])


# ----------------------------------------------------------------------------- зураг, tesseract
def tesseract_path() -> Optional[str]:
    return shutil.which("tesseract")


def clean_grid(img):
    """Хүснэгтийн шугамыг арилгана (шугам нь OCR-ийг тасалдуулдаг)."""
    import numpy as np
    from PIL import Image

    a = np.array(img.convert("L"))
    dark = a < 170
    for r in np.where(dark.mean(axis=1) > 0.45)[0]:
        a[max(0, r - 2):r + 3, :] = 255
    for c in np.where(dark.mean(axis=0) > 0.30)[0]:
        a[:, max(0, c - 2):c + 3] = 255
    return Image.fromarray(a)


def ocr_lines(img) -> tuple[list[tuple[list[tuple[int, int, str]], int, int]], int]:
    """Зургаас мөр бүрийн (үгс [(зүүн, өргөн, текст)], дээд, доод) ба зургийн өргөн."""
    with tempfile.TemporaryDirectory() as tmp:
        png = os.path.join(tmp, "page.png")
        img.save(png)
        out = subprocess.run([tesseract_path(), png, "stdout", "--psm", "6", "-l", "eng", "tsv"],
                             capture_output=True, text=True, timeout=180).stdout
    lines: dict[tuple, list] = {}
    for r in csv.DictReader(io.StringIO(out), delimiter="\t", quoting=csv.QUOTE_NONE):
        if r.get("level") == "5" and (r.get("text") or "").strip():
            lines.setdefault((r["block_num"], r["par_num"], r["line_num"]), []).append(
                (int(r["left"]), int(r["width"]), r["text"].strip(), int(r["top"]), int(r["height"])))
    result = []
    for ws in lines.values():
        ws.sort()
        result.append(([(left, w, t) for left, w, t, _, _ in ws],
                       min(top for *_, top, _ in ws), max(top + h for *_, top, h in ws)))
    return result, img.width


def _amount(tokens: list[str]) -> Optional[float]:
    s = "".join(tokens)
    if not AMOUNT.search(s):
        return None
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None
    v = int(digits) / 100
    return -v if s.startswith(("-", "—", "–")) else v


def _edges(lines, width) -> Optional[tuple[float, float]]:
    """Тоон хоёр баганын баруун ирмэг: тоонууд баруун тийш зэрэгцдэг тул хамгийн олон давтагдах 2 ирмэг."""
    bins: dict[int, list[int]] = {}
    for ws, _, _ in lines:
        for left, w, t in ws:
            if NUMTOK.match(t) and left > 0.45 * width:
                bins.setdefault(round((left + w) / 12), []).append(left + w)
    ranked = sorted(bins, key=lambda b: -len(bins[b]))
    if not ranked:
        return None
    first = ranked[0]
    second = next((b for b in ranked[1:] if abs(b - first) * 12 > 100), None)
    if second is None:
        return None
    e1, e2 = sorted((statistics.median(bins[first]), statistics.median(bins[second])))
    return e1, e2


def _strip_amount(img, top: int, bottom: int, right_edge: float, pitch: float = 330,
                  scale: int = 2, binarize: bool = False) -> Optional[float]:
    """Нэг мөрийн нэг тоон баганыг ТУСАД нь (зөвхөн цифр, таслал, цэг, хасах тэмдэгтийн жагсаалттай) дахин уншина.
    `img` нь шугамгүй болгоогүй анхны зураг: тод мөрийн хүрээ шугам арилгахад үсгийг гэмтээдэг."""
    import numpy as np
    from PIL import Image

    box = (max(0, int(right_edge - pitch + 14)), max(0, top - 2), int(right_edge) + 4, min(img.height, bottom + 2))
    a = np.array(img.convert("L").crop(box))
    dark = a < 170
    for r in np.where(dark.mean(axis=1) > 0.6)[0]:
        a[r, :] = 255
    for c in np.where(dark.mean(axis=0) > 0.6)[0]:
        a[:, c] = 255
    if binarize:
        a = np.where(a < 150, 0, 255).astype(np.uint8)
    crop = Image.fromarray(a)
    crop = crop.resize((crop.width * scale, crop.height * scale))
    crop = Image.fromarray(np.pad(np.array(crop), 20, constant_values=255))
    with tempfile.TemporaryDirectory() as tmp:
        png = os.path.join(tmp, "cell.png")
        crop.save(png)
        out = subprocess.run([tesseract_path(), png, "stdout", "--psm", "7", "-l", "eng",
                              "-c", "tessedit_char_whitelist=0123456789.,-"],
                             capture_output=True, text=True, timeout=60).stdout
    return _amount(out.split())


def page_records(lines, width, img=None, locs: Optional[list] = None) -> list[Record]:
    """Нэг хуудасны (дугаар, [эхний, эцсийн]) мөрүүд, дээрээс доош. Дугаар танигдаагүй бол None.
    `img` өгвөл дугаартай боловч тоо нь эвдэрсэн мөрийг тоон баганаар нь дахин уншина."""
    edges = _edges(lines, width)
    out: list[Record] = []
    if edges is None:
        return out
    e1, e2 = edges
    for ws, top, bottom in lines:
        words = [w for w in ws if w[0] < e2 - 4]                # баруун ирмэгээс цааших хуурамч тэмдэгтийг хаяна
        i, tail = len(words) - 1, []
        while i >= 0 and NUMTOK.match(words[i][2]) and words[i][0] > 0.45 * width:
            tail.insert(0, words[i])
            i -= 1
        head = words[:i + 1]
        m = CODE.match(head[0][2].strip("|").replace(",", ".")) if head else None
        cols: dict[int, list[str]] = {0: [], 1: []}
        for left, w, t in tail:
            cols[0 if left + w <= e1 + 14 else 1].append(t)
        vals = [_amount(cols[k]) if cols[k] else None for k in (0, 1)]
        if img is not None and m and any(v is None for v in vals) and (bottom - top) < 120:
            for k, edge in enumerate((e1, e2)):
                if vals[k] is None:
                    vals[k] = _strip_amount(img, top, bottom, edge, e2 - e1)
        if any(v is None for v in vals):
            continue                                              # хоёр утгатай (эхний, эцсийн) мөр биш
        out.append((m.group(1) if m else None, [v for v in vals if v is not None]))
        if locs is not None:
            locs.append((img, top, bottom, e1, e2))
    return out


# ----------------------------------------------------------------------------- шалгалт
def _close(a: float, b: float) -> bool:
    return abs(a - b) <= TOL


def check_balance(by: dict[str, float]) -> list[str]:
    """Нэг баганын баланс: нийлбэрийн шалгалтууд. Алдааны жагсаалт (хоосон бол зөв)."""
    g = lambda c: by.get(c, 0.0)   # noqa: E731
    sums = lambda codes: sum(g(c) for c in codes)   # noqa: E731
    errs = []
    for name, parts, total in (
        ("Эргэлтийн хөрөнгө", [f"1.1.{i}" for i in range(1, 11)], "1.1.11"),
        ("Эргэлтийн бус хөрөнгө", [f"1.2.{i}" for i in range(1, 10)], "1.2.10"),
        ("Богино хугацаат өр", [f"2.1.1.{i}" for i in range(1, 13)], "2.1.1.13"),
        ("Урт хугацаат өр", [f"2.1.2.{i}" for i in range(1, 6)], "2.1.2.6"),
        ("Эздийн өмч", ["2.3"] + [f"2.3.{i}" for i in range(4, 11)], "2.3.11"),
    ):
        if total not in by or not _close(sums(parts), g(total)):
            errs.append(f"{name}: {sums(parts):,.2f} ≠ {g(total):,.2f}")
    for name, parts, total in (
        ("Нийт хөрөнгө", ["1.1.11", "1.2.10"], "1.3"), ("Нийт өр", ["2.1.1.13", "2.1.2.6"], "2.2"),
        ("Өр + өмч", ["2.2", "2.3.11"], "2.4"), ("Хөрөнгө = өр + өмч", ["1.3"], "2.4"),
    ):
        if total not in by or not _close(sums(parts), g(total)):
            errs.append(f"{name}: {sums(parts):,.2f} ≠ {g(total):,.2f}")
    return errs


def check_income(by: dict[str, float]) -> list[str]:
    g = lambda c: by.get(c, 0.0)   # noqa: E731
    checks = (
        ("Нийт ашиг", g("1") - g("2"), g("3")),
        ("Татвар төлөхийн өмнөх ашиг",
         g("3") + sum(g(c) for c in ("4", "5", "6", "7", "8")) - sum(g(c) for c in ("9", "10", "11", "12"))
         + sum(g(c) for c in ("13", "14", "15", "16", "17")), g("18")),
        ("Татварын дараах ашиг", g("18") - g("19"), g("20")),
        ("Цэвэр ашиг", g("20") + g("21"), g("22")),
        ("Бусад дэлгэрэнгүй орлого", g("23.1") + g("23.2") + g("23.3"), g("23")),
        ("Нийт дэлгэрэнгүй орлого", g("22") + g("23"), g("24")),
    )
    return [f"{n}: {a:,.2f} ≠ {b:,.2f}" for n, a, b in checks if not _close(a, b)]


def build_sheets(records: list[Record]) -> dict[str, list[list[Any]]]:
    """Дарааллаар: баланс (2.4 мөрөөр төгсөнө), дараа нь ОДТ-ийн 28 мөр (дугаарыг байрлалаар нь). Шалгалтад унавал ScannedPdfError."""
    bs: dict[str, list[float]] = {}
    rest: list[Record] = []
    seen_total = False
    for code, vals in records:
        if not seen_total:
            if code in BS_KNOWN and code not in bs:
                bs[code] = vals
                seen_total = code == "2.4"
        else:
            rest.append((code, vals))
    if not seen_total:
        raise ScannedPdfError("OCR: баланс олдсонгүй (2.4 мөр танигдсангүй)")
    inc = rest[:len(IS_CODES)]
    if len(inc) < len(IS_CODES):
        raise ScannedPdfError(f"OCR: ОДТ-ийн {len(IS_CODES)} мөрийн {len(inc)} л танигдлаа")
    for (code, _), expected in zip(inc, IS_CODES):
        if code is not None and code != expected:
            raise ScannedPdfError(f"OCR: ОДТ-ийн мөрийн дараалал зөрлөө ({code} ≠ {expected})")

    errors: list[str] = []
    for col, name in ((0, "эхний"), (1, "эцсийн")):
        errors += [f"баланс/{name}: {e}" for e in check_balance({c: v[col] for c, v in bs.items()})]
        errors += [f"ОДТ/{name}: {e}" for e in check_income({c: v[col] for c, (_, v) in zip(IS_CODES, inc)})]
    if errors:
        raise ScannedPdfError("OCR-оор уншсан тоо нийлбэрийн шалгалтад унав — " + "; ".join(errors[:4]))

    header = ["", "№", "Үзүүлэлт", "Эхний үлдэгдэл", "Эцсийн үлдэгдэл"]
    bs_rows = [["", c, BS_LABELS[c], *bs[c]] for c in BS_LABELS if c in bs]
    bs_rows += [["", new, label, *bs[old]] for old, new, label in EQUITY_B if old in bs]
    is_rows = [["", c, label, *v] for (c, label), (_, v) in zip(IS_ROWS, inc)]
    return {"СБД": [header] + bs_rows, "ОДТ": [header] + is_rows}


def _variants(loc, col: int) -> list[float]:
    """Нэг нүдийг өөр масштаб/босготой уншсан өөр утгууд."""
    img, top, bottom, e1, e2 = loc
    seen: list[float] = []
    for scale, binar in ((3, False), (4, False), (3, True), (2, True), (5, False)):
        v = _strip_amount(img, top, bottom, (e1, e2)[col], e2 - e1, scale, binar)
        if v is not None and v not in seen:
            seen.append(v)
    return seen


def repair(records: list[Record], locs: list) -> Optional[dict[str, list[list[Any]]]]:
    """Шалгалтад унасан үед ЗӨВХӨН НЭГ нүдийг өөр уншилтаар солиход бүх нийлбэр таардаг эсэхийг шалгана.
    Нийлбэрт таарах утга олдохгүй бол None (таамаглахгүй)."""
    if len(records) != len(locs):
        return None
    for i, (code, vals) in enumerate(records):
        for col in range(len(vals)):
            for alt in _variants(locs[i], col):
                if alt == vals[col]:
                    continue
                trial = list(records)
                trial[i] = (code, [alt if k == col else v for k, v in enumerate(vals)])
                try:
                    sheets = build_sheets(trial)
                except ScannedPdfError:
                    continue
                log.info("OCR засвар: %s мөр, %d-р багана %s → %s", code or i, col, f"{vals[col]:,.2f}", f"{alt:,.2f}")
                return sheets
    return None


# ----------------------------------------------------------------------------- гол функц
def ocr_sheets(path) -> dict[str, list[list[Any]]]:
    """Скан PDF -> {"СБД", "ОДТ"} (pdf.read_pdf_sheets-тэй ижил хэлбэр)."""
    if not tesseract_path():
        raise ScannedPdfError("Скан PDF: OCR-д `tesseract` хэрэгтэй (Ubuntu: apt install tesseract-ocr)")
    try:
        import numpy as np
        import pdfplumber
    except ImportError as exc:
        raise ScannedPdfError(f"Скан PDF: OCR-д шаардлагатай сан алга ({exc.name})") from exc
    del np

    last_error = "OCR хийж чадсангүй"
    for dpi in DPIS:
        records: list[Record] = []
        locs: list = []
        try:
            with pdfplumber.open(str(Path(path))) as pdf:
                for page in pdf.pages:
                    raw = page.to_image(resolution=dpi).original
                    lines, width = ocr_lines(clean_grid(raw))
                    records += page_records(lines, width, raw, locs)
                    if sum(1 for c, _ in records if c == "2.4") and \
                            len(records) - next(i for i, (c, _) in enumerate(records) if c == "2.4") - 1 >= len(IS_CODES):
                        break                                      # баланс + ОДТ бүгд олдсон — үлдсэн хуудсыг уншихгүй
            try:
                sheets = build_sheets(records)
            except ScannedPdfError as first:
                sheets = repair(records, locs)
                if sheets is None:
                    raise first
        except ScannedPdfError as exc:
            last_error = str(exc)
            log.info("%s: OCR %d dpi — %s", Path(path).name, dpi, exc)
            continue
        log.warning("%s: скан PDF-г OCR-оор уншлаа (%d dpi); нийлбэрийн бүх шалгалт өнгөрсөн. Excel хувилбар гарвал "
                    "түүнийг илүүд үзнэ", Path(path).name, dpi)
        return sheets
    raise ScannedPdfError(last_error)

