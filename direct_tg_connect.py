#!/usr/bin/env python3
# filepath: /Users/siyahkare/code/telegram-bot/direct_tg_connect.py
"""
Doğrudan Telegram API bağlantısı için test
"""
import os
import asyncio
import sys
from telethon import TelegramClient, functions, errors
import logging
import time

# Hata ayıklama loglaması
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('TelegramTest')

# Test edilecek API kimlik bilgileri
# Tam değerleri doğrudan kullanın
API_ID = 20689123  # int olarak
API_HASH = '74dcf2a06df47f54389bec40303e3aca'  # string olarak

# Benzersiz oturum adı
SESSION = f"direct_test_{int(time.time())}"

async def main():
    print("-"*40)
    print(f"Doğrudan Telegram API Bağlantı Testi")
    print(f"API_ID: {API_ID} (type: {type(API_ID)})")
    print(f"API_HASH: {API_HASH[:4]}...{API_HASH[-4:]} (type: {type(API_HASH)}, length: {len(API_HASH)})")
    print(f"SESSION: {SESSION}")
    print("-"*40)
    
    # Her zaman temiz başla - varsa eski oturum dosyasını sil
    if os.path.exists(f"{SESSION}.session"):
        os.remove(f"{SESSION}.session")
        print(f"Eski oturum dosyası silindi: {SESSION}.session")

    client = None
    
    try:
        # İstemciyi oluştur (barebones yapılandırma)
        client = TelegramClient(
            SESSION, 
            API_ID, 
            API_HASH,
            device_model='Test Device',
            system_version='1.0',
            app_version='1.0',
            lang_code='tr',
            system_lang_code='tr'
        )
        
        print("İstemci oluşturuldu, bağlanıyor...")
        await client.connect()
        
        # Bağlantıyı doğrula
        if not client.is_connected():
            print("HATA: Bağlantı kurulamadı.")
            return 1
        
        print("Bağlantı BAŞARILI.")
        print(f"İstemci bağlantı durumu: {client.is_connected()}")
        
        print("\nBasit API sorgusu yapılıyor (GetConfig)...")
        try:
            config = await asyncio.wait_for(
                client(functions.help.GetConfigRequest()),
                timeout=15
            )
            print(f"API sorgusu BAŞARILI! DC: {config.this_dc}")
            return 0
        except asyncio.TimeoutError:
            print("HATA: API sorgusu zaman aşımına uğradı (15 saniye)")
            return 1
        except errors.ApiIdInvalidError:
            print("HATA: API ID veya HASH geçersiz.")
            return 1
        except Exception as e:
            print(f"HATA: API sorgusu sırasında hata: {type(e).__name__}: {e}")
            return 1
            
    except errors.ApiIdInvalidError:
        print("HATA: API ID veya HASH geçersiz.")
        return 1
    except Exception as e:
        print(f"HATA: Genel bir bağlantı hatası: {type(e).__name__}: {e}")
        return 1
    finally:
        # Bağlantıyı kapat
        if client and client.is_connected():
            print("Bağlantı kapatılıyor...")
            await client.disconnect()
            print("Bağlantı kapatıldı.")
        
        # Oturum dosyasını temizle
        if os.path.exists(f"{SESSION}.session"):
            os.remove(f"{SESSION}.session")
            print(f"Oturum dosyası silindi: {SESSION}.session")
    
    return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nTest kullanıcı tarafından kesildi.")
        sys.exit(1)
