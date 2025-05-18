#!/usr/bin/env python3
"""
# ============================================================================ #
# Dosya: test_full_bot.py
# İşlev: Telegram bot'unu tam olarak test etmek için yardımcı script.
#
# Kullanım: python test_full_bot.py
# ============================================================================ #
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

# Temel loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"bot_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)

logger = logging.getLogger("bot_tester")

# Ana uygulama sınıfını içe aktar
from app.main import TelegramBot

async def run_test():
    """Bot'u çalıştır ve test et."""
    logger.info("Bot testi başlatılıyor...")
    
    # Bot'u oluştur
    bot = TelegramBot()
    
    try:
        # Bot'u başlat
        initialized = await bot.initialize()
        if not initialized:
            logger.error("Bot başlatılamadı!")
            return False
        
        logger.info("Bot başarıyla başlatıldı.")
        
        # Servislerin durumunu kontrol et
        services = bot.get_services()
        logger.info(f"Aktif servisler: {', '.join(services.keys())}")
        
        for name, service in services.items():
            status = await service.get_status() if hasattr(service, 'get_status') else {"initialized": "Bilinmiyor"}
            logger.info(f"Servis '{name}' durumu: {status}")
        
        # Client bağlantı durumunu kontrol et
        if not bot.client.is_connected():
            logger.info("Telegram ile bağlantı kuruluyor...")
            await bot.client.connect()
            
        # API kimliğini doğrula
        logger.info("Telegram API kimliği doğrulanıyor...")
        try:
            config = await bot.client.get_me()
            logger.info(f"API doğrulama başarılı: {config.first_name if config else 'Bilinmeyen kullanıcı'}")
        except Exception as e:
            logger.warning(f"API doğrulama hatası: {str(e)}")
        
        # Bot'u çalıştır - client bağlantısını daha önce kontrol ettik
        logger.info("Bot çalışıyor. Kapatmak için Ctrl+C kullanın.")
        await asyncio.sleep(5)  # Kısa bir süre bekle
        
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu (Ctrl+C)")
    except Exception as e:
        logger.error(f"Bot çalıştırılırken hata: {str(e)}", exc_info=True)
    finally:
        # Bot'u temiz bir şekilde kapat
        logger.info("Bot kapatılıyor...")
        await bot.cleanup()
        logger.info("Bot testi tamamlandı.")

if __name__ == "__main__":
    try:
        # Ana event loop'u çalıştır
        asyncio.run(run_test())
    except KeyboardInterrupt:
        print("Program kullanıcı tarafından sonlandırıldı.")
    except Exception as e:
        print(f"Program çalıştırılırken hata: {str(e)}")
