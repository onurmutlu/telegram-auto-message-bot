#!/usr/bin/env python
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
from datetime import datetime, timedelta
import dotenv
import json
import random
from pathlib import Path

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

# Mesaj dosyasını tanımla
MESSAGES_FILE = Path('data/messages.json')

async def test_auto_messaging():
    """Gruplara otomatik mesaj gönderimi için test işlevi"""
    logger.info("Otomatik mesaj gönderimi testi başlatılıyor...")
    
    try:
        # Telegram client
        from telethon import TelegramClient
        import asyncio
        from app.db.session import get_session
        from sqlalchemy import text
        from app.core.unified.client import get_client
        from app.services.message_service import MessageService
        
        # Mesaj şablonlarını yükle
        if not MESSAGES_FILE.exists():
            logger.error(f"Mesaj dosyası bulunamadı: {MESSAGES_FILE}")
            return
            
        with open(MESSAGES_FILE, 'r', encoding='utf-8') as f:
            message_templates = json.load(f)
            
        # Yeni eklenen engaging ve dm_invite kategorilerini kontrol et
        categories = list(message_templates.keys())
        logger.info(f"Mevcut mesaj kategorileri: {categories}")
        
        if 'engage' not in categories or 'dm_invite' not in categories:
            logger.error("Gerekli mesaj kategorileri (engage, dm_invite) bulunamadı!")
            return
            
        # Telegram istemcisini başlat
        client = await get_client()
        if not client:
            logger.error("Telegram istemcisi başlatılamadı!")
            return
            
        logger.info(f"Telegram istemcisi başlatıldı: {(await client.get_me()).first_name}")
        
        # Grupları veritabanından al
        session = next(get_session())
        group_query = text("""
            SELECT group_id, name, is_active 
            FROM groups 
            WHERE is_active = TRUE 
            ORDER BY RANDOM() 
            LIMIT 5
        """)
        groups = session.execute(group_query).fetchall()
        
        if not groups:
            logger.error("Veritabanında aktif grup bulunamadı!")
            return
            
        logger.info(f"{len(groups)} aktif grup bulundu")
        
        # MessageService başlat
        message_service = MessageService(client=client)
        await message_service.initialize()
        
        # Her grup için bir engaging mesajı zamanla
        scheduled_count = 0
        
        for group in groups:
            group_id = group[0]
            group_name = group[1]
            
            # Rastgele bir kategori seç (engage veya dm_invite)
            category = random.choice(['engage', 'dm_invite'])
            
            # Kategori içinden rastgele bir mesaj seç
            messages = message_templates.get(category, [])
            if not messages:
                logger.warning(f"'{category}' kategorisinde mesaj bulunamadı!")
                continue
                
            message_content = random.choice(messages)
            
            # Zamanlanacak süreyi belirle (şimdi + 1-3 dakika)
            scheduled_time = datetime.now() + timedelta(minutes=random.randint(1, 3))
            
            # Mesajı zamanla
            message = await message_service.schedule_message(
                content=message_content,
                group_id=group_id,
                scheduled_for=scheduled_time
            )
            
            if message:
                logger.info(f"Mesaj zamanlandı: ID={message.id}, Grup={group_name}, Kategori={category}, Zaman={scheduled_time}")
                scheduled_count += 1
            else:
                logger.error(f"Mesaj zamanlanamadı: Grup={group_name}")
                
        logger.info(f"Toplam {scheduled_count} mesaj zamanlandı")
        
        # Zamanlanmış mesajları kontrol et
        scheduled_query = text("""
            SELECT id, group_id, content, scheduled_for, status
            FROM messages
            WHERE status = 'SCHEDULED'
            ORDER BY scheduled_for
            LIMIT 10
        """)
        scheduled_messages = session.execute(scheduled_query).fetchall()
        
        logger.info(f"Zamanlanmış mesajlar ({len(scheduled_messages)}):")
        for msg in scheduled_messages:
            logger.info(f"  ID={msg[0]}, Grup={msg[1]}, Zaman={msg[3]}, Durum={msg[4]}")
            logger.info(f"  İçerik: {msg[2][:50]}...")
            
        logger.info("Otomatik mesaj gönderimi testi tamamlandı!")
        
    except Exception as e:
        logger.exception(f"Test sırasında hata oluştu: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_auto_messaging()) 