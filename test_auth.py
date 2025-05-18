#!/usr/bin/env python3
"""
Telegram kimlik doğrulama testi.
Bu script, onay kodu ve 2FA işlemlerini test eder.
"""
import os
import sys
import asyncio
import argparse
import logging

# Proje kök dizini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(BASE_DIR, "auth_test.log"))
    ]
)
logger = logging.getLogger("AuthTest")

async def test_auth(phone=None, code=None, password=None):
    """
    Telegram kimlik doğrulama testi.
    
    Args:
        phone (str): Telefon numarası (None ise ayarlardan alınır)
        code (str): Doğrulama kodu (None ise canlı alınır)
        password (str): 2FA şifresi (None ise canlı alınır)
    """
    print("="*50)
    print("TELEGRAM KİMLİK DOĞRULAMA TESTİ")
    print("="*50)
    
    try:
        # Ayarları yükle
        from app.core.config import settings
        
        # API bilgileri
        api_id = settings.API_ID
        api_hash = settings.API_HASH
        if hasattr(api_hash, 'get_secret_value'):
            api_hash = api_hash.get_secret_value()
        
        # Telefon numarası
        if not phone:
            phone = settings.PHONE
            if hasattr(phone, 'get_secret_value'):
                phone = phone.get_secret_value()
        
        # Oturum dizini
        if hasattr(settings, "SESSIONS_DIR"):
            session_dir = settings.SESSIONS_DIR
        else:
            session_dir = os.path.join(BASE_DIR, "app", "sessions")
        
        # Geçici test oturumu
        session_name = "auth_test_session"
        session_path = os.path.join(session_dir, session_name)
        
        print(f"API ID: {api_id}")
        print(f"API HASH: {api_hash[:4]}...{api_hash[-4:]}")
        print(f"Telefon: {phone}")
        print(f"Test oturumu: {session_path}")
        
        # Telethon importu
        from telethon import TelegramClient, errors
        
        # İçeri aktarılmış olabilecek safe_input'u kullan veya standart input kullan
        try:
            from input_helper import safe_input
        except ImportError:
            def safe_input(prompt, file_path=None, retry_count=3, retry_delay=1):
                return input(prompt)
        
        # Client oluştur
        client = TelegramClient(session_path, api_id, api_hash)
        
        try:
            print("\nTelegram API'ye bağlanılıyor...")
            await client.connect()
            
            if not client.is_connected():
                print("Bağlantı kurulamadı!")
                return
            
            print("Bağlantı KURULDU ✓")
            
            # Oturum açık mı kontrol et
            is_authorized = await client.is_user_authorized()
            print(f"Oturum Açık: {'EVET' if is_authorized else 'HAYIR'}")
            
            if is_authorized:
                print("Zaten kimlik doğrulaması yapılmış durumda.")
                me = await client.get_me()
                print(f"Kullanıcı: {me.first_name} (ID: {me.id})")
                return
            
            # Doğrulama kodu gönder
            print("\nDoğrulama kodu isteniyor...")
            await client.send_code_request(phone)
            
            # Doğrulama kodu al
            if not code:
                auth_code_file = os.path.join(BASE_DIR, ".telegram_auth_code")
                code = safe_input("Telegram'dan gelen doğrulama kodunu girin: ", 
                                file_path=auth_code_file)
            else:
                print(f"Parametre olarak gelen doğrulama kodu kullanılıyor: {code}")
            
            # Oturum aç
            try:
                print("\nDoğrulama kodu ile giriş yapılıyor...")
                await client.sign_in(phone, code)
                
                print("Kimlik doğrulama BAŞARILI ✓")
                me = await client.get_me()
                print(f"Kullanıcı: {me.first_name} (ID: {me.id})")
                return
                
            except errors.SessionPasswordNeededError:
                print("\n2FA şifresi gerekli!")
                
                # 2FA şifresi al
                if not password:
                    two_fa_file = os.path.join(BASE_DIR, ".telegram_2fa_password")
                    password = safe_input("2FA şifrenizi girin: ", file_path=two_fa_file)
                else:
                    print("Parametre olarak gelen 2FA şifresi kullanılıyor.")
                
                # 2FA ile giriş
                try:
                    print("2FA şifresi ile giriş yapılıyor...")
                    await client.sign_in(password=password)
                    
                    print("2FA ile kimlik doğrulama BAŞARILI ✓")
                    me = await client.get_me()
                    print(f"Kullanıcı: {me.first_name} (ID: {me.id})")
                    
                except errors.PasswordHashInvalidError:
                    print("Geçersiz 2FA şifresi!")
                
            except errors.PhoneCodeInvalidError:
                print("Geçersiz doğrulama kodu!")
            
        except Exception as e:
            print(f"Hata: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Geçici dosyaları temizle
            auth_code_file = os.path.join(BASE_DIR, ".telegram_auth_code")
            two_fa_file = os.path.join(BASE_DIR, ".telegram_2fa_password")
            
            for file_path in [auth_code_file, two_fa_file]:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"Geçici dosya silindi: {file_path}")
                    except Exception as e:
                        print(f"Dosya silinemedi: {e}")
            
            # Bağlantıyı kapat
            if client.is_connected():
                await client.disconnect()
            print("\nBağlantı kapatıldı.")
            
    except ImportError as e:
        print(f"Modül içe aktarma hatası: {e}")
    except Exception as e:
        print(f"Beklenmeyen hata: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telegram kimlik doğrulama testi")
    parser.add_argument("--phone", type=str, help="Telefon numarası")
    parser.add_argument("--code", type=str, help="Doğrulama kodu")
    parser.add_argument("--password", type=str, help="2FA şifresi")
    
    args = parser.parse_args()
    
    asyncio.run(test_auth(args.phone, args.code, args.password))
