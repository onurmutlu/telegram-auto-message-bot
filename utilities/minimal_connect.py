#!/usr/bin/env python3
"""
Minimal Telegram bağlantı testi ve oturum oluşturma aracı.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient, errors

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("minimal_connect.log")
    ]
)

logger = logging.getLogger("minimal_connect")

# Çevre değişkenlerinden API bilgilerini al
API_ID = int(os.environ.get("API_ID", "23692263"))
API_HASH = os.environ.get("API_HASH", "ff5d6c93c8b1dde8aca7b87a824e0e77e")
PHONE = os.environ.get("PHONE", "+905382617727")
SESSION_NAME = os.environ.get("SESSION_NAME", "telegram_fresh_session")

async def main():
    """Ana çalışma fonksiyonu."""
    logger.info(f"Minimal Telegram bağlantı testi başlatılıyor (Session: {SESSION_NAME})")
    
    # Her seferinde yeni bir oturum oluştur
    if os.path.exists(f"{SESSION_NAME}.session"):
        logger.info(f"Mevcut oturum dosyası kullanılıyor: {SESSION_NAME}.session")
    else:
        logger.info(f"Oturum dosyası bulunamadı, yeni oturum oluşturulacak: {SESSION_NAME}.session")
    
    # TelegramClient oluştur
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    try:
        # Bağlan
        logger.info("Telegram API'ye bağlanılıyor...")
        await client.connect()
        
        # Bağlantı kontrolü
        if not client.is_connected():
            logger.error("Bağlantı kurulamadı!")
            return
        
        logger.info("Bağlantı başarılı!")
        
        # Oturum durumunu kontrol et
        is_authorized = await client.is_user_authorized()
        
        if is_authorized:
            logger.info("Kullanıcı zaten yetkilendirilmiş, kullanıcı bilgileri alınıyor...")
            me = await client.get_me()
            logger.info(f"Mevcut kullanıcı: {me.first_name} {getattr(me, 'last_name', '')} (@{me.username}) - ID: {me.id}")
            
            # Örnek bir işlem yap (mesela diyalogları al)
            async for dialog in client.iter_dialogs(limit=5):
                logger.info(f"Dialog: {dialog.name} - ID: {dialog.id}")
        else:
            logger.info("Kullanıcı henüz yetkilendirilmemiş, giriş yapılıyor...")
            
            # Telefon numarasına kod gönder
            await client.send_code_request(PHONE)
            logger.info(f"Doğrulama kodu {PHONE} numaralı telefona gönderildi.")
            
            # Kullanıcıdan kodu al
            code = input("Lütfen telefonunuza gelen kodu girin: ")
            
            try:
                # Giriş yap
                me = await client.sign_in(PHONE, code)
                logger.info(f"Başarıyla giriş yapıldı: {me.first_name} (@{me.username})")
            except errors.SessionPasswordNeededError:
                # 2FA gerekiyorsa
                logger.info("İki faktörlü kimlik doğrulama gerekli.")
                password = input("Lütfen iki faktörlü kimlik doğrulama şifrenizi girin: ")
                me = await client.sign_in(password=password)
                logger.info(f"2FA ile başarıyla giriş yapıldı: {me.first_name} (@{me.username})")
        
        # Oturum dosyası hakkında bilgi
        logger.info(f"Oturum dosyası: {SESSION_NAME}.session oluşturuldu/güncellendi.")
        logger.info(f"Oturum dosyasını hataların çözümü için kullanabilirsiniz.")
        
        # Veri yollarını görüntüle
        logger.info("Oturum dosya yolu: " + os.path.abspath(f"{SESSION_NAME}.session"))
    except Exception as e:
        logger.error(f"Hata: {str(e)}", exc_info=True)
    finally:
        # Bağlantıyı kapat
        await client.disconnect()
        logger.info("Bağlantı kapatıldı.")
        
if __name__ == "__main__":
    # Komut satırı argümanlarını kontrol et
    if len(sys.argv) > 1:
        SESSION_NAME = sys.argv[1]
    
    # Ana döngüyü başlat
    asyncio.run(main())
