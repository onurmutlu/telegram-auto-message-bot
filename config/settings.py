"""
# ============================================================================ #
# Dosya: settings.py
# Yol: /Users/siyahkare/code/telegram-bot/config/settings.py
# İşlev: Bot yapılandırma ayarlarını .env dosyasından yükler.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class Config:
    """
    Bot yapılandırma sınıfı.
    
    Bu sınıf, botun çalışması için gerekli yapılandırma ayarlarını .env dosyasından
    veya ortam değişkenlerinden yükler.
    """
    
    def __init__(self, env_path: str = ".env"):
        """
        Config sınıfının başlatıcısı.
        
        Args:
            env_path: .env dosyasının yolu
        """
        # .env dosyasını yükle
        self.load_success = load_dotenv(env_path)
        if not self.load_success:
            logger.warning(f".env dosyası bulunamadı: {env_path}, ortam değişkenleri kullanılacak")
        
        # Telegram yapılandırması
        self.telegram = self._load_telegram_config()
        
        # Veritabanı yapılandırması
        self.database = self.db = self._load_database_config()
        
        # Mesajlaşma ayarları
        self.messaging = self._load_messaging_config()
        
        # Genel ayarlar
        self.settings = self._load_general_settings()
        
        logger.info("Yapılandırma yüklendi")
    
    def _load_telegram_config(self) -> Any:
        """
        Telegram yapılandırmasını yükler.
        
        Returns:
            Any: Telegram yapılandırması
        """
        class TelegramConfig:
            def __init__(self):
                self.api_id = os.environ.get('API_ID')
                self.api_hash = os.environ.get('API_HASH')
                self.bot_token = os.environ.get('BOT_TOKEN')
                self.session_name = os.environ.get('SESSION_NAME', 'bot_session')
                
                # Opsiyonel proxy ayarları
                proxy_host = os.environ.get('PROXY_HOST')
                proxy_port = os.environ.get('PROXY_PORT')
                proxy_username = os.environ.get('PROXY_USERNAME')
                proxy_password = os.environ.get('PROXY_PASSWORD')
                
                if proxy_host and proxy_port:
                    self.proxy = {
                        'proxy_type': os.environ.get('PROXY_TYPE', 'socks5'),
                        'addr': proxy_host,
                        'port': int(proxy_port),
                        'username': proxy_username,
                        'password': proxy_password
                    }
                else:
                    self.proxy = None
        
        return TelegramConfig()
    
    def _load_database_config(self) -> Any:
        """
        Veritabanı yapılandırmasını yükler.
        
        Returns:
            Any: Veritabanı yapılandırması
        """
        class DatabaseConfig:
            def __init__(self):
                self.type = os.environ.get('DB_TYPE', 'sqlite')
                
                # SQLite için
                if self.type.lower() == 'sqlite':
                    self.path = os.environ.get('DB_PATH', 'data/bot.db')
                    
                # PostgreSQL için
                elif self.type.lower() == 'postgres':
                    self.host = os.environ.get('DB_HOST', 'localhost')
                    self.port = int(os.environ.get('DB_PORT', '5432'))
                    self.user = os.environ.get('DB_USER')
                    self.password = os.environ.get('DB_PASSWORD')
                    self.database = os.environ.get('DB_NAME')
        
        return DatabaseConfig()
    
    def _load_messaging_config(self) -> Any:
        """
        Mesajlaşma yapılandırmasını yükler.
        
        Returns:
            Any: Mesajlaşma yapılandırması
        """
        class MessagingConfig:
            def __init__(self):
                self.templates_path = os.environ.get('TEMPLATES_PATH', 'data/messages.json')
                self.invites_path = os.environ.get('INVITES_PATH', 'data/invites.json')
                self.responses_path = os.environ.get('RESPONSES_PATH', 'data/responses.json')
        
        return MessagingConfig()
    
    def _load_general_settings(self) -> Any:
        """
        Genel ayarları yükler.
        
        Returns:
            Any: Genel ayarlar
        """
        class GeneralSettings:
            def __init__(self):
                self.environment = os.environ.get('ENVIRONMENT', 'production')
                self.debug_mode = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
                self.admin_groups = self._parse_list(os.environ.get('ADMIN_GROUPS', ''))
                self.super_users = self._parse_list(os.environ.get('SUPER_USERS', ''))
            
            def _parse_list(self, value: str) -> list:
                return [item.strip() for item in value.split(',')] if value else []
        
        return GeneralSettings()
    
    @property
    def env(self):
        """
        Ortam bilgisini döndürür.
        Varsayılan olarak "production" değerini döndürür.
        """
        return self.settings.environment

    @property
    def debug(self):
        """
        Debug modunu döndürür.
        Varsayılan olarak False değerini döndürür.
        """
        return self.settings.debug_mode

    @property
    def admin_groups(self):
        """
        Yönetici gruplarını döndürür (Yönetici/Kurucu olduğunuz gruplar).
        """
        return self.settings.admin_groups

    @property
    def super_users(self):
        """
        Süper kullanıcıların listesini döndürür.
        """
        return self.settings.super_users