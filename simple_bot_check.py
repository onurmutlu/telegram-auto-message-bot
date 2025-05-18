#!/usr/bin/env python3
"""
Telegram botunun çalışıp çalışmadığını test eder.
Bu daha basit ve doğrudan bir testtir.
"""
import os
import sys
import asyncio
from pathlib import Path

# Ana dizini ekle
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Settings'i yükle
from app.core.config import settings

async def run_simple_test():
    print("BOT DURUM KONTROL")
    print("="*50)
    
    # API bilgileri
    api_id = settings.API_ID
    api_hash = settings.API_HASH
    if hasattr(api_hash, 'get_secret_value'):
        api_hash = api_hash.get_secret_value()
    
    print(f"API ID: {api_id}")
    print(f"API HASH: {api_hash[:4]}...{api_hash[-4:]}")
    
    # Oturum ve bağlantı
    from telethon import TelegramClient, functions
    
    session_path = f"{settings.SESSION_NAME}"
    if hasattr(settings, "SESSIONS_DIR"):
        session_path = settings.SESSIONS_DIR / f"{settings.SESSION_NAME}"
    
    print(f"Oturum: {session_path}")
    
    client = TelegramClient(session_path, api_id, api_hash)
    
    try:
        print("Bağlanılıyor...")
        await client.connect()
        
        if not client.is_connected():
            print("Bağlantı kurulamadı!")
            return
        
        print("Bağlantı: TAMAM")
        
        is_authorized = await client.is_user_authorized()
        print(f"Oturum Açık: {'EVET' if is_authorized else 'HAYIR'}")
        
        if is_authorized:
            me = await client.get_me()
            print(f"\nKullanıcı: {me.first_name} {me.last_name or ''}")
            print(f"ID: {me.id}")
            print(f"Kullanıcı adı: @{me.username or 'Yok'}")
            
            # Dialog sayılarını kontrol et
            dialogs = await client.get_dialogs()
            groups = [d for d in dialogs if d.is_group]
            channels = [d for d in dialogs if d.is_channel]
            users = [d for d in dialogs if d.is_user]
            
            print(f"\nToplam: {len(dialogs)} diyalog")
            print(f"Gruplar: {len(groups)}")
            print(f"Kanallar: {len(channels)}")
            print(f"Kullanıcılar: {len(users)}")
            
            # İlk 3 grubu göster
            if groups:
                print("\nİlk 3 Grup:")
                for i, group in enumerate(groups[:3], 1):
                    print(f"{i}. {group.name} (ID: {group.id})")
                    
                    # Son bir kaç mesajı göster
                    try:
                        messages = await client.get_messages(group.entity, limit=3)
                        if messages:
                            print("  Son mesajlar:")
                            for msg in messages:
                                if hasattr(msg, 'message') and msg.message:
                                    sender = await client.get_entity(msg.from_id.user_id) if msg.from_id and hasattr(msg.from_id, 'user_id') else None
                                    sender_name = f"{sender.first_name}" if sender else "Bilinmeyen"
                                    text = msg.message[:50] + "..." if len(msg.message) > 50 else msg.message
                                    print(f"    - {sender_name}: {text}")
                    except Exception as e:
                        print(f"  Mesaj alınamadı: {e}")
            else:
                print("\nHiç grup bulunamadı!")
            
    except Exception as e:
        print(f"Hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client.is_connected():
            await client.disconnect()
        print("\nBağlantı kapatıldı.")

if __name__ == "__main__":
    asyncio.run(run_simple_test())
