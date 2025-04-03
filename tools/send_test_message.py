#!/usr/bin/env python3

import os
import sys
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Telethon için gerekli bilgiler
API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
PHONE_NUMBER = os.environ.get('PHONE_NUMBER')
SESSION_PATH = os.environ.get('SESSION_PATH', 'runtime/sessions/bot_session')
TARGET_GROUPS = os.environ.get('ADMIN_GROUPS', '').split(',')

async def send_test_messages():
    """Test mesajları gönderir."""
    print("Test mesajı gönderme betiği çalışıyor...")
    print(f"API ID: {API_ID}")
    print(f"Hedef gruplar: {TARGET_GROUPS}")
    print(f"Session yolu: {SESSION_PATH}")
    
    # TelegramClient oluştur
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    try:
        # Bağlan
        print("Telegram'a bağlanılıyor...")
        await client.connect()
        
        # Giriş kontrolü
        if not await client.is_user_authorized():
            print(f"Oturum bulunamadı! Lütfen önce botu başlatın ve {PHONE_NUMBER} numaralı telefon ile giriş yapın.")
            return
        
        # Mesaj gönderme
        print("Oturum bulundu! Mesaj gönderiliyor...")
        
        me = await client.get_me()
        print(f"Gönderen: {me.username} ({me.first_name})")
        
        # Her grup için test mesajı gönder
        for group in TARGET_GROUPS:
            if not group.strip():
                continue
                
            try:
                print(f"'{group}' grubuna gönderiliyor...")
                entity = await client.get_entity(group)
                message = f"🧪 TEST MESAJI 🧪\n\nBu bir test mesajıdır. Bot çalışıyor ve bu mesaj {me.first_name} tarafından gönderildi.\nZaman: {asyncio.get_event_loop().time()}"
                
                # Mesajı gönder
                await client.send_message(entity, message)
                print(f"✅ Başarılı! '{group}' grubuna mesaj gönderildi")
            except Exception as e:
                print(f"❌ Hata! '{group}' grubuna mesaj gönderilemedi: {str(e)}")
    
    except Exception as e:
        print(f"Genel hata: {str(e)}")
    
    finally:
        # Bağlantıyı kapat
        await client.disconnect()
        print("İşlem tamamlandı.")

if __name__ == "__main__":
    # Windows için Policy ayarla
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    # Ana fonksiyonu çalıştır
    asyncio.run(send_test_messages())