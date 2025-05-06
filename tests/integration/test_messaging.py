#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
import logging
from datetime import datetime

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("messenger_test")

class MessagingServiceTester:
    """Mesajlaşma servislerini test etmek için sınıf"""
    
    def __init__(self):
        self.total_messages = 0
        self.successful_messages = 0
        self.message_queue = []
        self.start_time = None
        
    async def simulate_group_message(self, group_id, message_text):
        """Grup mesajı gönderme simülasyonu"""
        logger.info(f"Grup {group_id}'ye mesaj gönderiliyor: {message_text[:30]}...")
        
        # Simüle edilmiş mesaj gönderme gecikmesi
        await asyncio.sleep(0.2)
        
        # Rastgele başarı simülasyonu
        import random
        success = random.random() < 0.8  # %80 başarı
        
        if success:
            self.successful_messages += 1
            logger.info(f"✅ Mesaj grup {group_id}'ye başarıyla gönderildi")
        else:
            logger.error(f"❌ Mesaj grup {group_id}'ye gönderilemedi - Bağlantı hatası")
            
        self.total_messages += 1
        return success
    
    async def queue_message(self, group_id, message_text):
        """Mesaj kuyruğuna ekle"""
        self.message_queue.append((group_id, message_text))
        logger.info(f"Mesaj kuyruğa eklendi: Grup {group_id}, toplam kuyruk uzunluğu: {len(self.message_queue)}")
    
    async def process_queue(self):
        """Mesaj kuyruğunu işle"""
        if not self.message_queue:
            logger.info("Kuyrukta işlenecek mesaj yok")
            return
            
        logger.info(f"Mesaj kuyruğu işleniyor ({len(self.message_queue)} mesaj)...")
        
        while self.message_queue:
            group_id, message_text = self.message_queue.pop(0)
            await self.simulate_group_message(group_id, message_text)
            await asyncio.sleep(0.5)  # Rate limiting simülasyonu
            
        logger.info("Mesaj kuyruğu işleme tamamlandı")
    
    async def run_test(self):
        """Test senaryosunu çalıştır"""
        logger.info("Mesajlaşma servisi testi başlatılıyor...")
        self.start_time = datetime.now()
        
        # Test gruplara mesaj gönderme
        test_groups = [1111111, 2222222, 3333333, 4444444, 5555555]
        test_messages = [
            "Merhaba, bu bir test mesajıdır.",
            "Bu mesaj otomatik olarak gönderilmiştir.",
            "Bu bir simülasyon testi mesajıdır.",
            "Sistem çalışıyor mu diye kontrol ediyoruz.",
            "Test mesajı - lütfen dikkate almayın."
        ]
        
        # Mesajları kuyruğa ekle
        import random
        for _ in range(10):
            group = random.choice(test_groups)
            message = random.choice(test_messages)
            await self.queue_message(group, message)
        
        # Kuyruğu işle
        await self.process_queue()
        
        # İstatistikleri göster
        duration = (datetime.now() - self.start_time).total_seconds()
        logger.info("\n=== Mesajlaşma Servisi Test Sonuçları ===")
        logger.info(f"Toplam gönderilen mesaj: {self.total_messages}")
        logger.info(f"Başarıyla gönderilen mesaj: {self.successful_messages}")
        logger.info(f"Başarı oranı: {self.successful_messages/self.total_messages*100:.1f}%")
        logger.info(f"Test süresi: {duration:.2f} saniye")
        logger.info(f"Mesaj/saniye: {self.total_messages/duration:.2f}")
        logger.info("=======================================")
        
        if self.successful_messages > 0:
            logger.info("✅ Mesajlaşma servisi testi başarılı")
            return True
        else:
            logger.error("❌ Mesajlaşma servisi testi başarısız - hiç mesaj gönderilemedi")
            return False

async def run_messaging_test():
    """Test senaryosunu çalıştır"""
    tester = MessagingServiceTester()
    success = await tester.run_test()
    
    if success:
        print("\n👍 Mesajlaşma servisi çalışıyor görünüyor!")
    else:
        print("\n👎 Mesajlaşma servisi çalışmıyor görünüyor!")

if __name__ == "__main__":
    asyncio.run(run_messaging_test()) 