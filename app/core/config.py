import os
import secrets
import re
from typing import Any, Dict, List, Optional, Union
from pydantic import validator, AnyHttpUrl, SecretStr, PostgresDsn
from pydantic_settings import BaseSettings

def safe_getenv_int(name: str, default: str) -> int:
    """Güvenli bir şekilde çevre değişkenini integer'a çevirir."""
    value = os.getenv(name, default)
    # Yorum veya boşluk karakterlerini temizle
    if isinstance(value, str):
        # Yorumları temizle
        if '#' in value:
            value = value.split('#')[0].strip()
        # Tüm boşlukları temizle
        value = value.strip()
        # Boş ise, varsayılanı kullan
        if not value:
            value = default
    
    try:
        return int(value)
    except (ValueError, TypeError):
        print(f"UYARI: {name} değeri ({value}) integer'a çevrilemedi, varsayılan değer ({default}) kullanılıyor")
        return int(default)

def safe_getenv_bool(name: str, default: str) -> bool:
    """Güvenli bir şekilde çevre değişkenini boolean'a çevirir."""
    value = os.getenv(name, default)
    # Yorum veya boşluk karakterlerini temizle
    if isinstance(value, str):
        # Yorumları temizle
        if '#' in value:
            value = value.split('#')[0].strip()
        # Tüm boşlukları temizle
        value = value.strip().lower()
        # Boş ise, varsayılanı kullan
        if not value:
            value = default.lower()
    
    return value in ("true", "yes", "1", "t", "y")

class Settings(BaseSettings):
    """
    Uygulama ayarlarını yöneten merkezi sınıf.
    
    .env dosyasından veya çevre değişkenlerinden ayarları otomatik olarak yükler.
    """
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Telegram Bot"
    
    # Uygulama
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = safe_getenv_bool("DEBUG", "false")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    BOT_ENABLED: bool = safe_getenv_bool("BOT_ENABLED", "true")
    
    # JWT Yetkilendirme
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = safe_getenv_int("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")  # 7 gün
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    
    # Database
    POSTGRES_SERVER: str = os.getenv("DB_HOST", "localhost")
    POSTGRES_USER: str = os.getenv("DB_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("DB_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("DB_NAME", "telegram_bot")
    POSTGRES_PORT: str = os.getenv("DB_PORT", "5432")
    POSTGRES_DSN: Optional[str] = None
    DB_CONNECTION: Optional[str] = os.getenv("DB_CONNECTION", None)
    
    # Database bağlantı ayarları
    DB_POOL_SIZE: int = safe_getenv_int("DB_POOL_SIZE", "5")
    DB_MAX_OVERFLOW: int = safe_getenv_int("DB_MAX_OVERFLOW", "10")
    DB_POOL_TIMEOUT: int = safe_getenv_int("DB_POOL_TIMEOUT", "30")  # saniye
    DB_POOL_RECYCLE: int = safe_getenv_int("DB_POOL_RECYCLE", "1800")  # 30 dakika
    
    # SQL Echo (geliştirme için)
    SQL_ECHO: bool = safe_getenv_bool("SQL_ECHO", "false")
    
    # Telegram
    API_ID: int = safe_getenv_int("API_ID", "0")
    API_HASH: SecretStr = os.getenv("API_HASH", "")
    BOT_TOKEN: SecretStr = os.getenv("BOT_TOKEN", "")
    PHONE: str = os.getenv("PHONE", "")
    SESSION_NAME: str = os.getenv("SESSION_NAME", "telegram_session")
    USER_MODE: bool = safe_getenv_bool("USER_MODE", "true")
    
    # Telegram bağlantı ayarları
    TG_CONNECTION_RETRIES: int = safe_getenv_int("TG_CONNECTION_RETRIES", "5")
    TG_RETRY_DELAY: int = safe_getenv_int("TG_RETRY_DELAY", "1")
    TG_TIMEOUT: int = safe_getenv_int("TG_TIMEOUT", "60")  # saniye
    TG_REQUEST_RETRIES: int = safe_getenv_int("TG_REQUEST_RETRIES", "3")
    TG_FLOOD_SLEEP_THRESHOLD: int = safe_getenv_int("TG_FLOOD_SLEEP_THRESHOLD", "60")
    
    # Servis Ayarları
    MESSAGE_BATCH_SIZE: int = safe_getenv_int("MESSAGE_BATCH_SIZE", "50")
    MESSAGE_BATCH_INTERVAL: int = safe_getenv_int("MESSAGE_BATCH_INTERVAL", "30")
    SCHEDULER_INTERVAL: int = safe_getenv_int("SCHEDULER_INTERVAL", "60")
    
    # Ağ Ayarları
    SOCKET_TIMEOUT: int = safe_getenv_int("SOCKET_TIMEOUT", "30")  # saniye
    MAX_CONNECTIONS: int = safe_getenv_int("MAX_CONNECTIONS", "100")
    
    # Redis
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_SOCKET_TIMEOUT: int = safe_getenv_int("REDIS_SOCKET_TIMEOUT", "5")
    REDIS_SOCKET_CONNECT_TIMEOUT: int = safe_getenv_int("REDIS_SOCKET_CONNECT_TIMEOUT", "5")
    
    # HTTP Ayarları
    HTTP_TIMEOUT: int = safe_getenv_int("HTTP_TIMEOUT", "10")  # saniye
    
    # Email ayarları
    EMAILS_ENABLED: bool = safe_getenv_bool("EMAILS_ENABLED", "false")
    SMTP_TLS: bool = safe_getenv_bool("SMTP_TLS", "true")
    SMTP_PORT: Optional[int] = safe_getenv_int("SMTP_PORT", "587")
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST", None)
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER", None)
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD", None)
    EMAILS_FROM_EMAIL: Optional[str] = os.getenv("EMAILS_FROM_EMAIL", None)
    EMAILS_FROM_NAME: Optional[str] = os.getenv("EMAILS_FROM_NAME", None)
    
    # API Uygulama Port Ayarı
    PORT: int = safe_getenv_int("PORT", "8000")
    
    @validator("POSTGRES_DSN", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
            
        # Direkt olarak bağlantı dizesini oluştur
        db_url = f"postgresql://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}@{values.get('POSTGRES_SERVER')}:{values.get('POSTGRES_PORT')}/{values.get('POSTGRES_DB')}"
        return db_url
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            # JSON dizisi olabilir
            if v.startswith("[") and v.endswith("]"):
                try:
                    import json
                    return json.loads(v)
                except Exception:
                    pass
            
            # Virgülle ayrılmış liste olabilir
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Bilinmeyen alanları yok say

# Tek bir settings örneği oluştur
settings = Settings()

# İlave yardımcı fonksiyonlar
def get_settings() -> Settings:
    """Settings örneğini döndürür."""
    return settings 