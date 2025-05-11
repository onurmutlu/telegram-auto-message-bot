import os
import sys
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from functools import wraps

import structlog
from structlog.stdlib import LoggerFactory
from structlog.processors import (
    TimeStamper, 
    JSONRenderer, 
    format_exc_info, 
    UnicodeDecoder,
    add_log_level,
    StackInfoRenderer
)
import logging.handlers
import json
from pythonjsonlogger import jsonlogger

from app.core.config import settings

# Prometheus metrikleri (varsa)
try:
    from prometheus_client import Counter, Histogram
    PROM_ENABLED = True
    
    # Temel metrikler
    LOG_ENTRIES = Counter(
        "log_entries_total", 
        "Total number of log entries", 
        ["level", "module"]
    )
    
    EXCEPTION_COUNT = Counter(
        "exceptions_total", 
        "Total number of caught exceptions", 
        ["type", "module"]
    )
    
    FUNCTION_DURATION = Histogram(
        "function_duration_seconds", 
        "Duration of function execution in seconds",
        ["function", "module"],
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
    )
except ImportError:
    PROM_ENABLED = False

# Çıktı formatları
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s (%(filename)s:%(lineno)d)"
JSON_FORMAT = "%(timestamp)s %(level)s %(name)s %(message)s"

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Özel JSON log formatı.
    """
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        log_record['level'] = record.levelname
        log_record['name'] = record.name
        
        # Ekstra alanlar ekle
        if hasattr(settings, "SERVICE_NAME"):
            log_record['service'] = settings.SERVICE_NAME
        
        if hasattr(settings, "ENV"):
            log_record['environment'] = settings.ENV
            
        # Trace ID (Open Telemetry/OpenTracing için)
        if hasattr(record, "trace_id"):
            log_record['trace_id'] = record.trace_id
            
        if hasattr(record, "span_id"):
            log_record['span_id'] = record.span_id

# Prometheus metrikleri için processor
def prometheus_processor(logger, method_name, event_dict):
    """
    Log olaylarını Prometheus metriklerine dönüştürür.
    """
    if PROM_ENABLED:
        # Log seviyesi metriklerini güncelle
        level = event_dict.get('level', 'info')
        module = logger.name or 'unknown'
        
        LOG_ENTRIES.labels(
            level=level,
            module=module
        ).inc()
        
        # Exception metriklerini güncelle
        exc_info = event_dict.get('exc_info')
        if exc_info:
            exception_type = exc_info[0].__name__ if exc_info and len(exc_info) > 0 else 'unknown'
            EXCEPTION_COUNT.labels(
                type=exception_type,
                module=module
            ).inc()
            
    return event_dict

def setup_logging(
    level: str = None,
    fmt: str = LOG_FORMAT,
    json_format: bool = False,
    log_file: Optional[str] = None,
    console: bool = True,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5,
    add_prometheus: bool = True,
    add_sentry: bool = True
) -> None:
    """
    Loglama sistemini yapılandırır.
    
    Args:
        level: Log seviyesi (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        fmt: Log formatı
        json_format: JSON formatında loglar için True
        log_file: Log dosyası yolu
        console: Konsola log çıktısı için True
        max_bytes: Tek bir log dosyasının maksimum boyutu
        backup_count: Saklanacak log dosyası sayısı
        add_prometheus: Prometheus metriklerini eklemek için True
        add_sentry: Sentry entegrasyonu için True
    """
    # Log seviyesini ayarla
    log_level = getattr(logging, level or os.getenv("LOG_LEVEL", "INFO"))
    
    # Root logger ayarları
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Önceki tüm handlers'ları temizle
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Handler'lar
    handlers = []
    
    # Konsola log
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        
        if json_format:
            formatter = CustomJsonFormatter(JSON_FORMAT)
        else:
            formatter = logging.Formatter(fmt)
            
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)
        
    # Dosyaya log
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        if json_format:
            formatter = CustomJsonFormatter(JSON_FORMAT)
        else:
            formatter = logging.Formatter(fmt)
            
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Sentry entegrasyonu
    if add_sentry and hasattr(settings, "SENTRY_DSN") and settings.SENTRY_DSN:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration
            
            sentry_logging = LoggingIntegration(
                level=log_level,
                event_level=logging.ERROR
            )
            
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                traces_sample_rate=0.1,
                environment=getattr(settings, "ENV", "production"),
                integrations=[sentry_logging]
            )
            
            print(f"Sentry entegrasyonu yapılandırıldı: {settings.SENTRY_DSN[:20]}...")
        except ImportError:
            print("Sentry SDK kurulu değil, entegrasyon atlandı.")
        except Exception as e:
            print(f"Sentry entegrasyonu hatası: {str(e)}")
    
    # Handler'ları ekle
    for handler in handlers:
        root_logger.addHandler(handler)
        
    # structlog yapılandırması
    shared_processors = [
        add_log_level,
        TimeStamper(fmt="iso", utc=True),
        StackInfoRenderer(),
        format_exc_info,
        UnicodeDecoder(),
    ]
    
    # Prometheus metrikerini ekle
    if add_prometheus and PROM_ENABLED:
        shared_processors.append(prometheus_processor)
    
    structlog.configure(
        processors=shared_processors + [JSONRenderer(sort_keys=True)],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Diğer loggerların seviyelerini ayarla
    for logger_name in ["uvicorn", "uvicorn.access", "fastapi"]:
        logging.getLogger(logger_name).setLevel(log_level)
    
def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """
    Yapılandırılmış bir logger döndürür.
    
    Args:
        name: Logger adı
        
    Returns:
        structlog.stdlib.BoundLogger: Yapılandırılmış logger
    """
    return structlog.get_logger(name)

def with_log(func: Callable = None, **log_params) -> Callable:
    """
    Fonksiyonu loglayan dekoratör.
    
    Args:
        func: Decore edilecek fonksiyon
        log_params: Log mesajına eklenecek parametreler
        
    Returns:
        Callable: Loglama eklentili fonksiyon
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            module = func.__module__ or "unknown"
            start_time = time.time()
            
            # Fonksiyon parametreleri
            params = {**log_params}
            if args:
                params["args"] = [repr(arg) for arg in args]
            if kwargs:
                params["kwargs"] = {k: repr(v) for k, v in kwargs.items()}
            
            logger.info(
                f"{func.__name__} başlatıldı",
                function=func.__name__,
                **params
            )
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                logger.info(
                    f"{func.__name__} tamamlandı",
                    function=func.__name__,
                    execution_time=f"{execution_time:.4f}s"
                )
                
                # Fonksiyon süresini Prometheus'a kaydet
                if PROM_ENABLED:
                    FUNCTION_DURATION.labels(
                        function=func.__name__,
                        module=module
                    ).observe(execution_time)
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                
                logger.exception(
                    f"{func.__name__} hatası: {str(e)}",
                    function=func.__name__,
                    error=str(e),
                    execution_time=f"{execution_time:.4f}s"
                )
                
                # Fonksiyon süresini Prometheus'a kaydet
                if PROM_ENABLED:
                    FUNCTION_DURATION.labels(
                        function=func.__name__,
                        module=module
                    ).observe(execution_time)
                
                raise
                
        return wrapper
    
    if func is None:
        return decorator
    return decorator(func)

# Async fonksiyonlar için log dekoratörü
def with_async_log(func: Callable = None, **log_params) -> Callable:
    """
    Async fonksiyonu loglayan dekoratör.
    
    Args:
        func: Decore edilecek async fonksiyon
        log_params: Log mesajına eklenecek parametreler
        
    Returns:
        Callable: Loglama eklentili async fonksiyon
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            module = func.__module__ or "unknown"
            start_time = time.time()
            
            # Fonksiyon parametreleri
            params = {**log_params}
            if args:
                params["args"] = [repr(arg) for arg in args]
            if kwargs:
                params["kwargs"] = {k: repr(v) for k, v in kwargs.items()}
            
            logger.info(
                f"{func.__name__} başlatıldı",
                function=func.__name__,
                **params
            )
            
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                logger.info(
                    f"{func.__name__} tamamlandı",
                    function=func.__name__,
                    execution_time=f"{execution_time:.4f}s"
                )
                
                # Fonksiyon süresini Prometheus'a kaydet
                if PROM_ENABLED:
                    FUNCTION_DURATION.labels(
                        function=func.__name__,
                        module=module
                    ).observe(execution_time)
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                
                logger.exception(
                    f"{func.__name__} hatası: {str(e)}",
                    function=func.__name__,
                    error=str(e),
                    execution_time=f"{execution_time:.4f}s"
                )
                
                # Fonksiyon süresini Prometheus'a kaydet
                if PROM_ENABLED:
                    FUNCTION_DURATION.labels(
                        function=func.__name__,
                        module=module
                    ).observe(execution_time)
                
                raise
                
        return wrapper
    
    if func is None:
        return decorator
    return decorator(func) 