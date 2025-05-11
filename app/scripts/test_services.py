#!/usr/bin/env python3
"""
Telegram bot servislerini test eden script.
Bu script, servislerin doğru çalışıp çalışmadığını kontrol eder.
Kullanım: python test_services.py [service_name]
Örnek: python test_services.py engagement
"""

import asyncio
import logging
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import get_db
from app.core.config import settings
from app.models.message_template import MessageTemplate
from app.services.messaging.engagement_service import EngagementService
from app.services.messaging.dm_service import DirectMessageService
from app.services.messaging.promo_service import PromoService
from app.services.analytics.activity_service import ActivityService
from app.services.analytics.user_service import UserService
from telethon import TelegramClient

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("service_test.log")
    ]
)

logger = logging.getLogger(__name__)

async def test_engagement_service(client, db):
    """EngagementService'i test et."""
    logger.info("EngagementService testi başlatılıyor...")
    
    try:
        # Servisi başlat
        service = EngagementService(client=client, db=db)
        await service.initialize()
        
        # Mesaj şablonlarını kontrol et
        if not service.message_templates:
            logger.error("Mesaj şablonları yüklenemedi!")
            return False
            
        logger.info(f"{len(service.message_templates)} mesaj şablonu bulundu.")
        
        # Özel metodları test et
        test_group = {
            "id": 1,
            "chat_id": -1001234567890,
            "title": "Test Grubu",
            "message_count": 100,
            "is_admin": True,
            "member_count": 500,
            "engagement_rate": 0.2
        }
        
        # _should_send_message metodunu test et
        should_send = await service._should_send_message(test_group)
        logger.info(f"Mesaj gönderilmeli mi: {should_send}")
        
        # _select_message_template metodunu test et
        template = await service._select_message_template(test_group)
        if template:
            logger.info(f"Seçilen şablon: {template['content'][:30]}...")
        else:
            logger.warning("Şablon seçilemedi.")
        
        # Servis durumunu kontrol et
        status = await service.get_status()
        logger.info(f"Servis durumu: {status}")
        
        logger.info("EngagementService testi tamamlandı.")
        return True
        
    except Exception as e:
        logger.error(f"EngagementService testi sırasında hata: {str(e)}", exc_info=True)
        return False

async def test_dm_service(client, db):
    """DirectMessageService'i test et."""
    logger.info("DirectMessageService testi başlatılıyor...")
    
    try:
        # Servisi başlat
        service = DirectMessageService(client=client, db=db)
        await service.initialize()
        
        # Şablonları kontrol et
        if not service.welcome_templates:
            logger.warning("Karşılama şablonları yüklenemedi!")
            
        if not service.service_templates:
            logger.warning("Hizmet şablonları yüklenemedi!")
            
        if not service.group_invite_templates:
            logger.warning("Grup davet şablonları yüklenemedi!")
        
        # Servis durumunu kontrol et
        status = await service.get_status()
        logger.info(f"Servis durumu: {status}")
        
        logger.info("DirectMessageService testi tamamlandı.")
        return True
        
    except Exception as e:
        logger.error(f"DirectMessageService testi sırasında hata: {str(e)}", exc_info=True)
        return False

async def test_promo_service(client, db):
    """PromoService'i test et."""
    logger.info("PromoService testi başlatılıyor...")
    
    try:
        # Servisi başlat
        service = PromoService(client=client, db=db)
        await service.initialize()
        
        # Şablonları kontrol et
        if not service.promo_templates:
            logger.warning("Tanıtım şablonları yüklenemedi!")
        else:
            logger.info(f"{len(service.promo_templates)} tanıtım şablonu bulundu.")
        
        # Test grup
        test_group = {
            "id": 1,
            "chat_id": -1001234567890,
            "title": "Test Grubu",
            "message_count": 100,
            "is_admin": False,
            "promo_count": 2,
            "member_count": 500,
            "category": "test"
        }
        
        # _should_send_promo metodunu test et
        should_send = await service._should_send_promo(test_group)
        logger.info(f"Tanıtım mesajı gönderilmeli mi: {should_send}")
        
        # _select_promo_template metodunu test et
        template = await service._select_promo_template(test_group)
        if template:
            logger.info(f"Seçilen tanıtım şablonu: {template['content'][:30]}...")
        else:
            logger.warning("Tanıtım şablonu seçilemedi.")
        
        # Servis durumunu kontrol et
        status = await service.get_status()
        logger.info(f"Servis durumu: {status}")
        
        logger.info("PromoService testi tamamlandı.")
        return True
        
    except Exception as e:
        logger.error(f"PromoService testi sırasında hata: {str(e)}", exc_info=True)
        return False

async def test_activity_service(db):
    """ActivityService'i test et."""
    logger.info("ActivityService testi başlatılıyor...")
    
    try:
        # Servisi başlat
        service = ActivityService(db=db)
        await service.initialize()
        
        # log_interaction metodunu test et
        interaction_result = await service.log_interaction(
            user_id=123456789,
            group_id=-1001234567890,
            message_id=1000,
            interaction_type="test"
        )
        logger.info(f"Etkileşim kaydedildi mi: {interaction_result}")
        
        # get_user_activity metodunu test et
        activity = await service.get_user_activity(user_id=123456789, days=30)
        logger.info(f"Kullanıcı aktivitesi: {activity}")
        
        logger.info("ActivityService testi tamamlandı.")
        return True
        
    except Exception as e:
        logger.error(f"ActivityService testi sırasında hata: {str(e)}", exc_info=True)
        return False

async def test_user_service(db):
    """UserService'i test et."""
    logger.info("UserService testi başlatılıyor...")
    
    try:
        # Servisi başlat
        service = UserService(db=db)
        await service.initialize()
        
        # Test user oluştur
        class TestUser:
            id = 123456789
            username = "test_user"
            first_name = "Test"
            last_name = "User"
        
        # register_or_update_user metodunu test et
        user_id = await service.register_or_update_user(TestUser())
        if user_id:
            logger.info(f"Kullanıcı kaydedildi/güncellendi: {user_id}")
        else:
            logger.warning("Kullanıcı kaydedilemedi/güncellenemedi.")
        
        # get_user metodunu test et
        user = await service.get_user(user_id=123456789)
        if user:
            logger.info(f"Kullanıcı bilgileri alındı: {user}")
        else:
            logger.warning("Kullanıcı bilgileri alınamadı.")
        
        # update_user_stats metodunu test et
        stats_updated = await service.update_user_stats(
            user_id=123456789,
            messages_received=1,
            messages_sent=1
        )
        logger.info(f"Kullanıcı istatistikleri güncellendi mi: {stats_updated}")
        
        # log_dm_activity metodunu test et
        dm_logged = await service.log_dm_activity(
            user_id=123456789,
            content="Test mesajı",
            message_type="test"
        )
        logger.info(f"DM aktivitesi kaydedildi mi: {dm_logged}")
        
        logger.info("UserService testi tamamlandı.")
        return True
        
    except Exception as e:
        logger.error(f"UserService testi sırasında hata: {str(e)}", exc_info=True)
        return False

async def test_template_access(db):
    """Veritabanından şablon erişimini test et."""
    logger.info("Şablon erişimi testi başlatılıyor...")
    
    try:
        # Şablonları getir
        query = "SELECT COUNT(*) FROM message_templates"
        result = await db.execute(query)
        count = result.scalar()
        
        if count:
            logger.info(f"Veritabanında {count} şablon bulundu.")
            
            # Şablon türlerini getir
            query = "SELECT DISTINCT type FROM message_templates"
            result = await db.execute(query)
            types = [row[0] for row in result.fetchall()]
            
            logger.info(f"Şablon türleri: {types}")
            
            # Bir şablon örneği getir
            query = "SELECT id, content, type FROM message_templates LIMIT 1"
            result = await db.execute(query)
            template = result.fetchone()
            
            if template:
                logger.info(f"Örnek şablon: ID={template[0]}, Tür={template[2]}, İçerik={template[1][:30]}...")
            
            return True
        else:
            logger.warning("Veritabanında şablon bulunamadı!")
            return False
            
    except Exception as e:
        logger.error(f"Şablon erişimi testi sırasında hata: {str(e)}", exc_info=True)
        return False

async def main():
    """Ana fonksiyon."""
    parser = argparse.ArgumentParser(description='Telegram bot servislerini test et.')
    parser.add_argument('service', nargs='?', help='Test edilecek servis (engagement, dm, promo, activity, user, all)')
    args = parser.parse_args()
    
    service_name = args.service.lower() if args.service else 'all'
    
    logger.info(f"Servis testi başlatılıyor: {service_name}")
    
    # Veritabanı bağlantısı
    db = await get_db().__anext__()
    
    # Telegram client
    client = TelegramClient(
        settings.SESSION_NAME,
        settings.API_ID,
        settings.API_HASH.get_secret_value(),
        proxy=None
    )
    
    try:
        # Şablonların varlığını kontrol et
        template_ok = await test_template_access(db)
        if not template_ok:
            logger.warning("Şablonlar bulunamadı veya erişilemedi! Devam etmeden önce şablonları yükleyin.")
            logger.info("Şablonları yüklemek için 'python app/scripts/load_templates.py' komutunu çalıştırın.")
        
        # Belirtilen servisi test et
        if service_name == 'engagement' or service_name == 'all':
            await test_engagement_service(client, db)
        
        if service_name == 'dm' or service_name == 'all':
            await test_dm_service(client, db)
        
        if service_name == 'promo' or service_name == 'all':
            await test_promo_service(client, db)
        
        if service_name == 'activity' or service_name == 'all':
            await test_activity_service(db)
        
        if service_name == 'user' or service_name == 'all':
            await test_user_service(db)
        
        logger.info("Servis testleri tamamlandı.")
        
    except Exception as e:
        logger.error(f"Test sırasında hata: {str(e)}", exc_info=True)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main()) 