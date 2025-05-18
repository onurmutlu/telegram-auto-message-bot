#!/usr/bin/env python3
"""
Telegram bağlantı sorunlarını çözen bir yardımcı araç.
- Telegram bağlantısını test eder
- Oturum dosyasını kontrol eder
- Bağlantıyı yeniden kurar ve optimize eder
"""

import os
import sys
import logging
import asyncio
import time
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import (
    PhoneNumberInvalidError, 
    ApiIdInvalidError, 
    SessionPasswordNeededError,
    AuthKeyError
)

# Proje kök dizinini Python yoluna ekle
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_dir)

# Environment değişkenlerini yükle
from app.core.config import settings

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(project_dir, "connection_fixer.log"))
    ]
)
logger = logging.getLogger('connection_fixer')

# Renklendirme için ANSI kodları
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

async def check_session_files():
    """Oturum dosyalarını kontrol eder."""
    print(f"\n{BLUE}Oturum Dosyası Kontrolü{RESET}")
    print("="*50)
    
    # Oturum dosyası kontrolü
    session_path = f"{settings.SESSION_NAME}.session"
    session_journal = f"{settings.SESSION_NAME}.session-journal"
    
    if os.path.exists(session_path):
        session_size = os.path.getsize(session_path)
        print(f"{GREEN}[✓] Oturum dosyası bulundu: {session_path} ({session_size} bytes){RESET}")
        
        # Dosya çok küçükse uyarı ver
        if session_size < 1000:
            print(f"{YELLOW}[!] Oturum dosyası çok küçük, bozuk olabilir.{RESET}")
    else:
        print(f"{RED}[✗] Oturum dosyası bulunamadı: {session_path}{RESET}")
        print(f"{YELLOW}Yeni oturum oluşturmanız gerekebilir.{RESET}")
        return False
    
    if os.path.exists(session_journal):
        journal_size = os.path.getsize(session_journal)
        print(f"{GREEN}[✓] Journal dosyası bulundu: {session_journal} ({journal_size} bytes){RESET}")
    
    return True

async def check_telegram_api_settings():
    """Telegram API ayarlarını kontrol eder."""
    print(f"\n{BLUE}Telegram API Ayarları Kontrolü{RESET}")
    print("="*50)
    
    # API_ID ve API_HASH kontrolü
    api_id = settings.API_ID
    api_hash = settings.API_HASH
    if hasattr(api_hash, 'get_secret_value'):
        api_hash = api_hash.get_secret_value()
    
    print(f"API ID: {api_id}")
    print(f"API HASH: {api_hash[:5]}...{api_hash[-5:]}")
    
    if api_id == 0 or not api_id:
        print(f"{RED}[✗] API ID geçersiz{RESET}")
        return False
    
    if not api_hash or len(api_hash) < 10:
        print(f"{RED}[✗] API HASH geçersiz{RESET}")
        return False
    
    print(f"{GREEN}[✓] API kimlik bilgileri geçerli görünüyor{RESET}")
    return True

async def test_telegram_connection():
    """Telegram bağlantısını test eder."""
    print(f"\n{BLUE}Telegram Bağlantı Testi{RESET}")
    print("="*50)
    
    client = None
    try:
        api_id = settings.API_ID
        api_hash = settings.API_HASH
        if hasattr(api_hash, 'get_secret_value'):
            api_hash = api_hash.get_secret_value()
        
        session_name = settings.SESSION_NAME
        
        # TelegramClient oluştur
        print(f"{BLUE}Telegram istemcisi oluşturuluyor...{RESET}")
        client = TelegramClient(
            session_name, 
            api_id, 
            api_hash,
            connection_retries=10,
            retry_delay=3
        )
        
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
                    
                    # BOT_USERNAME'i güncelle
                    if hasattr(me, 'username') and me.username:
                        settings.BOT_USERNAME = me.username
                        print(f"{GREEN}[✓] BOT_USERNAME güncellendi: {me.username}{RESET}")
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
                try:
                    start_time = time.time()
                    await client.get_me()
                    ping_ms = round((time.time() - start_time) * 1000, 2)
                    print(f"{GREEN}[✓] API ping: {ping_ms}ms{RESET}")
                except Exception as ping_err:
                    print(f"{RED}[✗] Ping hatası: {ping_err}{RESET}")
                
                print(f"\n{GREEN}{BOLD}Telegram bağlantısı ve oturum çalışıyor.{RESET}")
                return True
                
            else:
                print(f"{YELLOW}[!] Oturum yetkilendirilmemiş, yeniden giriş gerekli{RESET}")
                return await reconnect_session(client)
        else:
            print(f"{RED}[✗] Telegram API'ye bağlantı kurulamadı{RESET}")
            return False
            
    except Exception as e:
        print(f"{RED}[✗] Bağlantı hatası: {e}{RESET}")
        logger.exception("Bağlantı testi sırasında hata:")
        return False
    finally:
        if client:
            await client.disconnect()

async def reconnect_session(client):
    """Oturumu yeniden açar."""
    try:
        print(f"\n{BLUE}Yeniden oturum açılıyor...{RESET}")
        
        phone = settings.PHONE
        if hasattr(phone, 'get_secret_value'):
            phone = phone.get_secret_value()
        
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

async def clear_and_recreate_session():
    """Oturum dosyalarını temizler ve yeniden oluşturur."""
    print(f"\n{BLUE}Oturum Dosyaları Temizleniyor{RESET}")
    print("="*50)
    
    session_path = f"{settings.SESSION_NAME}.session"
    session_journal = f"{settings.SESSION_NAME}.session-journal"
    
    # Yedekleme yap
    backup_dir = os.path.join(project_dir, "session_backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    if os.path.exists(session_path):
        backup_path = os.path.join(backup_dir, f"{settings.SESSION_NAME}_{timestamp}.session")
        try:
            import shutil
            shutil.copy2(session_path, backup_path)
            print(f"{GREEN}[✓] Oturum dosyası yedeklendi: {backup_path}{RESET}")
        except Exception as e:
            print(f"{YELLOW}[!] Oturum dosyası yedeklenemedi: {e}{RESET}")
    
    # Dosyaları sil
    try:
        if os.path.exists(session_path):
            os.remove(session_path)
            print(f"{GREEN}[✓] Oturum dosyası silindi: {session_path}{RESET}")
        
        if os.path.exists(session_journal):
            os.remove(session_journal)
            print(f"{GREEN}[✓] Journal dosyası silindi: {session_journal}{RESET}")
    except Exception as e:
        print(f"{RED}[✗] Dosyalar silinirken hata: {e}{RESET}")
        return False
    
    # Yeni oturum oluştur
    print(f"\n{BLUE}Yeni oturum oluşturuluyor...{RESET}")
    
    client = None
    try:
        api_id = settings.API_ID
        api_hash = settings.API_HASH
        if hasattr(api_hash, 'get_secret_value'):
            api_hash = api_hash.get_secret_value()
        
        phone = settings.PHONE
        if hasattr(phone, 'get_secret_value'):
            phone = phone.get_secret_value()
        
        session_name = settings.SESSION_NAME
        
        # TelegramClient oluştur
        client = TelegramClient(
            session_name, 
            api_id, 
            api_hash,
            connection_retries=10,
            retry_delay=3
        )
        
        # Bağlantıyı kur
        await client.connect()
        
        if client.is_connected():
            print(f"{GREEN}[✓] Telegram API'ye bağlantı başarılı{RESET}")
            
            # Yeni oturum için kod iste
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
        else:
            print(f"{RED}[✗] Telegram API'ye bağlantı kurulamadı{RESET}")
            return False
            
    except Exception as e:
        print(f"{RED}[✗] Yeni oturum oluşturma hatası: {e}{RESET}")
        logger.exception("Yeni oturum oluşturma sırasında hata:")
        return False
    finally:
        if client:
            await client.disconnect()

async def fix_telegram_connection():
    """Telegram bağlantı sorunlarını çözer."""
    print(f"\n{BOLD}{BLUE}Telegram Bağlantı Sorunları Giderme Aracı{RESET}")
    print("="*50)
    
    # 1. Oturum dosyalarını kontrol et
    session_ok = await check_session_files()
    
    # 2. API ayarlarını kontrol et
    api_ok = await check_telegram_api_settings()
    
    # 3. Bağlantıyı test et
    if session_ok and api_ok:
        connection_ok = await test_telegram_connection()
        
        if connection_ok:
            print(f"\n{GREEN}{BOLD}Bağlantı testi başarılı! Telegram bağlantısı çalışıyor.{RESET}")
            return True
        else:
            print(f"\n{YELLOW}{BOLD}Bağlantı testi başarısız. Oturum yenileme deneniyor...{RESET}")
            
            # Kullanıcıya oturumu yeniden oluşturmak isteyip istemediğini sor
            recreate = input(f"{YELLOW}Oturum dosyasını silip yeniden oluşturmak ister misiniz? (E/H): {RESET}").lower().strip()
            
            if recreate in ('e', 'evet', 'y', 'yes'):
                result = await clear_and_recreate_session()
                if result:
                    print(f"\n{GREEN}{BOLD}Oturum başarıyla yenilendi! Telegram bağlantısı çalışıyor.{RESET}")
                    return True
                else:
                    print(f"\n{RED}{BOLD}Oturum yenileme başarısız.{RESET}")
                    return False
            else:
                print(f"\n{YELLOW}Oturum yenileme işlemi iptal edildi.{RESET}")
                return False
    else:
        print(f"\n{RED}{BOLD}Telegram bağlantısı için gerekli koşullar sağlanamıyor.{RESET}")
        if not session_ok:
            print(f"{RED}Oturum dosyası sorunlu veya eksik.{RESET}")
        if not api_ok:
            print(f"{RED}API kimlik bilgileri sorunlu veya eksik.{RESET}")
        return False

async def restart_bot():
    """Botu yeniden başlatır."""
    print(f"\n{BLUE}Bot Yeniden Başlatılıyor{RESET}")
    print("="*50)
    
    # Bot çalışıyor mu kontrol et
    pid_file = os.path.join(project_dir, "bot.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            
            # PID aktif mi kontrol et
            try:
                os.kill(pid, 0)  # 0 sinyali sadece kontrol amaçlı
                print(f"{YELLOW}Bot şu anda çalışıyor (PID: {pid}). Durduruluyor...{RESET}")
                
                # Botu durdur
                os.kill(pid, 15)  # SIGTERM
                
                # Botun kapanmasını bekle
                for i in range(10):
                    try:
                        os.kill(pid, 0)
                        print(f"Bot kapanıyor, bekleniyor... ({i+1}/10)")
                        time.sleep(1)
                    except OSError:
                        print(f"{GREEN}Bot başarıyla durduruldu.{RESET}")
                        break
                
                # Hala çalışıyor mu kontrol et
                try:
                    os.kill(pid, 0)
                    print(f"{RED}Bot normal şekilde durdurulamadı. Force kill uygulanıyor...{RESET}")
                    os.kill(pid, 9)  # SIGKILL
                except OSError:
                    pass
                    
            except OSError:
                print(f"{YELLOW}PID dosyası var ama bot çalışmıyor. PID dosyası temizleniyor.{RESET}")
            
            # PID dosyasını temizle
            os.remove(pid_file)
            
        except Exception as e:
            print(f"{RED}Bot durdurulurken hata: {e}{RESET}")
    
    # Botu yeniden başlat
    print(f"\n{BLUE}Bot başlatılıyor...{RESET}")
    
    try:
        # Restart betiğini çalıştır
        restart_script = os.path.join(project_dir, "restart_bot.sh")
        if os.path.exists(restart_script):
            import subprocess
            print(f"{GREEN}Restart betiği çalıştırılıyor: {restart_script}{RESET}")
            
            # Arka planda çalıştır
            subprocess.Popen(["bash", restart_script], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
            
            print(f"{GREEN}Bot yeniden başlatma işlemi başlatıldı (arka planda devam ediyor).{RESET}")
            print(f"{YELLOW}60 saniye sonra 'python -m app.cli status' komutu ile durumu kontrol edebilirsiniz.{RESET}")
            return True
        else:
            print(f"{RED}Restart betiği bulunamadı: {restart_script}{RESET}")
            return False
    except Exception as e:
        print(f"{RED}Bot yeniden başlatılırken hata: {e}{RESET}")
        return False

async def main():
    """Ana fonksiyon."""
    # Bağlantı sorunlarını çöz
    connection_fixed = await fix_telegram_connection()
    
    if connection_fixed:
        # Botu yeniden başlat
        print(f"\n{BLUE}Bağlantı sorunları çözüldü. Bot yeniden başlatılsın mı?{RESET}")
        restart = input(f"{YELLOW}Botu yeniden başlatmak istiyor musunuz? (E/H): {RESET}").lower().strip()
        
        if restart in ('e', 'evet', 'y', 'yes'):
            await restart_bot()
        else:
            print(f"\n{YELLOW}Bot yeniden başlatma işlemi iptal edildi.{RESET}")
    else:
        print(f"\n{RED}{BOLD}Bağlantı sorunları çözülemedi. Manuel müdahale gerekebilir.{RESET}")
        print(f"{YELLOW}Detaylı bilgi için lütfen log dosyasını kontrol edin.{RESET}")

if __name__ == "__main__":
    asyncio.run(main())
