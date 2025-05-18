#!/usr/bin/env python3
"""
Telegram API Kimlik Doğrulama Test Aracı

Bu betik, Telegram API kimlik bilgilerinin doğru olup olmadığını test eder ve 
olası sorunları tespit eder.
"""

import os
import sys
import time
import logging
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient, functions, types

# Log yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("api_test.log")
    ]
)
logger = logging.getLogger("telegram_api_tester")

# Sabit değerler
EXPECTED_API_ID = 23692263
EXPECTED_API_HASH = "ff5d6053b266f78d1293f9343f40e77e"

# ANSI renk kodları
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BLUE}{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'=' * len(text)}{Colors.END}")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️ {text}{Colors.END}")

async def test_telegram_api(api_id, api_hash, session_name, phone):
    """Telegram API kimlik bilgilerini test eder"""
    print_header("TELEGRAM API BAĞLANTI TESTİ")
    
    print_info(f"Kullanılan API_ID: {api_id}")
    print_info(f"Kullanılan API_HASH: {api_hash[:4]}...{api_hash[-4:]}")
    print_info(f"Oturum adı: {session_name}")
    
    client = None
    try:
        # Bağlantı kurmadan önce client oluştur
        client = TelegramClient(session_name, api_id, api_hash)
        
        # Bağlantıyı kur
        print_info("Telegram API'ye bağlanılıyor...")
        await client.connect()
        
        if not await client.is_user_authorized():
            print_warning("Henüz yetkilendirilmemiş oturum. Telefon doğrulaması gerekli olabilir.")
            print_info("Bu testin asıl amacı API_ID/API_HASH doğrulamasıdır, oturum açma işlemi gerçekleştirilmeyecek.")
        else:
            print_success("Oturum zaten yetkilendirilmiş.")
            me = await client.get_me()
            if me:
                print_success(f"Kullanıcı bilgileri alındı: {me.first_name} {me.last_name or ''} (@{me.username or 'Kullanıcı adı yok'})")
            
        # Basit bir API çağrısı dene
        print_info("Basit bir API çağrısı yapılıyor...")
        result = await client(functions.help.GetConfigRequest())
        if result:
            print_success("API çağrısı başarılı!")
            print_info(f"API yapılandırması alındı: {result.dc_options[0].ip_address}:{result.dc_options[0].port}")
            print_success("API_ID ve API_HASH geçerli.")
        
    except Exception as e:
        print_error(f"Telegram API bağlantı hatası: {e}")
        if "api_id/api_hash" in str(e).lower():
            print_error("API_ID/API_HASH kombinasyonu geçersiz. Lütfen değerlerinizi kontrol edin.")
            print_info(f"Beklenen API_ID: {EXPECTED_API_ID}")
            print_info(f"Beklenen API_HASH: {EXPECTED_API_HASH}")
        elif "flood" in str(e).lower():
            print_warning("Çok fazla istek gönderildi. Lütfen birkaç dakika bekleyin ve tekrar deneyin.")
        else:
            logger.exception("Bağlantı sırasında beklenmeyen hata")
    finally:
        if client:
            await client.disconnect()

def check_env_vars():
    """Çevre değişkenlerini kontrol eder"""
    print_header("ÇEVRE DEĞİŞKENLERİ KONTROLÜ")
    
    # .env dosyasını yükle
    dotenv_path = Path('.env')
    if dotenv_path.exists():
        print_info(f".env dosyası bulundu: {dotenv_path.absolute()}")
        load_dotenv(dotenv_path=dotenv_path)
    else:
        print_warning(f".env dosyası bulunamadı: {dotenv_path.absolute()}")
    
    # Çevre değişkenlerini kontrol et
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    session_name = os.getenv("SESSION_NAME", "telegram_session")
    phone = os.getenv("PHONE")
    
    print_info("Çevre değişkenleri:")
    
    # API_ID kontrolü
    if not api_id:
        print_error("API_ID çevre değişkeni bulunamadı!")
    else:
        try:
            api_id_int = int(api_id)
            if api_id_int == EXPECTED_API_ID:
                print_success(f"API_ID çevre değişkeni doğru: {api_id}")
            else:
                print_warning(f"API_ID değeri beklenen değerden farklı!")
                print_info(f"  Bulunan: {api_id_int}")
                print_info(f"  Beklenen: {EXPECTED_API_ID}")
        except ValueError:
            print_error(f"API_ID sayısal bir değer değil: {api_id}")
    
    # API_HASH kontrolü
    if not api_hash:
        print_error("API_HASH çevre değişkeni bulunamadı!")
    else:
        if api_hash == EXPECTED_API_HASH:
            print_success(f"API_HASH çevre değişkeni doğru: {api_hash[:4]}...{api_hash[-4:]}")
        else:
            print_warning(f"API_HASH değeri beklenen değerden farklı!")
            print_info(f"  Bulunan: {api_hash}")
            print_info(f"  Beklenen: {EXPECTED_API_HASH}")
            
            # Karakter farklılıklarını analiz et
            if len(api_hash) != len(EXPECTED_API_HASH):
                print_warning(f"  Karakter sayısı farklı - Bulunan: {len(api_hash)}, Beklenen: {len(EXPECTED_API_HASH)}")
            
            # Farklılık pozisyonlarını göster
            differences = []
            for i, (found, expected) in enumerate(zip(api_hash, EXPECTED_API_HASH)):
                if found != expected:
                    differences.append((i, found, expected))
            
            if differences:
                print_warning("  Farklı karakterler:")
                for pos, found, expected in differences:
                    print_info(f"    Pozisyon {pos+1}: Bulunan '{found}', Beklenen '{expected}'")
    
    # SESSION_NAME kontrolü
    if not session_name:
        print_warning("SESSION_NAME çevre değişkeni bulunamadı, varsayılan 'telegram_session' kullanılacak")
    else:
        print_info(f"SESSION_NAME: {session_name}")
    
    # PHONE kontrolü
    if not phone:
        print_warning("PHONE çevre değişkeni bulunamadı!")
    else:
        print_info(f"PHONE: {phone}")
    
    # Oturum dosyalarını kontrol et
    check_session_files(session_name)
    
    return api_id, api_hash, session_name, phone

def check_session_files(session_name):
    """Telegram oturum dosyalarını kontrol eder"""
    print_header("OTURUM DOSYASI KONTROLÜ")
    
    session_file = f"{session_name}.session"
    session_journal = f"{session_name}.session-journal"
    
    if os.path.exists(session_file):
        size = os.path.getsize(session_file)
        modified = os.path.getmtime(session_file)
        modified_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(modified))
        print_success(f"Oturum dosyası bulundu: {session_file}")
        print_info(f"  Boyut: {size} bytes")
        print_info(f"  Son değiştirilme: {modified_time}")
    else:
        print_warning(f"Oturum dosyası bulunamadı: {session_file}")
    
    if os.path.exists(session_journal):
        size = os.path.getsize(session_journal)
        modified = os.path.getmtime(session_journal)
        modified_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(modified))
        print_info(f"Journal dosyası bulundu: {session_journal}")
        print_info(f"  Boyut: {size} bytes")
        print_info(f"  Son değiştirilme: {modified_time}")

async def main():
    """Ana fonksiyon"""
    print_header("TELEGRAM API KİMLİK DOĞRULAMA TEST ARACI")
    print_info("Sürüm: 1.0.0")
    print_info(f"Python: {sys.version}")
    print_info(f"Çalışma dizini: {os.getcwd()}")
    
    # Çevre değişkenlerini kontrol et
    api_id, api_hash, session_name, phone = check_env_vars()
    
    # API değerleri eksikse düzelt
    if not api_id or not api_hash:
        print_warning("API bilgileri eksik veya hatalı, varsayılan değerler kullanılacak.")
        api_id = EXPECTED_API_ID
        api_hash = EXPECTED_API_HASH
    
    # Kullanıcıdan testi onaylamasını iste
    print("\n")
    print_warning("Bu test, Telegram API'ye bağlanmayı deneyecek ve kimlik bilgilerinizi doğrulayacak.")
    print_warning("Eğer oturum açılmamışsa, sadece API_ID/API_HASH doğruluğu kontrol edilecek.")
    choice = input(f"{Colors.BLUE}Devam etmek istiyor musunuz? (e/h): {Colors.END}")
    
    if choice.lower() != 'e':
        print_info("Test iptal edildi.")
        return
    
    # Telegram API'yi test et
    await test_telegram_api(int(api_id), api_hash, session_name, phone)
    
    print_header("TEST TAMAMLANDI")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
