#!/usr/bin/env python

import asyncio
import logging
from app.core.unified.client import get_client

# Log yapılandırması
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('telegram_client_test')

async def test_telegram_client():
    """Telegram client bağlantısını test et"""
    try:
        logger.info("Telegram client bağlantısı test ediliyor...")
        client = await get_client()
        
        if client:
            logger.info(f"Client bağlantısı başarılı: {client}")
            logger.info(f"Client bağlı durumda: {client.is_connected()}")
            
            # Kullanıcı bilgilerini al
            me = await client.get_me()
            logger.info(f"Kullanıcı bilgileri: {me.first_name} {me.last_name} (@{me.username})")
            
            # Diyalogları al (grupları görme yetkimiz var mı kontrol et)
            dialogs = await client.get_dialogs(limit=5)
            logger.info(f"Son 5 diyalog:")
            for dialog in dialogs:
                logger.info(f"- {dialog.name} ({dialog.entity.id})")
            
            return True
        else:
            logger.error("Client bağlantısı başarısız!")
            return False
            
    except Exception as e:
        logger.error(f"Telegram client test hatası: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    asyncio.run(test_telegram_client()) 