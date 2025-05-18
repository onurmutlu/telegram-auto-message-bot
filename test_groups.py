#!/usr/bin/env python3
"""
Telegram bot grupları ve mesajlaşma işlevselliğini test eder.
"""
import asyncio
import logging
import sys
import os
import traceback

# Ana dizini ekle
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def test_dialogs():
    """Tüm grupları ve sohbetleri listeler."""
    from app.core.config import settings
    from telethon import TelegramClient
    
    # Client oluştur
    client = None
    try:
        # API kimlik bilgileri
        api_id = settings.API_ID
        api_hash = settings.API_HASH
        if hasattr(api_hash, 'get_secret_value'):
            api_hash = api_hash.get_secret_value()
            
        session_name = settings.SESSION_NAME
        
        # Oturum yolu
        if hasattr(settings, "SESSIONS_DIR"):
            session_path = settings.SESSIONS_DIR / f"{session_name}.session"
        else:
            session_path = f"{session_name}.session"
            
        print(f"Oturum dosyası: {session_path}")
        
        # TelegramClient oluştur
        client = TelegramClient(
            session_path, 
            api_id, 
            api_hash,
            device_model="Dialog Tester",
            system_version="1.0",
            app_version="1.0"
        )
        
        # Bağlan
        print("Telegram API'ye bağlanılıyor...")
        await client.connect()
        
        # Bağlantı durumunu kontrol et
        if not client.is_connected():
            print("Bağlantı kurulamadı!")
            return
            
        print("Bağlantı başarılı!")
        
        # Oturum açık mı kontrol et
        authorized = await client.is_user_authorized()
        if not authorized:
            print("Oturum açık değil! Lütfen önce oturum açın.")
            return
            
        print("Oturum açık.")
        
        # Kullanıcı bilgilerini al
        me = await client.get_me()
        print(f"Kullanıcı: {me.first_name} (ID: {me.id}, Kullanıcı adı: @{me.username or 'Yok'})")
        
        # Diyalogları (gruplar, sohbetler, kanallar) çek
        print("\nDiyaloglar çekiliyor...")
        dialogs = await client.get_dialogs()
        
        print(f"\n{len(dialogs)} diyalog bulundu:")
        
        # Tür bazında sayı
        groups = [d for d in dialogs if d.is_group]
        channels = [d for d in dialogs if d.is_channel]
        users = [d for d in dialogs if d.is_user]
        
        print(f"Gruplar: {len(groups)}")
        print(f"Kanallar: {len(channels)}")
        print(f"Kullanıcılar: {len(users)}")
        
        # İlk 10 diyaloğu listele
        print("\nİlk 10 diyalog:")
        for i, dialog in enumerate(dialogs[:10], 1):
            entity_type = "Grup" if dialog.is_group else "Kanal" if dialog.is_channel else "Kullanıcı"
            print(f"{i}. {dialog.name} ({entity_type}, ID: {dialog.id})")
            
            # Son mesajı göster
            if dialog.message:
                if hasattr(dialog.message, 'message') and dialog.message.message:
                    last_msg = dialog.message.message[:50] + "..." if len(dialog.message.message) > 50 else dialog.message.message
                    print(f"   Son mesaj: {last_msg}")
                    print(f"   Tarih: {dialog.message.date}")
        
        # Test mesajı gönderme seçeneği
        send_test = input("\nTest mesajı göndermek ister misiniz? (e/h): ").lower() == 'e'
        
        if send_test:
            # Hedef seçimi
            target_index = int(input("Hangi diyaloğa mesaj göndermek istersiniz? (1-10): ")) - 1
            
            if 0 <= target_index < min(10, len(dialogs)):
                target = dialogs[target_index]
                message = input("Gönderilecek mesaj: ")
                
                print(f"\n'{target.name}' adlı diyaloğa mesaj gönderiliyor...")
                await client.send_message(target.entity, message)
                print("Mesaj gönderildi!")
            else:
                print("Geçersiz diyalog seçimi.")
        
    except Exception as e:
        print(f"Hata: {str(e)}")
        traceback.print_exc()
    finally:
        # Bağlantıyı kapat
        if client and client.is_connected():
            await client.disconnect()
            print("\nBağlantı kapatıldı.")

if __name__ == "__main__":
    asyncio.run(test_dialogs())
