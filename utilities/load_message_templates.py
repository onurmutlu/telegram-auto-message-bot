#!/usr/bin/env python3
"""
Message templates veri yükleme scripti.
Bu script, json şablonlarını veritabanına yükler.
"""

import os
import json
import asyncio
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# .env dosyasını yükle
load_dotenv(override=True)

async def load_templates():
    """JSON şablonlarını veritabanına yükle"""
    
    # Veritabanı bağlantısı
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASS = os.getenv('DB_PASSWORD', 'postgres')
    DB_NAME = os.getenv('DB_NAME', 'telegram_bot')
    
    # SQLAlchemy bağlantı URL'si
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    print(f"Veritabanına bağlanılıyor: {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    
    # Engine oluştur
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # messages.json dosyasını yükle
        print("\nMessages.json dosyası yükleniyor...")
        with open('data/messages.json', 'r', encoding='utf-8') as f:
            messages_data = json.load(f)
            
        template_count = 0
        for category, messages in messages_data.items():
            print(f"  '{category}' kategorisinden {len(messages)} şablon işleniyor...")
            for message in messages:
                # Şablonun var olup olmadığını kontrol et
                check_query = text("""
                    SELECT id FROM message_templates 
                    WHERE content = :content AND category = :category
                """)
                
                result = session.execute(check_query, {
                    "content": message,
                    "category": category
                })
                
                if not result.fetchone():
                    # Şablonu ekle
                    insert_query = text("""
                        INSERT INTO message_templates (content, category, type, is_active, created_at, updated_at)
                        VALUES (:content, :category, :type, :is_active, :created_at, :updated_at)
                    """)
                    
                    session.execute(insert_query, {
                        "content": message,
                        "category": category,
                        "type": "general" if category not in ["dm_invite", "promo_general", "promo_event", "promo_offer", "promo_info"] else "dm" if category == "dm_invite" else "promo",
                        "is_active": True,
                        "created_at": datetime.now(),
                        "updated_at": datetime.now()
                    })
                    
                    template_count += 1
        
        # dm_templates.json dosyasını yükle
        print("\nDM Templates dosyası yükleniyor...")
        dm_count = 0
        try:
            with open('data/dm_templates.json', 'r', encoding='utf-8') as f:
                dm_data = json.load(f)
                
            for category, messages in dm_data.items():
                print(f"  '{category}' kategorisinden {len(messages)} DM şablonu işleniyor...")
                for message in messages:
                    # Şablonun var olup olmadığını kontrol et
                    check_query = text("""
                        SELECT id FROM message_templates 
                        WHERE content = :content AND category = :category
                    """)
                    
                    result = session.execute(check_query, {
                        "content": message,
                        "category": category
                    })
                    
                    if not result.fetchone():
                        # Şablonu ekle
                        insert_query = text("""
                            INSERT INTO message_templates (content, category, type, is_active, created_at, updated_at)
                            VALUES (:content, :category, :type, :is_active, :created_at, :updated_at)
                        """)
                        
                        session.execute(insert_query, {
                            "content": message,
                            "category": category,
                            "type": "dm",
                            "is_active": True,
                            "created_at": datetime.now(),
                            "updated_at": datetime.now()
                        })
                        
                        dm_count += 1
        except FileNotFoundError:
            print("DM Templates dosyası bulunamadı, bu adım atlanıyor.")
        
        # promo_templates.json dosyasını yükle
        print("\nPromo Templates dosyası yükleniyor...")
        promo_count = 0
        try:
            with open('data/promo_templates.json', 'r', encoding='utf-8') as f:
                promo_data = json.load(f)
                
            for category, messages in promo_data.items():
                print(f"  '{category}' kategorisinden {len(messages)} promo şablonu işleniyor...")
                for message in messages:
                    # Şablonun var olup olmadığını kontrol et
                    check_query = text("""
                        SELECT id FROM message_templates 
                        WHERE content = :content AND category = :category
                    """)
                    
                    result = session.execute(check_query, {
                        "content": message,
                        "category": category
                    })
                    
                    if not result.fetchone():
                        # Şablonu ekle
                        insert_query = text("""
                            INSERT INTO message_templates (content, category, type, is_active, created_at, updated_at)
                            VALUES (:content, :category, :type, :is_active, :created_at, :updated_at)
                        """)
                        
                        session.execute(insert_query, {
                            "content": message,
                            "category": category,
                            "type": "promo",
                            "is_active": True,
                            "created_at": datetime.now(),
                            "updated_at": datetime.now()
                        })
                        
                        promo_count += 1
        except FileNotFoundError:
            print("Promo Templates dosyası bulunamadı, bu adım atlanıyor.")
        
        # Değişiklikleri kaydet
        session.commit()
        
        print(f"\nToplam {template_count} genel şablon, {dm_count} DM şablonu ve {promo_count} promo şablonu yüklendi.")
        
    except Exception as e:
        print(f"Hata oluştu: {str(e)}")
        session.rollback()
    finally:
        session.close()
        print("\nİşlem tamamlandı.")

if __name__ == "__main__":
    asyncio.run(load_templates()) 