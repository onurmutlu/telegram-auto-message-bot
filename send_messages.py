#!/usr/bin/env python3
"""
Telegram gruplarına mesaj gönderen script.
"""

import os
import sys
import json
import asyncio
import random
import logging
from datetime import datetime

from telethon import TelegramClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("message_send.log")
    ]
)

logger = logging.getLogger(__name__)

# .env dosyasını yükle
load_dotenv(override=True)

# Global değişkenler
API_ID = os.getenv("API_ID", "12345")
API_HASH = os.getenv("API_HASH", "your_api_hash_here")
PHONE = os.getenv("PHONE", "+905551234567")
SESSION_NAME = os.getenv("SESSION_NAME", "telegram_session")

# API_ID integer olmalı
try:
    API_ID = int(API_ID)
except ValueError:
    logger.error(f"API_ID geçerli bir sayı değil: {API_ID}")
    sys.exit(1)

# Veritabanı bağlantısı
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASS = os.getenv('DB_PASSWORD', 'postgres')
DB_NAME = os.getenv('DB_NAME', 'telegram_bot')

# SQLAlchemy bağlantı URL'si
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

async def get_groups(session):
    """Veritabanından aktif grupları çek"""
    query = text("""
        SELECT id, group_id, name, is_active, is_admin, member_count
        FROM groups
        WHERE is_active = true
        ORDER BY member_count DESC, name
        LIMIT 10;
    """)
    
    result = session.execute(query)
    groups = [dict(row._mapping) for row in result.fetchall()]
    return groups

async def get_templates(session, template_type='general', category=None, limit=5):
    """Veritabanından mesaj şablonlarını çek"""
    if category:
        query = text("""
            SELECT id, content, type, category
            FROM message_templates
            WHERE type = :type AND category = :category AND is_active = true
            ORDER BY RANDOM()
            LIMIT :limit;
        """)
        params = {"type": template_type, "category": category, "limit": limit}
    else:
        query = text("""
            SELECT id, content, type, category
            FROM message_templates
            WHERE type = :type AND is_active = true
            ORDER BY RANDOM()
            LIMIT :limit;
        """)
        params = {"type": template_type, "limit": limit}
    
    result = session.execute(query, params)
    templates = [dict(row._mapping) for row in result.fetchall()]
    return templates

async def send_message_to_group(client, group, template, session):
    """Gruba mesaj gönder ve veritabanına kaydet"""
    try:
        logger.info(f"Mesaj gönderiliyor: Grup: {group['name']} (ID: {group['group_id']})")
        logger.info(f"Şablon: {template['category']} - {template['content'][:50]}...")
        
        # Mesajı gönder
        message = await client.send_message(
            group['group_id'],
            template['content']
        )
        
        # Mesajı veritabanına kaydet
        insert_query = text("""
            INSERT INTO messages 
            (group_id, content, message_type, status, sent_at, is_active, created_at, updated_at)
            VALUES 
            (:group_id, :content, :message_type, :status, :sent_at, true, :created_at, :updated_at)
            RETURNING id;
        """)
        
        now = datetime.now()
        params = {
            "group_id": group['group_id'],
            "content": template['content'],
            "message_type": template['type'].upper(),
            "status": "SENT",
            "sent_at": now,
            "created_at": now,
            "updated_at": now
        }
        
        result = session.execute(insert_query, params)
        message_id = result.fetchone()[0]
        session.commit()
        
        logger.info(f"Mesaj başarıyla gönderildi ve kaydedildi. DB ID: {message_id}")
        return True, message_id
        
    except Exception as e:
        logger.error(f"Mesaj gönderme hatası: {str(e)}")
        session.rollback()
        return False, None

async def main():
    """Ana fonksiyon"""
    logger.info("Telegram mesaj gönderme scripti başlatılıyor...")
    
    # Engine oluştur
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Telegram client oluştur
        logger.info(f"Telegram istemcisi oluşturuluyor... (API ID: {API_ID}, Session: {SESSION_NAME})")
        client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        
        # Bağlan
        logger.info("Telegram'a bağlanılıyor...")
        await client.connect()
        
        # Oturum açık mı kontrol et
        if not await client.is_user_authorized():
            logger.error("Telegram oturumu açık değil! Önce telegram_login.py ile oturum açın.")
            return
        
        # Aktif grupları çek
        groups = await get_groups(session)
        if not groups:
            logger.warning("Aktif grup bulunamadı.")
            return
        
        logger.info(f"{len(groups)} aktif grup bulundu:")
        for i, group in enumerate(groups, 1):
            logger.info(f"{i}. {group['name']} (ID: {group['group_id']}, Üye: {group['member_count']})")
        
        # Rastgele bir mesaj kategorisi seç
        categories = ['general', 'question', 'engage', 'morning', 'evening', 'weekend', 'motivation']
        selected_category = random.choice(categories)
        
        # Şablonları çek
        templates = await get_templates(session, 'general', selected_category, 1)
        if not templates:
            logger.warning(f"'{selected_category}' kategorisinde şablon bulunamadı.")
            return
        
        # Mesajı gönder
        template = templates[0]
        selected_group = groups[0]  # İlk grubu seç (veya random.choice(groups) ile rastgele seç)
        
        logger.info(f"Seçilen grup: {selected_group['name']}")
        logger.info(f"Seçilen şablon kategorisi: {selected_category}")
        logger.info(f"Gönderilecek mesaj: {template['content']}")
        
        confirm = input("Bu mesajı göndermek istiyor musunuz? (e/h): ").lower()
        if confirm != 'e':
            logger.info("İşlem iptal edildi.")
            return
        
        success, message_id = await send_message_to_group(client, selected_group, template, session)
        
        if success:
            logger.info("Mesaj başarıyla gönderildi!")
        else:
            logger.error("Mesaj gönderme işlemi başarısız oldu.")
        
    except Exception as e:
        logger.error(f"Hata oluştu: {str(e)}")
    finally:
        # Bağlantıları kapat
        session.close()
        if 'client' in locals() and client.is_connected():
            await client.disconnect()
        logger.info("İşlem tamamlandı.")

if __name__ == "__main__":
    # Windows için policy ayarla
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main()) 