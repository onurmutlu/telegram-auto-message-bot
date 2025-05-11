"""
Prometheus metrik toplama modülü.

Bu modül, uygulama genelinde metrikleri toplar ve Prometheus'a sunar.
"""

import time
from typing import Callable, Dict, Optional, Union, Any
from functools import wraps

from prometheus_client import (
    Counter, 
    Gauge, 
    Histogram, 
    Summary,
    CollectorRegistry,
    push_to_gateway,
    REGISTRY
)

from app.core.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)

# Metrik kayıt defteri
registry = REGISTRY

# Temel metrikler
TELEGRAM_API_REQUESTS = Counter(
    'telegram_bot_api_requests_total',
    'Telegram API istekleri sayısı',
    ['method', 'status']
)

TELEGRAM_API_ERRORS = Counter(
    'telegram_bot_api_errors_total',
    'Telegram API hataları sayısı',
    ['method', 'error_code', 'error_type']
)

TELEGRAM_API_LATENCY = Histogram(
    'telegram_bot_api_latency_seconds',
    'Telegram API yanıt süreleri',
    ['method'],
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 15.0, 30.0, 60.0)
)

SCHEDULED_MESSAGES = Counter(
    'telegram_bot_scheduled_messages_total',
    'Zamanlanmış mesajlar sayısı',
    ['status']
)

FLOOD_WAIT_EVENTS = Counter(
    'telegram_bot_flood_wait_events_total',
    'FloodWait olayları sayısı',
    ['method']
)

FLOOD_WAIT_SECONDS = Gauge(
    'telegram_bot_flood_wait_seconds',
    'FloodWait hatasında beklenen saniye',
    ['method']
)

ACTIVE_SESSIONS = Gauge(
    'telegram_bot_active_sessions',
    'Aktif Telegram oturumları sayısı'
)

ACTIVE_USERS = Gauge(
    'telegram_bot_active_users',
    'Aktif kullanıcılar sayısı'
)

ACTIVE_GROUPS = Gauge(
    'telegram_bot_active_groups',
    'Aktif gruplar sayısı'
)

MESSAGE_PROCESSING_TIME = Histogram(
    'telegram_bot_message_processing_seconds',
    'Mesaj işleme süreleri',
    ['message_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)

def push_metrics_to_gateway(job: str, url: Optional[str] = None) -> None:
    """
    Metrikleri Prometheus push gateway'e gönderir.
    
    Args:
        job: İş adı
        url: Push gateway URL'si (None ise settings'ten alınır)
    """
    if not url and hasattr(settings, "PROMETHEUS_PUSH_GATEWAY"):
        url = settings.PROMETHEUS_PUSH_GATEWAY
    
    if not url:
        logger.warning("Push gateway URL'si belirtilmemiş, metrikler gönderilmiyor")
        return
        
    try:
        push_to_gateway(url, job=job, registry=registry)
        logger.debug(f"Metrikler push gateway'e gönderildi: {url} (job: {job})")
    except Exception as e:
        logger.error(f"Prometheus push gateway hatası: {str(e)}")

def track_telegram_request(method: str):
    """
    Telegram API isteğini izleyen dekoratör.
    
    Args:
        method: Telegram API metodu
    
    Returns:
        Callable: Decore edilmiş fonksiyon
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                # Fonksiyonu çalıştır
                result = await func(*args, **kwargs)
                
                # Metrik güncelle
                TELEGRAM_API_REQUESTS.labels(method=method, status="success").inc()
                TELEGRAM_API_LATENCY.labels(method=method).observe(time.time() - start_time)
                
                return result
            except Exception as e:
                # Hata metriği
                error_type = type(e).__name__
                error_code = getattr(e, "code", 0)
                
                TELEGRAM_API_REQUESTS.labels(method=method, status="error").inc()
                TELEGRAM_API_ERRORS.labels(
                    method=method, 
                    error_code=str(error_code),
                    error_type=error_type
                ).inc()
                
                # FloodWait hatası kontrolü
                if error_type == "FloodWaitError" and hasattr(e, "seconds"):
                    seconds = getattr(e, "seconds", 0)
                    FLOOD_WAIT_EVENTS.labels(method=method).inc()
                    FLOOD_WAIT_SECONDS.labels(method=method).set(seconds)
                    
                raise
        return wrapper
    return decorator

def track_message_status(status: str):
    """
    Mesaj durumunu takip eder.
    
    Args:
        status: Mesaj durumu
    """
    SCHEDULED_MESSAGES.labels(status=status).inc()

def track_message_processing(message_type: str, process_time: float):
    """
    Mesaj işleme süresini takip eder.
    
    Args:
        message_type: Mesaj tipi
        process_time: İşleme süresi (saniye)
    """
    MESSAGE_PROCESSING_TIME.labels(message_type=message_type).observe(process_time)

def update_session_counts(active_count: int):
    """
    Aktif oturum sayısını günceller.
    
    Args:
        active_count: Aktif oturum sayısı
    """
    ACTIVE_SESSIONS.set(active_count)

def update_user_counts(active_count: int):
    """
    Aktif kullanıcı sayısını günceller.
    
    Args:
        active_count: Aktif kullanıcı sayısı
    """
    ACTIVE_USERS.set(active_count)
    
def update_group_counts(active_count: int):
    """
    Aktif grup sayısını günceller.
    
    Args:
        active_count: Aktif grup sayısı
    """
    ACTIVE_GROUPS.set(active_count) 