"""Скан PDF-ийг харааны загвараар (Anthropic API) унших нөөц арга.

tesseract скан тайланг тогтмол буруу уншдаг (цифр алдах, хасах тэмдэг нэмэх, мөр алгасах) тул түүнд амжилтгүй болсон
тохиолдолд л ашиглана. `ANTHROPIC_API_KEY` орчны хувьсагч байхгүй бол юу ч хийхгүй (None).
Загварын уншсан тоо нь tesseract-тай ЯГ адил нийлбэрийн шалгалтаар (`ocr.build_sheets`) баталгаажихгүй л бол хүлээж авахгүй.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

import requests

log = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_PAGES = 12

PROMPT = """Энэ бол Монголын компанийн санхүүгийн тайлангийн скан. Дараах хоёр хүснэгтийг ЯГ байгаагаар нь уншаарай:
1) «САНХҮҮ БАЙДЛЫН ТАЙЛАН» (баланс) — мөрийн дугаар (1, 1.1, 1.1.1 ... 1.3, 2.1.1.1 ... 2.4) бүрээр.
2) «ОРЛОГЫН ДЭЛГЭРЭНГҮЙ ТАЙЛАН» — мөрийн дугаар 1..25 (23.1, 23.2, 23.3 орно).
Хоёр тоон багана бий: эхний нь өмнөх үе, хоёр дахь нь тайлант үе. Тоог зөвхөн цифрээр, таслалгүй, аравтын цэгтэй, сөрөг бол
хасах тэмдэгтэй бич. Харагдахгүй, хоосон мөрийг 0 гэж бич. Таамаглаж болохгүй, тоог өөрчилж болохгүй.
ЗӨВХӨН энэ JSON-ыг буцаа (өөр текст үгүй):
{"balance":[{"code":"1.1.1","values":[өмнөх,тайлант]}, ...],"income":[{"code":"1","values":[өмнөх,тайлант]}, ...]}"""


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _page_images(path: Path, dpi: int = 150) -> list[str]:
    import pdfplumber
    out = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages[:MAX_PAGES]:
            buf = io.BytesIO()
            page.to_image(resolution=dpi).original.convert("RGB").save(buf, "PNG", optimize=True)
            out.append(base64.b64encode(buf.getvalue()).decode())
    return out


def _json_from(text: str) -> dict[str, Any]:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("JSON олдсонгүй")
    return json.loads(m.group(0))


def read_records(path: Path, session: Optional[requests.Session] = None, model: Optional[str] = None
                 ) -> Optional[list[tuple[str, list[float]]]]:
    """[(мөрийн дугаар, [өмнөх, тайлант])]: баланс, дараа нь ОДТ. Түлхүүр/хариу байхгүй бол None."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    content: list[dict] = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b}}
                           for b in _page_images(Path(path))]
    content.append({"type": "text", "text": PROMPT})
    body = {"model": model or os.environ.get("MSE_VISION_MODEL", DEFAULT_MODEL), "max_tokens": 8000,
            "messages": [{"role": "user", "content": content}]}
    try:
        resp = (session or requests).post(API_URL, json=body, timeout=300, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        resp.raise_for_status()
        text = "".join(b.get("text", "") for b in resp.json().get("content", []) if b.get("type") == "text")
        data = _json_from(text)
        recs = [(str(r["code"]).strip(), [float(x) for x in r["values"]])
                for part in ("balance", "income") for r in data.get(part, [])]
    except Exception as exc:                       # түлхүүр лог руу алдаагаар гоорохгүй
        log.warning("%s: харааны уншилт амжилтгүй (%s)", Path(path).name, type(exc).__name__)
        return None
    return recs
