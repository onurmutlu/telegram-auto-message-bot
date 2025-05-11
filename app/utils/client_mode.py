# Yeni bir yardımcı dosya oluşturun:

"""
Telethon istemcisinin mod kontrolü için yardımcı fonksiyonlar
"""
import os
from telethon import TelegramClient
from typing import Optional, Any

async def is_bot_mode(client: TelegramClient) -> bool:
    """
    İstemcinin bot modunda çalışıp çalışmadığını kontrol eder.
    
    Args:
        client: Telegram istemcisi
        
    Returns:
        bool: Bot modundaysa True, kullanıcı hesabıysa False
    """
    # İstemci bağlı değilse bağlan
    if not client.is_connected():
        await client.connect()
    
    # me özelliğini kullanarak bot olup olmadığını kontrol et
    me = await client.get_me()
    return getattr(me, 'bot', False)

async def get_appropriate_client(config: Any) -> TelegramClient:
    """
    Yapılandırmaya göre uygun istemci oluşturur.
    
    Args:
        config: Yapılandırma nesnesi
        
    Returns:
        TelegramClient: Yapılandırılmış Telegram istemcisi
    """
    # Mod kontrolü
    user_mode = getattr(config.telegram, 'user_mode', False) or not hasattr(config.telegram, 'bot_token')
    
    # İstemci oluştur
    client = TelegramClient(
        config.telegram.session_name,
        config.telegram.api_id,
        config.telegram.api_hash,
        proxy=getattr(config.telegram, 'proxy', None)
    )
    
    # İstemciyi başlat
    if user_mode:
        phone = getattr(config.telegram, 'phone', None)
        await client.start(phone=phone)
    else:
        await client.start(bot_token=config.telegram.bot_token)
    
    return client