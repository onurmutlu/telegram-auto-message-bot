# Bu dosya sadece settings.py'daki Config sınıfını içe aktarır

import os
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

from .settings import Config

# Gerekirse ek yapılandırma fonksiyonları buraya eklenebilir
def get_default_config():
    """Varsayılan yapılandırmayı döndürür."""
    return Config()

# Telegram için ayrı bir sınıf oluşturun, .env'den okur
class TelegramConfig:
    def __init__(self):
        # .env dosyasından değerleri oku, bulunamazsa varsayılan değerleri kullan
        self.session_name = os.getenv("SESSION_NAME", "telegram_session")
        
        # api_id sayısal değer olduğundan int'e dönüştürme gerekiyor
        api_id_str = os.getenv("API_ID", "123456")
        try:
            self.api_id = int(api_id_str)
        except ValueError:
            self.api_id = 123456
            
        self.api_hash = os.getenv("API_HASH", "your_api_hash_here")
        
        # user_mode bir boolean değer olduğundan string->bool dönüşümü gerekiyor
        self.user_mode = os.getenv("USER_MODE", "true").lower() in ["true", "yes", "1"]
        
        self.phone = os.getenv("PHONE", "+905551234567")
        
        # Opsiyonel: proxy değeri varsa ekle
        proxy_str = os.getenv("PROXY", None)
        self.proxy = proxy_str if proxy_str else None
        
        # Opsiyonel: bot_token varsa ekle
        self.bot_token = os.getenv("BOT_TOKEN", None)

class Config:
    def __init__(self):
        self.telegram = TelegramConfig()
        
    # Metodu sınıfa uygun şekilde değiştirin
    @classmethod
    def load_config(cls):
        """
        Yapılandırma yükler ve döndürür.
        
        Returns:
            Config: Doldurulmuş yapılandırma nesnesi
        """
        # Mevcut metodun içeriğini koruyun, sadece self -> cls olarak değiştirin
        config = cls()  # self.__class__() yerine cls() kullanın
        # ... diğer kod ...
        return config

    def get_setting(self, key, default=None):
        """
        Yapılandırma ayarını güvenli bir şekilde alır.
        
        Args:
            key (str): Ayar anahtarı
            default: Ayar bulunamazsa döndürülecek değer
        """
        # Nokta içeren anahtarlar için (örn: 'telegram.api_id')
        if '.' in key:
            parts = key.split('.')
            current = self
            for part in parts:
                if hasattr(current, part):
                    current = getattr(current, part)
                else:
                    return default
            return current
        
        # Basit anahtarlar için
        return getattr(self, key, default)