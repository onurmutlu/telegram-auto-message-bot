#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Bot Client

Telegram hesabına bağlanan istemci uygulaması.
Her bir client tek bir Telegram hesabını temsil eder.
"""

import os
import asyncio
import logging
import signal
import sys
from datetime import datetime

# Modül ve paket eklemelerinden önce PYTHONPATH'i yapılandır
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.logger import setup_logging
from app.services.telegram_client import TelegramClient
from app.services.base_service import BaseService
from app.services.service_manager import ServiceManager
from app.services.user_service import UserService
from app.services.group_service import GroupService
from app.services.message_service import MessageService
from app.db.session import init_db
from app.models import User, Group

# Loglama yapılandırması
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"client_{settings.SESSION_NAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

setup_logging(log_file=LOG_FILE)
logger = logging.getLogger("app.client")

# Sinyal işleyicileri
stop_event = asyncio.Event()

def signal_handler(sig, frame):
    """Sinyal işleyici fonksiyonu"""
    logger.info(f"Sinyal alındı: {sig}. Uygulamayı durduruyorum...")
    stop_event.set()

# Sinyalleri kaydet
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def shutdown(service_manager: ServiceManager):
    """
    Uygulamayı güvenli bir şekilde kapatır.
    
    Args:
        service_manager: Servis yöneticisi
    """
    logger.info("Uygulamayı durduruyorum...")
    
    # Tüm servisleri durdur
    await service_manager.stop_all_services()
    
    # Uygulama işlemine son ver
    logger.info("Uygulama durduruldu.")

async def main():
    """
    Ana uygulama fonksiyonu.
    
    Client uygulamasını başlatır ve servisleri yönetir.
    """
    try:
        logger.info(f"Telegram Bot Client başlatılıyor (Oturum: {settings.SESSION_NAME})...")
        
        # Veritabanını başlat
        logger.info("Veritabanı bağlantısı kuruluyor...")
        init_db()
        
        # Servis yöneticisini oluştur
        service_manager = ServiceManager()
        
        # TDLib istemcisini oluştur
        session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sessions")
        os.makedirs(session_dir, exist_ok=True)
        
        # Client yapılandırması
        client_config = {
            "api_id": settings.API_ID,
            "api_hash": settings.API_HASH.get_secret_value(),  # SecretStr tipindeki değeri güvenli şekilde al
            "phone": settings.PHONE,
            "session_name": settings.SESSION_NAME,
            "files_directory": os.path.join(session_dir, settings.SESSION_NAME),
        }
        
        # Servisleri kaydedelim
        logger.info("Servisleri kaydediyorum...")
        
        # TDLib istemcisini oluştur ve bağlan
        client = TelegramClient(config=client_config)
        await client.connect()
        
        if not client.is_authorized():
            logger.info("Telegram hesabı yetkilendirilmemiş. Giriş yapılıyor...")
            auth_result = await client.phone_login(settings.PHONE)
            
            if not auth_result:
                logger.error("Yetkilendirme başarısız oldu. Uygulama durduruluyor.")
                return
                
        # Servisleri oluştur
        user_service = UserService(client=client, stop_event=stop_event)
        group_service = GroupService(client=client, stop_event=stop_event, user_service=user_service)
        message_service = MessageService(client=client, stop_event=stop_event)
        
        # Servisleri kaydet
        service_manager.register_service(user_service)
        service_manager.register_service(group_service)
        service_manager.register_service(message_service)
        
        # Client bilgilerini al
        me = await client.get_me()
        logger.info(f"Bağlantı sağlandı: {me.first_name} {me.last_name} (@{me.username})")
        
        # Servisleri başlat
        logger.info("Servisleri başlatıyorum...")
        await service_manager.start_all_services()
        
        # Durdurma olayını bekle
        logger.info("Uygulama çalışıyor. Durdurmak için CTRL+C tuşlarına basın.")
        await stop_event.wait()
        
        # Uygulamayı durdur
        await shutdown(service_manager)
        
    except Exception as e:
        logger.exception(f"Uygulama hatası: {str(e)}")
        # Uygulama beklenmedik şekilde dursa bile servisleri düzgün kapatalım
        if 'service_manager' in locals():
            await shutdown(service_manager)

if __name__ == "__main__":
    # Uygulamayı başlat
    asyncio.run(main()) 