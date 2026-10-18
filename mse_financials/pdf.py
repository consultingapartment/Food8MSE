"""Текст давхаргатай PDF тайлангаас Баланс ба Орлогын тайланг Excel-тэй адил "sheet" болгож уншина.

Сангийн сайдын 2017 оны 361 дүгээр тушаалын маягтаар (МХБ-д ирүүлдэг стандарт PDF) бэлтгэсэн тайлан дээр
зориулагдсан: мөр бүр дугаартай ("1.1.3 Дансны авлага  1,234.00  2,345.00"), сүүлийн хоёр нь Эхний/Эцсийн үлдэгдэл.
Үр дүн нь `read_sheets`-ийн Excel-ийнхтэй ижил бүтэцтэй тул `parse.extract_statement` өөрчлөлтгүй ажиллана.

Скан хийсэн (зөвхөн зурагтай) PDF-г `ocr.py` (tesseract) уншина; боломжгүй бол `ScannedPdfError` шиднэ.
"""
from __future__ import annotations

import re
from typing import Any, Optional

BS_TITLE = re.compile(r"^Санхүү(?:гийн)?\s+байдлын\s+тайлан", re.I)
IS_TITLE = re.compile(r"^(?:Орлогын\s+дэлгэрэнгүй\s+тайлан|Дэлгэрэнгүй\s+орлогын\s+тайлан|Ашиг,?\s*алдагдлын\s+тайлан)", re.I)
END_TITLE = re.compile(r"^(?:Өмчийн\s+өөрчлөлтийн\s+тайлан|Мөнгөн\s+гүйлгээний\s+тайлан)", re.I)
CODE_ROW = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)?$")
# Дүн: "1,234.00" (аравтын цэгтэй), эсвэл бүхэл тоо ("30,153,766", "380,000" — зарим компани аравтын орон бичдэггүй).
# Нэг оронтой жижиг бүхэл тоо (мөрийн дугаар) дүн биш гэж үзнэ.
NUMBER = re.compile(r"^-?(?:\d[\d,]*\.\d+|\d{1,3}(?:,\d{3})+|\d{4,})$")
SKIP_LINE = re.compile(r"^(?:Үзүүлэлт\b|Хэвлэсэн\s+огноо|/?төгрөгөөр/?|үлдэгдэл\s*/?)", re.I)
TOTAL_CHECK_LABELS = {"актив", "пассив", "зөрүү"}             # балансын доорх шалгах мөрүүд
MIN_TEXT_CHARS = 200

PERIOD_LINE = re.compile(r"(\d{4})\s*оны\s*(.+?)\s*тайлан", re.I)   # "2022 оны4 улирлын тайлан" гэх мэт зайгүй бичлэг ч таарна


class ScannedPdfError(ValueError):
    """PDF-д текст давхарга байхгүй (скан хийсэн зураг) — OCR хэрэгтэй."""


# ----------------------------------------------------------------------------- мөр угсрах
def _split_numbers(line: str) -> tuple[str, list[float]]:
    """Мөрийн төгсгөлийн (сүүлийн 2 хүртэл) тоог салгана. '- 61,720,984.07' -> -61720984.07."""
    tokens = line.split()
    nums: list[float] = []
    while tokens and len(nums) < 2 and NUMBER.match(tokens[-1]):
        val = float(tokens.pop().replace(",", ""))
        if tokens and tokens[-1] == "-":
            tokens.pop()
            val = -val
        nums.insert(0, val)
    return " ".join(tokens), nums


def rows_from_lines(lines: list[str]) -> list[list[Any]]:
    """Текстийн мөрүүдийг ["", дугаар, нэр, эхний, эцсийн] мөр болгон угсарна.

    PDF-д урт нэр хэд хэдэн мөрөнд хуваагддаг бөгөөд тоо нь дунд мөрөнд гарч болно:
        2.1.1.13 Богино хугацаат өр      -> дугаар, нэрийн эхлэл
        14,954.00 17,078.00              -> тоо (өмнөх мөрийнх)
        төлбөрийн дүн                    -> жижиг үсгээр эхэлсэн = нэрийн үргэлжлэл
    Дугааргүй, нэргүй "0.00 0.00" мөр (дугаар нь хасагдсан мөр) тусдаа хоосон мөр болно.
    """
    rows: list[dict] = []
    started = False
    for raw in lines:
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if PERIOD_LINE.search(line):
            continue                                              # "2025 оны жилийн эцсийн тайлан" (хуудас бүрийн гарчиг)
        text, nums = _split_numbers(line)
        code_m = CODE_ROW.match(text) if text else None
        if not started:
            if code_m and code_m.group(2) and re.match(r"[^\W\d_]", code_m.group(2)):
                started = True                                    # хүснэгтийн эхний мөр ("1. ХӨРӨНГӨ")
            else:
                continue                                          # гарчиг, толгой, нэгжийн мөр
        if SKIP_LINE.match(line):
            continue
        cur = rows[-1] if rows else None
        if not text:                                              # зөвхөн тоо
            if cur is not None and not cur["nums"]:
                cur["nums"] = nums
            else:
                rows.append({"code": "", "label": "", "nums": nums})
        elif code_m:
            if cur is not None and cur["code"] == code_m.group(1) and cur["nums"] == nums:
                continue                                          # хуудасны зааг дээр давхарласан мөр
            rows.append({"code": code_m.group(1), "label": (code_m.group(2) or "").strip(), "nums": nums})
        elif cur is not None and text[0].islower():               # нэрийн үргэлжлэл
            if not cur["label"].endswith(text):                   # хуудасны зааг дээр мөрийн төгсгөл давхарладаг
                cur["label"] = f"{cur['label']} {text}".strip()
            if nums and not cur["nums"]:
                cur["nums"] = nums
        else:                                                     # дугааргүй мөр ("Тайлант үеийн  0.00  8,685.00")
            rows.append({"code": "", "label": text, "nums": nums})

    out: list[list[Any]] = []
    for r in rows:
        if r["label"].strip().lower() in TOTAL_CHECK_LABELS:
            continue
        n = r["nums"]
        first, last = (n[0], n[1]) if len(n) == 2 else (None, n[0] if n else None)
        out.append(["", r["code"], r["label"], first, last])
    return out


# ----------------------------------------------------------------------------- хугацаа, нэгж
def _period_end_text(title_line: str) -> Optional[str]:
    """'2025 оны жилийн эцсийн тайлан' -> 'YYYY.MM.DD-YYYY.MM.DD' (таниж чадахгүй бол None)."""
    m = PERIOD_LINE.search(title_line)
    if not m:
        return None
    year, what = int(m.group(1)), m.group(2)
    if re.search(r"хагас\s*жил", what, re.I):
        start, end = "01.01", "06.30"
    elif re.search(r"жилийн", what, re.I):
        start, end = "01.01", "12.31"
    elif re.search(r"(?:^|\s)4\s*(?:-р\s*)?улир|дөрөв", what, re.I):
        start, end = "01.01", "12.31"
    elif re.search(r"(?:^|\s)2\s*(?:-р\s*)?улир", what, re.I):
        start, end = "01.01", "06.30"
    elif re.search(r"(?:\b1\b|\bI\b|нэгдүгээр|нэг дүгээр)", what, re.I):
        start, end = "01.01", "03.31"
    elif re.search(r"(?:\b3\b|\bIII\b|гуравдугаар|гурав дугаар|9\s*сар)", what, re.I):
        start, end = "01.01", "09.30"
    else:
        return None                                               # (Q2 нь "хагас жил"-ээр, Q4 нь "жилийн"-ээр орно)
    return f"{year}.{start}-{year}.{end}"


def _garbled(lines: list[str]) -> bool:
    """Текст давхаргын фонт эвдэрсэн эсэх: '(cid:123)' эсвэл кирилл үсэг 20%-иас бага."""
    text = " ".join(lines)
    if text.count("(cid:") > 20:
        return True
    letters = re.findall(r"[^\W\d_]", text)
    if len(letters) < 100:
        return False
    cyr = sum(1 for ch in letters if "\u0400" <= ch <= "\u04ff")
    return cyr / len(letters) < 0.2


# ----------------------------------------------------------------------------- PDF унших
def read_pdf_lines(path) -> list[str]:
    """Хуудас бүрийн босоо (эргүүлээгүй) текстийг мөр мөрөөр. Эргүүлсэн хүснэгт (Өмчийн өөрчлөлт) орохгүй."""
    import pdfplumber

    lines: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.filter(lambda o: o.get("upright", True)).extract_text() or ""
            lines += text.splitlines()
    if sum(len(x.strip()) for x in lines) < MIN_TEXT_CHARS:
        raise ScannedPdfError("PDF-д текст давхарга алга (скан хийсэн зураг) — OCR хэрэгтэй, автоматаар задлахгүй")
    return lines


def read_pdf_sheets(path) -> dict[str, list[list[Any]]]:
    """{"СБД": баланс, "ОДТ": орлогын тайлан} — `parse.read_sheets`-ийн Excel-ийн хэлбэртэй ижил."""
    try:
        lines = read_pdf_lines(path)
    except ScannedPdfError:
        from .ocr import ocr_sheets                              # скан PDF: tesseract-ээр, нийлбэрийн шалгалттай

        return ocr_sheets(path)
    if _garbled(lines):                                           # текст давхарга байгаа ч фонт эвдэрсэн (cid / латин үсгээр орчуулагдсан)
        from .ocr import ocr_sheets

        return ocr_sheets(path)
    return sheets_from_lines(lines)


def sheets_from_lines(lines: list[str]) -> dict[str, list[list[Any]]]:
    """Текстийн мөрүүд (PDF-ээс авсан эсвэл харааны уншилтаар бичсэн) -> {"СБД", "ОДТ"}."""
    sections: dict[str, list[str]] = {}
    state: Optional[str] = None
    period_line = ""
    for line in lines:
        s = line.strip()
        if state is None or state == "СБД":
            if BS_TITLE.match(s) and "СБД" not in sections:
                state, sections["СБД"] = "СБД", []
                continue
        if IS_TITLE.match(s) and "ОДТ" not in sections:
            state, sections["ОДТ"] = "ОДТ", []
            continue
        if END_TITLE.match(s):
            state = "END" if state in ("СБД", "ОДТ") else state
            continue
        if state in ("СБД", "ОДТ"):
            if not period_line and PERIOD_LINE.search(s):
                period_line = s
            sections[state].append(s)
    unit = "/Төгрөг/" if any("төгрөгөөр" in x.lower() for x in lines[:120]) and \
        not any("мянган" in x.lower() for x in lines[:120]) else None
    header = ["", "№", "Үзүүлэлт", "Эхний үлдэгдэл", "Эцсийн үлдэгдэл"]
    end_text = _period_end_text(period_line) if period_line else None
    sheets: dict[str, list[list[Any]]] = {}
    for name, sec in sections.items():
        rows = rows_from_lines(sec)
        if not rows:
            continue
        top: list[list[Any]] = []
        if end_text:
            top.append(["", "", "Тайлант үе:", end_text])
        if unit:
            top.append(["", "", "", "", unit])
        sheets[name] = top + [header] + rows
    return sheets
