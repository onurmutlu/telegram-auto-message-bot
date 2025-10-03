import logging
import json
from logging.handlers import RotatingFileHandler
from typing import Optional
from pathlib import Path

from app.core.config import settings

def setup_logging(log_file=None, json_format=False):
    """
    Basit loglama sistemini yapılandırır.
    
    Args:
        log_file: Özel log dosyası yolu (varsayılan: settings.LOG_FILE veya 'bot.log')
        json_format: Log çıktısının JSON formatında olup olmayacağı (varsayılan: False)
    """
    # Root logger'ı temizle
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Log seviyesini ayarla
    level = settings.LOG_LEVEL.upper()
    numeric_level = getattr(logging, level, logging.INFO)
    root_logger.setLevel(numeric_level)
    
    # Log formatı
    if json_format:
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    'timestamp': self.formatTime(record, self.datefmt),
                    'name': record.name,
                    'level': record.levelname,
                    'message': record.getMessage(),
                }
                if record.exc_info:
                    log_data['exception'] = self.formatException(record.exc_info)
                return json.dumps(log_data)
        
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler
    if log_file is None:
        log_file = settings.LOG_FILE if hasattr(settings, 'LOG_FILE') else 'bot.log'
    
    try:
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        console_handler.setLevel(logging.WARNING)
        root_logger.warning(f"Log dosyasına yazılamıyor ({log_file}): {e}")
    
    return root_logger

def get_logger(name: str = None):
    """
    Basit bir logger döndürür.
    """
    if name is None:
        name = "telegram_bot"
    
    logger = logging.getLogger(name)
    # Eğer logger henüz yapılandırılmamışsa, varsayılan yapılandırmayı yap
    if not logger.handlers and not logger.parent.handlers:
        setup_logging()
    
    return logger

def setup_logger():
    """
    Logger sistemini başlatır.
    """
    setup_logging()
    return get_logger()

def with_log(func=None, **log_params):
    """
    Fonksiyonu loglayan dekoratör.
    """
    def decorator(f):
        from functools import wraps
        import time
        
        @wraps(f)
        def wrapper(*args, **kwargs):
            logger = get_logger(f.__module__)
            
            try:
                start_time = time.time()
                logger.info(f"Fonksiyon başlangıç: {f.__name__}")
                
                result = f(*args, **kwargs)
                
                end_time = time.time()
                duration = end_time - start_time
                
                logger.info(f"Fonksiyon tamamlandı: {f.__name__}, Süre: {duration:.2f}s")
                
                return result
                
            except Exception as e:
                logger.error(f"Fonksiyon hatası: {f.__name__}, Hata: {str(e)}")
                raise
        
        return wrapper
    
    return decorator if func is None else decorator(func)

def with_async_log(func=None, **log_params):
    """
    Async fonksiyonu loglayan dekoratör.
    """
    def decorator(f):
        from functools import wraps
        import time
        
        @wraps(f)
        async def wrapper(*args, **kwargs):
            logger = get_logger(f.__module__)
            
            try:
                start_time = time.time()
                logger.info(f"Async fonksiyon başlangıç: {f.__name__}")
                
                result = await f(*args, **kwargs)
                
                end_time = time.time()
                duration = end_time - start_time
                
                logger.info(f"Async fonksiyon tamamlandı: {f.__name__}, Süre: {duration:.2f}s")
                
                return result
                
            except Exception as e:
                logger.error(f"Async fonksiyon hatası: {f.__name__}, Hata: {str(e)}")
                raise
        
        return wrapper
    
    return decorator if func is None else decorator(func)
