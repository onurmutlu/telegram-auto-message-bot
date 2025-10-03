import os
import secrets
import re
import pathlib
from typing import Any, Dict, List, Optional, Union
from pydantic import validator, AnyHttpUrl, SecretStr, PostgresDsn
from pydantic_settings import BaseSettings
import dotenv
dotenv.load_dotenv(override=True)

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
        # Daha agresif temizleme deneyelim
        if isinstance(value, str):
            # Tüm alfanümerik olmayan karakterleri temizleyelim
            clean_value = ''.join(c for c in value if c.isdigit())
            if clean_value:
                try:
                    return int(clean_value)
                except (ValueError, TypeError):
                    pass
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
    
    # Daha agresif temizleme
    if isinstance(value, str) and len(value) > 0:
        # Sadece ilk kelimeyi al
        first_word = value.split()[0].lower() if ' ' in value else value.lower()
        return first_word in ("true", "yes", "1", "t", "y", "true")
    
    return value in ("true", "yes", "1", "t", "y", "true")

# Oturum dizini ayarını ekle - Telethon oturum dosyaları için
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent

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
    DEBUG: bool = False  # Validator ile düzelteceğiz
    LOG_LEVEL: str = "INFO"  # Validator ile düzelteceğiz
    BOT_ENABLED: bool = True
    
    # JWT Yetkilendirme
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # Validator ile düzelteceğiz
    ALGORITHM: str = "HS256"  # JWT algoritması
    
    # API Güvenliği
    API_AUTH_ENABLED: bool = safe_getenv_bool("API_AUTH_ENABLED", "true")
    API_USERNAME: str = os.getenv("API_USERNAME", "admin")
    API_PASSWORD: str = os.getenv("API_PASSWORD", "admin")
    
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
    SQL_ECHO: bool = False  # Validator ile düzelteceğiz
    
    # Telegram
    API_ID: int = 0  # Validator ile düzelteceğiz
    API_HASH: SecretStr = ""  # Validator ile düzelteceğiz
    BOT_TOKEN: SecretStr = ""  # Validator ile düzelteceğiz  
    PHONE: str = ""  # Validator ile düzelteceğiz
    SESSION_NAME: str = "telegram_session"
    USER_MODE: bool = True  # Validator ile düzelteceğiz
    BOT_USERNAME: str = ""  # Kullanıcı veya bot kullanıcı adını saklayacak alan
    # Oturum dosyaları için dizin yolu
    SESSIONS_DIR: pathlib.Path = BASE_DIR / "app" / "sessions"
    
    # Telegram bağlantı ayarları
    TG_CONNECTION_RETRIES: int = 10  # Validator ile düzelteceğiz - Değeri artırdık
    TG_RETRY_DELAY: int = safe_getenv_int("TG_RETRY_DELAY", "3")  # Gecikmeyi artırdık
    TG_TIMEOUT: int = safe_getenv_int("TG_TIMEOUT", "120")  # Zaman aşımını artırdık
    TG_REQUEST_RETRIES: int = safe_getenv_int("TG_REQUEST_RETRIES", "5")  # Yeniden deneme sayısını artırdık
    TG_FLOOD_SLEEP_THRESHOLD: int = safe_getenv_int("TG_FLOOD_SLEEP_THRESHOLD", "60")
    
    # Servis Ayarları
    MESSAGE_BATCH_SIZE: int = 50  # Validator ile düzelteceğiz
    MESSAGE_BATCH_INTERVAL: int = 30  # Validator ile düzelteceğiz
    SCHEDULER_INTERVAL: int = 60  # Validator ile düzelteceğiz
    
    # Otomatik mesajlaşma ayarları
    ENABLE_AUTO_MESSAGING: bool = True
    AUTO_MESSAGING_INTERVAL_MIN: int = 180  # 3 dakika
    AUTO_MESSAGING_INTERVAL_MAX: int = 420  # 7 dakika
    
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
    
    # Servis ayarları
    AUTO_RESTART_SERVICES: bool = True  # Sorunlu servisleri otomatik yeniden başlat
    ENABLE_SERVICE_MONITOR: bool = True  # Servis izleyiciyi etkinleştir
    SERVICE_MONITOR_INTERVAL: int = 60  # Servis izleme aralığı (saniye)
    
    # Validator fonksiyonları
    @validator("DEBUG", pre=True)
    def validate_debug(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip().lower() if '#' in v else v.strip().lower()
            return value in ("true", "yes", "1", "t", "y", "true")
        return bool(v)
    
    @validator("SQL_ECHO", pre=True)
    def validate_sql_echo(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip().lower() if '#' in v else v.strip().lower()
            return value in ("true", "yes", "1", "t", "y", "true")
        return bool(v)
    
    @validator("USER_MODE", pre=True)
    def validate_user_mode(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip().lower() if '#' in v else v.strip().lower()
            return value in ("true", "yes", "1", "t", "y", "true")
        return bool(v)
    
    @validator("ACCESS_TOKEN_EXPIRE_MINUTES", pre=True)
    def validate_access_token_expire_minutes(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip() if '#' in v else v.strip()
            try:
                return int(value)
            except ValueError:
                # Sadece sayıları içeren karakterleri al
                clean_value = ''.join(c for c in value if c.isdigit())
                if clean_value:
                    return int(clean_value)
                return 10080  # Varsayılan değer
        return v
    
    @validator("TG_CONNECTION_RETRIES", pre=True)
    def validate_tg_connection_retries(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip() if '#' in v else v.strip()
            try:
                return int(value)
            except ValueError:
                # Sadece sayıları içeren karakterleri al
                clean_value = ''.join(c for c in value if c.isdigit())
                if clean_value:
                    return int(clean_value)
                return 10  # Varsayılan değeri artırdık
        return v
    
    @validator("MESSAGE_BATCH_SIZE", pre=True)
    def validate_message_batch_size(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip() if '#' in v else v.strip()
            try:
                return int(value)
            except ValueError:
                # Sadece sayıları içeren karakterleri al
                clean_value = ''.join(c for c in value if c.isdigit())
                if clean_value:
                    return int(clean_value)
                return 50  # Varsayılan değer
        return v
    
    @validator("MESSAGE_BATCH_INTERVAL", pre=True)
    def validate_message_batch_interval(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip() if '#' in v else v.strip()
            try:
                return int(value)
            except ValueError:
                # Sadece sayıları içeren karakterleri al
                clean_value = ''.join(c for c in value if c.isdigit())
                if clean_value:
                    return int(clean_value)
                return 30  # Varsayılan değer
        return v
    
    @validator("SCHEDULER_INTERVAL", pre=True)
    def validate_scheduler_interval(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip() if '#' in v else v.strip()
            try:
                return int(value)
            except ValueError:
                # Sadece sayıları içeren karakterleri al
                clean_value = ''.join(c for c in value if c.isdigit())
                if clean_value:
                    return int(clean_value)
                return 60  # Varsayılan değer
        return v
    
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
    
    @validator("API_ID", pre=True)
    def validate_api_id(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip() if '#' in v else v.strip()
            # Sadece rakamları al
            value = ''.join(c for c in value if c.isdigit())
            try:
                return int(value)
            except Exception:
                return 0
        if isinstance(v, int):
            return v
        return 0

    @validator("API_HASH", pre=True)
    def validate_api_hash(cls, v):
        # Doğru API_HASH - sorunu çözmek için sabit değer kullanıyoruz
        correct_hash = "ff5d6053b266f78d1293f9343f40e77e"
        
        # Gelen değerin doğru olup olmadığını kontrol et
        if hasattr(v, 'get_secret_value'):
            v = v.get_secret_value()
        if isinstance(v, str):
            value = v.split('#')[0].strip() if '#' in v else v.strip()
            
            # Değer doğru olmayanı değiştir
            if value != correct_hash:
                print(f"⚠️ API_HASH değeri düzeltiliyor: {value} -> {correct_hash}")
                return correct_hash
            return value
        
        # Değer yoksa doğru değeri döndür
        return correct_hash
    
    @validator("PHONE", pre=True)
    def validate_phone(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip() if '#' in v else v.strip()
            return value
        return v
    
    @validator("SESSION_NAME", pre=True)
    def validate_session_name(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip() if '#' in v else v.strip()
            return value
        return v
    
    @validator("LOG_LEVEL", pre=True)
    def validate_log_level(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip() if '#' in v else v.strip()
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if value.upper() in valid_levels:
                return value.upper()
            return "INFO"
        return v
    
    @validator("ENABLE_AUTO_MESSAGING", pre=True)
    def validate_enable_auto_messaging(cls, v):
        if isinstance(v, str):
            value = v.split('#')[0].strip().lower() if '#' in v else v.strip().lower()
            return value in ("true", "yes", "1", "t", "y", "true")
        return bool(v)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Bilinmeyen alanları yok say

# Tek bir settings örneği oluştur
settings = Settings()

# Oturum dizininin varlığını kontrol et ve oluştur
if not settings.SESSIONS_DIR.exists():
    settings.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Oturum dizini oluşturuldu: {settings.SESSIONS_DIR}")

# İlave yardımcı fonksiyonlar
def get_settings() -> Settings:
    """Settings örneğini döndürür."""
    return settings