"""Telegram мэдэгдэл ба ажиллуулалтын хураангуй мессеж.

TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID орчны хувьсагч өгөөгүй бол юу ч илгээхгүй (алдаа гаргахгүй).
"""
from __future__ import annotations

import logging
import os
from datetime import date

import requests

log = logging.getLogger(__name__)
LIMIT = 4000          # Telegram: нэг мессеж ≤ 4096 тэмдэгт


class WarningCollector(logging.Handler):
    """WARNING/ERROR логуудыг цуглуулж мэдэгдэлд оруулна."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record.getMessage())


def send_telegram(text: str, token: str | None = None, chat_id: str | None = None,
                  session: requests.Session | None = None) -> bool:
    """Илгээсэн бол True. Тохиргоогүй эсвэл алдаа гарвал False (хэзээ ч exception шиддэггүй)."""
    token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        log.info("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID тохируулаагүй — Telegram алгасав")
        return False
    if len(text) > LIMIT:
        text = text[:LIMIT - 1] + "…"
    try:
        resp = (session or requests).post(f"https://api.telegram.org/bot{token}/sendMessage",
                                          json={"chat_id": chat_id, "text": text,
                                                "disable_web_page_preview": True}, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        # exception-ий текстэд URL (token) орсон байдаг тул зөвхөн төрлийг нь логлоно
        log.warning("Telegram илгээж чадсангүй (%s)", type(exc).__name__)
        return False
    log.info("Telegram мэдэгдэл илгээгдлээ")
    return True


def _warnings_block(warnings: list[str], limit: int = 8) -> list[str]:
    if not warnings:
        return []
    lines = ["", f"⚠️ Анхааруулга ({len(warnings)}):"]
    lines += [f"• {w[:200]}" for w in warnings[:limit]]
    if len(warnings) > limit:
        lines.append(f"… бусад {len(warnings) - limit}")
    return lines


def format_run(day: date, summary: dict, failed: list[str], warnings: list[str] | None = None) -> str:
    """`summary`: {"added": {тикер: [үеийн нэр]}, "last": {тикер: огноо}} (pipeline.run бөглөнө)."""
    added: dict[str, list[str]] = summary.get("added", {})
    last: dict[str, date | None] = summary.get("last", {})
    total = sum(len(v) for v in added.values())
    head = f"📊 МХБ хүнс — {day}: " + (f"{total} шинэ тайлан нэмэгдлээ" if total else "шинэ тайлан алга")
    lines = [head, ""]
    for t in sorted(set(added) | set(failed)):
        if t in failed:
            lines.append(f"❌ {t}: сайтаас татаж чадсангүй")
        elif added.get(t):
            lines.append(f"🆕 {t}: + {', '.join(added[t])}")
        else:
            lines.append(f"✓ {t}: шинэчлэл алга (сүүлд {last.get(t) or '—'})")
    return "\n".join(lines + _warnings_block(warnings or []))


def format_check(day: date, result: dict[str, dict]) -> str:
    """`result`: pipeline.check_updates-ийн үр дүн."""
    n_new = sum(len(v["new"]) for v in result.values())
    lines = [f"🔍 МХБ хүнс — {day}: " + (f"{n_new} шинэ тайлан гарсан байна" if n_new else "шинэ тайлан алга"), ""]
    for t, info in result.items():
        last = info["last"] or "—"
        if info["error"]:
            lines.append(f"❌ {t}: {info['error']}")
        elif info["new"]:
            items = ", ".join(f"{label}{' (зөвхөн PDF)' if kinds == {'pdf'} else ''}"
                              for label, kinds in info["new"])
            lines.append(f"🆕 {t}: {items} (Excel-д сүүлд {last})")
        else:
            lines.append(f"✓ {t}: шинэ алга (Excel-д сүүлд {last})")
        if info.get("unknown"):
            lines.append(f"   ⚠ үе тодорхойгүй {info['unknown']} файл")
    return "\n".join(lines)
