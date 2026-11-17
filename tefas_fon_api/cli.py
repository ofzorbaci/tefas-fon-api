"""Komut satırı: tefas-fon-api --out ./site [--mode topup]."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import pipeline as sync_mod


def _utf8_console() -> None:
    # Windows konsolu (cp1254) Türkçe karakterde takılmasın.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    p = argparse.ArgumentParser(prog="tefas-fon-api", description=sync_mod.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, help="funds/ klasörünün yazılacağı yer")
    p.add_argument("--mode", choices=("main", "topup"), default="main", help="topup: son günü de yeniden çeker")
    p.add_argument("--today", help="YYYY-MM-DD (varsayılan: bugün, Türkiye saati)")
    p.add_argument("--rebuild-monthly", action="store_true", help="çekmeden, mevcut geçmişten tüm ay dosyalarını yeniden üret")
    args = p.parse_args(argv)

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.rebuild_monthly:
        print(f"{sync_mod.write_monthly(out / 'funds')} ay dosyası yazıldı.")
        return 0
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone(timedelta(hours=3))).date()
    try:
        sync_mod.sync(out, args.mode, today)
    except Exception as e:  # noqa: BLE001 — iş başarısız görünsün, eski veri yerinde kalsın
        print(f"HATA: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
