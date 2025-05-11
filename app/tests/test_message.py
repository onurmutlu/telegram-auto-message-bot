#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mesaj servisi ve otomatik mesaj gönderme işlevselliğini test etmek için
basit bir test betiği.
"""

import asyncio
import logging
import sys
import os
import traceback
import json
from datetime import datetime, timedelta
import dotenv
from telethon import TelegramClient, events

# .env dosyasından değerleri yükle
dotenv.load_dotenv()

# Loglamayı yapılandır
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_message.log')
    ]
)

logger = logging.getLogger(__name__)

async def main():
    try:
        logger.info("Mesaj servisi testi başlatılıyor...")
        
        # Telegram API bilgilerini al
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        phone = os.getenv("PHONE")
        session_name = os.getenv("SESSION_NAME", "telegram_session")
        
        if not api_id or not api_hash:
            logger.error("API_ID veya API_HASH bulunamadı! .env dosyasını kontrol edin.")
            return

        logger.info(f"API bilgileri alındı: API_ID={api_id}, Session={session_name}")
        
        # Gerekli modülleri import et
        from app.config import Config
        from app.utils.db_setup import Database
        from app.service_manager import ServiceManager
        from app.services.message_service import MessageService
        from app.services.promo_service import PromoService
        from config_helper import ConfigAdapter
        
        # DB bağlantı bilgilerini ayarla
        db_config = {
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "postgres"),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
            "database": os.getenv("DB_NAME", "telegram_bot").replace("%", "")
        }
        
        # Telegram grupları
        groups = os.getenv("GROUPS", "").split(",")
        admin_groups = os.getenv("ADMIN_GROUPS", "").split(",")
        target_groups = os.getenv("TARGET_GROUPS", "").split(",")
        super_users = os.getenv("SUPER_USERS", "").split(",")
        
        # Konfigürasyonu oluştur
        config_dict = {
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone,
            "session_name": session_name,
            "database": db_config,
            "GROUPS": groups,
            "ADMIN_GROUPS": admin_groups,
            "TARGET_GROUPS": target_groups,
            "SUPER_USERS": super_users,
            "DEBUG": os.getenv("DEBUG", "true").lower() == "true"
        }
        
        # Config nesnesi oluştur
        config = Config(config_dict)
        
        # Telegram istemcisi oluştur
        logger.info("Telegram istemcisi oluşturuluyor...")
        # Telethon istemcisini başlat (oturum dosyası olarak session_name kullan)
        client = TelegramClient(f"session/{session_name}", api_id, api_hash)
        
        # Veritabanı bağlantısı
        logger.info("Veritabanı bağlantısı kuruluyor...")
        try:
            db_connection_string = os.getenv("DB_CONNECTION", f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}")
            db = Database(db_connection_string)
            await db.connect()
            logger.info("Veritabanı bağlantısı başarılı")
        except Exception as e:
            logger.error(f"Veritabanı bağlantısı hatası: {str(e)}")
            db = None
        
        # Stop event oluştur
        stop_event = asyncio.Event()
        
        # Test mesajı (gruplara gönderilecek)
        test_message = "Merhaba! Bu bir test mesajıdır. Otomatik mesaj gönderme sistemi test ediliyor."
        
        # İstemciyi başlat
        await client.connect()
        
        # Giriş durumunu kontrol et
        if not await client.is_user_authorized():
            logger.info(f"Kullanıcı girişi yapılmamış. Giriş yapılıyor... Telefon: {phone}")
            try:
                await client.send_code_request(phone)
                verification_code = input("Telegram'dan gelen doğrulama kodunu girin: ")
                await client.sign_in(phone, verification_code)
            except Exception as e:
                logger.error(f"Giriş hatası: {str(e)}")
                return
        
        logger.info("Telegram istemcisi başarıyla bağlandı ve giriş yapıldı!")
        
        # Kullanıcı bilgilerini al
        me = await client.get_me()
        logger.info(f"Giriş yapılan hesap: {me.username} (ID: {me.id})")
        
        # MessageService oluştur ve istemciyi aktar
        logger.info("MessageService oluşturuluyor...")
        message_service = MessageService(client, config, db, stop_event)
        
        # Servisi başlat
        logger.info("MessageService initialize ediliyor...")
        try:
            await message_service.initialize()
            logger.info("MessageService başarıyla initialize edildi")
        except Exception as e:
            logger.error(f"MessageService initialize hatası: {str(e)}")
            logger.debug(traceback.format_exc())
        
        logger.info("MessageService başlatılıyor...")
        try:
            await message_service.start()
            logger.info("MessageService başarıyla başlatıldı")
        except Exception as e:
            logger.error(f"MessageService başlatma hatası: {str(e)}")
            logger.debug(traceback.format_exc())
        
        # Diyalogları (grupları) getir
        logger.info("Telegram grupları alınıyor...")
        dialogs = await client.get_dialogs()
        groups = [d for d in dialogs if d.is_group or d.is_channel]
        
        if groups:
            logger.info(f"{len(groups)} grup bulundu:")
            for i, group in enumerate(groups):
                logger.info(f"  {i+1}. {group.title} (ID: {group.id})")
            
            # Grup ID'leri hedef gruplarla eşleştir
            target_group_ids = []
            for target_name in target_groups:
                for group in groups:
                    if target_name.lower() in group.title.lower():
                        target_group_ids.append(group.id)
                        logger.info(f"Hedef grup eşleşti: {group.title} (ID: {group.id})")
        else:
            logger.warning("Hiç grup bulunamadı!")
        
        # Aktif grupları kontrol et
        logger.info("Aktif gruplar alınıyor...")
        try:
            active_groups = await message_service._get_active_groups()
            
            if active_groups:
                logger.info(f"{len(active_groups)} aktif grup bulundu:")
                for group in active_groups:
                    logger.info(f"  - Grup: {group.get('name', 'İsimsiz')} (ID: {group.get('group_id', 'Bilinmiyor')})")
                    
                # İlk gruba test mesajı gönder
                if target_group_ids:
                    # Hedef grup varsa ilk hedef gruba gönder
                    test_group_id = target_group_ids[0]
                    logger.info(f"Test mesajı hedef gruba gönderiliyor: {test_group_id}")
                    try:
                        result = await message_service.send_message(test_group_id, test_message)
                        if result:
                            logger.info(f"✅ Mesaj başarıyla gönderildi: Grup {test_group_id}")
                        else:
                            logger.error(f"❌ Mesaj gönderilemedi: Grup {test_group_id}")
                    except Exception as e:
                        logger.error(f"Mesaj gönderme hatası: {str(e)}")
                        logger.debug(traceback.format_exc())
                elif active_groups:
                    # Aktif gruptan ilk gruba gönder
                    first_group = active_groups[0]
                    group_id = first_group.get('group_id')
                    
                    if group_id:
                        logger.info(f"Test mesajı gönderiliyor: Grup {group_id}")
                        try:
                            result = await message_service.send_message(group_id, test_message)
                            if result:
                                logger.info(f"✅ Mesaj başarıyla gönderildi: Grup {group_id}")
                            else:
                                logger.error(f"❌ Mesaj gönderilemedi: Grup {group_id}")
                        except Exception as e:
                            logger.error(f"Mesaj gönderme hatası: {str(e)}")
                            logger.debug(traceback.format_exc())
                    else:
                        logger.error("Grup ID'si bulunamadı!")
                else:
                    logger.warning("Mesaj gönderilecek grup bulunamadı!")
            else:
                logger.warning("Aktif grup bulunamadı!")
        except Exception as e:
            logger.error(f"Aktif grupları alma hatası: {str(e)}")
            logger.debug(traceback.format_exc())
        
        # Mesaj şablonlarını kontrol et
        logger.info("Mesaj şablonları kontrol ediliyor...")
        if hasattr(message_service, 'message_templates') and message_service.message_templates:
            logger.info(f"{len(message_service.message_templates)} şablon bulundu")
        else:
            logger.warning("Mesaj şablonu bulunamadı, şablonları yüklemeyi deniyorum...")
            message_service._load_message_templates()
            if hasattr(message_service, 'message_templates') and message_service.message_templates:
                logger.info(f"Şablonlar yüklendi: {len(message_service.message_templates)} şablon bulundu")
            else:
                logger.error("Mesaj şablonları yüklenemedi!")
        
        # MessageService run metodunu test et
        logger.info("MessageService run metodu test ediliyor...")
        # Run metodunu başlat ama 20 saniye sonra durdur
        run_task = asyncio.create_task(message_service.run())
        
        # Durumu kontrol et
        await asyncio.sleep(5)
        if hasattr(message_service, 'next_run_time'):
            logger.info(f"MessageService run metodu çalışıyor, bir sonraki çalışma zamanı: {message_service.next_run_time}")
        else:
            logger.warning("MessageService.next_run_time özelliği bulunamadı!")
        
        # 20 saniye çalıştır ve otomatik mesaj gönderimini izle
        logger.info("Servis 20 saniye süreyle test ediliyor...")
        await asyncio.sleep(15)
            
        # MessageService'i durdur
        logger.info("MessageService durduruluyor...")
        try:
            await message_service.stop()
            logger.info("MessageService başarıyla durduruldu")
        except Exception as e:
            logger.error(f"MessageService durdurma hatası: {str(e)}")
            logger.debug(traceback.format_exc())
        
        # Run görevini iptal et
        logger.info("Run görevi iptal ediliyor...")
        if not run_task.done():
            run_task.cancel()
            try:
                await run_task
            except asyncio.CancelledError:
                logger.info("Run görevi başarıyla iptal edildi")
            except Exception as e:
                logger.error(f"Run görevi iptal edilirken hata: {str(e)}")
        else:
            logger.warning("Run görevi zaten tamamlanmış!")
        
        # İstemciyi kapat
        await client.disconnect()
        logger.info("Telegram istemcisi kapatıldı.")
        
        logger.info("Test başarıyla tamamlandı!")
        
    except Exception as e:
        logger.error(f"Test sırasında hata: {str(e)}")
        logger.debug(traceback.format_exc())
    finally:
        logger.info("Test tamamlandı")

if __name__ == "__main__":
    asyncio.run(main()) 