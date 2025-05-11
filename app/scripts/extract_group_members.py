#!/usr/bin/env python3
"""
Telegram gruplarının ve üyelerinin detaylı bilgilerini çekip PostgreSQL veritabanına kaydeder.
Bu veriler kalıcı olarak saklanır ve analiz amaçlı kullanılabilir.

Kullanım:
    python extract_group_members.py [--group_id GROUP_ID] [--all]
    
Parametreler:
    --group_id: Belirli bir grubun verisini çekmek için grup ID'si
    --all: Tüm grupların verilerini çekmek için
"""

import os
import sys
import json
import logging
import asyncio
import argparse
from datetime import datetime
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import Json
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest, GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsRecent, ChannelParticipantsAdmins
from telethon.errors import FloodWaitError, ChannelPrivateError

# Projenin ana dizinini ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.models import Group, TelegramUser, GroupMember
from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter

# Log formatını ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Config ayarları
from dotenv import load_dotenv
load_dotenv()

# Telegram API bilgileri
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
SESSION_NAME = os.getenv('SESSION_NAME', 'session/anon')

# Veritabanı bağlantı bilgileri
db_url = os.getenv('DATABASE_URL')
if not db_url:
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'postgres')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'telegram_bot')
    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# Veritabanı bağlantı parametrelerini ayrıştır
url = urlparse(db_url)
db_params = {
    'dbname': url.path[1:],  # / işaretini kaldır
    'user': url.username or 'postgres',
    'password': url.password or 'postgres',
    'host': url.hostname or 'localhost',
    'port': url.port or 5432
}

# Rate limiter oluştur
rate_limiter = AdaptiveRateLimiter(
    initial_rate=0.2,  # Saniyede 0.2 istek (5 saniyede 1)
    period=60,
    error_backoff=2.0,
    max_jitter=5.0
)

async def get_db_connection():
    """PostgreSQL veritabanına bağlanır"""
    try:
        conn = psycopg2.connect(**db_params)
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"Veritabanına bağlanırken hata: {str(e)}")
        sys.exit(1)

async def get_group_info(client, group_id):
    """Grup bilgilerini alır"""
    try:
        logger.info(f"Grup bilgileri alınıyor: {group_id}")
        
        # Adım 1: Grup varlığını al
        entity = await client.get_entity(group_id)
        if not entity:
            logger.error(f"Grup bulunamadı: {group_id}")
            return None
        
        # Adım 2: Tam grup bilgilerini al
        try:
            full_channel = await client(GetFullChannelRequest(entity))
        except Exception as e:
            logger.error(f"Tam grup bilgileri alınamadı: {str(e)}")
            full_channel = None
        
        # Adım 3: Grup verilerini hazırla
        group_data = {
            'group_id': entity.id,
            'name': entity.title,
            'username': getattr(entity, 'username', None),
            'description': getattr(full_channel.full_chat, 'about', None) if full_channel else None,
            'member_count': getattr(entity, 'participants_count', 0),
            'is_public': getattr(entity, 'username', None) is not None,
            'source': 'extract_script',
            'last_update': datetime.now().isoformat()
        }
        
        logger.info(f"Grup bilgileri alındı: {entity.title} ({entity.id})")
        return group_data
        
    except Exception as e:
        logger.error(f"Grup bilgileri alınırken hata: {str(e)}")
        return None

async def get_group_members(client, group_id, limit=1000):
    """Grup üyelerini alır"""
    try:
        logger.info(f"Grup üyeleri alınıyor: {group_id} (limit: {limit})")
        
        # Adım 1: Grup varlığını al
        entity = await client.get_entity(group_id)
        if not entity:
            logger.error(f"Grup bulunamadı: {group_id}")
            return []
        
        # Adım 2: Önce admin listesini al
        admins = []
        try:
            admin_participants = await client(GetParticipantsRequest(
                entity, ChannelParticipantsAdmins(), offset=0, limit=100, hash=0
            ))
            admins = [admin.id for admin in admin_participants.users]
            logger.info(f"{len(admins)} admin bulundu")
        except Exception as e:
            logger.error(f"Adminler alınırken hata: {str(e)}")
        
        # Adım 3: Tüm üyeleri al
        all_members = []
        offset = 0
        chunk_size = 200  # Telethon'un sınırı
        
        while len(all_members) < limit:
            try:
                # Rate limit kontrolü
                await rate_limiter.wait()
                
                participants = await client(GetParticipantsRequest(
                    entity, ChannelParticipantsRecent(), offset=offset, limit=chunk_size, hash=0
                ))
                
                if not participants.users:
                    break
                
                # Her kullanıcı için
                for user in participants.users:
                    # Kullanıcı verilerini hazırla
                    user_data = {
                        'user_id': user.id,
                        'username': getattr(user, 'username', None),
                        'first_name': getattr(user, 'first_name', None),
                        'last_name': getattr(user, 'last_name', None),
                        'is_bot': getattr(user, 'bot', False),
                        'is_premium': getattr(user, 'premium', False),
                        'language_code': getattr(user, 'lang_code', None),
                        'phone': getattr(user, 'phone', None),
                        'is_admin': user.id in admins,
                        'group_id': group_id
                    }
                    all_members.append(user_data)
                
                offset += len(participants.users)
                logger.info(f"{len(all_members)} üye alındı...")
                
                # Limit kontrolü
                if len(participants.users) < chunk_size:
                    break
                    
                # Kısa bir bekleme
                await asyncio.sleep(1)
                
            except FloodWaitError as e:
                wait_time = e.seconds
                logger.warning(f"Rate limit aşıldı, {wait_time} saniye bekleniyor...")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Üyeler alınırken hata: {str(e)}")
                break
        
        logger.info(f"Toplam {len(all_members)} üye alındı")
        return all_members
        
    except Exception as e:
        logger.error(f"Grup üyeleri alınırken hata: {str(e)}")
        return []

async def save_group_to_db(conn, group_data):
    """Grup bilgilerini veritabanına kaydeder"""
    try:
        cursor = conn.cursor()
        
        # Grup var mı kontrol et
        cursor.execute(
            "SELECT group_id FROM groups WHERE group_id = %s",
            (group_data['group_id'],)
        )
        result = cursor.fetchone()
        
        if result:
            # Grubu güncelle
            cursor.execute("""
                UPDATE groups SET 
                    name = %s, 
                    username = %s, 
                    description = %s, 
                    member_count = %s,
                    is_public = %s,
                    source = %s,
                    updated_at = NOW()
                WHERE group_id = %s
            """, (
                group_data['name'],
                group_data['username'],
                group_data['description'],
                group_data['member_count'],
                group_data['is_public'],
                group_data['source'],
                group_data['group_id']
            ))
            logger.info(f"Grup güncellendi: {group_data['name']} ({group_data['group_id']})")
        else:
            # Yeni grup ekle
            cursor.execute("""
                INSERT INTO groups (
                    group_id, name, username, description, 
                    member_count, is_public, source, 
                    join_date, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW())
            """, (
                group_data['group_id'],
                group_data['name'],
                group_data['username'],
                group_data['description'],
                group_data['member_count'],
                group_data['is_public'],
                group_data['source']
            ))
            logger.info(f"Yeni grup eklendi: {group_data['name']} ({group_data['group_id']})")
        
        # Data mining tablosuna da kaydet
        cursor.execute("""
            INSERT INTO data_mining (
                telegram_id, group_id, type, source, data, 
                is_processed, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, TRUE, NOW(), NOW())
        """, (
            group_data['group_id'],
            group_data['group_id'],
            'group',
            'extract_script',
            Json(group_data)
        ))
        
        cursor.close()
        return True
        
    except Exception as e:
        logger.error(f"Grup veritabanına kaydedilirken hata: {str(e)}")
        return False

async def save_users_to_db(conn, users):
    """Kullanıcıları veritabanına kaydeder"""
    try:
        cursor = conn.cursor()
        
        success_count = 0
        failed_count = 0
        
        for user in users:
            try:
                # 1. Önce kullanıcıyı kaydet/güncelle
                cursor.execute(
                    "SELECT user_id FROM telegram_users WHERE user_id = %s",
                    (user['user_id'],)
                )
                result = cursor.fetchone()
                
                if result:
                    # Kullanıcıyı güncelle
                    cursor.execute("""
                        UPDATE telegram_users SET 
                            username = %s, 
                            first_name = %s, 
                            last_name = %s, 
                            is_bot = %s,
                            is_premium = %s,
                            language_code = %s,
                            phone = %s,
                            last_seen = NOW(),
                            updated_at = NOW()
                        WHERE user_id = %s
                    """, (
                        user['username'],
                        user['first_name'],
                        user['last_name'],
                        user['is_bot'],
                        user['is_premium'],
                        user['language_code'],
                        user['phone'],
                        user['user_id']
                    ))
                else:
                    # Yeni kullanıcı ekle
                    cursor.execute("""
                        INSERT INTO telegram_users (
                            user_id, username, first_name, last_name, 
                            is_bot, is_premium, language_code, phone,
                            first_seen, last_seen, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW(), NOW())
                    """, (
                        user['user_id'],
                        user['username'],
                        user['first_name'],
                        user['last_name'],
                        user['is_bot'],
                        user['is_premium'],
                        user['language_code'],
                        user['phone']
                    ))
                
                # 2. Grup-kullanıcı ilişkisini kaydet
                cursor.execute("""
                    INSERT INTO group_members (
                        user_id, group_id, is_admin, joined_at, 
                        last_seen, is_active, created_at, updated_at
                    ) VALUES (%s, %s, %s, NOW(), NOW(), TRUE, NOW(), NOW())
                    ON CONFLICT (user_id, group_id) DO UPDATE SET
                        is_admin = EXCLUDED.is_admin, 
                        last_seen = NOW(), 
                        is_active = TRUE, 
                        updated_at = NOW()
                """, (
                    user['user_id'],
                    user['group_id'],
                    user['is_admin']
                ))
                
                # 3. Data mining tablosuna kaydet
                cursor.execute("""
                    INSERT INTO data_mining (
                        telegram_id, user_id, group_id, type, source, data, 
                        is_processed, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
                """, (
                    user['user_id'],
                    user['user_id'],
                    user['group_id'],
                    'user',
                    'extract_script',
                    Json(user)
                ))
                
                success_count += 1
                
            except Exception as user_error:
                logger.error(f"Kullanıcı kaydedilirken hata (ID: {user['user_id']}): {str(user_error)}")
                failed_count += 1
        
        cursor.close()
        logger.info(f"Kullanıcı kayıtları tamamlandı: {success_count} başarılı, {failed_count} başarısız")
        return success_count, failed_count
        
    except Exception as e:
        logger.error(f"Kullanıcılar veritabanına kaydedilirken hata: {str(e)}")
        return 0, 0

async def get_all_groups(conn):
    """Veritabanındaki tüm grupları alır"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT group_id, name FROM groups WHERE is_active = TRUE")
        groups = cursor.fetchall()
        cursor.close()
        return groups
    except Exception as e:
        logger.error(f"Gruplar alınırken hata: {str(e)}")
        return []

async def main():
    parser = argparse.ArgumentParser(description='Telegram gruplarının ve üyelerinin verilerini çeker')
    parser.add_argument('--group_id', type=int, help='Belirli bir grubun ID\'si')
    parser.add_argument('--all', action='store_true', help='Tüm grupların verilerini çek')
    args = parser.parse_args()
    
    # Bağlantıları kur
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    
    conn = await get_db_connection()
    
    try:
        # Belirli bir grup için
        if args.group_id:
            group_id = args.group_id
            
            # Grup bilgilerini al ve kaydet
            group_data = await get_group_info(client, group_id)
            if group_data:
                await save_group_to_db(conn, group_data)
                
                # Grup üyelerini al ve kaydet
                members = await get_group_members(client, group_id)
                if members:
                    await save_users_to_db(conn, members)
            
        # Tüm gruplar için
        elif args.all:
            groups = await get_all_groups(conn)
            logger.info(f"{len(groups)} grup bulundu")
            
            for group in groups:
                group_id, group_name = group
                logger.info(f"İşleniyor: {group_name} ({group_id})")
                
                # Grup bilgilerini al ve kaydet
                group_data = await get_group_info(client, group_id)
                if group_data:
                    await save_group_to_db(conn, group_data)
                    
                    # Grup üyelerini al ve kaydet
                    members = await get_group_members(client, group_id)
                    if members:
                        await save_users_to_db(conn, members)
                
                # Her grup arasında biraz bekle
                await asyncio.sleep(5)
        
        else:
            logger.error("Lütfen --group_id veya --all parametrelerinden birini kullanın")
            
    except Exception as e:
        logger.error(f"İşlem sırasında hata: {str(e)}")
    finally:
        # Bağlantıları kapat
        await client.disconnect()
        conn.close()
        logger.info("İşlem tamamlandı")

if __name__ == "__main__":
    asyncio.run(main()) 