#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import random
import time
from datetime import datetime

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("error_handling_test")

class RetryStrategy:
    """Yeniden deneme stratejileri"""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"

class CircuitBreakerState:
    """Devre kesici durumları"""
    CLOSED = "closed"  # Normal durum - istekler geçiyor
    OPEN = "open"      # Kesik durum - istekler geçmiyor
    HALF_OPEN = "half_open"  # Yarı açık - test istekleri geçiyor

class ErrorSimulator:
    """Hata simülatörü"""
    
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.retried_requests = 0
        self.circuit_breaker_state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.failure_threshold = 3
        self.recovery_time = 5.0  # saniye
        self.last_failure_time = None
        self.service_name = "test_service"
    
    async def simulate_request(self, error_rate=0.3):
        """İstek simülasyonu"""
        self.total_requests += 1
        request_id = self.total_requests
        
        logger.info(f"İstek #{request_id} başlatıldı...")
        
        # Devre kesici kontrolü
        if self.circuit_breaker_state == CircuitBreakerState.OPEN:
            # Devre kesici açık - istekleri reddet
            elapsed = time.time() - self.last_failure_time if self.last_failure_time else 0
            if elapsed < self.recovery_time:
                logger.warning(f"DEVRE KESİCİ AÇIK - İstek #{request_id} reddedildi - {self.recovery_time-elapsed:.1f} saniye kaldı")
                self.failed_requests += 1
                return False
            else:
                # Recovery time geçti, half-open durumuna geç
                logger.info(f"DEVRE KESİCİ YARI AÇILIYOR - İstek #{request_id} test istekleri için geçiyor")
                self.circuit_breaker_state = CircuitBreakerState.HALF_OPEN
        
        # İsteği işle
        try:
            # Rastgele hata simülasyonu
            if random.random() < error_rate:
                raise Exception(f"Simüle edilmiş hata: İstek #{request_id} başarısız oldu")
            
            # Başarılı işlem simülasyonu
            await asyncio.sleep(0.1)  # İşlem süresi
            logger.info(f"✅ İstek #{request_id} başarıyla tamamlandı")
            
            # Başarılı istek sayacını güncelle
            self.successful_requests += 1
            
            # Half-open durumundan closed durumuna geç
            if self.circuit_breaker_state == CircuitBreakerState.HALF_OPEN:
                logger.info(f"DEVRE KESİCİ KAPATILIYOR - Test isteği başarılı oldu")
                self.circuit_breaker_state = CircuitBreakerState.CLOSED
                self.failure_count = 0
            
            return True
            
        except Exception as e:
            # Hata zamanını kaydet
            self.last_failure_time = time.time()
            
            # Hata sayacını güncelle
            self.failure_count += 1
            self.failed_requests += 1
            
            # Hatayı kaydet
            logger.error(f"❌ {str(e)}")
            
            # Devre kesici kontrolü
            if self.circuit_breaker_state == CircuitBreakerState.HALF_OPEN:
                logger.error(f"DEVRE KESİCİ AÇILIYOR - Test isteği başarısız oldu")
                self.circuit_breaker_state = CircuitBreakerState.OPEN
            elif self.failure_count >= self.failure_threshold:
                if self.circuit_breaker_state != CircuitBreakerState.OPEN:
                    logger.error(f"DEVRE KESİCİ AÇILIYOR - Hata eşiği aşıldı ({self.failure_count}/{self.failure_threshold})")
                    self.circuit_breaker_state = CircuitBreakerState.OPEN
            
            return False
    
    async def retry_request(self, max_attempts=3, retry_strategy=RetryStrategy.EXPONENTIAL):
        """Yeniden deneme mekanizması ile istek"""
        request_id = self.total_requests + 1
        logger.info(f"Yeniden deneme mekanizması ile istek #{request_id} başlatılıyor...")
        
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            
            # İsteği gönder
            success = await self.simulate_request(error_rate=0.4)  # Daha yüksek hata oranı
            
            if success:
                if attempt > 1:
                    self.retried_requests += 1
                    logger.info(f"✅ İstek #{request_id} {attempt}. denemede başarılı oldu")
                return True
            
            # Son deneme değilse bekle
            if attempt < max_attempts:
                # Bekleme süresini hesapla
                if retry_strategy == RetryStrategy.LINEAR:
                    wait_time = attempt * 1.0  # 1s, 2s, 3s, ...
                elif retry_strategy == RetryStrategy.EXPONENTIAL:
                    wait_time = (2 ** attempt) * 0.1  # 0.2s, 0.4s, 0.8s, ...
                elif retry_strategy == RetryStrategy.FIBONACCI:
                    # Fibonacci dizisi: 1, 1, 2, 3, 5, 8, ...
                    a, b = 1, 1
                    for _ in range(attempt):
                        a, b = b, a + b
                    wait_time = a * 0.1  # 0.1s, 0.1s, 0.2s, 0.3s, ...
                else:
                    wait_time = 1.0
                
                logger.warning(f"⚠️ İstek #{request_id} başarısız oldu. {wait_time:.1f} saniye sonra yeniden deneniyor ({attempt}/{max_attempts})...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ İstek #{request_id} {max_attempts} denemeden sonra başarısız oldu!")
        
        return False
    
    async def run_tests(self):
        """Test senaryosunu çalıştır"""
        logger.info("Hata yönetimi mekanizmaları testi başlatılıyor...")
        start_time = time.time()
        
        # Normal istekler
        logger.info("\n=== Normal İstekler ===")
        for i in range(5):
            await self.simulate_request()
            await asyncio.sleep(0.1)
        
        # Retry mekanizması
        logger.info("\n=== Yeniden Deneme Testi (Linear) ===")
        for i in range(3):
            await self.retry_request(retry_strategy=RetryStrategy.LINEAR)
            await asyncio.sleep(0.5)
        
        logger.info("\n=== Yeniden Deneme Testi (Exponential) ===")
        for i in range(3):
            await self.retry_request(retry_strategy=RetryStrategy.EXPONENTIAL)
            await asyncio.sleep(0.5)
        
        # Circuit breaker testi
        logger.info("\n=== Devre Kesici Testi ===")
        self.circuit_breaker_state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        
        # Hata eşiğini aşmak için yüksek hata oranlı istekler
        for i in range(10):
            await self.simulate_request(error_rate=0.8)
            await asyncio.sleep(0.1)
            
            if self.circuit_breaker_state == CircuitBreakerState.OPEN:
                logger.info("Devre kesici AÇIK duruma geçti. Birkaç istek daha gönderiyoruz...")
                
                # Devre kesici açıkken birkaç istek daha gönder
                for j in range(3):
                    await self.simulate_request()
                    await asyncio.sleep(0.1)
                
                # Devre kesicinin kendini kapatması için bekle
                logger.info(f"Devre kesicinin kendini kapatması için {self.recovery_time} saniye bekleniyor...")
                await asyncio.sleep(self.recovery_time + 0.1)
                
                # Devre kesici yarı açık modda olmalı, testi tamamlamak için bir istek daha gönder
                logger.info("Devre kesici YARI AÇIK olmalı, test isteği gönderiliyor...")
                await self.simulate_request(error_rate=0.0)  # Başarılı istek
                break
        
        # Test sonuçları
        elapsed = time.time() - start_time
        
        logger.info("\n=== Hata Yönetimi Testleri Sonuçları ===")
        logger.info(f"Toplam çalışma süresi: {elapsed:.2f} saniye")
        logger.info(f"Toplam istek: {self.total_requests}")
        logger.info(f"Başarılı istek: {self.successful_requests}")
        logger.info(f"Başarısız istek: {self.failed_requests}")
        logger.info(f"Yeniden deneme sonrası başarılı: {self.retried_requests}")
        logger.info(f"Başarı oranı: {(self.successful_requests / self.total_requests * 100):.1f}%")
        logger.info(f"Devre kesici son durum: {self.circuit_breaker_state}")
        
        return self.circuit_breaker_state == CircuitBreakerState.CLOSED and self.successful_requests > 0

async def main():
    """Ana fonksiyon"""
    simulator = ErrorSimulator()
    success = await simulator.run_tests()
    
    if success:
        print("\n👍 Hata yönetimi mekanizmaları çalışıyor!")
    else:
        print("\n👎 Hata yönetimi mekanizmalarında sorunlar tespit edildi!")

if __name__ == "__main__":
    asyncio.run(main()) 