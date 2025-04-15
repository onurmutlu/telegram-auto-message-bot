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
from datetime import datetime
import shutil
import subprocess
from dotenv import load_dotenv
import sqlite3

from telethon import TelegramClient
from telethon.sessions import StringSession
from logging.handlers import RotatingFileHandler  # Eklendi
from telethon.errors import SessionPasswordNeededError, UnauthorizedError
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

    # Konsol handler - Rich formatıyla
    from rich.logging import RichHandler
    console_handler = RichHandler(
        level=log_level,
        rich_tracebacks=True,
        show_time=False,
        omit_repeated_times=True
    )
    
    # Dosya handler (RotatingFileHandler kullanımı)
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        "runtime/logs/bot.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(log_level)

    # Formatlayıcı
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)

    # Root logger'a handler'ları ekle
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Eski handler'ları temizle
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Daha az ayrıntılı loglama için bazı modüllerin seviyelerini artır
    logging.getLogger('telethon').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('aiosqlite').setLevel(logging.WARNING)
    
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
    
    # Telethon uyarılarını daha sıkı filtrele
    class TaskDurationFilter(logging.Filter):
        def filter(self, record):
            return not (record.msg.startswith("Executing <Task") and "took" in record.msg)
    
    # Filtre ekle
    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.addFilter(TaskDurationFilter())
    
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
    def shutdown_handler():
        logger.info("Kapatma sinyali alındı. Servisleri durdurma...")
        stop_event.set()
        
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_handler)
    
    logger.info("Sinyal işleyicileri ayarlandı")

def clean_session_locks():
    """Tüm oturum kilit dosyalarını temizler."""
    import glob
    import os

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
    """Veritabanı başlangıç kurulumu."""
    try:
        # Temel tabloları oluştur
        db.cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_message TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            member_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            last_error TEXT,
            is_active INTEGER DEFAULT 1,
            retry_after TEXT,
            permanent_error INTEGER DEFAULT 0,
            is_target INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Tablonun şu anda varlığını kontrol et
        db.cursor.execute("PRAGMA table_info(groups)")
        columns = db.cursor.fetchall()
        
        # Bazı sütunlar eksik mi kontrol et ve ekle
        column_names = [col[1] for col in columns]
        
            # retry_after sütunu kontrol
        if 'retry_after' not in column_names:
            db.cursor.execute("ALTER TABLE groups ADD COLUMN retry_after TEXT")
            logger.info("Grup tablosu retry_after sütunu eklendi")
            
            # last_error sütunu kontrol
        if 'last_error' not in column_names:
            db.cursor.execute("ALTER TABLE groups ADD COLUMN last_error TEXT")
            logger.info("Grup tablosu last_error sütunu eklendi")
        
        # permanent_error sütunu kontrol
        if 'permanent_error' not in column_names:
            db.cursor.execute("ALTER TABLE groups ADD COLUMN permanent_error INTEGER DEFAULT 0")
            logger.info("Grup tablosu permanent_error sütunu eklendi")
        
        # Değişiklikleri kaydet
        db.conn.commit()
        
        logger.info("Veritabanı tabloları başarıyla oluşturuldu")
        return True
    except Exception as e:
        logger.error(f"Veritabanı kurulum hatası: {str(e)}")
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
    Telegram istemcisini yapılandırır ve başlatır.
    
    Args:
        db (Database): Kullanılacak veritabanı nesnesi
    
    Returns:
        TelegramClient: Yapılandırılmış ve bağlanmış Telegram istemcisi
    """
    try:
        # API kimlik bilgilerini kontrol et
        api_id = os.getenv('API_ID')
        api_hash = os.getenv('API_HASH')
        
        if not api_id or not api_hash:
            logger.error("API_ID veya API_HASH çevre değişkenleri tanımlanmamış!")
            raise ValueError("API kimlik bilgileri eksik")
        
        api_id = int(api_id)
        
        # Session dizinini kontrol et ve oluştur
        os.makedirs(session_dir, exist_ok=True)
        
        # Session dosyasının varlığını kontrol et - varsa disk tabanlı, yoksa StringSession kullan
        session_file = os.path.join(session_dir, "anon")
        use_string_session = not os.path.exists(session_file)
        
        if use_string_session:
            try:
                # Session string'i almayı dene
                session_string = await get_or_create_session_string(db)
                
                # Telethon istemcisini oluştur - StringSession kullanarak
                client = TelegramClient(
                    StringSession(session_string),
                    api_id, 
                    api_hash,
                    device_model="Telegram Bot",
                    system_version="Python Telethon",
                    app_version="1.0",
                    flood_sleep_threshold=60,
                    retry_delay=5,
                    auto_reconnect=True          
                )
                
                logger.info("StringSession tabanlı istemci oluşturuldu, bağlanılıyor...")
                await client.connect()
                
                # Kullanıcı yetkilendirmesini kontrol et
                if not await client.is_user_authorized():
                    logger.error("StringSession ile yetkilendirme başarısız, alternatif yöntemler deneniyor...")
                    raise Exception("StringSession yetkilendirme hatası")
                
                me = await client.get_me()
                if me:
                    logger.info(f"StringSession istemcisi bağlandı, kullanıcı: {me.first_name} (@{me.username})")
                    return client
                else:
                    logger.warning("Kullanıcı bilgisi alınamadı, alternatif yöntem deneniyor...")
                    raise Exception("Kullanıcı bilgisi alınamadı")
                
            except Exception as e:
                logger.error(f"StringSession ile bağlantı hatası: {str(e)}")
                logger.info("Disk tabanlı oturum deneniyor...")
                use_string_session = False
        
        # Disk tabanlı oturum kullan (StringSession başarısız olduysa ya da dosya zaten varsa)
        if not use_string_session:
            # Disk tabanlı oturum dene
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
            
            logger.info("Disk tabanlı istemci oluşturuldu, bağlanılıyor...")
            await client.connect()
            
            # Kullanıcı yetkilendirmesini kontrol et
            if not await client.is_user_authorized():
                logger.error("İstemci yetkili değil, manuel oturum açmayı deneyeceğiz.")
                
                # Manuel oturum açma işlemi
                phone = os.getenv('PHONE')
                if phone:
                    try:
                        await client.send_code_request(phone)
                        logger.info(f"Doğrulama kodu gönderildi: {phone}")
                        code = input("Doğrulama kodunu girin: ")
                        
                        try:
                            await client.sign_in(phone, code)
                        except SessionPasswordNeededError:
                            password = input("İki faktörlü doğrulama şifrenizi girin: ")
                            await client.sign_in(password=password)
                            
                        # Yetkilendirmeyi kontrol et
                        if await client.is_user_authorized():
                            me = await client.get_me()
                            if me:
                                logger.info(f"Manuel oturum açma başarılı: {me.first_name} (@{me.username})")
                                
                                # Session string'i kaydet
                                session_string = client.session.save()
                                db.cursor.execute(
                                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                                    ("session_string", session_string)
                                )
                                db.conn.commit()
                                logger.info("Session string başarıyla kaydedildi")
                                return client
                            else:
                                logger.error("Kullanıcı bilgisi alınamadı")
                                raise ValueError("Kullanıcı bilgisi alınamadı")
                    except Exception as auth_error:
                        logger.error(f"Manuel oturum açma hatası: {str(auth_error)}")
                        raise ValueError("Oturum açma başarısız")
                else:
                    raise ValueError("PHONE değişkeni tanımlanmamış, manuel oturum açılamıyor")
            else:
                me = await client.get_me()
                if me:
                    logger.info(f"Disk tabanlı istemci bağlandı, kullanıcı: {me.first_name} (@{me.username})")
                    
                    # Başarıyla bağlandıysa, string session'ı kaydet
                    try:
                        session_string = client.session.save()
                        db.cursor.execute(
                            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                            ("session_string", session_string)
                        )
                        db.conn.commit()
                        logger.info("Session string başarıyla kaydedildi")
                    except Exception as e2:
                        logger.error(f"Session string kaydedilirken hata: {str(e2)}")
                    
                    return client
                else:
                    logger.warning("Kullanıcı bilgisi alınamadı, ancak istemci yetkili görünüyor")
                    return client
    
    except Exception as e:
        logger.error(f"Telegram istemcisi kurulurken hata: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise

async def main():
    """Ana uygulama fonksiyonu."""
    try:
        # Çevre değişkenlerini yükle
        load_dotenv()
        
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
        
        # SQLite senkronizasyon modunu ve timeout'u ayarla
        sqlite3.connect(':memory:').execute('PRAGMA synchronous = NORMAL')
        sqlite3.connect(':memory:').execute('PRAGMA busy_timeout = 30000')
        
        # Veritabanı bağlantısı kur
        db_path = os.getenv("DB_PATH", "data/users.db")
        
        # Veritabanı dizininin varlığını kontrol et
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Veritabanı dizini oluşturuldu: {db_dir}")
            
        logger.info(f"Veritabanı bağlantısı kuruluyor: {db_path}")
        
        try:
            db = Database(db_path=db_path)
            await db.connect()
            
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
                me = await client.get_me()
                if me:
                    logger.info(f"Bağlı kullanıcı: {me.first_name} (@{me.username})")
                else:
                    logger.warning("Kullanıcı bilgisi alınamadı! Yetkilendirme sorunları olabilir.")
                    
                    # Yeniden oturum açmayı dene
                    phone = os.getenv('PHONE')
                    if phone:
                        try:
                            logger.info(f"Yeniden oturum açmayı deniyorum: {phone}")
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
                            else:
                                logger.error("Yeniden oturum açma başarısız oldu, kullanıcı bilgisi alınamadı")
                                raise ValueError("Geçerli bir kullanıcı oturumu gerekli")
                        except Exception as auth_error:
                            logger.error(f"Yeniden oturum açma hatası: {str(auth_error)}")
                            raise ValueError("Bot çalışması için geçerli bir kullanıcı oturumu gerekli")
                
                # Kesme sinyali olayını oluştur
                stop_event = asyncio.Event()
                
                # Sinyal işleyicileri ekle
                add_signal_handlers(stop_event)
                
                # ServiceFactory ve ServiceManager kullanarak servisleri yönet
                service_factory = ServiceFactory()
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
                    "message"        # MessageService
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
        finally:
            # Veritabanı bağlantısını kapat
            if 'db' in locals():
                await db.close()
                logger.info("Veritabanı bağlantısı kapatıldı.")
            
            # İstemciyi kapat
            if 'client' in locals():
                await client.disconnect()
                logger.info("Telegram istemcisi kapatıldı.")
    
    except Exception as e:
        logger.critical(f"Kritik hata: {e}")
        import traceback
        logger.critical(traceback.format_exc())

# Düzenli yedekleme yapın
def backup_database():
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    # SQLite için
    sqlite_path = "data/users.db"
    if os.path.exists(sqlite_path):
        backup_path = f"{backup_dir}/users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(sqlite_path, backup_path)
    
    # PostgreSQL için
    if os.getenv("DB_CONNECTION", "").startswith("postgresql"):
        # postgresql://username:password@hostname:port/database
        db_url = os.getenv("DB_CONNECTION", "")
        if db_url:
            # URL'den bilgileri ayıkla
            parts = db_url.replace("postgresql://", "").split("@")
            
            if len(parts) == 2:
                auth, connection = parts
                user_pass = auth.split(":")
                host_db = connection.split("/")
                
                user = user_pass[0] if len(user_pass) > 0 else ""
                host = host_db[0].split(":")[0] if len(host_db) > 0 else "localhost"
                dbname = host_db[1] if len(host_db) > 1 else ""
                
                backup_file = f"{backup_dir}/pg_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
                subprocess.run(["pg_dump", "-U", user, "-h", host, "-d", dbname, "-f", backup_file])

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
            
        # Signal handler kodu kaldırıldı, ana fonksiyona taşındı
        # Artık burada sinyal işleyicisi eklenmeyecek
        
        # Ana fonksiyonu çalıştır
        loop.run_until_complete(main())
        
    except Exception as e:
        import traceback
        print(f"Kritik hata: {e}")
        traceback.print_exc()
