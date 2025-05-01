import pytest
import time
from datetime import datetime, timedelta
from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter

class TestAdaptiveRateLimiter:
    """AdaptiveRateLimiter sınıfı için test sınıfı."""
    
    def test_init(self):
        """Yapılandırıcının doğru çalıştığını kontrol et."""
        limiter = AdaptiveRateLimiter(
            initial_rate=5.0,
            period=60,
            error_backoff=1.5,
            max_jitter=1.0
        )
        
        assert limiter.initial_rate == 5.0
        assert limiter.current_rate == 5.0
        assert limiter.period == 60
        assert limiter.error_backoff == 1.5
        assert limiter.max_jitter == 1.0
        assert limiter.last_used == 0
        assert limiter.errors == 0
        assert limiter.success_count == 0
        assert isinstance(limiter.last_requests, list)
        assert limiter.error_count == 0
    
    def test_mark_used(self):
        """mark_used metodunun başarılı istekleri doğru kaydettiğini kontrol et."""
        limiter = AdaptiveRateLimiter(initial_rate=10.0)
        
        # İlk 9 istek sonrası oran değişmemeli
        for _ in range(9):
            limiter.mark_used()
        
        assert limiter.success_count == 9
        assert limiter.current_rate == 10.0
        assert len(limiter.last_requests) == 9
        
        # 10. istek sonrası oran %10 artmalı
        limiter.mark_used()
        assert limiter.success_count == 10
        assert limiter.current_rate == 11.0  # 10.0 * 1.1 = 11.0
        assert len(limiter.last_requests) == 10
    
    def test_register_error(self):
        """register_error metodunun hataları doğru işlediğini kontrol et."""
        limiter = AdaptiveRateLimiter(initial_rate=10.0, error_backoff=2.0)
        
        # Hata kaydetme
        limiter.register_error()
        
        assert limiter.errors == 1
        assert limiter.error_count == 1
        assert limiter.current_rate == 5.0  # 10.0 / 2.0 = 5.0
        
        # İkinci hata
        limiter.register_error()
        
        assert limiter.errors == 2
        assert limiter.error_count == 2
        assert limiter.current_rate == 2.5  # 5.0 / 2.0 = 2.5
        
        # Çok fazla hata olursa minimum değere düşmeli
        for _ in range(10):
            limiter.register_error()
            
        assert limiter.errors == 12
        assert limiter.error_count == 12
        assert limiter.current_rate == 0.5  # Minimum değer
    
    def test_can_execute(self):
        """can_execute metodunun doğru çalıştığını kontrol et."""
        limiter = AdaptiveRateLimiter(initial_rate=10.0, period=60)
        
        # İlk çağrıda her zaman True dönmeli
        assert limiter.can_execute() is True
        
        # Son kullanımdan bu yana geçen süre çok kısa ise False dönmeli
        assert limiter.can_execute() is False
        
        # Yeterli süre geçtikten sonra (6 saniye) True dönmeli
        original_time = time.time
        try:
            # time.time'ı önce kaydedelim
            time.time = lambda: limiter.last_used + 6.1  # 60 / 10 = 6 saniye minimum bekleme
            assert limiter.can_execute() is True
        finally:
            # Orijinal fonksiyonu geri yükle
            time.time = original_time
    
    def test_get_wait_time(self):
        """get_wait_time metodunun doğru süreyi hesapladığını kontrol et."""
        limiter = AdaptiveRateLimiter(initial_rate=10.0, period=60)
        
        # İlk kullanımda bekleme süresi 0 olmalı
        assert limiter.get_wait_time() == 0
        
        # Kullanım işaretleme
        limiter.mark_used()
        
        # İşlem arası süre 6 saniye olmalı (60/10)
        expected_delay = 6.0
        
        # Gerçek bekleme süresi, geçen zamana bağlı olacak
        elapsed = time.time() - limiter.last_used
        expected_wait = max(0, expected_delay - elapsed)
        
        # Küçük bir tolerans payı ile kontrol et (0.1 saniye)
        assert abs(limiter.get_wait_time() - expected_wait) < 0.1
    
    def test_get_status(self):
        """get_status metodunun doğru durum bilgilerini döndürdüğünü kontrol et."""
        limiter = AdaptiveRateLimiter(
            initial_rate=5.0,
            period=30,
            error_backoff=1.5,
            max_jitter=0.5
        )
        
        # Bazı aktiviteler gerçekleştir
        limiter.mark_used()  # 1 başarılı istek
        limiter.register_error()  # 1 hata
        
        # Durum bilgisini al
        status = limiter.get_status()
        
        # Temel kontroller
        assert status['initial_rate'] == 5.0
        assert status['period'] == 30
        assert status['error_backoff'] == 1.5
        assert status['max_jitter'] == 0.5
        assert status['errors'] == 1
        assert status['error_count'] == 1
        assert status['success_count'] == 1
        assert status['requests_last_hour'] == 1
        assert status['active'] is True
        
        # current_rate kontrolü (5.0 / 1.5 = 3.333...)
        assert abs(status['current_rate'] - 3.333) < 0.01
        
        # wait_time değeri dinamik, bu yüzden sadece tipini kontrol et
        assert isinstance(status['wait_time'], float) 