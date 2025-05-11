#!/usr/bin/env python3
"""
Veri madenciliği tablolarını düzeltir ve eksik alanları tamamlar.
Bu script, veritabanındaki data_mining tablosunu ve ilişkili tabloları düzeltir.

Kullanım:
    python fix_mining_tables.py
"""

import os
import sys
import json
import logging
import asyncio
import asyncpg
from datetime import datetime
from dotenv import load_dotenv

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# .env dosyasından çevre değişkenlerini yükle
load_dotenv()

# Veritabanı bağlantı bilgileri
def get_db_url():
    """Veritabanı bağlantı URL'sini oluşturur"""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        user = os.getenv('DB_USER', 'postgres')
        password = os.getenv('DB_PASSWORD', 'postgres')
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'telegram_bot')
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    
    return db_url

async def fix_data_mining_table():
    """Data mining tablosunu düzeltir ve eksik alanları ekler"""
    logger.info("Data mining tablosu düzeltiliyor...")
    
    try:
        # Veritabanına bağlan
        conn = await asyncpg.connect(get_db_url())
        
        # Tablo varlığını kontrol et
        check_table = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'data_mining')"
        )
        
        if not check_table:
            logger.warning("data_mining tablosu bulunamadı, oluşturuluyor...")
            
            # Tablo oluştur
            await conn.execute("""
                CREATE TABLE data_mining (
                    mining_id SERIAL PRIMARY KEY,
                    telegram_id INTEGER,
                    user_id INTEGER,
                    group_id INTEGER,
                    type VARCHAR(50),
                    source VARCHAR(100),
                    data TEXT,
                    is_processed BOOLEAN DEFAULT FALSE,
                    processed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            logger.info("data_mining tablosu oluşturuldu")
        
        # Eksik kolonları kontrol et ve ekle
        columns = [
            ("telegram_id", "INTEGER"),
            ("user_id", "INTEGER"),
            ("group_id", "INTEGER"),
            ("type", "VARCHAR(50)"),
            ("source", "VARCHAR(100)"),
            ("is_processed", "BOOLEAN DEFAULT FALSE"),
            ("processed_at", "TIMESTAMP")
        ]
        
        for column_name, column_type in columns:
            column_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'data_mining' AND column_name = $1)",
                column_name
            )
            
            if not column_exists:
                logger.warning(f"'{column_name}' kolonu ekleniyor...")
                await conn.execute(f"ALTER TABLE data_mining ADD COLUMN {column_name} {column_type}")
                logger.info(f"'{column_name}' kolonu eklendi")
        
        # İndeksler oluştur
        indexes = [
            ("idx_data_mining_telegram_id", "CREATE INDEX IF NOT EXISTS idx_data_mining_telegram_id ON data_mining(telegram_id)"),
            ("idx_data_mining_user_id", "CREATE INDEX IF NOT EXISTS idx_data_mining_user_id ON data_mining(user_id)"),
            ("idx_data_mining_group_id", "CREATE INDEX IF NOT EXISTS idx_data_mining_group_id ON data_mining(group_id)"),
            ("idx_data_mining_type", "CREATE INDEX IF NOT EXISTS idx_data_mining_type ON data_mining(type)"),
            ("idx_data_mining_is_processed", "CREATE INDEX IF NOT EXISTS idx_data_mining_is_processed ON data_mining(is_processed)")
        ]
        
        for index_name, index_query in indexes:
            try:
                await conn.execute(index_query)
                logger.info(f"'{index_name}' indeksi oluşturuldu veya zaten mevcut")
            except Exception as e:
                logger.error(f"İndeks oluşturma hatası ({index_name}): {str(e)}")
        
        # Verileri düzelt
        # 1. Data alanı JSON formatında mı kontrol et
        rows = await conn.fetch(
            "SELECT mining_id, data FROM data_mining WHERE data IS NOT NULL LIMIT 1000"
        )
        
        fixed_data_count = 0
        for row in rows:
            try:
                mining_id = row['mining_id']
                data = row['data']
                
                # Veriyi JSON olarak parse etmeye çalış
                try:
                    json_data = json.loads(data)
                    # Zaten JSON - işlem gerekmiyor
                except (json.JSONDecodeError, TypeError):
                    # JSON değil, string ise JSON'a çevir
                    if isinstance(data, str) and data.strip():
                        # Basit string ise JSON formatına çevir
                        json_data = {"value": data, "fixed_at": datetime.now().isoformat()}
                        await conn.execute(
                            "UPDATE data_mining SET data = $1 WHERE mining_id = $2",
                            json.dumps(json_data), mining_id
                        )
                        fixed_data_count += 1
            except Exception as e:
                logger.error(f"Veri düzeltme hatası (ID: {row['mining_id']}): {str(e)}")
        
        logger.info(f"{fixed_data_count} adet veri JSON formatına dönüştürüldü")
        
        # 2. Type kolonu düzeltme
        rows = await conn.fetch(
            "SELECT mining_id, type, telegram_id, user_id, group_id FROM data_mining WHERE type IS NULL"
        )
        
        fixed_type_count = 0
        for row in rows:
            try:
                mining_id = row['mining_id']
                
                # Type değerini belirle
                new_type = None
                if row['group_id'] is not None:
                    new_type = 'group'
                elif row['user_id'] is not None or row['telegram_id'] is not None:
                    new_type = 'user'
                else:
                    new_type = 'unknown'
                
                # Type değerini güncelle
                await conn.execute(
                    "UPDATE data_mining SET type = $1 WHERE mining_id = $2",
                    new_type, mining_id
                )
                fixed_type_count += 1
            except Exception as e:
                logger.error(f"Type düzeltme hatası (ID: {row['mining_id']}): {str(e)}")
        
        logger.info(f"{fixed_type_count} adet kayıtta type değeri güncellendi")
        
        # Bağlantıyı kapat
        await conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Veritabanı işlemi sırasında hata: {str(e)}")
        return False

async def fix_telegram_users_table():
    """Telegram kullanıcıları tablosunu düzeltir"""
    logger.info("Telegram kullanıcıları tablosu düzeltiliyor...")
    
    try:
        # Veritabanına bağlan
        conn = await asyncpg.connect(get_db_url())
        
        # Tablo varlığını kontrol et
        check_table = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'telegram_users')"
        )
        
        if not check_table:
            logger.warning("telegram_users tablosu bulunamadı, oluşturuluyor...")
            
            # Tablo oluştur
            await conn.execute("""
                CREATE TABLE telegram_users (
                    user_id INTEGER PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    is_bot BOOLEAN DEFAULT FALSE,
                    is_premium BOOLEAN DEFAULT FALSE,
                    language_code VARCHAR(10),
                    phone VARCHAR(20),
                    bio TEXT,
                    first_seen TIMESTAMP DEFAULT NOW(),
                    last_seen TIMESTAMP DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT TRUE,
                    is_blocked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            logger.info("telegram_users tablosu oluşturuldu")
        
        # Data mining tablosundan kullanıcıları aktar
        rows = await conn.fetch("""
            SELECT DISTINCT telegram_id 
            FROM data_mining 
            WHERE telegram_id IS NOT NULL 
            AND type = 'user'
            AND telegram_id NOT IN (SELECT user_id FROM telegram_users)
        """)
        
        inserted_count = 0
        for row in rows:
            try:
                telegram_id = row['telegram_id']
                
                # Kullanıcıyı ekle
                await conn.execute("""
                    INSERT INTO telegram_users (
                        user_id, created_at, updated_at
                    ) VALUES ($1, NOW(), NOW())
                    ON CONFLICT (user_id) DO NOTHING
                """, telegram_id)
                
                inserted_count += 1
            except Exception as e:
                logger.error(f"Kullanıcı ekleme hatası (ID: {row['telegram_id']}): {str(e)}")
        
        logger.info(f"{inserted_count} adet kullanıcı telegram_users tablosuna eklendi")
        
        # İndeksler oluştur
        indexes = [
            ("idx_telegram_users_username", "CREATE INDEX IF NOT EXISTS idx_telegram_users_username ON telegram_users(username)"),
            ("idx_telegram_users_is_active", "CREATE INDEX IF NOT EXISTS idx_telegram_users_is_active ON telegram_users(is_active)")
        ]
        
        for index_name, index_query in indexes:
            try:
                await conn.execute(index_query)
                logger.info(f"'{index_name}' indeksi oluşturuldu veya zaten mevcut")
            except Exception as e:
                logger.error(f"İndeks oluşturma hatası ({index_name}): {str(e)}")
        
        # Bağlantıyı kapat
        await conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Veritabanı işlemi sırasında hata: {str(e)}")
        return False

async def fix_groups_table():
    """Gruplar tablosunu düzeltir"""
    logger.info("Gruplar tablosu düzeltiliyor...")
    
    try:
        # Veritabanına bağlan
        conn = await asyncpg.connect(get_db_url())
        
        # Tablo varlığını kontrol et
        check_table = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'groups')"
        )
        
        if not check_table:
            logger.warning("groups tablosu bulunamadı, oluşturuluyor...")
            
            # Tablo oluştur
            await conn.execute("""
                CREATE TABLE groups (
                    group_id INTEGER PRIMARY KEY,
                    name VARCHAR(255),
                    username VARCHAR(255),
                    description TEXT,
                    join_date TIMESTAMP DEFAULT NOW(),
                    last_message TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    member_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    last_error TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    permanent_error BOOLEAN DEFAULT FALSE,
                    is_target BOOLEAN DEFAULT FALSE,
                    retry_after TIMESTAMP,
                    is_admin BOOLEAN DEFAULT FALSE,
                    is_public BOOLEAN DEFAULT TRUE,
                    invite_link VARCHAR(255),
                    source VARCHAR(100),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            logger.info("groups tablosu oluşturuldu")
        
        # Eksik kolonları kontrol et ve ekle
        columns = [
            ("username", "VARCHAR(255)"),
            ("description", "TEXT"),
            ("is_admin", "BOOLEAN DEFAULT FALSE"),
            ("is_public", "BOOLEAN DEFAULT TRUE"),
            ("invite_link", "VARCHAR(255)"),
            ("source", "VARCHAR(100)")
        ]
        
        for column_name, column_type in columns:
            column_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'groups' AND column_name = $1)",
                column_name
            )
            
            if not column_exists:
                logger.warning(f"'{column_name}' kolonu ekleniyor...")
                await conn.execute(f"ALTER TABLE groups ADD COLUMN {column_name} {column_type}")
                logger.info(f"'{column_name}' kolonu eklendi")
        
        # Data mining tablosundan grupları aktar
        rows = await conn.fetch("""
            SELECT DISTINCT telegram_id 
            FROM data_mining 
            WHERE telegram_id IS NOT NULL 
            AND type = 'group'
            AND telegram_id NOT IN (SELECT group_id FROM groups)
        """)
        
        inserted_count = 0
        for row in rows:
            try:
                telegram_id = row['telegram_id']
                
                # Grup verilerini data_mining'den al
                group_data = await conn.fetchrow("""
                    SELECT data FROM data_mining 
                    WHERE telegram_id = $1 AND type = 'group' 
                    ORDER BY mining_id DESC LIMIT 1
                """, telegram_id)
                
                name = None
                username = None
                description = None
                
                if group_data and group_data['data']:
                    try:
                        data_json = json.loads(group_data['data'])
                        name = data_json.get('name')
                        username = data_json.get('username')
                        description = data_json.get('description')
                    except:
                        pass
                
                # Grubu ekle
                await conn.execute("""
                    INSERT INTO groups (
                        group_id, name, username, description, 
                        created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, NOW(), NOW())
                    ON CONFLICT (group_id) DO NOTHING
                """, telegram_id, name or f"Group {telegram_id}", username, description)
                
                inserted_count += 1
            except Exception as e:
                logger.error(f"Grup ekleme hatası (ID: {row['telegram_id']}): {str(e)}")
        
        logger.info(f"{inserted_count} adet grup groups tablosuna eklendi")
        
        # İndeksler oluştur
        indexes = [
            ("idx_groups_is_active", "CREATE INDEX IF NOT EXISTS idx_groups_is_active ON groups(is_active)"),
            ("idx_groups_is_target", "CREATE INDEX IF NOT EXISTS idx_groups_is_target ON groups(is_target)"),
            ("idx_groups_is_admin", "CREATE INDEX IF NOT EXISTS idx_groups_is_admin ON groups(is_admin)")
        ]
        
        for index_name, index_query in indexes:
            try:
                await conn.execute(index_query)
                logger.info(f"'{index_name}' indeksi oluşturuldu veya zaten mevcut")
            except Exception as e:
                logger.error(f"İndeks oluşturma hatası ({index_name}): {str(e)}")
        
        # Bağlantıyı kapat
        await conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Veritabanı işlemi sırasında hata: {str(e)}")
        return False

async def main():
    """Ana fonksiyon"""
    logger.info("Veri madenciliği tabloları düzeltme aracı başlatılıyor...")
    
    # Tabloları düzelt
    success_data_mining = await fix_data_mining_table()
    success_telegram_users = await fix_telegram_users_table()
    success_groups = await fix_groups_table()
    
    if success_data_mining and success_telegram_users and success_groups:
        logger.info("İşlem başarıyla tamamlandı, tüm tablolar düzeltildi")
    else:
        logger.warning("İşlem tamamlandı, ancak bazı tablolarda hatalar oluştu")

if __name__ == "__main__":
    asyncio.run(main()) 