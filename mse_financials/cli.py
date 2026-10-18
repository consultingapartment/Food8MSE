"""Командын мөрийн интерфэйс: python -m mse_financials"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from . import __version__
from .config import COMPANIES, DEFAULT_OUTPUT, DEFAULT_REPORTS_DIR
from . import schedule
from .client import Client
from .notify import WarningCollector, format_check, format_run, send_telegram
from .pipeline import check, run, today


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mse_financials",
                                description="МХБ-ээс хүнсний компаниудын санхүүгийн тайланг татаж нэг Excel болгоно.")
    p.add_argument("--tickers", nargs="+", default=list(COMPANIES), metavar="TICKER",
                   help="Тикерүүд (анхдагч: %(default)s)")
    p.add_argument("--reports-dir", type=Path, default=Path(DEFAULT_REPORTS_DIR),
                   help="Татсан файлуудыг хадгалах хавтас (анхдагч: %(default)s)")
    p.add_argument("--out", type=Path, default=Path(DEFAULT_OUTPUT),
                   help="Гаралтын НЭГ Excel файл; байвал шинэ тайланг нэмж шинэчилнэ (анхдагч: %(default)s)")
    p.add_argument("--date", type=date.fromisoformat, default=None, metavar="YYYY-MM-DD",
                   help="Хугацаа шалгахад ашиглах огноо (анхдагч: өнөөдөр, Улаанбаатарын цаг)")
    p.add_argument("--skip-download", action="store_true",
                   help="Татахгүй, --reports-dir доторх файлуудыг л задлана")
    p.add_argument("--rebuild", action="store_true",
                   help="Байгаа Excel-ийг үл хэрэгсэж бүх тайланг шинээр нэгтгэнэ")
    p.add_argument("--no-pdf", action="store_true", help="PDF файл татахгүй")
    p.add_argument("--check", action="store_true",
                   help="Юу ч татахгүй, Excel-д бичихгүй: сайтад ямар шинэ тайлан гарсныг л жагсаана")
    p.add_argument("--notify", action="store_true",
                   help="Үр дүнг Telegram-д илгээнэ (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID орчны хувьсагч хэрэгтэй)")
    p.add_argument("--strict-ssl", action="store_true",
                   help="SSL гэрчилгээний гинж дутуу үед баталгаажуулалтгүй дахин оролдохгүй (анхдагч: mse.mn дээр оролдоно)")
    p.add_argument("--if-due", action="store_true",
                   help="Зөвхөн өнөөдөр цуглуулах өдөр (хуулийн хугацаа + 14 хоног) бол ажиллана")
    p.add_argument("--show-schedule", action="store_true", help="Цуглуулах хуваарийг харуулаад гарна")
    p.add_argument("-v", "--verbose", action="store_true", help="Дэлгэрэнгүй лог")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")
    day = args.date or today()
    if args.show_schedule:
        print(schedule.describe(day))
        return 0
    if args.if_due and not schedule.is_collection_day(day):
        nxt, dl = schedule.next_collection(day)
        print(f"Өнөөдөр ({day}) цуглуулах өдөр биш. Дараагийнх: {nxt} ({dl.name})")
        return 0
    tickers = [t.upper() for t in args.tickers]
    unknown = [t for t in tickers if t not in COMPANIES]
    if unknown:
        logging.warning("Жагсаалтад байхгүй тикер: %s (config.COMPANIES/KNOWN_IDS-д нэмнэ үү)", ", ".join(unknown))
    if args.check and args.skip_download:
        print("--check нь сайтаас шалгадаг тул --skip-download-тай хамт ажиллахгүй")
        return 2
    client = None if args.skip_download else Client(strict_ssl=args.strict_ssl)
    if args.check:
        result = check(tickers, args.out, client=client, include_pdf=not args.no_pdf)
        text = format_check(day, result)
        print(text)
        if args.notify:
            send_telegram(text)
        return 1 if any(i["error"] for i in result.values()) else 0

    collector = WarningCollector()
    logging.getLogger().addHandler(collector)
    failed: list[str] = []
    summary: dict = {}
    try:
        xlsx = run(tickers, args.reports_dir, args.out, day=day, skip_download=args.skip_download,
                   include_pdf=not args.no_pdf, client=client, rebuild=args.rebuild, failed=failed,
                   summary=summary)
    except Exception as exc:
        if args.notify:
            send_telegram(f"❌ МХБ хүнс — {day}: ажиллуулалт унав ({type(exc).__name__}: {str(exc)[:200]})")
        raise
    finally:
        logging.getLogger().removeHandler(collector)
    print(f"Бэлэн: {xlsx.resolve()}")
    if failed:
        logging.error("Сайтаас татаж чадсангүй: %s — Excel-д эдгээрийн шинэ тайлан ороогүй", ", ".join(failed))
    if args.notify:
        send_telegram(format_run(day, summary, failed, collector.records))
    return 1 if failed else 0       # 1 бол GitHub Actions-д ажил "амжилтгүй" гэж харагдана


if __name__ == "__main__":
    sys.exit(main())
