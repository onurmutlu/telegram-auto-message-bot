"""
# ============================================================================ #
# Dosya: main.py
# Yol: /Users/siyahkare/code/telegram-bot/main.py
# İşlev: Telegram botunun ana giriş noktası ve uygulama başlangıcı.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import platform  # platform modülünü import edelim
from datetime import datetime
import shutil
import subprocess
from dotenv import load_dotenv
# SQLite kütüphanesini kaldırdık
import psycopg2
from urllib.parse import urlparse
import time
import glob

from telethon import TelegramClient
from telethon.sessions import StringSession
from logging.handlers import RotatingFileHandler  # Eklendi
from telethon.errors import SessionPasswordNeededError, UnauthorizedError, FloodWaitError
from telethon.errors import (
    SessionPasswordNeededError, 
    UnauthorizedError, 
    FloodWaitError, 
    PhoneCodeInvalidError, 
    RPCError
)
from telethon.tl.functions.channels import JoinChannelRequest

from config import Config
from database.user_db import UserDatabase as Database
from bot.services.service_factory import ServiceFactory
from bot.services.service_manager import ServiceManager
from bot.utils.cli_interface import handle_keyboard_input, print_banner, show_help
from bot.services.user_service import UserService
from bot.services.dm_service import DirectMessageService
from bot.services.group_service import GroupService
from bot.services.invite_service import InviteService
from bot.utils.logger_setup import setup_logger
from database.pg_db import PgDatabase
from rich.console import Console
from bot.celery_app import celery_app  # Celery uygulamasını import et

# Gerekli dizinleri oluştur
def create_required_directories():
    """Uygulama için gerekli dizinleri oluşturur"""
    directories = [
        'data',
        'session',
        'logs',
        'runtime',
        'runtime/logs',
        'runtime/database',
        'runtime/sessions'
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"Dizin oluşturuldu/kontrol edildi: {directory}")
        except Exception as e:
            print(f"Dizin oluşturma hatası ({directory}): {str(e)}")

# Uygulama başlatılmadan önce dizinleri oluştur
create_required_directories()

# Log yapılandırmasını yap
def configure_logging(debug_mode=False):
    """
    Log yapılandırmasını yapar.
    """
    # Varsayılan olarak INFO seviyesini kullan
    log_level = logging.INFO
    
    # Sadece DEBUG flag açıksa DEBUG seviyesini etkinleştir
    if debug_mode:
        log_level = logging.DEBUG

    # Root logger
    root_logger = logging.getLogger()
    
    # Önce tüm eski handler'ları temizle
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    
    # Ana log seviyesini ayarla
    root_logger.setLevel(log_level)
    
    # Konsol handler - Rich formatıyla
    from rich.logging import RichHandler
    console_handler = RichHandler(
        level=log_level,
        rich_tracebacks=True,
        show_time=False,
        omit_repeated_times=True
    )
    
    # Ana log dosyası için dönen dosya handler
    log_file_path = "runtime/logs/bot.log"
    file_handler = RotatingFileHandler(
        log_file_path, 
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,             # 10 adet yedek dosya
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    
    # Hata logları için ayrı bir dosya
    error_log_path = "runtime/logs/errors.log"
    error_file_handler = RotatingFileHandler(
        error_log_path, 
        maxBytes=5 * 1024 * 1024,   # 5MB
        backupCount=5,              # 5 adet yedek dosya
        encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)  # Sadece ERROR ve üstü

    # Formatlayıcılar
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    simple_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Formatlayıcıları ayarla
    file_handler.setFormatter(detailed_formatter)
    error_file_handler.setFormatter(detailed_formatter)
    
    # Root logger'a handler'ları ekle
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_file_handler)
    
    # Daha az ayrıntılı loglama için bazı modüllerin seviyelerini artır
    noise_loggers = [
        'telethon', 'asyncio', 'urllib3', 'aiosqlite', 
        'matplotlib', 'PIL', 'httpx', 'httpcore'
    ]
    
    for logger_name in noise_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # Task süre uyarılarını filtreleyen özel sınıf
    class TaskDurationFilter(logging.Filter):
        def filter(self, record):
            # Eğer mesaj "Executing <Task" ile başlıyorsa ve "took" içeriyorsa konsola yazdırma
            if record.getMessage().startswith("Executing <Task") and "took" in record.getMessage():
                # Bu mesajı sadece dosyaya yaz, konsolda gösterme
                return False
            return True
    
    # Konsol handler'a filtre ekle (sadece dosyaya yazılsın)
    console_handler.addFilter(TaskDurationFilter())
    
    # Telethon ve asyncio uyarılarını daha sıkı filtrele
    class NetworkNoisyFilter(logging.Filter):
        def filter(self, record):
            message = record.getMessage()
            # Gereksiz ağ mesajlarını filtrele
            if (
                message.startswith("Executing <Task") or
                message.startswith("Connection") or
                "Disconnected from" in message or
                "Reconnecting" in message or
                "Got response" in message
            ):
                return False
            return True
    
    # Filtre ekle
    for logger_name in ['asyncio', 'telethon']:
        module_logger = logging.getLogger(logger_name)
        module_logger.addFilter(NetworkNoisyFilter())
    
    # Çalıştırma zamanında log dosyasının yerini belirt
    print(f"Log dosyaları: {log_file_path} ve {error_log_path}")
    
    return root_logger

# Debug modu ayarlarını çevre değişkeninden al
debug_mode = os.getenv("DEBUG", "false").lower() == "true"

# Loglama ve konsol nesnelerini ayarla
logger = configure_logging(debug_mode=debug_mode)

from rich.console import Console
from rich.panel import Panel
console = Console()  # Rich Console nesnesi

# Çıkış olayı
quit_event = asyncio.Event()

# CLI arayüzü için kontrolcü
def start_cli(console_instance):
    """CLI arayüzünü başlatır"""
    return handle_keyboard_input(console_instance, quit_event)

def parse_proxy_string(proxy_str):
    """Proxy string'ini Telethon'un beklediği dict formatına dönüştürür."""
    if not proxy_str:
        return None
    
    try:
        # Format: socks5://user:pass@host:port
        protocol, rest = proxy_str.split('://', 1)
        
        auth_info = None
        if '@' in rest:
            auth, server = rest.split('@', 1)
            if ':' in auth:
                username, password = auth.split(':', 1)
                auth_info = (username, password)
        else:
            server = rest
        
        # Port kısmını güvenli bir şekilde ayrıştır
        host = server
        port = 1080  # Varsayılan port
        
        if ':' in server:
            host_parts = server.split(':')
            host = host_parts[0]
            try:
                port = int(host_parts[1])
            except (ValueError, IndexError):
                logger.warning(f"Geçersiz port: {server.split(':')[1] if len(server.split(':')) > 1 else 'yok'}, varsayılan port (1080) kullanılıyor")
        
        return {
            'proxy_type': protocol,
            'addr': host,
            'port': port,
            'username': auth_info[0] if auth_info else None,
            'password': auth_info[1] if auth_info else None,
            'rdns': True
        }
    except Exception as e:
        logger.error(f"Proxy ayrıştırma hatası: {str(e)}")
        return None

# Global session dizini - modül seviyesinde tanımlandı
session_dir = 'session'

def add_signal_handlers(stop_event):
    """
    SIGINT ve SIGTERM sinyallerini yakalayıp düzgün bir şekilde çıkış yapmak 
    için gerekli işleyicileri tanımlar.
    
    Args:
        stop_event (asyncio.Event): Durdurma sinyali için Event nesnesi
    """
    try:
        def shutdown_handler():
            logger.info("Kapatma sinyali alındı. Servisleri durdurma...")
            stop_event.set()
            
            # Ana döngüye shutdown görevi ekle
            if 'service_manager' in globals():
                asyncio.create_task(_graceful_shutdown(service_manager, stop_event))
        
        # Çalışan platform kontrolü
        if platform.system().lower() != 'windows':
            # Windows dışı platformlar için sinyal işleyicileri ayarla (Unix, Linux, macOS)
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, shutdown_handler)
                
            logger.info("Sinyal işleyicileri ayarlandı (Unix/Linux/macOS)")
        else:
            # Windows için sinyal işleyicileri
            # Windows'ta asyncio.add_signal_handler çalışmadığı için signal.signal kullanıyoruz
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda s, f: shutdown_handler())
                
            logger.info("Sinyal işleyicileri ayarlandı (Windows)")
    
    except Exception as e:
        logger.warning(f"Sinyal işleyicileri kaydedilemedi: {str(e)}")
        logger.info("Bot manuel olarak durdurulacak (Ctrl+C/Ctrl+Break kullanabilirsiniz)")
        # Hata olsa bile devam et

async def _graceful_shutdown(service_manager, stop_event):
    """
    Tüm servisleri düzgün bir şekilde kapatmak için asenkron görev.
    
    Args:
        service_manager: Servis yöneticisi
        stop_event: Durdurma sinyali
    """
    try:
        logger.info("Uygulamayı düzgün bir şekilde kapatma işlemi başlatılıyor...")
        
        # Servisleri düzgün bir şekilde durdur
        await service_manager.stop_services()
        
        logger.info("Tüm servisler başarıyla kapatıldı.")
        
        # Opsiyonel: Verileri yedekle
        backup_database()
        
        # 2 saniye bekleyip uygulamadan çık
        await asyncio.sleep(2)
        
        # Uygulamadan çık
        logger.info("Uygulama düzgün bir şekilde kapatılıyor...")
        loop = asyncio.get_running_loop()
        loop.stop()
        
    except Exception as e:
        logger.error(f"Düzgün kapatma sırasında hata: {str(e)}")
        # Hata durumunda da çıkış yap
        loop = asyncio.get_running_loop()
        loop.stop()

def clean_session_locks():
    """Tüm oturum kilit dosyalarını temizler."""
    try:
        # Session dizininin varlığını kontrol et
        if not os.path.exists(session_dir):
            os.makedirs(session_dir, exist_ok=True)
            logger.info(f"Session dizini oluşturuldu: {session_dir}")
        
        # .lock uzantılı dosyaları bul ve sil
        lock_files = glob.glob(os.path.join(session_dir, "*.lock"))
        for lock_file in lock_files:
            try:
                os.remove(lock_file)
                logger.info(f"Kilit dosyası temizlendi: {lock_file}")
            except Exception as e:
                logger.warning(f"Kilit dosyası temizlenirken hata: {lock_file} - {str(e)}")
                
        # .session.lock dosyalarını da bul ve sil
        lock_files = glob.glob(os.path.join(session_dir, "*.session.lock"))
        for lock_file in lock_files:
            try:
                os.remove(lock_file)
                logger.info(f"Session kilit dosyası temizlendi: {lock_file}")
            except Exception as e:
                logger.warning(f"Session kilit dosyası temizlenirken hata: {lock_file} - {str(e)}")
    except Exception as e:
        logger.error(f"Session kilit dosyalarını temizlerken hata: {str(e)}")

async def clean_session_locks_async():
    """Session kilit dosyalarını güvenli bir şekilde temizler (async versiyon)."""
    # Normal fonksiyonu çağır
    clean_session_locks()
    # Async fonksiyon olduğunu belirtmek için dummy await
    await asyncio.sleep(0)

# TDLib kütüphane yolunu otomatik bul
def find_tdlib_path():
    """Sistemde kurulu TDLib kütüphanesini bulur"""
    import platform
    import os
    
    # Olası yollar
    if platform.system().lower() == 'darwin':  # macOS
        paths = [
            '/opt/homebrew/lib/libtdjson.dylib',  # Apple Silicon
            '/usr/local/lib/libtdjson.dylib',     # Intel Mac
            '/usr/lib/libtdjson.dylib'
        ]
    elif platform.system().lower() == 'linux':
        paths = [
            '/usr/local/lib/libtdjson.so',
            '/usr/lib/libtdjson.so'
        ]
    else:  # Windows
        paths = [
            'C:\\Program Files\\TDLib\\bin\\tdjson.dll',
            'C:\\TDLib\\bin\\tdjson.dll',
            'tdjson.dll'
        ]
    
    # Yolları kontrol et
    for path in paths:
        if os.path.exists(path):
            print(f"TDLib kütüphanesi bulundu: {path}")
            # .env dosyasına ekle
            with open(".env", "r") as f:
                env_content = f.read()
            
            # TDJSON_PATH satırını güncelle veya ekle
            if "TDJSON_PATH=" in env_content:
                # Satırı değiştir
                lines = env_content.split("\n")
                for i, line in enumerate(lines):
                    if line.startswith("TDJSON_PATH="):
                        lines[i] = f"TDJSON_PATH={path}"
                env_content = "\n".join(lines)
            else:
                # Satır ekle
                env_content += f"\nTDJSON_PATH={path}"
            
            # Dosyayı yaz
            with open(".env", "w") as f:
                f.write(env_content)
                
            return path
    
    print("⚠️ TDLib kütüphanesi bulunamadı!")
    return None

# TDLib kütüphanesini ara ve yapılandır
tdlib_path = find_tdlib_path()
if tdlib_path:
    os.environ['TDJSON_PATH'] = tdlib_path

def setup_database(db):
    """
    Veritabanı bağlantısını ve gerekli tabloları hazırlar.
    
    Args:
        db: Veritabanı bağlantı nesnesi
    
    Returns:
        bool: Başarılı ise True, değilse False
    """
    try:
        # Veritabanı URL'si kontrol et
        db_url = os.getenv("DB_CONNECTION")
        
        if not db_url or not db_url.startswith("postgresql://"):
            logger.warning("PostgreSQL bağlantı bilgileri eksik veya geçersiz. Varsayılan ayarlar kullanılacak.")
            # Varsayılan PostgreSQL bağlantı URL'sini kullan
            os.environ["DB_CONNECTION"] = "postgresql://postgres:postgres@localhost:5432/telegram_bot"
            db_url = os.environ["DB_CONNECTION"]
        
        # PostgreSQL bağlantı parametrelerini ayrıştır
        try:
            url = urlparse(db_url)
            db_name = url.path[1:]  # / işaretini kaldır
            db_user = url.username
            db_password = url.password
            db_host = url.hostname
            db_port = url.port or 5432
            
            logger.info(f"PostgreSQL bağlantı detayları: {db_host}:{db_port}/{db_name}")
        except Exception as e:
            logger.error(f"PostgreSQL bağlantı URL'si ayrıştırma hatası: {str(e)}")
            logger.warning("Varsayılan bağlantı detayları kullanılacak.")
            
        logger.info("PostgreSQL veritabanı bağlantısı kuruluyor...")
        
        # Bağlantıyı başlat
        asyncio.create_task(db.connect())
        
        # Tabloları oluştur
        asyncio.create_task(db.create_tables())
        asyncio.create_task(db.create_user_profile_tables())
        
        # Migrasyonları çalıştır - eksik tablolar için (messages, mining_data, mining_logs)
        logger.info("Veritabanı migrasyonları çalıştırılıyor...")
        asyncio.create_task(db.run_migrations())
        
        logger.info("PostgreSQL veritabanı başarıyla yapılandırıldı.")
        return True
        
    except Exception as e:
        logger.error(f"PostgreSQL veritabanı kurulum hatası: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# Session string'ini veritabanından alır veya yeni oluşturur
async def get_or_create_session_string(db):
    """
    Veritabanından Telethon session string'i alır veya yoksa yeni oluşturur.
    
    Args:
        db (Database): Veritabanı bağlantısı
    
    Returns:
        str: Telethon session string'i
    """
    try:
        # API kimlik bilgilerini kontrol et
        api_id = os.getenv('API_ID')
        api_hash = os.getenv('API_HASH')
        phone = os.getenv('PHONE')
        
        if not api_id or not api_hash or not phone:
            logger.error("API_ID, API_HASH veya PHONE çevre değişkenleri tanımlanmamış!")
            raise ValueError("Gerekli çevre değişkenleri eksik")
        
        api_id = int(api_id)
        
        # Veritabanından session string'i al
        cursor = db.cursor.execute("SELECT value FROM settings WHERE key = 'session_string'")
        result = cursor.fetchone()
        
        if result and result[0]:
            logger.info("Session string veritabanından alındı.")
            return result[0]
        
        logger.info("Session string bulunamadı, yeni oluşturuluyor...")
        
        # Geçici bir istemci oluştur
        client = TelegramClient(
            StringSession(), 
            api_id, 
            api_hash,
            device_model="Telegram Bot",
            system_version="Python Telethon",
            app_version="1.0"
        )
        
        await client.connect()
        
        # Kullanıcı yetkilendirmesi
        if not await client.is_user_authorized():
            await client.send_code_request(phone)
            logger.info(f"Doğrulama kodu gönderildi: {phone}")
            
            try:
                verification_code = input("Doğrulama kodunu girin: ")
                await client.sign_in(phone, verification_code)
            except SessionPasswordNeededError:
                # İki faktörlü doğrulama gerekli
                logger.info("İki faktörlü kimlik doğrulama şifresi gerekli")
                password = input("İki faktörlü doğrulama şifrenizi girin: ")
                await client.sign_in(password=password)
            
            # Kullanıcı bilgileri
            me = await client.get_me()
            if not me:
                raise ValueError("Oturum açma işlemi başarısız oldu")
            logger.info(f"Oturum açıldı: {me.first_name} (@{me.username})")
        
        # Session string'i al ve sakla
        session_string = client.session.save()
        
        # Veritabanına kaydet
        db.cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("session_string", session_string)
        )
        db.conn.commit()
        
        logger.info("Yeni session string oluşturuldu ve veritabanına kaydedildi.")
        await client.disconnect()
        
        return session_string
    
    except Exception as e:
        logger.error(f"Session string alınırken/oluşturulurken hata: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise

async def setup_telegram_client(db):
    """
    Telegram istemcisini hazırlar ve bağlantıyı sağlar
    
    Args:
        db: Veritabanı bağlantısı
        
    Returns:
        Telegram istemcisi
    """
    try:
        # Telegram API anahtarları
        api_id = int(os.getenv('API_ID'))
        api_hash = os.getenv('API_HASH')
        bot_token = os.getenv('BOT_TOKEN')
        
        # API bilgilerini kontrol et
        if not api_id or not api_hash:
            logger.error("Telegram API bilgileri eksik. API_ID ve API_HASH çevre değişkenleri gereklidir.")
            raise ValueError("Telegram API bilgileri eksik")
        
        # Session dosyası adı
        session_name = os.getenv('SESSION_NAME', 'telegram_bot')
        session_file = os.path.join('session', session_name)
        
        # Eski session dosyalarını kontrol et - FloodWaitError durumunda
        flood_backup_files = glob.glob(os.path.join('session', f"{session_name}_*_flood.session"))
        if flood_backup_files:
            # En yeni flood backup dosyasını bul
            newest_backup = max(flood_backup_files, key=os.path.getctime)
            logger.info(f"FloodWaitError sonrası yedek session dosyası bulundu: {newest_backup}")
            
            # Mevcut session dosyası var mı?
            if os.path.exists(f"{session_file}.session"):
                # Eski session dosyasını yedekle
                backup_time = time.strftime("%Y%m%d_%H%M%S")
                os.rename(f"{session_file}.session", f"{session_file}_{backup_time}.session.bak")
                logger.info(f"Mevcut session dosyası yedeklendi: {session_file}_{backup_time}.session.bak")
            
            # Flood backup dosyasını kullan
            os.rename(newest_backup, f"{session_file}.session")
            logger.info(f"FloodWaitError sonrası yedek session dosyası aktif edildi: {session_file}.session")
        
        # Disk tabanlı oturum kullan
        client = TelegramClient(
            session_file,
            api_id, 
            api_hash,
            device_model="Telegram Bot",
            system_version="Python Telethon",
            app_version="1.0",
            flood_sleep_threshold=60,
            retry_delay=5,
            auto_reconnect=True
        )
        
        logger.info("Telegram istemcisi oluşturuldu, bağlanılıyor...")
        await client.connect()
        
        # Kullanıcı yetkilendirmesini kontrol et
        if not await client.is_user_authorized():
            logger.warning("İstemci yetkili değil, oturum açmayı deniyoruz...")
            
            # Oturum açma denemelerine başla
            auth_attempts = 0
            max_auth_attempts = 3
            flood_wait_triggered = False
            
            while auth_attempts < max_auth_attempts and not flood_wait_triggered:
                try:
                    # Telefon numarasını .env'den almayı dene
                    phone = os.getenv('PHONE')
                    
                    if not phone:
                        # Eğer .env'de telefon numarası yoksa kullanıcıdan iste
                        logger.warning("PHONE çevre değişkeni bulunamadı, manuel giriş gerekiyor.")
                        phone = input("Telefon numaranızı girin (+905xxxxxxxxx): ")
                    else:
                        logger.info(f"Telefon numarası .env dosyasından alındı: {phone}")
                    
                    try:
                        # Doğrulama kodu gönderilmesini iste
                        await client.send_code_request(phone)
                        logger.info(f"Doğrulama kodu gönderildi: {phone}")
                        
                        # Kullanıcıdan doğrulama kodunu iste
                        code = input("Doğrulama kodunu girin: ")
                        
                        try:
                            # Giriş yap
                            await client.sign_in(phone, code)
                            logger.info("Giriş başarılı! Oturum bilgileri kaydedildi.")
                            break  # Başarılı giriş, döngüden çık
                            
                        except SessionPasswordNeededError:
                            # İki faktörlü doğrulama gerekli
                            password = input("İki faktörlü doğrulama şifrenizi girin: ")
                            await client.sign_in(password=password)
                            logger.info("İki faktörlü doğrulama başarılı! Oturum bilgileri kaydedildi.")
                            break  # Başarılı giriş, döngüden çık
                            
                    except FloodWaitError as e:
                        # Flood wait hatası - bekle
                        wait_time = e.seconds
                        logger.error(f"Rate limit aşıldı. {wait_time} saniye beklemeniz gerekiyor.")
                        
                        # İnsan tarafından okunabilir zaman formatı
                        hours = wait_time // 3600
                        minutes = (wait_time % 3600) // 60
                        seconds = wait_time % 60
                        human_time = f"{hours} saat, {minutes} dakika, {seconds} saniye"
                        
                        logger.warning(f"Bu, yaklaşık {human_time} beklemek demektir.")
                        logger.warning("Daha sonra tekrar deneyiniz veya alternatif bir hesap kullanınız.")
                        
                        # Session dosyasını yedekle (flood durumu için)
                        if os.path.exists(f"{session_file}.session"):
                            backup_time = time.strftime("%Y%m%d_%H%M%S")
                            flood_backup = f"{session_file}_{backup_time}_flood.session"
                            os.rename(f"{session_file}.session", flood_backup)
                            logger.info(f"Session dosyası FloodWaitError nedeniyle yedeklendi: {flood_backup}")
                        
                        flood_wait_triggered = True
                        raise ValueError(f"Telegram API kısıtlaması: {human_time} boyunca beklemeniz gerekiyor.")
                        
                except Exception as auth_error:
                    # Diğer hatalar
                    logger.error(f"Oturum açma hatası: {str(auth_error)}")
                    auth_attempts += 1
                    
                    if auth_attempts >= max_auth_attempts:
                        logger.error(f"Maksimum oturum açma denemesi ({max_auth_attempts}) aşıldı.")
                        raise ValueError("Oturum açma başarısız oldu. Lütfen daha sonra tekrar deneyin.")
                    
                    # Bir sonraki denemeden önce bekle
                    wait_time = 5 * auth_attempts  # Her denemede daha uzun bekle
                    logger.info(f"Yeniden deneme öncesi {wait_time} saniye bekleniyor...")
                    await asyncio.sleep(wait_time)
        
        # Bu noktada kullanıcı oturumu açılmıştır, kullanıcı bilgilerini al
        me = await client.get_me()
        if me:
            logger.info(f"Bağlı kullanıcı: {me.first_name} (@{me.username})")
        else:
            logger.warning("Kullanıcı bilgisi alınamadı, ancak oturum açma başarılı!")
        
        return client
    
    except Exception as e:
        logger.error(f"Telegram istemcisi kurulurken hata: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise

async def main():
    """Ana uygulama başlangıç noktası"""
    client = None  # İleri kullanım için None olarak tanımla
    db = None
    
    try:
        # Banner'ı göster
        print_banner()
        
        # Redis bağlantısını kontrol et
        try:
            import redis
            redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))
            redis_client.ping()
            print("✅ Redis bağlantısı başarılı")
        except Exception as e:
            print(f"❌ Redis bağlantı hatası: {str(e)}")
            print("⚠️ Celery görevleri çalışmayacak!")
        
        # Celery worker'ı başlat
        try:
            celery_worker = subprocess.Popen(
                ['celery', '-A', 'bot.celery_app', 'worker', '--loglevel=info'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("✅ Celery worker başlatıldı")
        except Exception as e:
            print(f"❌ Celery worker başlatma hatası: {str(e)}")
        
        # Celery beat'i başlat
        try:
            celery_beat = subprocess.Popen(
                ['celery', '-A', 'bot.celery_app', 'beat', '--loglevel=info'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print("✅ Celery beat başlatıldı")
        except Exception as e:
            print(f"❌ Celery beat başlatma hatası: {str(e)}")
        
        load_dotenv()
        
        # .env dosyasındaki API anahtarlarını kontrol et
        api_id = os.getenv('API_ID')
        api_hash = os.getenv('API_HASH')
        
        if not api_id or not api_hash:
            logger.critical("API_ID ve API_HASH çevre değişkenleri ayarlanmamış. .env dosyasını kontrol edin.")
            print("❌ Kritik Hata: API_ID ve API_HASH ayarlanmamış. Program durduruluyor.")
            return
        
        # Gerekli dizinleri kontrol et ve oluştur
        directories = [
            'data', 
            'logs', 
            'session', 
            'runtime/logs',
            'runtime/database',
            'runtime/sessions'
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Dizin kontrolü yapıldı: {directory}")
        
        # Veritabanı bağlantısı kur
        # PostgreSQL bağlantı bilgilerini .env'den al
        db_connection = os.getenv("DB_CONNECTION")
        
        # Bağlantı URL'si kontrolü
        if not db_connection or not db_connection.startswith("postgresql://"):
            logger.error("PostgreSQL bağlantı bilgileri bulunamadı veya geçersiz. DB_CONNECTION çevre değişkeni ayarlanmalıdır (postgresql://...)")
            # Varsayılan bağlantıyı kullan
            db_connection = "postgresql://postgres:postgres@localhost:5432/telegram_bot"
            logger.info(f"Varsayılan PostgreSQL bağlantısı kullanılıyor: {db_connection.split('@')[1].split('/')[0]}")
        else:
            logger.info(f"PostgreSQL bağlantısı kullanılıyor: {db_connection.split('@')[1].split('/')[0]}")
            
        # PostgreSQL veritabanını başlat
        db = Database(db_url=db_connection)
        
        try:
            # Veritabanına bağlan
            connection_success = await db.connect()
            
            if not connection_success:
                logger.error("PostgreSQL veritabanı bağlantısı başarısız oldu. Uygulama durduruluyor.")
                return
            
            # Veritabanı tablolarını oluştur
            await db.create_tables()
            
            # Oturum kilitlerini temizle
            await clean_session_locks_async()
            
            # Yapılandırma nesnesini oluştur
            config = Config()
            
            # Telegram istemcisini oluştur
            try:
                logger.info("Telegram istemcisi kuruluyor...")
                client = await setup_telegram_client(db)
                
                # Kullanıcı bilgilerini al
                user_info_success = False
                
                try:
                    me = await client.get_me()
                    if me:
                        logger.info(f"Bağlı kullanıcı: {me.first_name} (@{me.username})")
                        user_info_success = True
                    else:
                        logger.warning("Kullanıcı bilgisi alınamadı! Yetkilendirme sorunları olabilir.")
                except Exception as me_error:
                    logger.error(f"Kullanıcı bilgisi alınamadı: {str(me_error)}")
                
                # Eğer kullanıcı bilgisi alınamadıysa ve phone ayarı varsa yeniden login dene
                if not user_info_success:
                    # Yeniden oturum açmayı dene
                    phone = os.getenv('PHONE')
                    if phone:
                        try:
                            logger.info(f"Yeniden oturum açmayı deniyorum: {phone}")
                            
                            try:
                                await client.send_code_request(phone)
                                code = input("Doğrulama kodunu girin: ")
                                
                                try:
                                    await client.sign_in(phone, code)
                                except SessionPasswordNeededError:
                                    password = input("İki faktörlü doğrulama şifrenizi girin: ")
                                    await client.sign_in(password=password)
                                    
                                me = await client.get_me()
                                if me:
                                    logger.info(f"Yeniden oturum açma başarılı: {me.first_name} (@{me.username})")
                                    user_info_success = True
                                else:
                                    logger.error("Yeniden oturum açma başarısız oldu, kullanıcı bilgisi alınamadı")
                                    raise ValueError("Geçerli bir kullanıcı oturumu gerekli")
                            except FloodWaitError as e:
                                wait_time = e.seconds
                                hours = wait_time // 3600
                                minutes = (wait_time % 3600) // 60
                                seconds = wait_time % 60
                                logger.error(f"Flood Wait hatası: {hours} saat, {minutes} dakika, {seconds} saniye beklemek gerekiyor.")
                                
                                # Oturum dosyasını işaretle (bir sonraki seferde hatırlansın)
                                session_name = os.getenv('SESSION_NAME', 'telegram_bot')
                                session_file = os.path.join('session', session_name)
                                
                                if os.path.exists(f"{session_file}.session"):
                                    backup_time = time.strftime("%Y%m%d_%H%M%S")
                                    flood_backup = f"{session_file}_{backup_time}_flood.session"
                                    try:
                                        os.rename(f"{session_file}.session", flood_backup)
                                        logger.info(f"Session dosyası FloodWaitError nedeniyle yedeklendi: {flood_backup}")
                                    except Exception as rename_error:
                                        logger.error(f"Session dosyası yedeklenirken hata: {str(rename_error)}")
                                
                                raise ValueError(f"Flood Wait hatası: {hours} saat, {minutes} dakika, {seconds} saniye beklemek gerekiyor.")
                        except Exception as auth_error:
                            logger.error(f"Yeniden oturum açma hatası: {str(auth_error)}")
                            raise ValueError("Bot çalışması için geçerli bir kullanıcı oturumu gerekli")
                
                # Kesme sinyali olayını oluştur
                stop_event = asyncio.Event()
                
                # Sinyal işleyicileri ekle
                try:
                    add_signal_handlers(stop_event)
                except Exception as signal_error:
                    logger.warning(f"Sinyal işleyicileri kaydedilemedi: {str(signal_error)}")
                
                # ServiceFactory ve ServiceManager kullanarak servisleri yönet
                service_factory = ServiceFactory(client, config, db, stop_event)
                
                # Service manager'ı global değişken olarak tanımla
                global service_manager
                service_manager = ServiceManager(service_factory, client, config, db, stop_event)
                
                # Aktif servisleri belirle - tüm servisleri dahil ediyoruz
                active_services = [
                    "user",          # UserService
                    "group",         # GroupService
                    "reply",         # ReplyService
                    "gpt",           # GptService
                    "dm",            # DirectMessageService
                    "invite",        # InviteService
                    "promo",         # PromoService
                    "announcement",  # AnnouncementService
                    "datamining",    # DataMiningService
                    "message",       # MessageService
                ]
                
                # Servisleri oluştur ve kaydet
                await service_manager.create_and_register_services(active_services)
                
                # Servisleri başlat
                await service_manager.start_services()
                
                # Servisler hazır
                logger.info("Tüm servisler başlatıldı ve ServiceManager tarafından yönetiliyor")
                
                # Hoş geldiniz banner'ını ve yardımı göster
                print_banner()
                console.print("[cyan]Klavye komutları aktif. Yardım için 'h' tuşuna basın.[/cyan]")
                
                # CLI arayüzünü başlat
                cli_task = asyncio.create_task(handle_keyboard_input(console, service_manager, stop_event))
                
                # Beklenecek görevleri hazırla
                tasks = [cli_task]
                tasks.extend(service_manager.tasks)
                
                # Tüm görevleri bekle
                await asyncio.gather(*tasks, return_exceptions=True)
                
            except Exception as e:
                logger.error(f"Telegram istemcisi oluşturulurken hata: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
        except Exception as e:
            logger.critical(f"Kritik hata: {e}")
            import traceback
            logger.critical(traceback.format_exc())
    except Exception as e:
        print(f"❌ Ana uygulama hatası: {str(e)}")
        logging.error(f"Ana uygulama hatası: {str(e)}")
        sys.exit(1)
    finally:
        # Veritabanı bağlantısını kapat
        if db is not None:
            try:
                await db.disconnect()
                logger.info("Veritabanı bağlantısı kapatıldı.")
            except Exception as e:
                logger.error(f"Veritabanı bağlantısı kapatılırken hata: {str(e)}")
        
        # İstemciyi kapat
        if client is not None:
            try:
                try:
                    # client.connected özelliğini kontrol et
                    if hasattr(client, 'connected') and client.connected:
                        await client.disconnect()
                        logger.info("Telegram istemcisi kapatıldı.")
                    else:
                        logger.info("Telegram istemcisi zaten kapalı.")
                except AttributeError:
                    # client.connected özelliği yoksa genel durdurma denemesi yap
                    await client.disconnect()
                    logger.info("Telegram istemcisi kapatıldı (genel durdurma).")
            except Exception as e:
                logger.error(f"Telegram istemcisi kapatılırken hata: {str(e)}")
        
        # Celery worker ve beat'i temizle
        try:
            if 'celery_worker' in locals():
                celery_worker.terminate()
            if 'celery_beat' in locals():
                celery_beat.terminate()
        except Exception as e:
            print(f"❌ Celery temizleme hatası: {str(e)}")

# Veritabanı yedekleme fonksiyonu
def backup_database():
    """PostgreSQL veritabanının yedeklemesini alır."""
    try:
        # .env'den veritabanı bilgilerini al
        db_url = os.getenv("DB_CONNECTION")
        
        if not db_url or not db_url.startswith("postgresql://"):
            logger.warning("PostgreSQL bağlantı bilgileri eksik veya geçersiz, yedekleme yapılamıyor.")
            return False
            
        # Bağlantı bilgilerini ayrıştır
        url_parts = db_url.replace("postgresql://", "").split("@")
        if len(url_parts) != 2:
            logger.warning("Geçersiz PostgreSQL bağlantı URL'si, yedekleme yapılamıyor.")
            return False
            
        auth = url_parts[0].split(":")
        server = url_parts[1].split("/")
        
        if len(auth) != 2 or len(server) != 2:
            logger.warning("PostgreSQL bağlantı bilgileri eksik, yedekleme yapılamıyor.")
            return False
            
        username = auth[0]
        password = auth[1]
        host_port = server[0].split(":")
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else "5432"
        database = server[1]
        
        # Yedekleme dizinini oluştur
        backup_dir = "runtime/database/backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Yedek dosya adını oluştur
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/postgres_{database}_{timestamp}.sql"
        
        # pg_dump komutu ile yedekleme yap
        cmd = [
            "pg_dump",
            "-h", host,
            "-p", port,
            "-U", username,
            "-d", database,
            "-f", backup_file
        ]
        
        # Ortam değişkenine şifreyi ekle
        env = os.environ.copy()
        env["PGPASSWORD"] = password
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"PostgreSQL veritabanı başarıyla yedeklendi: {backup_file}")
            
            # Eski yedekleri temizle (son 5 yedeği tut)
            all_backups = sorted([f for f in os.listdir(backup_dir) if f.startswith(f"postgres_{database}_")])
            if len(all_backups) > 5:
                for old_backup in all_backups[:-5]:
                    os.remove(os.path.join(backup_dir, old_backup))
                    logger.info(f"Eski yedek silindi: {old_backup}")
            
            return True
        else:
            logger.error(f"PostgreSQL yedekleme hatası: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Veritabanı yedekleme hatası: {str(e)}")
        return False

# Bot kapatma işlevi
def shutdown_bot():
    try:
        logger.info("Bot kapatılıyor...")
        
        # ServiceManager'ı durdur
        if 'service_manager' in globals() and service_manager and hasattr(service_manager, 'stop'):
            try:
                asyncio.run(service_manager.stop())
                logger.info("ServiceManager başarıyla durduruldu")
            except Exception as e:
                logger.error(f"Servis durdurma hatası: {str(e)}")
                
        # Veritabanı bağlantısını kapat
        if 'database' in globals() and database and database.connected:
            try:
                asyncio.run(database.disconnect())
                logger.info("PostgreSQL veritabanı bağlantısı kapatıldı.")
            except Exception as e:
                logger.error(f"Veritabanı kapatılırken hata: {str(e)}")
        
        logger.info("Bot başarıyla kapatıldı.")
        
        # Telegram istemcisini kapat
        if 'client' in globals() and client:
            try:
                asyncio.run(client.disconnect())
                logger.info("Telegram istemcisi kapatılıyor...")
            except:
                pass
    except Exception as e:
        logger.error(f"Kapatma sırasında hata: {str(e)}")
        
    logger.info("Bot kapatıldı.")

if __name__ == "__main__":
    try:
        # Windows için asyncio ayarı
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # AsyncIO event loop al
        loop = asyncio.get_event_loop()
        
        # Debug modunda asyncio debug etkinleştir
        if os.getenv("DEBUG", "false").lower() == "true":
            loop.set_debug(True)
            
        # Sinyalleri işleyecek fonksiyonlar
        def signal_handler(signal_num, frame):
            logger.info(f"Sinyal alındı: {signal_num}. Bot kapatılıyor...")
            # Event'i set et
            if stop_event and not stop_event.is_set():
                stop_event.set()
            # Ana fonksiyondan çıkmak için
            if main_task and not main_task.done():
                main_task.cancel()
            # Ek temizleme
            shutdown_bot()

        # Sinyalleri bağla
        try:
            if platform.system() != "Windows":
                signal.signal(signal.SIGINT, signal_handler)
                signal.signal(signal.SIGTERM, signal_handler)
                logger.debug("Sinyal işleyicileri kaydedildi")
        except Exception as e:
            logger.warning(f"Sinyal işleyicileri kaydedilemedi: {str(e)}")

        # Ana fonksiyonu çalıştır
        loop.run_until_complete(main())
        
    except Exception as e:
        import traceback
        print(f"Kritik hata: {e}")
        traceback.print_exc()
