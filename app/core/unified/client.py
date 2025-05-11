"""
Telegram client bağlantısı için yardımcı fonksiyonlar
"""
import logging
import asyncio
import os
from typing import Optional
from telethon import TelegramClient
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global client nesnesi
_client = None
_client_lock = asyncio.Lock()

async def get_client() -> Optional[TelegramClient]:
    """
    Telegram client nesnesini döndürür. Eğer bağlantı yoksa bağlantı kurar.
    
    Returns:
        Optional[TelegramClient]: Bağlantı kurulmuş client nesnesi veya None
    """
    global _client
    
    if _client and _client.is_connected():
        return _client
        
    async with _client_lock:
        # Lock içinde tekrar kontrol et (başka bir thread bağlantı kurmuş olabilir)
        if _client and _client.is_connected():
            return _client
            
        try:
            logger.info("Telegram client bağlantısı kuruluyor...")
            
            # Session dosyasının varlığını kontrol et
            session_file = f"{settings.SESSION_NAME}.session"
            if not os.path.exists(session_file):
                logger.warning(f"Session dosyası bulunamadı: {session_file}")
                # Session dosyası yoksa önce telegram_login.py dosyasını çalıştırmak gerekiyor
                logger.error("Telegram hesabına giriş yapılmamış! Lütfen önce telegram_login.py dosyasını çalıştırın.")
                return None
            
            # API_HASH değerini SecretStr türünden string'e dönüştür
            api_hash = settings.API_HASH.get_secret_value() if hasattr(settings.API_HASH, 'get_secret_value') else str(settings.API_HASH)
            
            # Client oluştur
            _client = TelegramClient(
                settings.SESSION_NAME,
                settings.API_ID,
                api_hash,
                proxy=settings.PROXY if hasattr(settings, "PROXY") else None,
                connection_retries=5
            )
            
            # Bağlantı kur
            await _client.connect()
            
            # Giriş yapıldı mı kontrol et
            if not await _client.is_user_authorized():
                logger.error("Telegram hesabına giriş yapılmamış! Lütfen önce telegram_login.py dosyasını çalıştırın.")
                await _client.disconnect()
                _client = None
                return None
                
            # Bağlantı başarılı
            me = await _client.get_me()
            logger.info(f"Telegram client bağlantısı başarılı. Kullanıcı: {me.first_name} (@{me.username})")
            return _client
            
        except Exception as e:
            logger.error(f"Telegram client bağlantı hatası: {e}", exc_info=True)
            
            if _client:
                try:
                    await _client.disconnect()
                except:
                    pass
                    
            _client = None
            return None

async def disconnect_client():
    """
    Mevcut client bağlantısını kapatır
    """
    global _client
    
    if _client:
        try:
            await _client.disconnect()
            logger.info("Telegram client bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"Client bağlantısını kapatma hatası: {e}")
        finally:
            _client = None 