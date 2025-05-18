#!/usr/bin/env python3
"""
Telegram mesajları listeleme örneği.
"""

import os
import json
import asyncio
from datetime import datetime, timedelta

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# .env dosyasını yükle
load_dotenv(override=True)

async def list_messages_from_db():
    """Veritabanından örnek mesajları listele"""
    
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
        # Grupları listeleme
        print("\n--- GRUPLAR ---")
        groups_query = text("""
            SELECT id, group_id, name AS title, member_count, is_active, created_at
            FROM groups 
            ORDER BY created_at DESC
            LIMIT 10;
        """)
        
        groups = session.execute(groups_query).fetchall()
        if groups:
            for group in groups:
                print(f"ID: {group.id}, Group ID: {group.group_id}, İsim: {group.title}, Üye: {group.member_count}, Aktif: {group.is_active}")
        else:
            print("Hiç grup bulunamadı.")
        
        # Kullanıcıları listeleme
        print("\n--- KULLANICILAR ---")
        users_query = text("""
            SELECT id, user_id, username, first_name, last_name, is_active, created_at
            FROM users
            ORDER BY created_at DESC
            LIMIT 10;
        """)
        
        users = session.execute(users_query).fetchall()
        if users:
            for user in users:
                print(f"ID: {user.id}, User ID: {user.user_id}, Kullanıcı Adı: {user.username}, İsim: {user.first_name} {user.last_name or ''}")
        else:
            print("Hiç kullanıcı bulunamadı.")
        
        # Mesajları listeleme
        print("\n--- MESAJLAR ---")
        messages_query = text("""
            SELECT m.id, m.content, m.message_type as type, m.sent_at, m.created_at,
                   g.name as group_title
            FROM messages m
            LEFT JOIN groups g ON m.group_id = g.group_id
            ORDER BY m.created_at DESC
            LIMIT 10;
        """)
        
        messages = session.execute(messages_query).fetchall()
        if messages:
            for msg in messages:
                content = msg.content[:50] + "..." if msg.content and len(msg.content) > 50 else msg.content
                print(f"ID: {msg.id}, Grup: {msg.group_title}, Tip: {msg.type}, İçerik: {content}")
        else:
            print("Hiç mesaj bulunamadı.")
        
        # Şablonları listeleme
        print("\n--- ŞABLONLAR ---")
        templates_query = text("""
            SELECT id, type, category, content, is_active
            FROM message_templates
            ORDER BY type, category
            LIMIT 10;
        """)
        
        templates = session.execute(templates_query).fetchall()
        if templates:
            for tmpl in templates:
                content = tmpl.content[:50] + "..." if tmpl.content and len(tmpl.content) > 50 else tmpl.content
                print(f"ID: {tmpl.id}, Tip: {tmpl.type}, Kategori: {tmpl.category}, İçerik: {content}")
        else:
            print("Hiç şablon bulunamadı.")
        
        # JSON şablonlarından örnek mesajlar gösterme
        print("\n--- JSON ŞABLONLARINDAN ÖRNEKLER ---")
        try:
            # messages.json dosyasını oku
            with open('data/messages.json', 'r', encoding='utf-8') as f:
                messages_data = json.load(f)
                
            # Her kategoriden bir örnek göster
            for category, msgs in messages_data.items():
                if msgs:
                    print(f"\nKategori: {category}")
                    sample = msgs[0]
                    print(f"Örnek: {sample}")
        except Exception as e:
            print(f"JSON şablonları okunurken hata: {str(e)}")
            
    except Exception as e:
        print(f"Veritabanı sorgusu sırasında hata: {str(e)}")
    finally:
        session.close()
        print("\nİşlem tamamlandı.")

if __name__ == "__main__":
    asyncio.run(list_messages_from_db()) 