#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MessageService'i test etmek için betik.
Bu betik, MessageService'in düzgün çalışıp çalışmadığını kontrol eder.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
import dotenv

# .env dosyasından değerleri yükle
dotenv.load_dotenv()

# Loglamayı yapılandır
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('service_test.log')
    ]
)

logger = logging.getLogger(__name__)

class ServiceTester:
    """
    MessageService test sınıfı
    """
    def __init__(self):
        self.client = None
        self.message_service = None
        self.test_group_id = None
        self.stop_event = asyncio.Event()
        
    async def setup(self):
        """Test için gerekli kurulumları yapar"""
        from app.core.unified.client import get_client
        from app.services.message_service import MessageService
        
        # Telegram client bağlantısını kur
        self.client = await get_client()
        if not self.client:
            logger.error("Telegram client bağlantısı başarısız!")
            return False
            
        # Client bağlantı bilgilerini göster
        me = await self.client.get_me()
        logger.info(f"Telegram client bağlantısı başarılı: {me.first_name} (@{me.username})")
        
        # Mesaj servisini başlat
        self.message_service = MessageService(
            client=self.client,
            stop_event=self.stop_event
        )
        
        # Servisi başlat
        init_success = await self.message_service.initialize()
        if not init_success:
            logger.error("Mesaj servisi başlatılamadı!")
            return False
            
        start_success = await self.message_service.start()
        if not start_success:
            logger.error("Mesaj servisi başlatılamadı!")
            return False
            
        logger.info("Mesaj servisi başarıyla başlatıldı")
        
        # Test için bir grup seç
        await self.select_test_group()
        if not self.test_group_id:
            logger.error("Test için grup seçilemedi!")
            return False
            
        return True
        
    async def select_test_group(self):
        """Test için bir grup seçer"""
        try:
            # Grupları listele
            dialogs = await self.client.get_dialogs()
            groups = [d for d in dialogs if d.is_group or d.is_channel]
            
            if not groups:
                logger.error("Herhangi bir grup bulunamadı!")
                return
                
            logger.info("Mevcut gruplar:")
            for i, group in enumerate(groups[:10], 1):  # İlk 10 grubu göster
                logger.info(f"{i}. {group.name} (ID: {group.id})")
                
            # İlk grubu test için seç
            test_group = groups[0]
            self.test_group_id = test_group.id
            logger.info(f"Test için seçilen grup: {test_group.name} (ID: {self.test_group_id})")
            
        except Exception as e:
            logger.error(f"Grup seçme hatası: {e}")
            
    async def test_immediate_message(self):
        """Anlık mesaj gönderme testini yapar"""
        try:
            logger.info("Anlık mesaj gönderme testi başlatılıyor...")
            
            message_content = f"Bu bir anlık test mesajıdır. Zaman: {datetime.now().strftime('%H:%M:%S')}"
            
            result = await self.message_service.schedule_message(
                content=message_content,
                group_id=self.test_group_id
            )
            
            if result:
                logger.info(f"Anlık mesaj gönderildi: ID={result.id}")
                return True
            else:
                logger.error("Anlık mesaj gönderilemedi!")
                return False
                
        except Exception as e:
            logger.error(f"Anlık mesaj testi hatası: {e}")
            return False
            
    async def test_scheduled_message(self):
        """Zamanlanmış mesaj gönderme testini yapar"""
        try:
            logger.info("Zamanlanmış mesaj gönderme testi başlatılıyor...")
            
            # 1 dakika sonrası için zamanla
            scheduled_time = datetime.utcnow() + timedelta(minutes=1)
            message_content = f"Bu zamanlanmış bir test mesajıdır. Planlanan zaman: {scheduled_time.strftime('%H:%M:%S')}"
            
            result = await self.message_service.schedule_message(
                content=message_content,
                group_id=self.test_group_id,
                scheduled_for=scheduled_time
            )
            
            if result:
                logger.info(f"Zamanlanmış mesaj oluşturuldu: ID={result.id}, Zaman={scheduled_time}")
                return True
            else:
                logger.error("Zamanlanmış mesaj oluşturulamadı!")
                return False
                
        except Exception as e:
            logger.error(f"Zamanlanmış mesaj testi hatası: {e}")
            return False
            
    async def test_service_run(self):
        """Servis döngüsünü test eder"""
        try:
            logger.info("MessageService.run() metodu test ediliyor...")
            
            # Servisi başlat
            service_task = asyncio.create_task(self.message_service.run())
            
            # Biraz bekle
            logger.info("Servis döngüsü 10 saniye çalışacak...")
            await asyncio.sleep(10)
            
            # Servisi durdur
            self.stop_event.set()
            await service_task
            
            logger.info("Servis döngüsü testi tamamlandı")
            return True
            
        except Exception as e:
            logger.error(f"Servis döngüsü testi hatası: {e}")
            return False
            
    async def test_cancel_scheduled_message(self):
        """Zamanlanmış mesaj iptal etme testini yapar"""
        try:
            logger.info("Zamanlanmış mesaj iptal testi başlatılıyor...")
            
            # 1 saat sonrası için zamanla
            scheduled_time = datetime.utcnow() + timedelta(hours=1)
            message_content = f"Bu iptal edilecek bir test mesajıdır."
            
            result = await self.message_service.schedule_message(
                content=message_content,
                group_id=self.test_group_id,
                scheduled_for=scheduled_time
            )
            
            if not result:
                logger.error("İptal testi için mesaj oluşturulamadı!")
                return False
                
            message_id = result.id
            logger.info(f"İptal edilecek mesaj oluşturuldu: ID={message_id}")
            
            # Biraz bekle
            await asyncio.sleep(2)
            
            # Mesajı iptal et
            cancel_result = await self.message_service.cancel_scheduled_message(message_id)
            
            if cancel_result:
                logger.info(f"Mesaj başarıyla iptal edildi: ID={message_id}")
                return True
            else:
                logger.error(f"Mesaj iptal edilemedi: ID={message_id}")
                return False
                
        except Exception as e:
            logger.error(f"Mesaj iptal testi hatası: {e}")
            return False
            
    async def cleanup(self):
        """Test sonrası temizlik işlemleri"""
        try:
            logger.info("Temizlik işlemleri yapılıyor...")
            
            # Mesaj servisini durdur
            if self.message_service:
                await self.message_service.stop()
                
            # Client bağlantısını kapat
            from app.core.unified.client import disconnect_client
            await disconnect_client()
            
            logger.info("Temizlik işlemleri tamamlandı")
            
        except Exception as e:
            logger.error(f"Temizlik işlemleri sırasında hata: {e}")

async def main():
    tester = ServiceTester()
    
    try:
        # Kurulum
        setup_success = await tester.setup()
        if not setup_success:
            logger.error("Test kurulumu başarısız oldu!")
            return
            
        # Test 1: Anlık mesaj gönder
        await tester.test_immediate_message()
        
        # Test 2: Zamanlanmış mesaj oluştur
        await tester.test_scheduled_message()
        
        # Test 3: Mesaj iptal et
        await tester.test_cancel_scheduled_message()
        
        # Test 4: Servis döngüsünü çalıştır
        await tester.test_service_run()
        
        logger.info("Tüm testler tamamlandı!")
        
    except Exception as e:
        logger.error(f"Test sırasında beklenmeyen hata: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Temizlik
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 