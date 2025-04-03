# Yeni bir dosya oluşturun

import time
import random
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class AdaptiveRateLimiter:
    """
    Telegram API sınırlarını otomatik algılayan ve uyum sağlayan akıllı hız sınırlayıcı.
    Hatalardan öğrenir ve otomatik olarak beklemeleri ayarlar.
    """
    
    def __init__(self, initial_rate=5, initial_period=60, cooldown_factor=2):
        """
        Args:
            initial_rate: Başlangıç hızı (işlem/dönem)
            initial_period: Başlangıç periyodu (saniye)
            cooldown_factor: Hata durumunda bekleme çarpanı 
        """
        self.max_rate = initial_rate  # Maksimum izin verilen işlem sayısı
        self.current_rate = initial_rate  # Mevcut hız
        self.period = initial_period  # Dönem süresi (saniye)
        self.cooldown_factor = cooldown_factor  # Hata sonrası yavaşlama faktörü
        self.last_requests = []  # Son isteklerin zamanı
        self.error_count = 0  # Hata sayacı
        self.last_error_time = None  # Son hata zamanı
        self.cooldown_until = datetime.now()  # Soğuma süresi
        self.backoff_time = 10  # Başlangıç bekleme süresi (saniye)
    
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
        jitter = random.uniform(1, 3)
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