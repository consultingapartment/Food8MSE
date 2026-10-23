"""Командын мөр: `python -m mse_analysis`."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .config import TICKERS, Assumptions
from .engine import compute
from .prices import parse_trade_history, write_csv
from .workbook import build

log = logging.getLogger("mse_analysis")


def _ub_today() -> date:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).date()


def import_trades(txt: Path, inputs: Path) -> list[str]:
    """МХБ-ээс хуулсан арилжааны түүхийн текстийг `inputs/prices/<ТИКЕР>.csv` болгоно (өмнөх файлтай нэгтгэнэ)."""
    from .inputs import load_market
    from .prices import read_csv
    market = load_market(inputs / "market.csv")
    refs = {t: m.price for t, m in market.items() if m.price}
    parsed = parse_trade_history(txt.read_text("utf-8", errors="replace"), refs)
    done = []
    for t, bars in parsed.items():
        if t not in TICKERS:
            log.warning("%s: жагсаалтад байхгүй тикер — алгасав", t)
            continue
        path = inputs / "prices" / f"{t}.csv"
        old = read_csv(path) if path.exists() else []
        by_day = {b.day: b for b in old}
        by_day.update({b.day: b for b in bars})
        write_csv(path, [by_day[d] for d in sorted(by_day)])
        done.append(f"{t}: {len(by_day)} өдөр (сүүлийн {max(by_day)})")
    return done


def _alert(args, text: str) -> None:
    if args.notify:
        from mse_financials.notify import send_telegram
        send_telegram(text)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mse_analysis", description="МХБ-ийн хүнсний 8 компанийн шинжилгээ -> Excel")
    p.add_argument("--reports", type=Path, default=Path("reports/FOOD mse.xlsx"), help="нэгтгэсэн санхүүгийн тайлан")
    p.add_argument("--inputs", type=Path, default=Path("inputs"), help="market.csv, ownership.csv, prices/, assumptions.json")
    p.add_argument("--out", type=Path, default=Path("reports/FOOD analysis.xlsx"))
    p.add_argument("--tickers", nargs="+", metavar="TICKER", help="зөвхөн сонгосон тикерүүд")
    p.add_argument("--date", type=date.fromisoformat, default=None, help="өнөөдрийн огноо (YYYY-MM-DD), анхдагч: Улаанбаатарын өнөөдөр")
    p.add_argument("--import-trades", type=Path, metavar="TXT", help="МХБ-ээс хуулсан арилжааны түүхийн текстийг inputs/prices руу оруулна")
    p.add_argument("--fetch-prices", action="store_true",
                   help="open.mse.mn-аас хаалтын ханшийн түүхийг татаж inputs/-д бичээд шинжилнэ")
    p.add_argument("--charts", type=Path, nargs="?", const=Path("reports/charts"), default=Path("reports/charts"), metavar="DIR",
                   help="Харьцуулсан зураг, инфографикийн хавтас (анхдагч: reports/charts)")
    p.add_argument("--no-charts", action="store_true", help="Зураг, инфографик үүсгэхгүй")
    p.add_argument("--notify", action="store_true",
                   help="Хураангуй, зураг, Excel-ийг Telegram-д илгээнэ (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID хэрэгтэй)")
    p.add_argument("--no-technical", action="store_true", help="техник шинжилгээг алгасна")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    if args.fetch_prices:
        from . import live
        today = args.date or _ub_today()
        try:
            history = live.fetch(args.inputs / "_raw", today)
        except Exception as e:                                   # сүлжээ, сайтын өөрчлөлт
            log.error("Ханш татаж чадсангүй: %s", e)
            _alert(args, f"❌ МХБ хүнс — {today}: ханш татаж чадсангүй ({type(e).__name__})")
            return 1
        if not history and len(live.STALE) == len(live.SECURITY_IDS):          # бүх хуудас өмнөх өдрийн ханштай
            log.info("%s: арилжаа болоогүй (баяр, амралт) — ханш, шинжилгээ шинэчлэхгүй", today)
            return 0
        if not history:
            log.error("Ханшийн мөр олдсонгүй — татсан хуудсыг %s-д хадгалсан, шалгана уу", args.inputs / "_raw")
            _alert(args, f"❌ МХБ хүнс — {today}: ханшийн мөр олдсонгүй (сайтын бүтэц өөрчлөгдсөн байж магадгүй), файл өөрчлөгдөөгүй")
            return 1
        for line in live.apply(history, args.inputs):
            log.info("ханш: %s", line)
        missing = sorted(set(TICKERS) - set(history))
        if missing:
            log.warning("Ханш олдоогүй тикер: %s (market.csv-д хуучин ханш хэвээр)", ", ".join(missing))
    if args.import_trades:
        for line in import_trades(args.import_trades, args.inputs):
            log.info("ханш: %s", line)
    if not args.reports.exists():
        log.error("%s олдсонгүй — эхлээд `python -m mse_financials` ажиллуулна", args.reports)
        return 1
    a = Assumptions.load(args.inputs / "assumptions.json")
    tickers = [t.upper() for t in args.tickers] if args.tickers else None
    bad = [t for t in tickers or [] if t not in TICKERS]
    if bad:
        log.error("Үл мэдэгдэх тикер: %s", ", ".join(bad))
        return 1
    res = compute(args.reports, args.inputs, args.date or _ub_today(), a, tickers=tickers, with_technical=not args.no_technical)
    if not res.tickers:
        log.error("Шинжилгээ хийх компани алга")
        return 1
    for w in res.warnings:
        log.warning(w)
    pngs: list[Path] = []
    if not args.no_charts:
        from . import charts
        pngs = charts.build(res, args.charts)
        log.info("Зураг, инфографик: %d файл (%s)", len(pngs), args.charts)
    build(res, args.out, pngs)                                   # зургууд Excel-ийн «Инфографик» хуудсанд орно
    log.info("Бичигдлээ: %s (%d компани)", args.out, len(res.tickers))
    if args.notify:
        from .notify import notify
        notify(res, pngs, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
