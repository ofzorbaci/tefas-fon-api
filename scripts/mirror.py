"""Yedek kaynak: aynı şemadaki başka bir funds/ klasörü daha yeniyse onu kopyalar.

GitHub'ın sunucuları TEFAS'a her zaman erişemiyor (bağlantı yanıtsız kapanıyor). Bu durumda
aynı betikle başka bir yerde (ör. ParaLens'in fund-data dalı) üretilmiş veri kullanılır.

    python scripts/mirror.py --src <yedek>/funds --dst data/funds
    python scripts/mirror.py --dst data/funds --check-age 5   # 5 günden eskiyse çıkış 1

Çıkış kodu: 0 kopyalandı ya da gerek yok, 1 veri bayat (yalnızca --check-age ile).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def last_date(funds: Path) -> str | None:
    try:
        meta = json.loads((funds / "meta.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return meta.get("lastDate") if meta.get("schema") == 1 else None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--src", type=Path)
    p.add_argument("--dst", type=Path, required=True)
    p.add_argument("--check-age", type=int, help="son fiyat bu kadar günden eskiyse çıkış 1")
    a = p.parse_args()

    if a.src:
        src, dst = last_date(a.src), last_date(a.dst)
        print(f"yedek: {src}, mevcut: {dst}")
        if src and (not dst or src > dst):
            if a.dst.exists():
                shutil.rmtree(a.dst)
            shutil.copytree(a.src, a.dst)
            print(f"Yedekten alındı: son fiyat tarihi {src}")
        else:
            print("Yedek daha yeni değil; dokunulmadı.")

    if a.check_age is not None:
        d = last_date(a.dst)
        today = datetime.now(timezone(timedelta(hours=3))).date()
        if not d or (today - date.fromisoformat(d)).days > a.check_age:
            print(f"::error::Fon verisi bayat: son fiyat tarihi {d}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
