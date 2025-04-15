"""
# ============================================================================ #
# Dosya: adaptive_rate_limiter.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/utils/adaptive_rate_limiter.py
# İşlev: Akıllı ve adaptif hız sınırlayıcı sınıf
#
# Build: 2025-04-05
# Versiyon: v3.5.0
# ============================================================================ #
#
# Bu modül, Telegram API sınırlarına otomatik uyum sağlayan ve hata durumlarına
# göre kendini ayarlayan gelişmiş bir hız sınırlayıcı sınıfı sağlar.
#
# ============================================================================ #
"""

import time
import random
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Daha yumuşak varsayılan değerler
DEFAULT_RATE = 5.0  # dakikada 5 işlem (1.5 yerine)
DEFAULT_ERROR_BACKOFF = 1.2  # hata oranı çarpanı (1.5 yerine)
DEFAULT_MAX_JITTER = 1.0  # maksimum rastgele gecikme (2.0 yerine)

class AdaptiveRateLimiter:
    """Adaptive rate limiting implementation with exponential backoff."""
    
    def __init__(self, 
                initial_rate=10.0,  # Dakikada 10 işlem (daha yüksek)
                period=60,         # 60 saniye
                error_backoff=1.5, # Daha düşük backoff
                max_jitter=1.0):   # Daha düşük jitter
        """Initialize rate limiter with given parameters."""
        self.initial_rate = initial_rate
        self.current_rate = initial_rate
        self.period = period
        self.error_backoff = error_backoff
        self.max_jitter = max_jitter
        self.last_used = 0
        self.errors = 0
        self.success_count = 0
        self.last_requests = []  # Son isteklerin zamanını tutmak için
        self.error_count = 0     # Hata sayısını tutmak için
        
        logger.debug(f"AdaptiveRateLimiter başlatıldı: {self.current_rate}/{self.period}s, "
                    f"error_backoff={self.error_backoff}, max_jitter={self.max_jitter}")
    
    def mark_used(self):
        """
        Başarılı bir istek işlemini kaydeder ve rate'i yavaşça artırır.
        """
        self.last_used = time.time()
        self.success_count += 1
        self.last_requests.append(datetime.now())
        
        # Son istekleri temizle (son 1 saatlik isteği tut)
        one_hour_ago = datetime.now() - timedelta(hours=1)
        self.last_requests = [req for req in self.last_requests if req > one_hour_ago]
        
        # Her 10 başarılı işlemden sonra rate'i %10 artır
        if self.success_count % 10 == 0 and self.success_count > 0:
            self.current_rate *= 1.1
            
            # Maximum 3x initial rate'e kadar artırabilir
            if self.current_rate > self.initial_rate * 3:
                self.current_rate = self.initial_rate * 3
                
            logger.debug(f"Rate limiter hız artışı: {self.current_rate:.2f}/dk")

    def register_error(self, error=None):
        """
        Bir hata oluştuğunda rate limiter'ı günceller ve bekleme süresini artırır.
        
        Args:
            error: Oluşan hata (opsiyonel)
        """
        self.errors += 1
        self.error_count += 1  # Toplam hata sayısını artır
        self.current_rate /= self.error_backoff
        
        # Minimum 0.5 işlem/dk'ya düşür
        if self.current_rate < 0.5:
            self.current_rate = 0.5
        
        # Loglama
        if error:
            error_type = type(error).__name__
            logger.warning(f"Rate limiter hata kaydedildi ({error_type}): yeni oran = {self.current_rate:.2f}/dk")
        else:
            logger.warning(f"Rate limiter hata kaydedildi: yeni oran = {self.current_rate:.2f}/dk")
    
    def can_execute(self):
        """
        İşlem yapılıp yapılamayacağını kontrol eder.
        
        Returns:
            bool: İşlem yapılabilirse True
        """
        # İlk kullanım ya da çok uzun süre geçmişse her zaman izin ver
        now = time.time()
        if self.last_used == 0 or (now - self.last_used) > self.period * 5:
            self.last_used = now
            return True
            
        # İki işlem arasında geçmesi gereken minimum süre (saniye)
        delay = self.period / self.current_rate
        
        # Son kullanımdan bu yana geçen süre
        elapsed = now - self.last_used
        
        # Süre yeterliyse işlem yapılabilir
        if elapsed >= delay:
            self.last_used = now
            return True
        
        # Hata durumunda bile riskli yaklaşım
        if elapsed >= delay * 0.8:  # %80'ine ulaşıldıysa da izin ver
            logger.warning(f"Agresif rate limiter: {elapsed:.1f}s geçti (minimum {delay:.1f}s)")
            self.last_used = now
            return True
            
        return False

    def get_wait_time(self):
        """
        İşlem yapabilmek için beklenecek süreyi saniye cinsinden hesaplar.
        
        Returns:
            float: Beklenecek süre (saniye)
        """
        try:
            # İlk kullanım ya da çok uzun süre geçmişse bekleme yok
            now = time.time()
            if self.last_used == 0 or (now - self.last_used) > self.period * 5:
                return 0
                
            # İki işlem arasında geçmesi gereken minimum süre (saniye)
            delay = self.period / self.current_rate
            
            # Son kullanımdan bu yana geçen süre
            elapsed = now - self.last_used
            
            # Eğer yeterince zaman geçtiyse bekleme yapma
            if elapsed >= delay:
                return 0
                
            # Aksi halde beklenecek süreyi döndür
            return max(0, delay - elapsed)
            
        except Exception as e:
            logger.error(f"Bekleme süresi hesaplama hatası: {str(e)}")
            return 1.0  # Hata durumunda 1 saniye bekle