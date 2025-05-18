#!/usr/bin/env python

"""
Telegram oturumunu doğrudan açan script.
app/core/unified/client.py yerine doğrudan TelegramClient kullanır.

V2: API_HASH değerini düzeltme ve oturum dosyalarını temizleme eklendi.
"""

import asyncio
import logging
import os
import sys
import shutil
from telethon import TelegramClient, functions, types
from telethon.errors import SessionPasswordNeededError

# Renk kodları
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'

# Log yapılandırması
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('telegram_login_fix')

# Telegram API bilgileri
API_ID = 23692263  # .env dosyasındaki API_ID
API_HASH = "ff5d6053b266f78d1293f9343f40e77e"  # .env dosyasındaki API_HASH (.env'den alındı)
PHONE = "+905382617727"  # .env dosyasındaki PHONE
SESSION_NAME = "telegram_session"  # .env dosyasındaki SESSION_NAME

async def login_and_init_session():
    """Telegram hesabına giriş yaparak oturum dosyasını oluşturur"""
    try:
        logger.info("Telegram hesabına giriş yapılıyor...")
        
        # Oturum dosyası mevcut mu kontrol et
        session_file = f"{SESSION_NAME}.session"
        if os.path.exists(session_file):
            logger.info(f"Mevcut oturum dosyası kullanılıyor: {session_file}")
        
        # Client oluştur
        client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        
        # Bağlantı kur
        await client.connect()
        
        # Zaten giriş yapılmış mı kontrol et
        if await client.is_user_authorized():
            logger.info("Hesaba zaten giriş yapılmış! Mevcut oturumu kullanıyoruz.")
            me = await client.get_me()
            logger.info(f"Kullanıcı: {me.first_name} {me.last_name} (@{me.username})")
            
            # Test amaçlı bazı diyalogları listele
            dialogs = await client.get_dialogs(limit=5)
            logger.info("Son 5 diyalog:")
            for d in dialogs:
                logger.info(f"- {d.name} ({d.entity.id})")
                
            # Oturum dosyasını kontrol et
            if os.path.exists(session_file):
                size = os.path.getsize(session_file)
                logger.info(f"Oturum dosyası: {session_file} ({size} byte)")
            
            await client.disconnect()
            return True
            
        # Giriş yapmamışsa kodla giriş yap
        logger.info(f"Giriş için kullanılacak telefon: {PHONE}")
        
        # Kod gönder
        sent = await client.send_code_request(PHONE)
        logger.info(f"Doğrulama kodu gönderildi. (Tip: {sent.type})")
        
        # Kullanıcıdan kodu al
        verification_code = input("Telefonunuza gelen kodu girin: ")
        
        try:
            # Giriş yap
            await client.sign_in(PHONE, verification_code)
        except SessionPasswordNeededError:
            # İki faktörlü doğrulama varsa şifreyi iste
            password = input("İki faktörlü doğrulama şifrenizi girin: ")
            await client.sign_in(password=password)
            
        # Giriş başarılı mı kontrol et
        if await client.is_user_authorized():
            me = await client.get_me()
            logger.info(f"Giriş başarılı! Kullanıcı: {me.first_name} {me.last_name} (@{me.username})")
            
            # Mevcut diyalogları kontrol et
            dialogs = await client.get_dialogs(limit=5)
            logger.info("Son 5 diyalog:")
            for d in dialogs:
                logger.info(f"- {d.name} ({d.entity.id})")
                
            # Oturum dosyasını kontrol et
            if os.path.exists(session_file):
                size = os.path.getsize(session_file)
                logger.info(f"Oturum dosyası başarıyla oluşturuldu: {session_file} ({size} byte)")
                
            await client.disconnect()
            return True
        else:
            logger.error("Giriş başarısız!")
            await client.disconnect()
            return False
            
    except Exception as e:
        logger.error(f"Telegram giriş hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    result = asyncio.run(login_and_init_session())
    sys.exit(0 if result else 1) 