#!/usr/bin/env python3

import os
import sys
import asyncio
from telethon import TelegramClient, errors
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Telethon için gerekli bilgiler
API_ID = int(os.environ.get('API_ID', '23692263'))
API_HASH = os.environ.get('API_HASH', 'ff5d6053b266f78d1293f9343f40e77e')
PHONE_NUMBER = os.environ.get('PHONE', '+905382617727')
SESSION_PATH = 'session/anon'  # Basitleştirilmiş - anon session kullan
TARGET_GROUPS = os.environ.get('ADMIN_GROUPS', '').split(',')

# Eğer ADMIN_GROUPS boşsa, varsayılan gruplara veya kendinize mesaj gönderin
if not any(group.strip() for group in TARGET_GROUPS):
    print("Hedef grup bulunamadı, kendinize mesaj gönderilecek...")
    TARGET_GROUPS = ['me']  # Kendinize mesaj göndermek için 'me' kullanın

async def send_test_messages():
    """Test mesajları gönderir."""
    print("Test mesajı gönderme betiği çalışıyor...")
    print(f"API ID: {API_ID}")
    print(f"Hedef gruplar: {TARGET_GROUPS}")
    print(f"Session yolu: {SESSION_PATH}")
    
    # Session dizinini oluştur (eğer yoksa)
    os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
    
    # TelegramClient oluştur
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    try:
        # Bağlan
        print("Telegram'a bağlanılıyor...")
        await client.connect()
        
        # Giriş kontrolü
        if not await client.is_user_authorized():
            print(f"Oturum bulunamadı! Telefon numarası ile giriş yapılıyor: {PHONE_NUMBER}")
            await client.send_code_request(PHONE_NUMBER)
            code = input("Doğrulama kodunu girin: ")
            await client.sign_in(PHONE_NUMBER, code)
            print("Oturum başarıyla açıldı ve kaydedildi!")
        
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
                
                if group.lower() == 'me':
                    # Kendinize mesaj gönderin
                    entity = me
                else:
                    # Grup, kanal veya kullanıcı
                    try:
                        entity = await client.get_entity(group)
                    except ValueError as e:
                        # İlk deneme başarısız olduysa, sayı olarak dene
                        try:
                            entity = int(group.strip())
                        except:
                            raise e
                
                message = f"🧪 TEST MESAJI 🧪\n\nBu bir test mesajıdır. Bot çalışıyor ve bu mesaj {me.first_name} tarafından gönderildi."
                
                # Mesajı gönder
                await client.send_message(entity, message)
                print(f"✅ Başarılı! '{group}' grubuna mesaj gönderildi")
                
                # Session string'i oluştur ve göster
                session_string = client.session.save()
                print(f"\nSession String (veritabanına kaydedin):\n{session_string}\n")
                
                # Veritabanına kaydet
                try:
                    import sqlite3
                    conn = sqlite3.connect("data/users.db")
                    cursor = conn.cursor()
                    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY, 
                        value TEXT
                    )''')
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                                ("session_string", session_string))
                    conn.commit()
                    conn.close()
                    print(f"Session string veritabanına kaydedildi!")
                except Exception as e:
                    print(f"Veritabanına kaydederken hata: {e}")
                
            except errors.FloodWaitError as e:
                print(f"⚠️ FloodWait hatası! {e.seconds} saniye beklemeniz gerekiyor.")
            except Exception as e:
                print(f"❌ Hata! '{group}' grubuna mesaj gönderilemedi: {str(e)}")
    
    except Exception as e:
        print(f"Genel hata: {str(e)}")
        import traceback
        traceback.print_exc()
    
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