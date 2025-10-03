#!/usr/bin/env python3
"""
Telegram Bot - Konfigürasyon
-----------------
Bot ayarlarını yönetir.
"""
import os
import logging
from typing import Dict, Any, Optional

# Loglama
logger = logging.getLogger(__name__)

# Varsayılan ayarlar
DEFAULT_SETTINGS = {
    # Mesajlaşma ayarları
    "AUTO_ENGAGE": True,
    "ENGAGE_INTERVAL": 1,  # Saat cinsinden
    "ENGAGE_MODE": "Grup aktivitesine göre",  # Aktif kullanıcılara göre, Son mesajlara göre, Grup aktivitesine göre, Tüm gruplara
    
    # Oturum ayarları
    "SESSION_NAME": "telegram_session",
    
    # Dashboard ayarları
    "DASHBOARD_PORT": 8000,
    "DASHBOARD_HOST": "0.0.0.0",
    
    # Log ayarları
    "LOG_LEVEL": "INFO",
}

# Ayarları yükle
def load_settings() -> Dict[str, Any]:
    """Ayarları .env dosyasından veya ortam değişkenlerinden yükler."""
    settings = DEFAULT_SETTINGS.copy()
    
    # Ortam değişkenlerini kontrol et
    for key in settings.keys():
        env_value = os.getenv(key)
        if env_value is not None:
            # Boolean değerleri dönüştür
            if env_value.lower() in ["true", "false"]:
                settings[key] = env_value.lower() == "true"
            # Sayısal değerleri dönüştür
            elif env_value.isdigit():
                settings[key] = int(env_value)
            # Diğer değerleri doğrudan kullan
            else:
                settings[key] = env_value
    
    logger.info(f"Ayarlar yüklendi: {settings}")
    return settings

# Global ayarlar nesnesi
settings = load_settings()

# Ayar erişim fonksiyonları
def get_setting(key: str, default: Optional[Any] = None) -> Any:
    """Belirli bir ayarı döndürür."""
    return settings.get(key, default)

def update_setting(key: str, value: Any) -> None:
    """Belirli bir ayarı günceller."""
    settings[key] = value
    
    # Ortam değişkenini de güncelle
    os.environ[key] = str(value)
    
    logger.info(f"Ayar güncellendi: {key}={value}")

# .env dosyasını güncelle
def update_env_file(key: str, value: Any) -> None:
    """Belirli bir ayarı .env dosyasında günceller."""
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    
    if os.path.exists(env_file):
        # Dosyayı oku
        with open(env_file, "r") as f:
            lines = f.readlines()
        
        # Değişkeni bul veya ekle
        key_found = False
        new_lines = []
        
        for line in lines:
            if line.strip() and not line.strip().startswith("#"):
                if line.startswith(f"{key}="):
                    new_lines.append(f"{key}={value}\n")
                    key_found = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        # Değişken yoksa ekle
        if not key_found:
            new_lines.append(f"{key}={value}\n")
        
        # Dosyayı yaz
        with open(env_file, "w") as f:
            f.writelines(new_lines)
        
        logger.info(f".env dosyası güncellendi: {key}={value}")
    else:
        logger.warning(f".env dosyası bulunamadı: {env_file}") 