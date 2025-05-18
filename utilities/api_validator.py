#!/usr/bin/env python3
# filepath: /Users/siyahkare/code/telegram-bot/api_validator.py
"""
Telegram API kimlik bilgilerini doğrulama aracı.
Bu betik, API_ID ve API_HASH'in doğru olduğunu doğrulamak için
basit bir bağlantı testi yapar ve bot başlatmadan önce
sorunları görmenize yardımcı olur.
"""
import os
import sys
import asyncio
import logging
import dotenv
import platform
import time
import json
from telethon import TelegramClient, functions, errors

# Renk kodları
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("ApiValidator")

def print_banner():
    """Program banner'ını göster"""
    banner = f"""
{Colors.BLUE}{Colors.BOLD}=================================================
  TELEGRAM API DOĞRULAMA ARACI
  Bağlantı ve API kimlik bilgisi doğrulaması yapar
================================================={Colors.ENDC}
"""
    print(banner)

def print_colored(text, color=Colors.BLUE):
    """Renklendirilmiş metin yaz"""
    print(f"{color}{text}{Colors.ENDC}")

def load_env_vars():
    """Çevre değişkenlerini yükle"""
    print_colored("Ortam değişkenleri yükleniyor...", Colors.YELLOW)
    dotenv.load_dotenv(override=True)
    
    # Değerleri al
    api_id = os.getenv("API_ID", "")
    api_hash = os.getenv("API_HASH", "")
    session_name = os.getenv("SESSION_NAME", "validator_session")
    phone = os.getenv("PHONE", "")
    
    # API_ID'yi integer'a çevir
    try:
        api_id = int(api_id)
    except ValueError:
        api_id = 0
    
    # Kontrol et
    if api_id == 0 or not api_hash:
        print_colored("HATA: API_ID veya API_HASH çevre değişkenleri eksik veya hatalı.", Colors.RED)
        print_colored("Lütfen .env dosyasının doğru yapılandırıldığından emin olun.", Colors.RED)
        sys.exit(1)
    
    print_colored(f"API_ID: {api_id}", Colors.GREEN)
    print_colored(f"API_HASH: {api_hash[:4]}...{api_hash[-4:]}", Colors.GREEN)
    print_colored(f"SESSION_NAME: {session_name}", Colors.GREEN)
    print_colored(f"PHONE: {phone if phone else 'Belirlenmemiş'}", Colors.GREEN)
    
    return api_id, api_hash, session_name, phone

async def validate_api(api_id, api_hash, session_name):
    """API kimlik bilgilerini doğrula"""
    print_colored("\nAPI doğrulama testi başlatılıyor...", Colors.BLUE)
    
    # Benzersiz session oluştur
    unique_session = f"{session_name}_validate_{int(time.time())}"
    print_colored(f"Kullanılan oturum adı: {unique_session}", Colors.YELLOW)
    
    # Olası eski session dosyasını temizle
    if os.path.exists(f"{unique_session}.session"):
        os.remove(f"{unique_session}.session")
    
    # Sistem bilgileri
    system_info = platform.system()
    python_version = platform.python_version()
    
    device_model = f"Python {python_version} on {system_info}"
    print_colored(f"Kullanılan cihaz bilgisi: {device_model}", Colors.YELLOW)
    
    # istemci oluştur
    client = TelegramClient(
        unique_session,
        api_id,
        api_hash,
        device_model=device_model,
        system_version=platform.version(),
        app_version='1.0',
    )
    
    validation_results = {
        "api_connection": False,
        "api_auth": False,
        "api_validation": False,
    }
    
    try:
        print_colored("Telegram API sunucularına bağlanılıyor...", Colors.YELLOW)
        await client.connect()
        
        if not client.is_connected():
            print_colored("HATA: Bağlantı kurulamadı!", Colors.RED)
            return validation_results
        
        validation_results["api_connection"] = True
        print_colored("Bağlantı başarılı! ✓", Colors.GREEN)
        
        # Sunucu yapılandırmasını al
        print_colored("API kimlik bilgileri doğrulanıyor...", Colors.YELLOW)
        try:
            config = await client(functions.help.GetConfigRequest())
            validation_results["api_validation"] = True
            print_colored("API kimlik bilgileri doğrulandı! ✓", Colors.GREEN)
            print_colored(f"Bağlantı kuruldu - DC: {config.this_dc}", Colors.GREEN)
            
            for dc in config.dc_options[:3]:  # Sadece ilk 3 DC bilgisini göster
                print_colored(f"DC {dc.id}: {dc.ip_address}:{dc.port} {'(CDN)' if dc.cdn else ''}", Colors.YELLOW)
            
        except errors.ApiIdInvalidError:
            print_colored("HATA: API_ID veya API_HASH geçersiz!", Colors.RED)
            print_colored("Lütfen my.telegram.org adresinden kimlik bilgilerinizi kontrol edin.", Colors.RED)
        except Exception as e:
            print_colored(f"API doğrulama hatası: {type(e).__name__}: {str(e)}", Colors.RED)
    
    except Exception as e:
        print_colored(f"Bağlantı hatası: {type(e).__name__}: {str(e)}", Colors.RED)
    
    finally:
        # Bağlantıyı kapat
        if client and client.is_connected():
            await client.disconnect()
            print_colored("Bağlantı kapatıldı.", Colors.YELLOW)
        
        # Oturum dosyasını temizle
        if os.path.exists(f"{unique_session}.session"):
            os.remove(f"{unique_session}.session")
            print_colored(f"{unique_session}.session dosyası silindi.", Colors.YELLOW)
    
    return validation_results
    
async def main():
    """Ana fonksiyon"""
    print_banner()
    
    api_id, api_hash, session_name, phone = load_env_vars()
    
    validation_results = await validate_api(api_id, api_hash, session_name)
    
    # Sonuçları göster
    print_colored("\n--- Doğrulama Sonuçları ---", Colors.BOLD + Colors.BLUE)
    
    if validation_results["api_connection"]:
        print_colored("✓ Telegram sunucularına bağlantı: BAŞARILI", Colors.GREEN)
    else:
        print_colored("✗ Telegram sunucularına bağlantı: BAŞARISIZ", Colors.RED)
    
    if validation_results["api_validation"]:
        print_colored("✓ API kimlik bilgileri: DOĞRU", Colors.GREEN)
    else:
        print_colored("✗ API kimlik bilgileri: GEÇERSİZ", Colors.RED)
    
    print_colored("-------------------------", Colors.BLUE)
    
    # Genel sonuç
    if validation_results["api_validation"]:
        print_colored("\nAPI KİMLİK BİLGİLERİ DOĞRULANDI! ✓", Colors.GREEN + Colors.BOLD)
        print_colored("Bot'u başlatabilirsiniz.", Colors.GREEN)
    else:
        print_colored("\nAPI KİMLİK BİLGİLERİ DOĞRULANAMADI! ✗", Colors.RED + Colors.BOLD)
        print_colored("Lütfen .env dosyasındaki API_ID ve API_HASH değerlerini kontrol edin.", Colors.RED)
    
    return 0 if validation_results["api_validation"] else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_colored("\nProgram kullanıcı tarafından durduruldu.", Colors.YELLOW)
        sys.exit(1)
