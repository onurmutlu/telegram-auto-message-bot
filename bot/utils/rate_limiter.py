"""
# ============================================================================ #
# Dosya: rate_limiter.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/utils/rate_limiter.py
# İşlev: Hız sınırlayıcı sınıf
#
# Build: 2025-04-02
# Versiyon: v3.4.1
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

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Hız sınırlayıcı sınıf.
    Belirli bir süre içinde yapılabilecek işlem sayısını sınırlandırır.
    """
    def __init__(self, rate: int, per: int):
        """
        RateLimiter sınıfının başlatıcı metodu.
        
        Args:
            rate (int): İzin verilen maksimum işlem sayısı
            per (int): İşlemlerin yapılabileceği süre (saniye)
        """
        self.rate = rate  # maksimum işlem sayısı
        self.per = per    # saniye cinsinden süre
        self.allowance = rate  # kalan izin
        self.last_check = time.time()  # son kontrol zamanı
        self._last_warning = 0  # son uyarı zamanı
        self.warning_interval = 10  # uyarılar arası minimum süre (saniye)
        
    def is_allowed(self) -> bool:
        """
        Şu anda işlemin izin verilip verilmediğini kontrol eder.
        
        Returns:
            bool: İşlem izinli ise True, değilse False
        """
        current = time.time()
        time_passed = current - self.last_check
        self.last_check = current
        
        # Geçen süreye göre allowance'ı arttır
        self.allowance += time_passed * (self.rate / self.per)
        
        # Allowance'ı maximum rate ile sınırla
        if self.allowance > self.rate:
            self.allowance = self.rate
            
        # İşlem yapılabilir mi?
        if self.allowance < 1.0:
            # Log flood'u önle - sadece belirli aralıklarla log üret
            if current - self._last_warning > self.warning_interval:
                logger.debug(f"Hız sınırlamasına takıldı: {self.rate}/{self.per}s")
                self._last_warning = current
            return False  # İşlem yapılamaz
            
        return True  # İşlem yapılabilir
        
    def mark_used(self) -> None:
        """
        Bir işlemin kullanıldığını işaretler ve allowance'ı azaltır.
        """
        self.allowance -= 1.0
        
    def limited(self) -> bool:
        """
        İşlemin sınırlandırıldığını kontrol eder ve kullanımı işaretler.
        İkinci sınıfın yöntemini ilkine entegre eder.
        
        Returns:
            bool: İşlem sınırlandırıldıysa True, değilse False
        """
        if self.is_allowed():
            self.mark_used()
            return False  # Sınırlandırılmadı
        return True  # Sınırlandırıldı

class AdaptiveRateLimiter:
    """
    Adaptif oran sınırlayıcı - Telegram API sınırlarını aşmamak için akıllı beklemeler ekler.
    
    Sınırları otomatik ayarlayan ve hataları algılayarak kendini düzenleyen bir mekanizma.
    """
    
    def __init__(self, initial_rate=3, initial_period=60, error_backoff=1.5, max_jitter=2.0):
        """
        Args:
            initial_rate: İlk başlangıç hızı (işlem/period)
            initial_period: Periyod süresi (saniye)
            error_backoff: Hatada hız çarpanı (hız bu değerle bölünür)
            max_jitter: Maksimum rastgele bekleme eklentisi (saniye)
        """
        self.rate = initial_rate  # Her periyotta izin verilen işlem sayısı
        self.period = initial_period  # Saniye cinsinden periyod
        self.used_slots = []  # Kullanılan zaman slotlarını tut
        self.error_count = 0  # Hata sayacı
        self.last_error_time = None
        self.error_backoff = error_backoff
        self.max_jitter = max_jitter
        
        # Hata almadan geçen süre - güvenli işlem için
        self.safe_time = 0
        # Başlangıç hızı ve periyotları (sıfırlanma için)
        self.initial_rate = initial_rate
        self.initial_period = initial_period
        
        logger.debug(f"AdaptiveRateLimiter başlatıldı: {initial_rate}/{initial_period}s")
        
    def is_allowed(self):
        """Yeni bir işlemin yapılıp yapılamayacağını belirler."""
        now = datetime.now()
        
        # Süresi dolmuş slotları temizle
        self.used_slots = [time for time in self.used_slots 
                          if now - time < timedelta(seconds=self.period)]
        
        # Mevcut periyotta kullanılan slot sayısı
        used = len(self.used_slots)
        
        # Son hatadan beri belirli bir süre geçtiyse hızı kademeli artır
        if self.last_error_time:
            time_since_error = (now - self.last_error_time).total_seconds()
            if time_since_error > 3600:  # 1 saat
                self.safe_time += 1
                if self.safe_time >= 3 and self.rate < self.initial_rate:
                    # Kademeli olarak hızı artır
                    self.rate = min(self.initial_rate, self.rate + 1)
                    self.period = max(self.initial_period, self.period / 1.2)
                    logger.info(f"Hız sınırları düzeltildi: {self.rate}/{self.period:.1f}s (Güvenli çalışma süresi: {self.safe_time} saat)")
        
        # Kalan kapasite varsa izin ver
        return used < self.rate
    
    def mark_used(self):
        """Bir slot kullanıldı olarak işaretler."""
        self.used_slots.append(datetime.now())
    
    def register_error(self, error_type=None):
        """
        Bir hata kaydet ve rate limit'i düşür.
        
        Args:
            error_type: Hata tipi (opsiyonel)
        """
        now = datetime.now()
        self.error_count += 1
        self.last_error_time = now
        self.safe_time = 0  # Güvenli süreyi sıfırla
        
        # Hata tipine göre ayarlamaları yap
        if "Too many requests" in str(error_type):
            # Ciddi bir hız aşımı - daha agresif yavaşlat
            self.rate = max(1, int(self.rate / self.error_backoff))  # En az 1 işlem bırak
            self.period = min(600, self.period * 1.5)  # En fazla 10 dakika
            logger.warning(f"Too many requests hatası nedeniyle hız sınırı düşürüldü: {self.rate}/{self.period:.1f}s")
        elif "FloodWaitError" in str(error_type) or hasattr(error_type, "seconds"):
            # FloodWaitError, Telegram'ın belirttiği süre kadar bekleme gerektirir
            wait_seconds = getattr(error_type, "seconds", 30)
            self.period = max(self.period, wait_seconds * 1.1)  # Biraz daha fazla bekle
            self.rate = max(1, self.rate - 1)  # Hızı düşür
            logger.warning(f"FloodWaitError nedeniyle hız sınırı düşürüldü: {self.rate}/{self.period:.1f}s (Bekleme: {wait_seconds}s)")
        else:
            # Genel bir hata - biraz yavaşlat
            self.rate = max(1, int(self.rate * 0.8))
            self.period = min(300, self.period * 1.2)
            logger.warning(f"Genel hata nedeniyle hız ayarlandı: {self.rate}/{self.period:.1f}s")
    
    def get_wait_time(self):
        """
        Bir sonraki işlem için bekleme süresini hesaplar.
        
        Returns:
            float: Beklenecek saniye sayısı
        """
        if not self.used_slots:
            return 0
            
        now = datetime.now()
        newest_slot = max(self.used_slots)
        time_since_newest = (now - newest_slot).total_seconds()
        
        # Her işlem arasında minimum bekleme süresi
        min_interval = self.period / self.rate
        
        # Rastgele jitter ekle - daha organik davranış için
        jitter = random.uniform(0, self.max_jitter)
        
        # Beklenmesi gereken süre
        return max(0, min_interval - time_since_newest) + jitter
    
    def get_status(self):
        """
        Mevcut durumu döndürür
        
        Returns:
            dict: Sınırlayıcının durum bilgisi
        """
        now = datetime.now()
        # Süresi dolmuş slotları temizle
        self.used_slots = [time for time in self.used_slots 
                          if now - time < timedelta(seconds=self.period)]
        
        return {
            "rate": self.rate,
            "period": self.period,
            "used_slots": len(self.used_slots),
            "available_slots": self.rate - len(self.used_slots),
            "error_count": self.error_count,
            "time_since_error": (now - self.last_error_time).total_seconds() if self.last_error_time else None,
            "safe_hours": self.safe_time
        }