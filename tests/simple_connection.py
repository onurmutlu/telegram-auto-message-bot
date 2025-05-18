#!/usr/bin/env python3
# filepath: /Users/siyahkare/code/telegram-bot/simple_connection.py
"""
Ultra-basit Telegram API bağlantı testi.
"""
import asyncio
from telethon import TelegramClient, errors

# API Kimlik Bilgileri - doğrudan kodda tanımlı
API_ID = 23692263
API_HASH = "ff5d6053b266f78d1293f9343f40e77e"

async def main():
    print("Ultra-basit Telegram API Bağlantı Testi")
    print(f"API_ID: {API_ID}")
    print(f"API_HASH: {API_HASH}")
    
    # İstemci oluştur
    client = TelegramClient('simple_test', API_ID, API_HASH)
    
    try:
        print("Bağlanılıyor...")
        await client.connect()
        
        if not client.is_connected():
            print("Bağlantı başarısız!")
            return
        
        print("Bağlantı başarılı!")
        print("API doğrulaması tamamlanıyor...")
        
        # API kimlik doğrula (bu API ID ve HASH geçersizse hata verecektir)
        try:
            # NOT: GetConfig, auth gerektirir, istemci bağlanabilse bile.
            # Bu nedenle, me_request yapacağız, bu da auth gerektirmeden çalışır.
            is_authorized = await client.is_user_authorized()
            print(f"Kullanıcı oturum durumu: {'Oturum açmış' if is_authorized else 'Oturum açmamış'}")
            
            # Auth gerektirmeyen API çağrısı
            await client.get_peer_dialogs()
            print("API kimlik bilgileri doğru!")
            
        except errors.ApiIdInvalidError as e:
            print(f"API ID/HASH geçersiz: {e}")
            return
            
    except Exception as e:
        print(f"Hata: {type(e).__name__}: {e}")
    finally:
        if client.is_connected():
            await client.disconnect()
            print("Bağlantı kapatıldı.")

if __name__ == "__main__":
    asyncio.run(main())
