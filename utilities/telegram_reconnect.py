#!/usr/bin/env python3
"""
Telegram oturumunu doğrudan yeniden başlatan ve bağlantı sorunlarını gidermeye yardımcı olan script.
"""

import os
import sys
import asyncio
import logging
import time
from telethon import TelegramClient, functions, types
from telethon.errors import SessionPasswordNeededError
from pathlib import Path

# Renkli çıktı için ANSI kodları
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("reconnect.log")
    ]
)
logger = logging.getLogger('telegram_reconnect')

# Çalışma dizinini al
root_dir = Path(__file__).parent.parent.absolute()
env_path = root_dir / '.env'

def load_env_variables():
    """Çevre değişkenlerini .env dosyasından yükler"""
    env_vars = {}
    
    if env_path.exists():
        print(f"{GREEN}[✓] .env dosyası bulundu: {env_path}{RESET}")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('//'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    else:
        print(f"{RED}[✗] .env dosyası bulunamadı: {env_path}{RESET}")
        
    return env_vars

async def test_telegram_connection(api_id, api_hash, session_name, phone):
    """Telegram bağlantısını test eder ve oturum durumunu kontrol eder"""
    print(f"\n{BOLD}{BLUE}Telegram Bağlantı Testi{RESET}")
    print("=" * 50)
    
    # Oturum dosyalarını kontrol et
    session_file = Path(f"{session_name}.session")
    session_journal = Path(f"{session_name}.session-journal")
    
    if session_file.exists():
        print(f"{GREEN}[✓] Oturum dosyası bulundu: {session_file} ({session_file.stat().st_size} bytes){RESET}")
    else:
        print(f"{YELLOW}[!] Oturum dosyası bulunamadı: {session_file}{RESET}")
    
    if session_journal.exists():
        print(f"{GREEN}[✓] Oturum journal dosyası bulundu: {session_journal} ({session_journal.stat().st_size} bytes){RESET}")
    
    # TelegramClient oluştur
    client = None
    try:
        print(f"\n{BLUE}Telegram istemcisi oluşturuluyor...{RESET}")
        client = TelegramClient(session_name, api_id, api_hash)
        
        # Bağlantıyı kur
        print(f"{BLUE}Telegram API'ye bağlanılıyor...{RESET}")
        await client.connect()
        
        # Bağlantı durumunu kontrol et
        if client.is_connected():
            print(f"{GREEN}[✓] Telegram API'ye bağlantı başarılı{RESET}")
            
            # Oturum yetkilendirme durumunu kontrol et
            is_authorized = await client.is_user_authorized()
            
            if is_authorized:
                print(f"{GREEN}[✓] Oturum yetkilendirilmiş{RESET}")
                
                # Kullanıcı bilgilerini al
                me = await client.get_me()
                if me:
                    print(f"{GREEN}[✓] Kullanıcı bilgileri alındı:{RESET}")
                    print(f"    Kullanıcı: {me.first_name} {me.last_name or ''}")
                    print(f"    ID: {me.id}")
                    print(f"    Kullanıcı adı: @{me.username or 'Yok'}")
                    print(f"    Telefon: {me.phone or 'Gizli'}")
                else:
                    print(f"{YELLOW}[!] Kullanıcı bilgileri alınamadı{RESET}")
                
                # Diyalogları kontrol et
                print(f"\n{BLUE}Son 3 diyalog kontrol ediliyor...{RESET}")
                dialogs = await client.get_dialogs(limit=3)
                if dialogs:
                    print(f"{GREEN}[✓] {len(dialogs)} diyalog alındı{RESET}")
                    for d in dialogs:
                        print(f"    - {d.name} (ID: {d.id})")
                else:
                    print(f"{YELLOW}[!] Diyalog alınamadı{RESET}")
                
                # API ping testi
                print(f"\n{BLUE}API ping testi yapılıyor...{RESET}")
                start_time = time.time()
                config = await client(functions.help.GetConfigRequest())
                ping_ms = round((time.time() - start_time) * 1000, 2)
                print(f"{GREEN}[✓] API ping: {ping_ms}ms{RESET}")
                
                print(f"\n{GREEN}{BOLD}Tüm testler başarılı! Telegram bağlantısı ve oturum çalışıyor.{RESET}")
                
            else:
                print(f"{YELLOW}[!] Oturum yetkilendirilmemiş, yeniden giriş gerekli{RESET}")
                await reconnect_session(client, phone)
        else:
            print(f"{RED}[✗] Telegram API'ye bağlantı kurulamadı{RESET}")
            
    except Exception as e:
        print(f"{RED}[✗] Hata: {e}{RESET}")
        logger.exception("Bağlantı testi sırasında hata:")
    finally:
        if client:
            await client.disconnect()
    
    print("\n" + "=" * 50)

async def reconnect_session(client, phone):
    """Oturumu yeniden açar"""
    try:
        print(f"\n{BLUE}Yeniden oturum açılıyor...{RESET}")
        
        # Telefondan doğrulama kodu iste
        print(f"{BLUE}Telefon numarasına doğrulama kodu gönderiliyor: {phone}{RESET}")
        await client.send_code_request(phone)
        
        # Kullanıcıdan kodu al
        code = input(f"{YELLOW}Telefonunuza gelen doğrulama kodunu girin: {RESET}")
        
        try:
            # Kod ile giriş yap
            user = await client.sign_in(phone, code)
            print(f"{GREEN}[✓] Giriş başarılı: {user.first_name}{RESET}")
            return True
        except SessionPasswordNeededError:
            # 2FA gerekli
            print(f"{YELLOW}[!] İki faktörlü kimlik doğrulama (2FA) gerekli{RESET}")
            password = input(f"{YELLOW}2FA şifrenizi girin: {RESET}")
            user = await client.sign_in(password=password)
            print(f"{GREEN}[✓] 2FA ile giriş başarılı: {user.first_name}{RESET}")
            return True
            
    except Exception as e:
        print(f"{RED}[✗] Yeniden bağlantı hatası: {e}{RESET}")
        logger.exception("Yeniden bağlantı sırasında hata:")
        return False

async def main():
    """Ana fonksiyon"""
    print(f"\n{BOLD}{BLUE}Telegram Bot Bağlantı Yenileme Aracı{RESET}")
    print(f"{BLUE}======================================{RESET}")
    
    # Çevre değişkenlerini yükle
    env_vars = load_env_variables()
    
    # Gerekli değişkenleri al
    api_id = int(env_vars.get('API_ID', 0))
    api_hash = env_vars.get('API_HASH', '')
    phone = env_vars.get('PHONE', '')
    session_name = env_vars.get('SESSION_NAME', 'telegram_session')
    
    # Değişkenleri kontrol et
    print(f"\n{BLUE}Telegram Kimlik Bilgileri:{RESET}")
    print(f"API ID: {api_id}")
    print(f"API HASH: {api_hash[:4]}...{api_hash[-4:]}")
    print(f"Telefon: {phone}")
    print(f"Oturum adı: {session_name}")
    
    if not api_id or not api_hash or not phone:
        print(f"\n{RED}[✗] Gerekli kimlik bilgileri eksik!{RESET}")
        print("Lütfen .env dosyasında API_ID, API_HASH ve PHONE değerlerinin doğru olduğundan emin olun.")
        return
    
    # Bağlantıyı test et
    await test_telegram_connection(api_id, api_hash, session_name, phone)

if __name__ == "__main__":
    asyncio.run(main())
