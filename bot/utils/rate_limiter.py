"""
# ============================================================================ #
# Dosya: rate_limiter.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/utils/rate_limiter.py
# İşlev: Hız sınırlayıcı sınıf
#
# Build: 2025-04-05
# Versiyon: v3.5.0
# ============================================================================ #
#
# Bu modül, belirli bir süre içinde yapılabilecek işlem sayısını sınırlandırmak için
# bir RateLimiter sınıfı sağlar. Örneğin, her dakika en fazla 1 mesaj gönderimini sınırlamak için kullanılabilir.
#
# ============================================================================ #
"""
import time
import logging
from datetime import datetime, timedelta
import random

# Tam implementasyonu ayrı dosyada bulunan AdaptiveRateLimiter'ı buradan import et
from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Hız sınırlayıcı sınıf. Belirli bir zaman aralığında belirli sayıda işleme izin verir.
    """
    
    def __init__(self, max_requests=5, time_window=60):
        """Rate limiter başlatır
        
        Args:
            max_requests: Zaman aralığında izin verilen maksimum istek sayısı
            time_window: Zaman aralığı (saniye)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.request_timestamps = []
    
    def is_allowed(self):
        """
        Yeni bir istek yapılmasına izin verilip verilmediğini kontrol eder
        
        Returns:
            bool: İstek yapılabilir ise True, aksi halde False
        """
        current_time = time.time()
        
        # Zaman aşımına uğramış istekleri temizle
        self.request_timestamps = [ts for ts in self.request_timestamps 
                                   if current_time - ts <= self.time_window]
        
        # İzin verilen maksimum istek sayısından daha az istek yapıldıysa True döndür
        return len(self.request_timestamps) < self.max_requests
    
    def mark_used(self):
        """
        Yeni bir istek yapıldığını işaretler
        """
        self.request_timestamps.append(time.time())
        
    def get_wait_time(self):
        """Ne kadar beklemek gerektiğini hesaplar
        
        Returns:
            float: Beklenecek süre (saniye)
        """
        if self.is_allowed():
            return 0
            
        current_time = time.time()
        oldest_timestamp = min(self.request_timestamps)
        
        return max(0, self.time_window - (current_time - oldest_timestamp))

# Not: AdaptiveRateLimiter sınıfı artık adaptive_rate_limiter.py dosyasından import ediliyor

# AdaptiveRateLimiter sınıfına eklenecek (yaklaşık 40-80 satır arasında)
def increase_rate(self):
    """
    Rate limit oranını artırır - başarılı gönderimlerden sonra çağrılır
    """
    try:
        self.current_rate += 1
        self.current_rate = min(self.current_rate, self.max_rate)
        self.logger.debug(f"Rate limit artırıldı: {self.current_rate}/{self.max_rate}")
    except Exception as e:
        self.logger.error(f"Rate limit artırma hatası: {str(e)}")