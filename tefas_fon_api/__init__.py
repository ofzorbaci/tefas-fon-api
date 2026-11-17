"""TEFAS fon fiyatlarını statik JSON API'ye dönüştürür."""

from .calc import returns
from .source import fetch_rows
from .pipeline import SCHEMA_VERSION, sync, write_monthly

__all__ = ["SCHEMA_VERSION", "fetch_rows", "returns", "sync", "write_monthly"]
__version__ = "0.1.0"
