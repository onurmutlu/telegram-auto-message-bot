#!/usr/bin/env python3
# filepath: /Users/siyahkare/code/telegram-bot/direct_user_auth.py
"""
Direkt olarak kullanıcı modunda Telegram kimlik doğrulaması testi
"""
import os
import asyncio
import logging
from telethon import TelegramClient, errors
import time
import dotenv

# Hata ayıklama loglaması
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TelegramUserAuth')
logger.setLevel(logging.DEBUG)

# .env dosyasını yükle 
dotenv.load_dotenv(override=True)

# Ortam değişkenlerini al
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')
SESSION_NAME = os.getenv('SESSION_NAME', 'telegram_session')

# Değerleri göster
print(f"Yüklenen değerler:")
print(f"API_ID: {API_ID}")
print(f"API_HASH: {API_HASH[:4]}...{API_HASH[-4:]}")
print(f"PHONE: {PHONE}")
print(f"SESSION_NAME: {SESSION_NAME}")
print("-" * 40)

# Sağlama kontrolü
if API_ID == 0 or not API_HASH or not PHONE:
    print("HATA: .env dosyasındaki değerler eksik veya hatalı!")
    print("Lütfen .env dosyasını kontrol edin ve gerekli değerleri ekleyin.")
    exit(1)

# Benzersiz oturum adı için timestamp ekle (session çakışmasını önlemek için)
UNIQUE_SESSION = f"{SESSION_NAME}_{int(time.time())}"

async def telegram_auth():
    """Telegram kullanıcı kimlik doğrulama süreci"""
    print(f"Telethon kullanıcı kimlik doğrulama testi başlıyor: {UNIQUE_SESSION}")
    
    # Oturum dosyalarını temizle (.session ve .session-journal)
    session_files = [f"{UNIQUE_SESSION}.session", f"{UNIQUE_SESSION}.session-journal"]
    for session_file in session_files:
        if os.path.exists(session_file):
            os.remove(session_file)
            print(f"Eski oturum dosyası silindi: {session_file}")
    
    # İstemci oluştur
    client = TelegramClient(
        UNIQUE_SESSION,
        API_ID,
        API_HASH,
        device_model='Python Test',
        app_version='1.0',
        system_version='1.0',
    )
    
    try:
        print("Bağlantı kuruluyor...")
        await client.connect()
        
        if not client.is_connected():
            print("HATA: Bağlantı kurulamadı!")
            return False
        
        print("Telegram sunucusuna bağlandı.")
        print("İstemci durumu: Bağlı")
        
        # Oturum açıp açmadığını kontrol et
        if await client.is_user_authorized():
            print("Kullanıcı zaten yetkili!")
            me = await client.get_me()
            print(f"Aktif kullanıcı: {me.first_name} {me.last_name if me.last_name else ''} (@{me.username if me.username else 'bilinmiyor'})")
            return True
        
        # Kod gönder
        print(f"Telefon numarası doğrulanıyor: {PHONE}")
        try:
            print("SMS kodu isteniyor...")
            result = await client.send_code_request(PHONE)
            print(f"Kod gönderildi! Tip: {result.type}, sonraki tip: {result.next_type}")
            print("Lütfen telefonunuza gelen doğrulama kodunu girin:")
            verification_code = input("Kodu girin: ")
            
            print(f"Doğrulama kodu girildi, giriş yapılıyor...")
            me = await client.sign_in(phone=PHONE, code=verification_code.strip())
            print(f"Giriş başarılı: {me.first_name} {me.last_name if me.last_name else ''}")
            return True
            
        except errors.PhoneCodeInvalidError:
            print("HATA: Girilen kod geçersiz!")
        except errors.PhoneCodeExpiredError:
            print("HATA: Kod süresi doldu. Lütfen tekrar deneyin.")
        except errors.SessionPasswordNeededError:
            print("2FA şifresi gerekli. Bu test iki faktörlü kimlik doğrulamayı desteklemiyor.")
        except errors.FloodWaitError as e:
            print(f"HATA: Flood wait. {e.seconds} saniye beklemelisiniz.")
        except Exception as e:
            print(f"HATA: Kod doğrulama sırasında beklenmeyen hata: {type(e).__name__}: {e}")
        
        return False
            
    except errors.ApiIdInvalidError:
        print("HATA: API ID veya API HASH geçersiz!")
        return False
    except errors.PhoneNumberInvalidError:
        print(f"HATA: Telefon numarası geçersiz: {PHONE}")
        return False
    except Exception as e:
        print(f"HATA: Beklenmeyen hata: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Bağlantıyı kapat
        if client and client.is_connected():
            print("Bağlantı kesiliyor...")
            await client.disconnect()
            print("Bağlantı kesildi.")
    
    return False

if __name__ == "__main__":
    try:
        success = asyncio.run(telegram_auth())
        if success:
            print("\nKullanıcı Kimlik Doğrulama Testi: BAŞARILI ✓")
            exit(0)
        else:
            print("\nKullanıcı Kimlik Doğrulama Testi: BAŞARISIZ ✗")
            exit(1)
    except KeyboardInterrupt:
        print("\nTest kullanıcı tarafından durduruldu.")
        exit(1)
