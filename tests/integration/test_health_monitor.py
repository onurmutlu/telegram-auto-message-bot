#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import random
from datetime import datetime

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("health_monitor_test")

class ServiceHealthMonitor:
    """Servis sağlık izleme simülatörü"""
    
    def __init__(self):
        self.services = {
            "database": {"status": "up", "latency": 12, "errors": 0, "last_check": None},
            "message_service": {"status": "up", "latency": 45, "errors": 0, "last_check": None},
            "user_service": {"status": "up", "latency": 28, "errors": 0, "last_check": None},
            "group_service": {"status": "up", "latency": 37, "errors": 0, "last_check": None},
            "api_gateway": {"status": "up", "latency": 56, "errors": 0, "last_check": None},
            "file_service": {"status": "up", "latency": 78, "errors": 0, "last_check": None},
        }
        self.start_time = datetime.now()
        self.check_count = 0
        self.alerts = []
        
    async def check_service(self, service_name):
        """Bir servisin durumunu kontrol eder"""
        # Simüle edilmiş kontrol gecikmesi
        await asyncio.sleep(0.1)
        
        # Servis bilgilerini al
        service = self.services[service_name]
        
        # Rastgele durum ve gecikme simülasyonu
        r = random.random()
        if r < 0.05:  # %5 hata olasılığı
            service["status"] = "down"
            service["errors"] += 1
            service["latency"] = 500 + random.randint(0, 200)
            logger.error(f"❌ {service_name.upper()} - DURUM: KAPALI - Gecikme: {service['latency']}ms")
            self.alerts.append(f"UYARI: {service_name} servisi yanıt vermiyor - {datetime.now().strftime('%H:%M:%S')}")
        elif r < 0.15:  # %10 yavaş yanıt olasılığı
            service["status"] = "degraded"
            service["latency"] = 200 + random.randint(0, 150)
            logger.warning(f"⚠️ {service_name.upper()} - DURUM: YAVAŞ - Gecikme: {service['latency']}ms")
            if service["latency"] > 300:
                self.alerts.append(f"UYARI: {service_name} servisi yavaş çalışıyor - {datetime.now().strftime('%H:%M:%S')}")
        else:  # %85 normal çalışma
            service["status"] = "up"
            service["latency"] = random.randint(5, 100)
            logger.info(f"✅ {service_name.upper()} - DURUM: ÇALIŞIYOR - Gecikme: {service['latency']}ms")
        
        # Son kontrol zamanını güncelle
        service["last_check"] = datetime.now()
        return service
    
    async def check_all_services(self):
        """Tüm servislerin durumunu kontrol eder"""
        logger.info("\n=== Servis Sağlık Kontrolü Başlatılıyor ===")
        self.check_count += 1
        
        tasks = []
        for service_name in self.services:
            tasks.append(self.check_service(service_name))
            
        results = await asyncio.gather(*tasks)
        logger.info(f"=== Servis Kontrolleri Tamamlandı ({self.check_count}. kontrol) ===")
        
        # Genel sistem durumunu değerlendir
        down_services = [s for s, info in self.services.items() if info["status"] == "down"]
        degraded_services = [s for s, info in self.services.items() if info["status"] == "degraded"]
        
        if down_services:
            logger.error(f"❌ GENEL SİSTEM DURUMU: SORUNLU - {len(down_services)} servis çalışmıyor")
            for s in down_services:
                logger.error(f"  - {s}: ÇALIŞMIYOR")
        elif degraded_services:
            logger.warning(f"⚠️ GENEL SİSTEM DURUMU: DÜŞÜK PERFORMANS - {len(degraded_services)} servis yavaş")
            for s in degraded_services:
                logger.warning(f"  - {s}: YAVAŞ ({self.services[s]['latency']}ms)")
        else:
            logger.info("✅ GENEL SİSTEM DURUMU: NORMAL - Tüm servisler çalışıyor")
    
    async def generate_system_metrics(self):
        """Sistem metriklerini üretir"""
        cpu_usage = random.randint(20, 95)
        memory_usage = random.randint(30, 85)
        disk_usage = random.randint(40, 75)
        active_connections = random.randint(10, 150)
        
        logger.info("\n=== Sistem Metrikleri ===")
        logger.info(f"CPU Kullanımı: {cpu_usage}%")
        logger.info(f"Bellek Kullanımı: {memory_usage}%")
        logger.info(f"Disk Kullanımı: {disk_usage}%")
        logger.info(f"Aktif Bağlantılar: {active_connections}")
        
        if cpu_usage > 80:
            self.alerts.append(f"UYARI: Yüksek CPU kullanımı ({cpu_usage}%) - {datetime.now().strftime('%H:%M:%S')}")
        if memory_usage > 80:
            self.alerts.append(f"UYARI: Yüksek bellek kullanımı ({memory_usage}%) - {datetime.now().strftime('%H:%M:%S')}")
        
        return {
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "disk_usage": disk_usage,
            "active_connections": active_connections
        }
    
    async def show_alerts(self):
        """Uyarıları gösterir"""
        if not self.alerts:
            logger.info("\n=== Aktif Uyarı Bulunmuyor ===")
            return
            
        logger.warning("\n=== Aktif Uyarılar ===")
        for i, alert in enumerate(self.alerts[-5:], 1):
            logger.warning(f"{i}. {alert}")
    
    async def run_simulation(self, cycles=3):
        """Simülasyonu çalıştırır"""
        logger.info(f"Sağlık izleme simülasyonu başlatılıyor ({cycles} döngü)...")
        
        for i in range(cycles):
            # Tüm servisleri kontrol et
            await self.check_all_services()
            
            # Sistem metriklerini üret
            await self.generate_system_metrics()
            
            # Uyarıları göster
            await self.show_alerts()
            
            if i < cycles - 1:
                logger.info(f"Sonraki kontrol için bekleniyor ({i+1}/{cycles})...")
                await asyncio.sleep(2)
        
        # Sonuçları göster
        total_duration = (datetime.now() - self.start_time).total_seconds()
        
        logger.info("\n=== Sağlık İzleme Simülasyonu Sonuçları ===")
        logger.info(f"Toplam çalışma süresi: {total_duration:.2f} saniye")
        logger.info(f"Kontrol sayısı: {self.check_count}")
        logger.info(f"Uyarı sayısı: {len(self.alerts)}")
        
        service_status = {
            "up": len([s for s, info in self.services.items() if info["status"] == "up"]),
            "degraded": len([s for s, info in self.services.items() if info["status"] == "degraded"]),
            "down": len([s for s, info in self.services.items() if info["status"] == "down"])
        }
        
        logger.info(f"Servis durumları: {service_status['up']} ÇALIŞIYOR, {service_status['degraded']} YAVAŞ, {service_status['down']} ÇALIŞMIYOR")
        
        if service_status["down"] > 0:
            logger.error("❌ Sistem durumu: SORUNLU - Müdahale gerekiyor!")
            return False
        elif service_status["degraded"] > 0:
            logger.warning("⚠️ Sistem durumu: DÜŞÜK PERFORMANS - İzlemeye devam edilmeli")
            return True
        else:
            logger.info("✅ Sistem durumu: NORMAL - Tüm servisler çalışıyor")
            return True

async def main():
    """Ana fonksiyon"""
    monitor = ServiceHealthMonitor()
    success = await monitor.run_simulation(cycles=3)
    
    if success:
        print("\n👍 Sağlık izleme servisi çalışıyor!")
    else:
        print("\n👎 Sağlık izleme servisinde sorunlar tespit edildi!")

if __name__ == "__main__":
    asyncio.run(main()) 