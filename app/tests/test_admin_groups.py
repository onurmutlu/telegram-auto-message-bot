#!/usr/bin/env python3
"""
Admin Grupları Mesaj Gönderme Testi

Bu script, .env dosyasında tanımlanan admin gruplarına
mesaj göndermek için GroupService sınıfını kullanır.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Ana dizini ekleyerek import'ların çalışmasını sağla
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from telethon.sessions import StringSession

# Bot koduna erişim için importlar
from database.user_db import UserDatabase as Database
from config.config import Config
from app.services.group_service import GroupService

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/admin_group_test.log")
    ]
)

logger = logging.getLogger("admin_group_tester")

async def get_client():
    """Telegram istemcisini yapılandırır ve döndürür"""
    load_dotenv()
    
    # API kimlik bilgilerini kontrol et
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')
    
    if not api_id or not api_hash:
        logger.error("API_ID veya API_HASH çevre değişkenleri tanımlanmamış!")
        return None
    
    api_id = int(api_id)
    
    # Veritabanı bağlantısı kur
    db_path = os.getenv("DB_PATH", "data/users.db")
    logger.info(f"Veritabanı bağlantısı kuruluyor: {db_path}")
    db = Database(db_path=db_path)
    await db.connect()
    
    # Session string'i al
    cursor = db.cursor.execute("SELECT value FROM settings WHERE key = 'session_string'")
    result = cursor.fetchone()
    
    if not result or not result[0]:
        logger.error("Session string bulunamadı!")
        return None, None
    
    session_string = result[0]
    logger.info("Session string veritabanından alındı")
    
    # Telethon istemcisini oluştur
    client = TelegramClient(
        StringSession(session_string),
        api_id, 
        api_hash,
        device_model="Telegram Bot",
        system_version="Python Telethon",
        app_version="1.0"
    )
    
    logger.info("Telegram istemcisi oluşturuldu, bağlanılıyor...")
    await client.connect()
    
    # Kullanıcı yetkilendirmesini kontrol et
    if not await client.is_user_authorized():
        logger.error("İstemci yetkili değil!")
        return None, None
    
    me = await client.get_me()
    if me:
        logger.info(f"Bağlı kullanıcı: {me.first_name} (@{me.username})")
    else:
        logger.warning("Kullanıcı bilgisi alınamadı!")
    
    return client, db

async def _run_async_db_method(method, *args, **kwargs):
    """
    Veritabanı metodunu thread-safe biçimde çalıştırır.
    
    Args:
        method: Çalıştırılacak veritabanı metodu
        *args: Metoda geçirilecek argümanlar
        **kwargs: Metoda geçirilecek anahtar kelimeli argümanlar
        
    Returns:
        Any: Metodun döndürdüğü değer
    """
    import functools
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        functools.partial(method, *args, **kwargs)
    )

async def test_admin_groups():
    """Admin gruplarını test eder ve mesaj gönderir"""
    # Çevre değişkenlerini yükle
    load_dotenv()
    
    # Admin grupları al
    admin_groups_str = os.getenv("ADMIN_GROUPS", "")
    admin_groups = [group.strip() for group in admin_groups_str.split(",") if group.strip()]
    
    logger.info(f"Admin grupları: {admin_groups}")
    
    if not admin_groups:
        logger.error("Admin grup tanımlanmamış!")
        return
    
    # Telegram istemcisini oluştur
    client, db = await get_client()
    if not client:
        return
    
    try:
        # Stop event oluştur
        stop_event = asyncio.Event()
        
        # Yapılandırma nesnesi oluştur
        config = Config()
        
        # GroupService oluştur
        logger.info("GroupService başlatılıyor...")
        group_service = GroupService(client, config, db, stop_event)
        await group_service.initialize()
        
        # Her admin grubunu doğrudan entity olarak almayı dene
        for admin_group in admin_groups:
            try:
                logger.info(f"Admin grup '{admin_group}' işleniyor...")
                
                # Farklı formatlarda deneme yap
                entity = None
                error_messages = []
                
                # Format 1: @username şeklinde dene
                if not entity:
                    try:
                        username = admin_group.lstrip('@')
                        logger.info(f"@{username} formatıyla aranıyor...")
                        entity = await client.get_entity(f"@{username}")
                        logger.info(f"Grup bulundu: {entity.title} (ID: {entity.id})")
                    except Exception as e:
                        error_messages.append(f"@{username} formatı hatası: {str(e)}")
                
                # Format 2: Direkt username şeklinde dene
                if not entity:
                    try:
                        username = admin_group.lstrip('@')
                        logger.info(f"{username} formatıyla aranıyor...")
                        entity = await client.get_entity(username)
                        logger.info(f"Grup bulundu: {entity.title} (ID: {entity.id})")
                    except Exception as e:
                        error_messages.append(f"{username} formatı hatası: {str(e)}")
                
                # Format 3: ID olarak dene
                if not entity and admin_group.lstrip('-').isdigit():
                    try:
                        group_id = int(admin_group)
                        logger.info(f"ID: {group_id} ile aranıyor...")
                        entity = await client.get_entity(group_id)
                        logger.info(f"Grup bulundu: {entity.title} (ID: {entity.id})")
                    except Exception as e:
                        error_messages.append(f"ID formatı hatası: {str(e)}")
                
                # Grup bulunduysa mesaj gönder
                if entity:
                    # Veritabanına gruba kaydet
                    try:
                        query = """
                        INSERT OR REPLACE INTO groups 
                        (chat_id, title, is_active, last_activity) 
                        VALUES (?, ?, 1, datetime('now'))
                        """
                        await _run_async_db_method(db.cursor.execute, query, (entity.id, entity.title))
                        await _run_async_db_method(db.conn.commit)
                        logger.info(f"Grup veritabanına kaydedildi: {entity.title} (ID: {entity.id})")
                    except Exception as db_error:
                        logger.error(f"Grup veritabanına kaydederken hata: {str(db_error)}")
                    
                    # Test mesajı oluştur
                    message = (
                        f"🧪 Bu bir test mesajıdır - {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"Admin grup testi: {entity.title}\n"
                        f"ID: {entity.id}"
                    )
                    
                    # GroupService'in _send_message_to_group metodunu kullanarak mesajı gönder
                    logger.info(f"Gruba mesaj gönderiliyor: {entity.title} (ID: {entity.id})")
                    success = await group_service._send_message_to_group(entity.id, message)
                    
                    if success:
                        logger.info(f"✅ Mesaj başarıyla gönderildi: {entity.title}")
                    else:
                        logger.error(f"❌ Mesaj gönderilemedi: {entity.title}")
                else:
                    error_details = "\n".join(error_messages)
                    logger.error(f"Grup bulunamadı: {admin_group}. Hatalar:\n{error_details}")
                
                # 5 saniye bekle (oran sınırlama için)
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Admin grup {admin_group} işlenirken hata: {str(e)}")
        
    except Exception as e:
        logger.error(f"Test sırasında genel hata: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # İstemciyi kapat
        if client:
            await client.disconnect()
            logger.info("Telegram istemcisi kapatıldı.")
        
        # Veritabanını kapat
        if db:
            await db.close()
            logger.info("Veritabanı bağlantısı kapatıldı.")

if __name__ == "__main__":
    # Event loop oluştur ve ana fonksiyonu çalıştır
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_admin_groups()) 