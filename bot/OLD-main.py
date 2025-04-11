import sys
import os
from pathlib import Path

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

# Yapılandırmayı iki şekilde de içe aktarabilirsiniz:
try:
    # Öncelikle doğrudan settings'den almayı dene
    from config.settings import Config
except ImportError:
    try:
        # Olmadıysa, config üzerinden almayı dene
        from config.config import Config
    except ImportError:
        # Son çare olarak config paketinden almayı dene
        from config import Config

import asyncio
import logging
import logging.config
from dotenv import load_dotenv
from telethon import TelegramClient

# Dashboard modülünü içe aktar
from bot.utils.interactive_dashboard import InteractiveDashboard

# Logging yapılandırması
logging_config = {
    'version': 1,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': 'runtime/logs/bot_debug.log',
            'mode': 'a'
        }
    },
    'loggers': {
        'bot': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
            'propagate': False
        },
        'telethon': {
            'level': 'INFO',
            'handlers': ['file'],
            'propagate': False
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
}

logging.config.dictConfig(logging_config)

logger = logging.getLogger(__name__)

# Klavye girişlerini dinleyen asenkron fonksiyon
async def keyboard_input_handler(bot, config, user_db):
    """Klavye komutlarını dinler ve dashboard'u başlatır"""
    
    while True:
        try:
            cmd = await asyncio.to_thread(input)
            
            if cmd.lower() == 'i':
                logger.info("Interactive Dashboard başlatılıyor...")
                try:
                    from bot.utils.interactive_dashboard import InteractiveDashboard
                    
                    # Servis nesneleri sözlüğü - bot.services attribute'undan al
                    # Bu şekilde tüm servisler için tutarlı erişim sağlanır
                    if hasattr(bot, 'services') and bot.services:
                        services_dict = bot.services
                    else:
                        # Geriye dönük uyumluluk için
                        services_dict = {}
                        if hasattr(bot, 'group_service'):
                            services_dict["group"] = bot.group_service
                        if hasattr(bot, 'dm_service'):
                            services_dict["dm"] = bot.dm_service
                        if hasattr(bot, 'reply_service'):
                            services_dict["reply"] = bot.reply_service
                        if hasattr(bot, 'user_service'):
                            services_dict["user"] = bot.user_service
                    
                    # Dashboard'u başlat
                    dashboard = InteractiveDashboard(services_dict, config, user_db)
                    await dashboard.run()
                    logger.info("Interactive Dashboard kapatıldı")
                except Exception as e:
                    logger.error(f"Dashboard hatası: {str(e)}", exc_info=True)
                
        except asyncio.CancelledError:
            # Bot kapatılıyorsa bu görevi de sonlandır
            break
            
        except Exception as e:
            logger.error(f"Klavye girişi işlenirken hata: {e}", exc_info=True)

async def main():
    """
    Ana bot işlevi
    """
    logger.info("Ana Telegram Botu başlatılıyor...")
    
    try:
        # Config yükleme
        config_instance = Config()
        
        # Eğer config sınıfı load_config metodu destekliyorsa
        if hasattr(config_instance, 'load_config'):
            config = config_instance.load_config()
        else:
            config = config_instance
            
        # Database bağlantısı
        from database.user_db import UserDatabase
        db_path = os.environ.get('DB_PATH', 'runtime/database/users.db')
        user_db = UserDatabase(db_path)
        
        # Service factory ve client düzenli hali
        from bot.services.service_factory import ServiceFactory
        client = TelegramClient('session/bot_session', int(os.getenv("API_ID", 0)), os.getenv("API_HASH", ""))
        service_factory = ServiceFactory(client, config, user_db)
        
        # Ana bot nesnesi oluştur
        logger.info("Bot yapılandırma bilgileri yüklendi, servisler başlatılıyor...")
        
        # Çevre değişkenlerini yükle
        load_dotenv()
        
        # Bu kısım doğru ve çalışıyor
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        phone_number = os.getenv("PHONE_NUMBER")

        # Telegram client bağlantısı
        client = TelegramClient('mysession', api_id, api_hash)
        
        # Botu başlat
        logger.info("Bot başlatılıyor...")
        await bot.start()

        # Servisleri açıkça başlat
        logger.info("Servisleri başlatıyor...")

        # Debug için çıktı
        logger.info(f"Bot servis özellikleri: {dir(bot)}")
        if hasattr(bot, 'services'):
            logger.info(f"Bot servis anahtarları: {bot.services.keys()}")

        if hasattr(bot, 'init_services'):
            success = await bot.init_services()
            logger.info(f"Servisler başlatıldı: {success}")
        elif hasattr(bot, 'start_services'):
            await bot.start_services()
        
        logger.info("Bot çalışmaya başladı, Ctrl+C ile durdurabilirsiniz")
        logger.info("Dashboard'u açmak için 'i' tuşuna basın")
        
        # Klavye girdilerini işleyen görevi başlat
        input_task = asyncio.create_task(keyboard_input_handler(bot, config, user_db))
        
        # Ana döngü - hem bot çalışır hem de klavye girişlerini dinler
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Ana görev iptal edilirse, klavye görevini de iptal et
            input_task.cancel()
            raise
            
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Bot çalışırken hata oluştu: {e}", exc_info=True)
    finally:
        # Varsa botu durdur ve kaynakları serbest bırak
        if 'bot' in locals() and hasattr(bot, 'stop'):
            logger.info("Bot kapatılıyor...")
            await bot.stop()
        
        logger.info("Bot kapatıldı.")

def run():
    """Ana botu çalıştırır"""
    asyncio.run(main())

if __name__ == "__main__":
    run()