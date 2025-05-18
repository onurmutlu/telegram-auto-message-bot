#!/usr/bin/env python3
# filepath: /Users/siyahkare/code/telegram-bot/force_login.py
"""
Telegram bot için son çare oturum açma aracı.
Bu betik, telegram_session.session dosyasını oluşturur ve
ana uygulamadan bağımsız olarak API kimlik doğrulama sorunlarını çözer.
"""
import os
import sys
import asyncio
import logging
import platform
import time
import dotenv
from telethon import TelegramClient, errors
from telethon.sessions import StringSession

# Loglama ayarlama
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TelegramLogin")

# Renkli çıktı
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
BOLD = '\033[1m'
ENDC = '\033[0m'

# Banner
def print_banner():
    print(f"""
{BLUE}{BOLD}=======================================================
  TELEGRAM BOT ZORUNLU OTURUM AÇMA ARACI
  Telegram API_ID/API_HASH sorunu için son çare
======================================================={ENDC}
""")

# Doğru kimlik bilgileri - my.telegram.org'dan
API_ID = 23692263  
API_HASH = "ff5d6053b266f78d1293f9343f40e77e"
SESSION_FILE = "telegram_session"

# Çevre değişkenlerini yükle
dotenv.load_dotenv(override=True)

# Çevre değişkenlerinde tanımlanan telefon numarasını al
PHONE = os.getenv("PHONE", "")
if not PHONE:
    PHONE = input("Telefon numaranızı girin (+905xxxxxxxxx formatında): ")

async def main():
    print_banner()
    print(f"{YELLOW}NOT: Bu araç, API ID/HASH sorununu çözmeye çalışır.{ENDC}")
    print(f"{YELLOW}Telegram API kimlik bilgileriniz:{ENDC}")
    print(f"API ID: {API_ID}")
    print(f"API HASH: {API_HASH[:4]}...{API_HASH[-4:]}")
    print(f"Telefon: {PHONE}")
    print(f"Oturum dosyası: {SESSION_FILE}.session")
    
    # Eski oturum dosyalarını temizle
    if os.path.exists(f"{SESSION_FILE}.session"):
        os.remove(f"{SESSION_FILE}.session")
        print(f"{YELLOW}Eski oturum dosyası silindi.{ENDC}")
    if os.path.exists(f"{SESSION_FILE}.session-journal"):
        os.remove(f"{SESSION_FILE}.session-journal")
    
    # Cihaz bilgileri
    device_model = f"Python {platform.python_version()} on {platform.system()}"
    
    # String session oluştur (yedekleme için)
    string_session = StringSession()
    
    # Telethon istemcisini oluştur - DOĞRUDAN SABİT DEĞERLERLE
    client = TelegramClient(
        SESSION_FILE,  # Oturum dosya adı
        API_ID,        # API ID
        API_HASH,      # API Hash
        device_model=device_model,
        system_version='1.0',
        app_version='2.0',
        connection_retries=5
    )
    
    print(f"\n{YELLOW}Telegram API sunucularına bağlanılıyor...{ENDC}")
    await client.connect()
    
    if not client.is_connected():
        print(f"{RED}Bağlantı başarısız! Ağ bağlantınızı kontrol edin.{ENDC}")
        return False
    
    print(f"{GREEN}Bağlantı başarılı!{ENDC}")
    
    # Kullanıcı zaten yetkili mi kontrol et  
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"{GREEN}Zaten oturum açmışsınız: {me.first_name} (@{me.username}){ENDC}")
        
        # String session kaydet
        saved_session = StringSession.save(client.session)
        print(f"\n{YELLOW}Yedek string session (saklamak için kopyalayın):{ENDC}")
        print(f"{YELLOW}{saved_session}{ENDC}")
        
        print(f"\n{GREEN}Oturum dosyası başarıyla kaydedildi: {SESSION_FILE}.session{ENDC}")
        print(f"{GREEN}Bot'u şu komutla başlatabilirsiniz: bash start.sh{ENDC}")
        return True
    
    try:
        print(f"{YELLOW}Telegram'a kod gönderme isteği yapılıyor...{ENDC}")
        await client.send_code_request(PHONE)
        
        print(f"{GREEN}Kod başarıyla istendi!{ENDC}")
        code = input(f"{BLUE}Telegram'dan aldığınız doğrulama kodunu girin: {ENDC}")
        
        print(f"{YELLOW}Doğrulama kodu ile giriş yapılıyor...{ENDC}")
        me = await client.sign_in(phone=PHONE, code=code.strip())
        
        print(f"{GREEN}Başarıyla giriş yapıldı: {me.first_name} (@{me.username}){ENDC}")
        
        # String session kaydet
        saved_session = StringSession.save(client.session)
        print(f"\n{YELLOW}Yedek string session (saklamak için kopyalayın):{ENDC}")
        print(f"{YELLOW}{saved_session}{ENDC}")
        
        print(f"\n{GREEN}Oturum dosyası başarıyla kaydedildi: {SESSION_FILE}.session{ENDC}")
        print(f"{GREEN}Bot'u şu komutla başlatabilirsiniz: bash start.sh{ENDC}")
        return True
        
    except errors.ApiIdInvalidError:
        print(f"{RED}HATA: API ID veya API HASH geçersiz!{ENDC}")
        print(f"{RED}Lütfen my.telegram.org adresinden kimlik bilgilerinizi doğrulayın.{ENDC}")
        return False
        
    except errors.PhoneNumberInvalidError:
        print(f"{RED}HATA: Telefon numarası geçersiz: {PHONE}{ENDC}")
        print(f"{RED}Lütfen uluslararası formatta girin: +905xxxxxxxxx{ENDC}")
        return False
        
    except errors.SessionPasswordNeededError:
        print(f"{YELLOW}İki faktörlü doğrulama şifresi gerekli.{ENDC}")
        password = input(f"{BLUE}Lütfen 2FA şifrenizi girin: {ENDC}")
        me = await client.sign_in(password=password)
        print(f"{GREEN}Başarıyla giriş yapıldı: {me.first_name}{ENDC}")
        
        # String session kaydet
        saved_session = StringSession.save(client.session)
        print(f"\n{YELLOW}Yedek string session (saklamak için kopyalayın):{ENDC}")
        print(f"{YELLOW}{saved_session}{ENDC}")
        
        print(f"\n{GREEN}Oturum dosyası başarıyla kaydedildi: {SESSION_FILE}.session{ENDC}")
        print(f"{GREEN}Bot'u şu komutla başlatabilirsiniz: bash start.sh{ENDC}")
        return True
        
    except Exception as e:
        print(f"{RED}HATA: {type(e).__name__}: {e}{ENDC}")
        return False
    
    finally:
        await client.disconnect()
        print(f"{YELLOW}Bağlantı kapatıldı.{ENDC}")
    
    return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"{YELLOW}\nİşlem kullanıcı tarafından iptal edildi.{ENDC}")
        sys.exit(1)
