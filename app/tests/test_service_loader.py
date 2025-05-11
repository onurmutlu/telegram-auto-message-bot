#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
# ============================================================================ #
# Dosya: test_service_loader.py
# Yol: /Users/siyahkare/code/telegram-bot/test_service_loader.py
# İşlev: Telegram bot servislerini yükleme ve başlatma test betiği
# ============================================================================ #
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Çevre değişkenlerini yükle
load_dotenv()

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_db_connection():
    """Veritabanı bağlantısını test eder"""
    try:
        from app.utils.postgres_db import setup_postgres_db
        
        logger.info("PostgreSQL bağlantısı test ediliyor...")
        db = setup_postgres_db()
        
        if db and hasattr(db, 'connected') and db.connected:
            logger.info("✅ PostgreSQL bağlantısı başarılı!")
            
            # Test sorgusu
            try:
                await db.execute("SELECT 1")
                logger.info("✅ SQL sorgusu başarılı!")
            except Exception as e:
                logger.error(f"❌ SQL sorgusu hatası: {str(e)}")
                
            return db
        else:
            logger.error("❌ PostgreSQL bağlantısı başarısız!")
            return None
            
    except Exception as e:
        logger.error(f"❌ Veritabanı bağlantı hatası: {str(e)}")
        return None

class Config:
    """Test için basit yapılandırma sınıfı"""
    def __init__(self):
        self.data = {
            'api_id': os.getenv('API_ID'),
            'api_hash': os.getenv('API_HASH'),
            'bot_token': os.getenv('BOT_TOKEN'),
            'message_batch_size': int(os.getenv('MESSAGE_BATCH_SIZE', '50')),
            'message_batch_interval': int(os.getenv('MESSAGE_BATCH_INTERVAL', '30'))
        }
    
    def get(self, key, default=None):
        return self.data.get(key, default)
        
    def get_setting(self, key, default=None):
        return self.get(key, default)

class MockClient:
    """Test için mock Telegram istemcisi"""
    async def get_me(self):
        class User:
            def __init__(self):
                self.id = 12345
                self.username = "test_bot"
                self.first_name = "Test"
                self.last_name = "Bot"
        return User()

async def test_services():
    """Servisleri test et"""
    try:
        # Veritabanı bağlantısını al
        db = await test_db_connection()
        
        # Yapılandırma ve mock istemci
        config = Config()
        client = MockClient()
        
        # ServiceManager'ı import et ve oluştur
        from app.service_manager import ServiceManager
        stop_event = asyncio.Event()
        service_manager = ServiceManager(config, db, client)
        
        # Test servisleri için basit mock sınıfları
        from app.services.base_service import BaseService
        
        class MockEventService(BaseService):
            def __init__(self, client=None, config=None, db=None, stop_event=None):
                super().__init__("event", client, config, db, stop_event)
                
            async def initialize(self) -> bool:
                self.initialized = True
                return True
                
            async def start(self) -> bool:
                if not self.initialized:
                    await self.initialize()
                self._is_running = True
                self.start_time = datetime.now()
                return True
                
            async def stop(self) -> None:
                self._is_running = False
                
            async def run(self) -> None:
                while not self.stop_event.is_set() and self._is_running:
                    await asyncio.sleep(1)
        
        class MockMessageService(BaseService):
            def __init__(self, client=None, config=None, db=None, stop_event=None):
                super().__init__("message", client, config, db, stop_event)
                
            async def initialize(self) -> bool:
                self.initialized = True
                return True
                
            async def start(self) -> bool:
                if not self.initialized:
                    await self.initialize()
                self._is_running = True
                self.start_time = datetime.now()
                return True
                
            async def stop(self) -> None:
                self._is_running = False
                
            async def run(self) -> None:
                while not self.stop_event.is_set() and self._is_running:
                    await asyncio.sleep(1)
                    
        class MockGroupService(BaseService):
            def __init__(self, client=None, config=None, db=None, stop_event=None):
                super().__init__("group", client, config, db, stop_event)
                
            async def initialize(self) -> bool:
                self.initialized = True
                return True
                
            async def start(self) -> bool:
                if not self.initialized:
                    await self.initialize()
                self._is_running = True
                self.start_time = datetime.now()
                return True
                
            async def stop(self) -> None:
                self._is_running = False
                
            async def run(self) -> None:
                while not self.stop_event.is_set() and self._is_running:
                    await asyncio.sleep(1)
        
        class MockUserService(BaseService):
            def __init__(self, client=None, config=None, db=None, stop_event=None):
                super().__init__("user", client, config, db, stop_event)
                
            async def initialize(self) -> bool:
                self.initialized = True
                return True
                
            async def start(self) -> bool:
                if not self.initialized:
                    await self.initialize()
                self._is_running = True
                self.start_time = datetime.now()
                return True
                
            async def stop(self) -> None:
                self._is_running = False
                
            async def run(self) -> None:
                while not self.stop_event.is_set() and self._is_running:
                    await asyncio.sleep(1)
                    
        # Servisleri kaydet
        event_service = MockEventService(client, config, db, stop_event)
        message_service = MockMessageService(client, config, db, stop_event)
        group_service = MockGroupService(client, config, db, stop_event)
        user_service = MockUserService(client, config, db, stop_event)
        
        service_manager.register_service(event_service)
        service_manager.register_service(message_service, dependencies=["event"])
        service_manager.register_service(group_service, dependencies=["event"])
        service_manager.register_service(user_service, dependencies=["event", "group"])
        
        # Bağımlılıkları kontrol et
        await service_manager.dependency_check(print_graph=True)
        
        # Servisleri başlat
        logger.info("Servisleri başlatma testi...")
        success = await service_manager.start_all_services()
        
        if success:
            logger.info("✅ Tüm servisler başarıyla başlatıldı!")
            
            # 3 saniye çalıştır
            logger.info("Servisler 3 saniye çalışacak...")
            await asyncio.sleep(3)
            
            # Servisleri durdur
            logger.info("Servisleri durdurma testi...")
            await service_manager.stop_all_services()
            logger.info("✅ Tüm servisler başarıyla durduruldu!")
        else:
            logger.error("❌ Servisler başlatılamadı!")
            
    except Exception as e:
        logger.error(f"❌ Test sırasında hata: {str(e)}", exc_info=True)

def main():
    """Ana fonksiyon"""
    try:
        asyncio.run(test_services())
    except KeyboardInterrupt:
        logger.info("Test kullanıcı tarafından kesildi")
    except Exception as e:
        logger.error(f"Test çalıştırılırken hata: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 