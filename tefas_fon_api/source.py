"""Veri kaynağı: TEFAS (pytefas üzerinden).

Kaynağa özgü tek fonksiyon `fetch_rows`'dur. Başka bir sağlayıcıya geçerken yalnızca bu
dosya değişir; üretilen JSON şeması (SCHEMA_VERSION) aynı kalır.
"""

from __future__ import annotations

from datetime import date

KINDS = ("YAT", "EMK", "BYF")
KIND_LABEL = {"YAT": "Yatırım fonu", "EMK": "Emeklilik fonu", "BYF": "Borsa yatırım fonu"}


def fetch_rows(start: date, end: date, kinds: tuple[str, ...] = KINDS) -> list[dict]:
    """[start, end] aralığındaki fonların günlük satırları.

    pytefas TEFAS'ın dakikada 6 istek sınırını kendisi yönetir ve uzun aralıkları
    28 günlük parçalara böler; burada ek istek atılmaz.
    """
    from pytefas import Crawler  # yalnızca gerçek çekimde gerekir

    crawler = Crawler(timeout=90, max_retry=6)
    rows: list[dict] = []
    for kind in kinds:
        df = crawler.fetch(start.isoformat(), end.isoformat(), kind=kind, columns="info")
        if df.empty:
            continue
        for r in df.to_dict("records"):
            rows.append(
                {
                    "code": str(r.get("fund_code") or "").strip().upper(),
                    "name": str(r.get("fund_name") or "").strip(),
                    "kind": kind,
                    "date": str(r.get("date"))[:10],
                    "price": r.get("price"),
                    "aum": r.get("portfolio_size"),
                    "investors": r.get("investor_count"),
                }
            )
    return rows
