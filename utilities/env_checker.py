#!/usr/bin/env python3
# filepath: /Users/siyahkare/code/telegram-bot/env_checker.py
"""
.env dosyasından API_ID ve API_HASH değerlerinin
doğru yüklendiğini kontrol eden basit betik.
"""
import os
import dotenv
import logging
import asyncio
from telethon import TelegramClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def print_separator(title=""):
    print("\n" + "="*50)
    if title:
        print(f"  {title}")
        print("="*50)
    print()

# Ortam değişkenlerini yükle
print_separator("ORTAM DEĞİŞKENLERİ TESTİ")
print("Ortam değişkenlerini yüklüyorum...")

# Önce mevcut değerleri göster
print("Yükleme ÖNCESİ API_ID:", os.getenv("API_ID", "YOK"))
print("Yükleme ÖNCESİ API_HASH:", os.getenv("API_HASH", "YOK"))

# dotenv ile yükle
dotenv.load_dotenv(override=True)
print("\ndotenv.load_dotenv() çağrıldı.")

# Sonraki değerleri göster
print("Yükleme SONRASI API_ID:", os.getenv("API_ID", "YOK"))
print("Yükleme SONRASI API_HASH:", os.getenv("API_HASH", "YOK"))

# Tanımladığımız sabit değerlerle test
print_separator("DOĞRUDAN BAĞLANTI TESTİ")
print("Sabit tanımlı değerlerle test:")

# Doğru olduğunu bildiğimiz değerler
CORRECT_API_ID = 23692263
CORRECT_API_HASH = "ff5d6053b266f78d129f9343f40e77e"

print(f"CORRECT_API_ID: {CORRECT_API_ID}")
print(f"CORRECT_API_HASH: {CORRECT_API_HASH}")

# Daha önce basit bağlantı testinden geçen değerlerle bir istemci oluşturalım
async def test_connection():
    print("\nBağlantı testi başlıyor...")
    
    client = TelegramClient('env_test_session', CORRECT_API_ID, CORRECT_API_HASH)
    
    try:
        print("Bağlanılıyor...")
        await client.connect()
        
        if client.is_connected():
            print("✅ Bağlantı BAŞARILI!")
        else:
            print("❌ Bağlantı BAŞARISIZ!")
        
    except Exception as e:
        print(f"❌ HATA: {type(e).__name__}: {e}")
    finally:
        if client and client.is_connected():
            await client.disconnect()
            print("Bağlantı kapatıldı.")
    
    print("\nENV VARİABLES testi yapılıyor...")
    
    # .env'den okunan değerlerle test edelim
    env_api_id = os.getenv("API_ID", "0")
    env_api_hash = os.getenv("API_HASH", "")
    
    try:
        env_api_id = int(env_api_id)
    except ValueError:
        env_api_id = 0
    
    print(f"ENV'den okunan API_ID: {env_api_id}")
    print(f"ENV'den okunan API_HASH: {env_api_hash}")
    
    if env_api_id == CORRECT_API_ID and env_api_hash == CORRECT_API_HASH:
        print("✅ ENVİRONMENT DEĞERLERİ DOĞRU!")
    else:
        print("❌ ENVİRONMENT DEĞERLERİ YANLIŞ!")
        
        if env_api_id != CORRECT_API_ID:
            print(f"❌ API_ID Sorunu: {env_api_id} != {CORRECT_API_ID}")
        
        if env_api_hash != CORRECT_API_HASH:
            print(f"❌ API_HASH Sorunu: '{env_api_hash}' != '{CORRECT_API_HASH}'")
    
    print_separator("SORUN GİDERME ÖNERİLERİ")
    
    if env_api_id != CORRECT_API_ID or env_api_hash != CORRECT_API_HASH:
        print("1. .env dosyasını doğrudan düzenleyip API_ID ve API_HASH değerlerini güncelleyin:")
        print(f"   API_ID={CORRECT_API_ID}")
        print(f"   API_HASH={CORRECT_API_HASH}")
        print("\n2. Tüm oturum dosyalarını temizleyin:")
        print("   rm -f telegram_session*.session*")
        print("\n3. Sonra tekrar deneyin:")
        print("   bash start.sh")
    else:
        print("👍 API kimlik bilgileriniz doğru yüklenmiş!")
        print("Başka bir sorun olmalı. Lütfen `start.sh` betiğini çalıştırın.")

if __name__ == "__main__":
    asyncio.run(test_connection())
