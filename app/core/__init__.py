"""
Telegram Bot Çekirdek Bileşenleri

Bu paket, Telegram Bot Platform'un çekirdek bileşenlerini içerir.
"""

# Yapılandırma
from app.core.config import settings

# Güvenlik
from app.core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    generate_random_token
)

# Loglama
from app.core.logger import setup_logging, get_logger, with_log

# Zamanlayıcı
from app.core.scheduler import scheduler

# Metrikler
from app.core.metrics import (
    track_telegram_request,
    track_message_status,
    track_message_processing,
    update_session_counts,
    update_user_counts,
    update_group_counts,
    push_metrics_to_gateway
)

# TDLib entegrasyonu
from app.core.tdlib.client import TDLibClient
from app.core.tdlib.setup import setup_tdlib

# Tüm çekirdek bileşenleri dışa aktar
__all__ = [
    "settings",
    "create_access_token",
    "verify_password",
    "get_password_hash",
    "generate_random_token",
    "setup_logging",
    "get_logger",
    "with_log",
    "scheduler",
    "track_telegram_request",
    "track_message_status",
    "track_message_processing",
    "update_session_counts",
    "update_user_counts",
    "update_group_counts",
    "push_metrics_to_gateway",
    "TDLibClient",
    "setup_tdlib"
] 