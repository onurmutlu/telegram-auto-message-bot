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

class AdaptiveRateLimiter:
    """
    Adaptif hız sınırlama sınıfı.
    Rate limit hatalarına göre otomatik uyarlanan bir hız sınırlayıcı.
    """
    
    def __init__(self, initial_rate=3, period=60, error_backoff=1.5, max_jitter=2.0):
        """
        Args:
            initial_rate: Başlangıç hızı (mesaj/period)
            period: Periyot (saniye)
            error_backoff: Hata durumunda hız azaltma çarpanı
            max_jitter: Maksimum rastgele sapma
        """
        self.initial_rate = initial_rate  # Düşürüldü
        self.current_rate = initial_rate * 0.5  # İlk başta 1.5 mesaj/dakika ile başla
        self.period = period
        self.error_backoff = error_backoff
        self.max_jitter = max_jitter
        
        # Kullanım takibi
        self.usage_times = []
        self.last_wait = 0
        self.consecutive_errors = 0
        self.consecutive_success = 0
        
        logger.debug(
            f"AdaptiveRateLimiter başlatıldı: {self.current_rate}/{self.period}s, "
            f"error_backoff={error_backoff}, max_jitter={max_jitter}"
        )
    
    def is_allowed(self):
        """Yeni bir istek göndermenin uygun olup olmadığını kontrol eder."""
        now = datetime.now()
        
        # Soğuma dönemindeyse beklet
        if now < self.cooldown_until:
            return False
            
        # Zaman aşımına uğramış istekleri temizle
        self.last_requests = [t for t in self.last_requests if (now - t).total_seconds() < self.period]
        
        # İzin verilen sayının altındaysa izin ver
        return len(self.last_requests) < self.current_rate
    
    def mark_used(self):
        """Yapılan bir isteği kaydet."""
        self.last_requests.append(datetime.now())
    
    def register_error(self, error_type=None):
        """
        Bir hata oluştuğunu bildir ve hızı düşür.
        
        Args:
            error_type: Hata tipi (isteğe bağlı)
        """
        now = datetime.now()
        self.error_count += 1
        self.last_error_time = now
        
        # Hata tipine göre hareket et
        if "Too many requests" in str(error_type):
            # Ciddi bir Telegram API hatası - hızı çok daha fazla düşür
            self.current_rate = max(1, int(self.current_rate * 0.5))  # Hızı yarıya düşür
            
            # Üstel geri çekilme (exponential backoff)
            self.backoff_time = min(300, self.backoff_time * self.cooldown_factor)  # En fazla 5 dakika
            self.cooldown_until = now + timedelta(seconds=self.backoff_time)
            
            logger.warning(f"⚠️ 'Too many requests' hatası nedeniyle {self.backoff_time}s bekleniyor")
            logger.warning(f"⚠️ Hız {self.current_rate} istek/dönem'e düşürüldü")
        else:
            # Diğer hatalar için daha hafif bir yavaşlama
            self.current_rate = max(1, int(self.current_rate * 0.8))
            self.backoff_time = min(60, self.backoff_time * 1.5)
            self.cooldown_until = now + timedelta(seconds=self.backoff_time)
    
    def get_wait_time(self):
        """Bir sonraki istek için beklenmesi gereken süreyi hesaplar (saniye)."""
        now = datetime.now()
        
        # Soğuma dönemindeyse kalan süreyi döndür
        if now < self.cooldown_until:
            return (self.cooldown_until - now).total_seconds()
            
        # Zaman aşımına uğramış istekleri temizle
        self.last_requests = [t for t in self.last_requests if (now - t).total_seconds() < self.period]
        
        if not self.last_requests:
            return 0
        
        # İstekler arası minimum süreyi hesapla
        time_per_request = self.period / self.current_rate
        
        # İsteğin yapılabileceği en erken zamanı hesapla
        last_request = max(self.last_requests)
        earliest_next_time = last_request + timedelta(seconds=time_per_request)
        
        # Şimdiden en erken zamana kalan süre
        wait_seconds = max(0, (earliest_next_time - now).total_seconds())
        
        # Biraz rastgelelik ekle (1-2 saniye)
        jitter = random.uniform(1, self.max_jitter)
        total_wait = wait_seconds + jitter
        
        return total_wait
    
    def is_in_cooldown(self):
        """Soğuma döneminde olup olmadığını kontrol eder."""
        return datetime.now() < self.cooldown_until
    
    def get_status(self):
        """Mevcut durumu döndürür."""
        now = datetime.now()
        return {
            "current_rate": self.current_rate,
            "max_rate": self.max_rate,
            "period": self.period,
            "used_slots": len(self.last_requests),
            "error_count": self.error_count,
            "cooldown_until": self.cooldown_until.strftime("%H:%M:%S") if self.is_in_cooldown() else "Aktif",
            "backoff_time": self.backoff_time,
            "wait_time": self.get_wait_time()
        }

    def reset(self):
        """Rate limiter'ı başlangıç değerlerine sıfırlar."""
        # Kullanım geçmişini sil ama hata sayacını koru
        self.last_requests = []
        self.cooldown_until = datetime.now()
        # Hızı yavaşça tekrar artır
        self.current_rate = max(1, min(self.max_rate, self.current_rate + 1))

    def increase_rate(self, factor=1.2):
        """
        Hız limitini artırır
        
        Args:
            factor: Artış faktörü (1.2 = %20 artış)
        """
        new_rate = self.current_rate * factor
        max_rate = self.initial_rate * 3  # En fazla başlangıç değerinin 3 katı
        self.current_rate = min(new_rate, max_rate)
        logger.debug(f"Rate limiter rate artırıldı: {self.current_rate:.2f} mesaj/dakika")
        return self.current_rate