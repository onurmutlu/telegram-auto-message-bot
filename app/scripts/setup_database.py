#!/usr/bin/env python3
"""
Veritabanı yapısını oluşturan script.
Bu script, tüm gerekli tabloları oluşturur ve ilk kullanıcı, grup vb. verileri ekler.
Kullanım: python setup_database.py
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import get_db
from app.core.config import settings

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("db_setup.log")
    ]
)

logger = logging.getLogger(__name__)

async def create_tables(db: AsyncSession):
    """Tüm tabloları oluştur."""
    logger.info("Tablolar oluşturuluyor...")
    
    try:
        # users tablosu
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                is_active BOOLEAN DEFAULT true,
                is_blocked BOOLEAN DEFAULT false,
                messages_received INT DEFAULT 0,
                messages_sent INT DEFAULT 0,
                promos_sent INT DEFAULT 0,
                last_activity_at TIMESTAMP,
                last_dm_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # groups tablosu
        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL UNIQUE,
                title VARCHAR(255) NOT NULL,
                username VARCHAR(255),
                description TEXT,
                invite_link VARCHAR(255),
                member_count INT DEFAULT 0,
                is_active BOOLEAN DEFAULT true,
                is_banned BOOLEAN DEFAULT false,
                is_joined BOOLEAN DEFAULT true,
                is_admin BOOLEAN DEFAULT false,
                category VARCHAR(50),
                priority INT DEFAULT 0,
                engagement_rate FLOAT DEFAULT 0.0,
                last_activity_at TIMESTAMP,
                last_promo_at TIMESTAMP,
                last_error TEXT,
                promo_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # group_cooldowns tablosu
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_cooldowns (
                id SERIAL PRIMARY KEY,
                group_id INT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                until TIMESTAMP NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(group_id)
            );
        """)
        
        # message_templates tablosu
        await db.execute("""
            CREATE TABLE IF NOT EXISTS message_templates (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                type VARCHAR(50) NOT NULL,
                engagement_rate FLOAT DEFAULT 0.0,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # messages tablosu
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                group_id INT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                message_id BIGINT,
                user_id BIGINT,
                reply_to_message_id BIGINT,
                content TEXT,
                template_id INT REFERENCES message_templates(id),
                type VARCHAR(50) DEFAULT 'text',
                status VARCHAR(50) DEFAULT 'sent',
                error TEXT,
                sent_at TIMESTAMP,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # user_interactions tablosu
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_interactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                group_id BIGINT,
                message_id BIGINT,
                interaction_type VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # user_dm_activities tablosu
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_dm_activities (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                content TEXT,
                message_type VARCHAR(50) NOT NULL,
                response_to TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # services tablosu
        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price DECIMAL(10,2) NOT NULL,
                priority INT DEFAULT 0,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        await db.commit()
        logger.info("Tablolar başarıyla oluşturuldu.")
        
    except Exception as e:
        logger.error(f"Tablo oluşturma hatası: {str(e)}", exc_info=True)
        await db.rollback()

async def add_demo_data(db: AsyncSession):
    """Demo verileri ekle."""
    logger.info("Demo veriler ekleniyor...")
    
    try:
        # Demo grup ekle
        await db.execute("""
            INSERT INTO groups (
                chat_id, title, username, description, invite_link, 
                member_count, is_active, is_admin, category, priority
            ) VALUES (
                -1001234567890, 'Demo Grup', 'demo_grup', 'Bu bir demo gruptur', 
                't.me/joinchat/demo_invite', 
                100, true, true, 'test', 10
            )
            ON CONFLICT (chat_id) DO NOTHING;
        """)
        
        # Demo servis ekle
        await db.execute("""
            INSERT INTO services (
                name, description, price, priority, is_active
            ) VALUES
                ('Premium Üyelik', 'Tüm özelliklere erişim sağlayan premium üyelik', 49.90, 10, true),
                ('Grup Yönetimi', 'Telegram gruplarınızın profesyonel yönetimi', 99.90, 5, true),
                ('Bot Geliştirme', 'Özel Telegram bot geliştirme hizmeti', 199.90, 3, true)
            ON CONFLICT DO NOTHING;
        """)
        
        await db.commit()
        logger.info("Demo veriler başarıyla eklendi.")
        
    except Exception as e:
        logger.error(f"Demo veri ekleme hatası: {str(e)}", exc_info=True)
        await db.rollback()

async def check_database(db: AsyncSession):
    """Veritabanı bağlantısını ve yapısını kontrol et."""
    logger.info("Veritabanı bağlantısı kontrol ediliyor...")
    
    try:
        # Veritabanı bağlantısını kontrol et
        result = await db.execute("SELECT 1")
        if result.scalar() == 1:
            logger.info("Veritabanı bağlantısı başarılı.")
        else:
            logger.error("Veritabanı bağlantısı başarısız.")
            return False
            
        # Tabloları kontrol et
        tables = [
            "users", "groups", "group_cooldowns", "message_templates", 
            "messages", "user_interactions", "user_dm_activities", "services"
        ]
        
        for table in tables:
            query = f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{table}'
                );
            """
            result = await db.execute(query)
            if result.scalar():
                logger.info(f"'{table}' tablosu mevcut.")
            else:
                logger.warning(f"'{table}' tablosu bulunamadı!")
                return False
                
        return True
            
    except Exception as e:
        logger.error(f"Veritabanı kontrol hatası: {str(e)}", exc_info=True)
        return False

async def create_indexes(db: AsyncSession):
    """Veritabanı indekslerini oluştur."""
    logger.info("İndeksler oluşturuluyor...")
    
    try:
        # users tablosu indeksleri
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
            CREATE INDEX IF NOT EXISTS idx_users_last_activity ON users(last_activity_at);
            CREATE INDEX IF NOT EXISTS idx_users_last_dm ON users(last_dm_at);
        """)
        
        # groups tablosu indeksleri
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_groups_is_active ON groups(is_active);
            CREATE INDEX IF NOT EXISTS idx_groups_is_admin ON groups(is_admin);
            CREATE INDEX IF NOT EXISTS idx_groups_priority ON groups(priority);
            CREATE INDEX IF NOT EXISTS idx_groups_last_activity ON groups(last_activity_at);
        """)
        
        # message_templates tablosu indeksleri
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_templates_type ON message_templates(type);
            CREATE INDEX IF NOT EXISTS idx_templates_engagement ON message_templates(engagement_rate);
        """)
        
        # messages tablosu indeksleri
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_group_id ON messages(group_id);
            CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
            CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
        """)
        
        # user_interactions tablosu indeksleri
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_user_id ON user_interactions(user_id);
            CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON user_interactions(created_at);
        """)
        
        await db.commit()
        logger.info("İndeksler başarıyla oluşturuldu.")
        
    except Exception as e:
        logger.error(f"İndeks oluşturma hatası: {str(e)}", exc_info=True)
        await db.rollback()

async def main():
    """Ana fonksiyon."""
    logger.info("Veritabanı kurulumu başlatılıyor...")
    
    # Veritabanı bağlantısı
    db = await get_db().__anext__()
    
    try:
        # Veritabanı bağlantısını kontrol et
        db_ok = await check_database(db)
        
        if not db_ok:
            # Tabloları oluştur
            await create_tables(db)
            
            # İndeksleri oluştur
            await create_indexes(db)
            
            # Demo verileri ekle
            await add_demo_data(db)
            
            logger.info("Veritabanı kurulumu tamamlandı.")
            logger.info("Şimdi şablonları yüklemek için 'python app/scripts/load_templates.py' komutunu çalıştırın.")
        else:
            logger.info("Veritabanı zaten yapılandırılmış görünüyor. İşlem yapılmadı.")
            logger.info("Veritabanını sıfırlamak için önce tabloları düşürün ve bu scripti tekrar çalıştırın.")
            
    except Exception as e:
        logger.error(f"Veritabanı kurulumu sırasında hata: {str(e)}", exc_info=True)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main()) 