"""
Rate Limiter Modülü

Basit rate limiting uygulaması için modül.
"""

import time
import logging
import asyncio
from typing import Dict, Any, Optional, Callable
from functools import wraps

from app.core.logger import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """
    İstek sıklığını sınırlamak için kullanılan sınıf.
    """
    
    def __init__(self, max_calls: int, time_frame: float):
        """
        Rate limiter başlatma.
        
        Args:
            max_calls: Zaman diliminde izin verilen maksimum çağrı sayısı
            time_frame: Zaman dilimi (saniye)
        """
        self.max_calls = max_calls
        self.time_frame = time_frame
        self.calls = []
        
    def _cleanup(self):
        """
        Eski çağrıları temizler.
        """
        cutoff = time.time() - self.time_frame
        while self.calls and self.calls[0] <= cutoff:
            self.calls.pop(0)
            
    def can_call(self) -> bool:
        """
        Yeni bir çağrı yapılıp yapılamayacağını kontrol eder.
        
        Returns:
            bool: Çağrı yapılabilirse True
        """
        self._cleanup()
        return len(self.calls) < self.max_calls
        
    def add_call(self):
        """
        Yeni bir çağrı ekler.
        """
        self.calls.append(time.time())
        
    def time_to_wait(self) -> float:
        """
        Yeni çağrı yapabilmek için beklenecek süreyi hesaplar.
        
        Returns:
            float: Beklenecek süre (saniye)
        """
        self._cleanup()
        
        if len(self.calls) < self.max_calls:
            return 0
            
        return self.calls[0] + self.time_frame - time.time()
        
    async def wait_for_call(self) -> bool:
        """
        Yeni çağrı yapabilmek için gerekirse bekler.
        
        Returns:
            bool: Çağrı izni verildiyse True
        """
        wait_time = self.time_to_wait()
        
        if wait_time > 0:
            logger.debug(f"Rate limit aşıldı, {wait_time:.2f} saniye bekleniyor")
            await asyncio.sleep(wait_time)
            
        self.add_call()
        return True
        
def rate_limited(limiter: RateLimiter):
    """
    Rate limit uygulayan dekoratör.
    
    Args:
        limiter: Kullanılacak rate limiter
        
    Returns:
        Callable: Decore edilmiş fonksiyon
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await limiter.wait_for_call()
            return await func(*args, **kwargs)
        return wrapper
    return decorator 