"""TEFAS fon verisini statik JSON dosyalarına senkronlar.

Üretilen dosyalar (<out>/funds/ altında):

    latest.json          tüm fonların son fiyatı, büyüklüğü, yatırımcı sayısı ve getirileri
    history/<KOD>.json   her fonun günlük fiyat geçmişi
    daily/<YYYY-MM>.json o ayın her işlem gününde tüm fonların fiyatı
    meta.json            güncelleme zamanı, fon başına son fiyat tarihi, kaynak, şema

Hata olursa <out> içindeki eski dosyalara dokunulmaz: yeni dosyalar önce geçici klasöre
yazılır, doğrulanır, sonra tek hamlede yerine konur.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .calc import num, read_json, retry, returns, shift_months, write_json
from .source import KIND_LABEL, KINDS, fetch_rows

SCHEMA_VERSION = 1
SOURCE = "TEFAS"
HISTORY_YEARS = 5  # TEFAS 5 yıldan eski başlangıcı reddeder.
MIN_FUNDS = 500  # İlk yüklemede bundan az fon gelirse yanıt bozuk sayılır (TEFAS'ta ~2.500 fon var).


def write_monthly(funds_dir: Path, months: set[str] | None = None) -> int:
    """daily/<YYYY-MM>.json dosyalarını history/ klasöründen üretir; `months` None ise hepsini.

    Biçim: {"dates": [...], "prices": {"AAK": [3.1, null, ...]}}, her tarih için bir fiyat
    (o gün fiyat yoksa null). Bir ayın tüm fonları tek dosyada olduğu için istemci hangi fona
    baktığını sunucuya söylemeden alım günü fiyatını bulabilir.
    """
    by_month: dict[str, dict[str, dict[str, float]]] = {}
    for path in (funds_dir / "history").glob("*.json"):
        hist = read_json(path) or {}
        code = hist.get("code") or path.stem
        for d, p in hist.get("prices", []):
            m = d[:7]
            if months is None or m in months:
                by_month.setdefault(m, {}).setdefault(code, {})[d] = p
    daily = funds_dir / "daily"
    daily.mkdir(parents=True, exist_ok=True)
    for m, funds in by_month.items():
        dates = sorted({d for prices in funds.values() for d in prices})
        write_json(
            daily / f"{m}.json",
            {
                "schema": SCHEMA_VERSION,
                "source": SOURCE,
                "month": m,
                "dates": dates,
                "prices": {code: [prices.get(d) for d in dates] for code, prices in sorted(funds.items())},
            },
        )
    return len(by_month)


def _fund_summary(code: str, newest: dict, ordered: list[tuple[str, float]]) -> dict:
    aum, investors = num(newest["aum"]), num(newest["investors"])
    return {
        "code": code,
        "name": newest["name"],
        "kind": newest["kind"],
        "price": round(num(newest["price"]), 6),
        "date": newest["date"],
        "aum": round(aum) if aum is not None else None,
        "investors": int(investors) if investors is not None else None,
        "returns": returns([[d, p] for d, p in ordered]),
    }


def _fetch_with_checkpoint(fetch, start: date, today: date, checkpoint: Path, label: str) -> list[dict]:
    # Biten bir indirme dosyalar yerine konana kadar saklanır; son adımda bir hata olursa
    # (ör. Windows klasörü kilitlerse) uzun çekim baştan yapılmaz. Çıktı klasörüne değil,
    # geçici klasöre yazılır ki yayınlanan veriyle birlikte commit edilmesin.
    cached = read_json(checkpoint)
    if cached is not None:
        print(f"Önceki çekim kullanılıyor: {checkpoint.name}")
        return cached
    print(f"Çekiliyor: {start} - {today} ({label})")
    fetched = fetch(start, today)
    checkpoint.write_text(json.dumps(fetched, ensure_ascii=False, default=str), encoding="utf-8")
    return fetched


def _swap_in(out: Path, staging_funds: Path, now: str) -> None:
    funds_dir = out / "funds"
    backup = None
    if funds_dir.exists():
        backup = out / f".funds-old-{now[:19].replace(':', '')}"
        retry(lambda: funds_dir.rename(backup))
    try:
        retry(lambda: staging_funds.rename(funds_dir))
    except OSError:
        # Windows yeni klasörü kilitli tutabilir (antivirüs, dizinleyici). Kopyala; dosyalar
        # hazır ve doğrulanmış, yalnızca değişim tek adımda olmuyor.
        shutil.copytree(staging_funds, funds_dir)
    if backup:
        shutil.rmtree(backup, ignore_errors=True)


def sync(out: Path, mode: str, today: date, fetch=fetch_rows, checkpoint_dir: Path | None = None) -> dict:
    """Yeni dosyaları geçici klasörde hazırlar, doğrular ve <out>/funds yerine koyar.

    mode "main": son tarihten sonraki günleri çeker. "topup": son günü de yeniden çeker
    (geç gelen fiyatlar ve eksik fonlar için).
    """
    funds_dir = out / "funds"
    meta = read_json(funds_dir / "meta.json") or {}
    last_date = meta.get("lastDate")

    if not last_date:
        start = shift_months(today, 12 * HISTORY_YEARS) + timedelta(days=1)
        first_load = True
    else:
        last = date.fromisoformat(last_date)
        start = last if mode == "topup" else last + timedelta(days=1)
        first_load = False

    if start > today:
        print("Yeni gün yok; değişiklik yapılmadı.")
        return {"changed": False}

    checkpoint = (checkpoint_dir or Path(tempfile.gettempdir())) / f"tefas-fon-api-{start}-{today}.json"
    fetched = _fetch_with_checkpoint(fetch, start, today, checkpoint, "ilk yükleme" if first_load else mode)
    rows = [r for r in fetched if r["code"] and num(r["price"]) and num(r["price"]) > 0]
    if not rows:
        print("Kaynakta bu aralık için fiyat yok (hafta sonu/tatil olabilir); değişiklik yapılmadı.")
        return {"changed": False}

    by_code: dict[str, list[dict]] = {}
    for r in rows:
        by_code.setdefault(r["code"], []).append(r)
    if first_load and len(by_code) < MIN_FUNDS:
        raise RuntimeError(f"İlk yüklemede yalnızca {len(by_code)} fon geldi; yanıt eksik görünüyor.")

    staging = Path(tempfile.mkdtemp(prefix="funds-", dir=out if out.exists() else None))
    try:
        if funds_dir.exists():
            shutil.copytree(funds_dir, staging / "funds")
        history_dir = staging / "funds" / "history"
        history_dir.mkdir(parents=True, exist_ok=True)

        info = {f["code"]: f for f in (read_json(staging / "funds" / "latest.json") or {}).get("funds", [])}

        for code, fund_rows in by_code.items():
            path = history_dir / f"{code}.json"
            prices = {d: p for d, p in (read_json(path) or {}).get("prices", [])}
            for r in fund_rows:
                prices[r["date"]] = round(num(r["price"]), 6)
            ordered = sorted(prices.items())
            newest = max(fund_rows, key=lambda r: r["date"])
            write_json(
                path,
                {"schema": SCHEMA_VERSION, "source": SOURCE, "code": code, "name": newest["name"], "kind": newest["kind"], "prices": [[d, p] for d, p in ordered]},
            )
            prev = info.get(code, {})
            if not prev.get("date") or newest["date"] >= prev["date"]:
                info[code] = _fund_summary(code, newest, ordered)

        daily_dir = staging / "funds" / "daily"
        months = None if first_load or not daily_dir.exists() else {r["date"][:7] for r in rows}
        write_monthly(staging / "funds", months)

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        funds = sorted(info.values(), key=lambda f: f["code"])
        latest_date = max(f["date"] for f in funds)
        write_json(staging / "funds" / "latest.json", {"schema": SCHEMA_VERSION, "source": SOURCE, "updatedAt": now, "funds": funds})
        write_json(
            staging / "funds" / "meta.json",
            {
                "schema": SCHEMA_VERSION,
                "source": SOURCE,
                "updatedAt": now,
                "lastDate": latest_date,
                "kinds": {k: KIND_LABEL[k] for k in KINDS},
                "fundCount": len(funds),
                "priceDates": {f["code"]: f["date"] for f in funds},
            },
        )

        check = read_json(staging / "funds" / "latest.json")
        if not check or len(check["funds"]) < (MIN_FUNDS if first_load else 1):
            raise RuntimeError("latest.json doğrulanamadı")
        if not read_json(staging / "funds" / "meta.json"):
            raise RuntimeError("meta.json doğrulanamadı")

        _swap_in(out, staging / "funds", now)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    checkpoint.unlink(missing_ok=True)

    print(f"Tamam: {len(by_code)} fonda yeni fiyat, toplam {len(funds)} fon, son fiyat tarihi {latest_date}")
    return {"changed": True, "funds": len(funds), "lastDate": latest_date}
