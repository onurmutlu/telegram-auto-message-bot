"""
Rate limiting işlemleri için yardımcı sınıf
"""
import asyncio
import random
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Mesaj gönderimi için rate limiting yönetimi"""
    
    def __init__(self):
        """Rate limiting parametrelerini başlat"""
        # Rate limiting parametreleri
        self.pm_delays = {
            'min_delay': 45,      # Min bekleme süresi (saniye)
            'max_delay': 120,     # Max bekleme süresi (saniye)
            'burst_limit': 5,     # Art arda gönderim limiti
            'burst_delay': 300,   # Burst limit sonrası bekleme (5 dk)
            'hourly_limit': 15    # Saatlik maksimum mesaj
        }
        
        # Rate limiting için durum takibi
        self.state = {
            'burst_count': 0,
            'hourly_count': 0,
            'hour_start': datetime.now(),
            'last_pm_time': None,
            'consecutive_errors': 0
        }
    
    def increment_burst(self):
        """Art arda gönderim sayacını artırır"""
        self.state['burst_count'] += 1
        
    def increment_hourly(self):
        """Saatlik gönderim sayacını artırır"""
        self.state['hourly_count'] += 1
        
    def reset_burst(self):
        """Art arda gönderim sayacını sıfırlar"""
        self.state['burst_count'] = 0
        
    def is_hourly_limit_reached(self):
        """Saatlik limitin dolup dolmadığını kontrol eder"""
        # Saatlik limit sıfırlama
        current_time = datetime.now()
        if (current_time - self.state['hour_start']).total_seconds() >= 3600:
            self.state['hourly_count'] = 0
            self.state['hour_start'] = current_time
            return False
            
        return self.state['hourly_count'] >= self.pm_delays['hourly_limit']
    
    def is_burst_limit_reached(self):
        """Art arda gönderim limitinin dolup dolmadığını kontrol eder"""
        return self.state['burst_count'] >= self.pm_delays['burst_limit']
    
    async def apply_smart_delay(self):
        """Akıllı gecikme uygular"""
        try:
            current_time = datetime.now()
            
            # Saatlik limit sıfırlama
            if (current_time - self.state['hour_start']).total_seconds() >= 3600:
                self.state['hourly_count'] = 0
                self.state['hour_start'] = current_time
                logger.debug("Saatlik sayaç sıfırlandı")
            
            # Ardışık hata oranına göre gecikme artışı
            if self.state['consecutive_errors'] > 0:
                # Her ardışık hata için gecikmeyi iki kat artır (exp backoff)
                error_delay = min(300, 5 * (2 ** self.state['consecutive_errors']))
                logger.info(f"⚠️ {self.state['consecutive_errors']} ardışık hata nedeniyle {error_delay} saniye ek bekleme")
                await asyncio.sleep(error_delay)
            
            # Burst kontrolü
            if self.state['burst_count'] >= self.pm_delays['burst_limit']:
                logger.info(f"⏳ Art arda gönderim limiti aşıldı: {self.pm_delays['burst_delay']} saniye bekleniyor")
                await asyncio.sleep(self.pm_delays['burst_delay'])
                self.state['burst_count'] = 0
            
            # Son mesajdan bu yana geçen süre
            if self.state['last_pm_time']:
                time_since_last = (current_time - self.state['last_pm_time']).total_seconds()
                min_delay = self.pm_delays['min_delay']
                
                # Henüz minimum süre geçmemişse bekle
                if time_since_last < min_delay:
                    wait_time = min_delay - time_since_last
                    await asyncio.sleep(wait_time)
            
            # Doğal görünmesi için rastgele gecikme
            human_delay = random.randint(3, 8)
            await asyncio.sleep(human_delay)
            
            # Son pm zamanını güncelle
            self.state['last_pm_time'] = datetime.now()
            
            return True
            
        except Exception as e:
            logger.error(f"Akıllı gecikme hesaplama hatası: {str(e)}")
            await asyncio.sleep(60)
            return False