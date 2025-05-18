#!/usr/bin/env python3
# filepath: /Users/siyahkare/code/telegram-bot/barebones_tg_test.py
"""
Telegram API bağlantısını test etmek için çok temel bir betik.
Bu betik yalnızca en temel bağlantı ve API doğrulamasını yapar.
"""
import os
import sys
import asyncio
import logging
from telethon import TelegramClient, functions, errors
import datetime

# Loglama ayarlaması
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# API Bilgileri
API_ID_1 = 23692263
API_HASH_1 = 'ff5d6053b266f78d1293f9343f40e77e'  # Tam hash değerinizi kontrol edin!

API_ID_2 = 20689123
API_HASH_2 = '74dcf2a06df47f54389bec40303e3aca'

# Hangi API bilgisini kullanacağımızı belirle (1 veya 2)
USE_CREDENTIAL_SET = 2

if USE_CREDENTIAL_SET == 1:
    API_ID = API_ID_1
    API_HASH = API_HASH_1
    print(f"1. Kimlik bilgisi seti kullanılıyor: API_ID={API_ID}")
else:
    API_ID = API_ID_2
    API_HASH = API_HASH_2
    print(f"2. Kimlik bilgisi seti kullanılıyor: API_ID={API_ID}")

# Benzersiz bir session ismi
SESSION_NAME = f"barebones_test_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
print(f"Oturum adı: {SESSION_NAME}")

async def test_connection():
    """API bağlantısını en basit şekilde test eder."""
    print("-" * 50)
    print(f"Bağlantı testi başlıyor: API_ID={API_ID}, API_HASH={API_HASH[:4]}...{API_HASH[-4:]}")
    print("-" * 50)
    
    # Zamanı kaydet
    start_time = datetime.datetime.now()
    
    # İstemci oluştur (basit yapılandırmayla)
    client = TelegramClient(
        SESSION_NAME,
        API_ID,
        API_HASH,
        receive_updates=False,  # Güncellemeleri alma (daha az yük)
        auto_reconnect=False    # Otomatik yeniden bağlanma yok (tek bir test)
    )
    
    try:
        # Bağlan
        print("Bağlantı kuruluyor...")
        await client.connect()
        
        if not client.is_connected():
            print("HATA: Bağlantı kurulamadı!")
            return False
        
        print("Bağlantı başarılı!")
        
        # Basit bir RPC çağrısı yap - Telegram sürümünü al
        print("Telegram API sürüm bilgisi sorgulanıyor...")
        try:
            # 10 saniye zaman aşımıyla bekle
            result = await asyncio.wait_for(
                client(functions.help.GetConfigRequest()), 
                timeout=10
            )
            print(f"Telegram API Sürümü: {result.dc_options[0].cdn}")
            print(f"Kullanılan DC: {result.this_dc}")
            print("API doğrulaması başarılı!")
            return True
        except asyncio.TimeoutError:
            print("HATA: Telegram API sorgusu zaman aşımına uğradı (10 saniye)")
            return False
        except errors.ApiIdInvalidError:
            print("HATA: API ID veya API HASH geçersiz!")
            return False
        except Exception as e:
            print(f"HATA: API sorgusu başarısız: {type(e).__name__}: {e}")
            return False
            
    except Exception as e:
        print(f"HATA: Bağlantı kurulurken hata oluştu: {type(e).__name__}: {e}")
        return False
    finally:
        # İşlem süresi
        end_time = datetime.datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        print(f"Test süresi: {elapsed:.2f} saniye")
        
        # Bağlantıyı kapat
        if client.is_connected():
            print("Bağlantı kesiliyor...")
            await client.disconnect()
            print("Bağlantı kesildi.")
        
        # Oturum dosyasını temizle
        session_path = f"{SESSION_NAME}.session"
        if os.path.exists(session_path):
            os.remove(session_path)
            print(f"{session_path} dosyası silindi.")
            
        return False

if __name__ == "__main__":
    # Ana fonksiyonu çalıştır
    try:
        result = asyncio.run(test_connection())
        if result:
            print("\nAPI bağlantı testi BAŞARILI!")
            sys.exit(0)
        else:
            print("\nAPI bağlantı testi BAŞARISIZ!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nTest kullanıcı tarafından kesildi.")
        sys.exit(1)
