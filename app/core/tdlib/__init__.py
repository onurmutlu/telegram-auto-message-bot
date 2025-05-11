"""
Telegram Bot TDLib Entegrasyonu

Bu paket, Telegram Bot Platform'un TDLib (Telegram Database Library) entegrasyonunu içerir.
"""

# TDLib bileşenleri
from app.core.tdlib.client import TDLibClient
from app.core.tdlib.setup import setup_tdlib

# Tüm TDLib bileşenlerini dışa aktar
__all__ = [
    "TDLibClient",
    "setup_tdlib"
] 