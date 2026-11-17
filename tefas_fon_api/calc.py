"""Saf yardımcılar: sayı temizleme, tarih kaydırma, getiri hesabı, JSON okuma/yazma."""

from __future__ import annotations

import json
import math
import time
from datetime import date
from pathlib import Path


def num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Boşluksuz, Türkçe karakterler olduğu gibi; statik sunucular zaten gzip'ler.
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def retry(action, attempts: int = 6, wait: float = 2.0):
    """Windows yolu kısa süre kilitlediğinde (PermissionError) işlemi yeniden dener."""
    for i in range(attempts):
        try:
            return action()
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(wait)


def price_at_or_before(prices: list[list], target: str) -> float | None:
    """prices: [["YYYY-MM-DD", fiyat], ...] eskiden yeniye. target gününde ya da öncesindeki son fiyat."""
    lo, hi, found = 0, len(prices) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if prices[mid][0] <= target:
            found = prices[mid][1]
            lo = mid + 1
        else:
            hi = mid - 1
    return found


def shift_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 - months, 12)
    year, month = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return date(year, month, 28)


def returns(prices: list[list]) -> dict:
    """1 ay, 3 ay, 6 ay, yılbaşından beri ve 1 yıl getirisi (oran, ör. 0.042 = %4,2)."""
    if not prices:
        return {}
    last_date = date.fromisoformat(prices[-1][0])
    last = prices[-1][1]
    first_date = prices[0][0]
    targets = {
        "m1": shift_months(last_date, 1),
        "m3": shift_months(last_date, 3),
        "m6": shift_months(last_date, 6),
        # Yılbaşından beri: önceki yılın son kapanışına göre.
        "ytd": date(last_date.year - 1, 12, 31),
        "y1": shift_months(last_date, 12),
    }
    out = {}
    for key, t in targets.items():
        iso = t.isoformat()
        base = price_at_or_before(prices, iso) if iso >= first_date else None
        out[key] = round(last / base - 1, 5) if base and base > 0 else None
    return out
