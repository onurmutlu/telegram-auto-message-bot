#!/usr/bin/env python3
"""
Şablon JSON dosyalarını veritabanına yükleyen script.
Kullanım: python load_templates.py
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
from app.models.message_template import MessageTemplate

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("template_load.log")
    ]
)

logger = logging.getLogger(__name__)

# JSON dosya yolları
DATA_DIR = Path(__file__).parents[2] / "data"
MESSAGES_JSON = DATA_DIR / "messages.json"
DM_TEMPLATES_JSON = DATA_DIR / "dm_templates.json"
PROMO_TEMPLATES_JSON = DATA_DIR / "promo_templates.json"

async def load_engagement_templates(db: AsyncSession):
    """Mesaj şablonlarını yükle."""
    logger.info("Engagement şablonları yükleniyor...")
    
    try:
        with open(MESSAGES_JSON, 'r', encoding='utf-8') as file:
            templates_data = json.load(file)
            
        count = 0
        for category, templates in templates_data.items():
            engagement_rate = 0.5  # Default değer
            
            # Kategoriye göre engagement rate ayarla
            if category == "engage":
                engagement_rate = 0.9
            elif category in ["question", "dm_invite"]:
                engagement_rate = 0.8
            elif category in ["welcome", "holiday"]:
                engagement_rate = 0.7
            elif category in ["tips", "reminder"]:
                engagement_rate = 0.6
            
            for template in templates:
                # Şablonu veritabanında kontrol et
                query = """
                    SELECT id FROM message_templates 
                    WHERE content = :content AND type = :type
                """
                result = await db.execute(query, {"content": template, "type": category})
                existing = result.fetchone()
                
                if not existing:
                    # Şablon yoksa ekle
                    query = """
                        INSERT INTO message_templates (
                            content, type, engagement_rate, is_active, created_at, updated_at
                        ) VALUES (
                            :content, :type, :engagement_rate, true, NOW(), NOW()
                        )
                    """
                    await db.execute(query, {
                        "content": template,
                        "type": category if category != "engage" else "engagement",
                        "engagement_rate": engagement_rate
                    })
                    count += 1
        
        await db.commit()
        logger.info(f"{count} engagement şablonu yüklendi.")
        
    except Exception as e:
        logger.error(f"Engagement şablonları yüklenirken hata: {str(e)}", exc_info=True)
        await db.rollback()

async def load_dm_templates(db: AsyncSession):
    """DM şablonlarını yükle."""
    logger.info("DM şablonları yükleniyor...")
    
    try:
        with open(DM_TEMPLATES_JSON, 'r', encoding='utf-8') as file:
            templates_data = json.load(file)
            
        count = 0
        for category, templates in templates_data.items():
            for template in templates:
                # Şablonu veritabanında kontrol et
                query = """
                    SELECT id FROM message_templates 
                    WHERE content = :content AND type = :type
                """
                result = await db.execute(query, {"content": template, "type": f"dm_{category}"})
                existing = result.fetchone()
                
                if not existing:
                    # Şablon yoksa ekle
                    query = """
                        INSERT INTO message_templates (
                            content, type, engagement_rate, is_active, created_at, updated_at
                        ) VALUES (
                            :content, :type, :engagement_rate, true, NOW(), NOW()
                        )
                    """
                    await db.execute(query, {
                        "content": template,
                        "type": f"dm_{category}",
                        "engagement_rate": 0.7  # DM şablonları için varsayılan değer
                    })
                    count += 1
        
        await db.commit()
        logger.info(f"{count} DM şablonu yüklendi.")
        
    except Exception as e:
        logger.error(f"DM şablonları yüklenirken hata: {str(e)}", exc_info=True)
        await db.rollback()

async def load_promo_templates(db: AsyncSession):
    """Tanıtım şablonlarını yükle."""
    logger.info("Tanıtım şablonları yükleniyor...")
    
    try:
        with open(PROMO_TEMPLATES_JSON, 'r', encoding='utf-8') as file:
            templates_data = json.load(file)
            
        count = 0
        for category, templates in templates_data.items():
            for template in templates:
                # Şablonu veritabanında kontrol et
                query = """
                    SELECT id FROM message_templates 
                    WHERE content = :content AND type = :type
                """
                result = await db.execute(query, {"content": template, "type": "promo" if "promo" in category else category})
                existing = result.fetchone()
                
                if not existing:
                    # Şablon yoksa ekle
                    query = """
                        INSERT INTO message_templates (
                            content, type, engagement_rate, is_active, created_at, updated_at
                        ) VALUES (
                            :content, :type, :engagement_rate, true, NOW(), NOW()
                        )
                    """
                    await db.execute(query, {
                        "content": template,
                        "type": "promo" if "promo" in category else category,
                        "engagement_rate": 0.6  # Promo şablonları için varsayılan değer
                    })
                    count += 1
        
        await db.commit()
        logger.info(f"{count} tanıtım şablonu yüklendi.")
        
    except Exception as e:
        logger.error(f"Tanıtım şablonları yüklenirken hata: {str(e)}", exc_info=True)
        await db.rollback()

async def ensure_table_exists(db: AsyncSession):
    """message_templates tablosunun varlığını kontrol et ve gerekirse oluştur."""
    try:
        # Tablo var mı kontrol et
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'message_templates'
            );
        """
        result = await db.execute(query)
        table_exists = result.scalar()
        
        if not table_exists:
            # Tablo yoksa oluştur
            logger.info("message_templates tablosu oluşturuluyor...")
            
            create_table_query = """
                CREATE TABLE IF NOT EXISTS message_templates (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    engagement_rate FLOAT DEFAULT 0.0,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """
            await db.execute(create_table_query)
            await db.commit()
            logger.info("message_templates tablosu oluşturuldu.")
        else:
            logger.info("message_templates tablosu zaten mevcut.")
            
    except Exception as e:
        logger.error(f"Tablo kontrolü sırasında hata: {str(e)}", exc_info=True)
        await db.rollback()

async def main():
    """Ana fonksiyon."""
    logger.info("Şablon yükleme işlemi başlatılıyor...")
    
    # Veritabanı bağlantısı
    db = await get_db().__anext__()
    
    try:
        # Tablo kontrolü
        await ensure_table_exists(db)
        
        # Şablonları yükle
        await load_engagement_templates(db)
        await load_dm_templates(db)
        await load_promo_templates(db)
        
        logger.info("Tüm şablonlar başarıyla yüklendi.")
        
    except Exception as e:
        logger.error(f"Şablon yükleme işlemi sırasında hata: {str(e)}", exc_info=True)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main()) 