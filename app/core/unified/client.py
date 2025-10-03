"""
Telegram client bağlantısı için yardımcı fonksiyonlar
"""
import logging
import asyncio
import os
import shutil
import signal
import sys
import sqlite3
import atexit
import time
from typing import Optional
from telethon import TelegramClient
from telethon.sessions import MemorySession, StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from app.core.config import settings
from app.core.tdlib.session import create_memory_session, create_string_session, create_postgres_session, create_session

logger = logging.getLogger(__name__)

# Global client nesnesi
_client = None
_client_lock = asyncio.Lock()
_is_shutting_down = False

# Uygulama kapatılırken çağrılacak fonksiyon
def _cleanup_on_exit():
    """Uygulama kapatılırken client bağlantısını düzgün şekilde kapatır"""
    global _is_shutting_down
    
    if _is_shutting_down:
        return  # Tekrarlı cleanup çağrılarını önle
        
    _is_shutting_down = True
    logger.info("Uygulama kapanıyor, Telegram bağlantısı temizleniyor...")
    
    if _client:
        try:
            # Event loop kontrolü
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # Event loop kapalı veya bulunamadı, yeni loop oluştur
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if not loop.is_closed():
                loop.run_until_complete(_client.disconnect())
                # Kapanma işlemi için biraz bekle
                loop.run_until_complete(asyncio.sleep(0.5))
                
            logger.info("Telegram client bağlantısı temiz bir şekilde kapatıldı")
        except Exception as e:
            logger.error(f"Client kapatılırken hata: {e}")

# Çıkış fonksiyonunu atexit'e kaydet
atexit.register(_cleanup_on_exit)

# SIGINT (Ctrl+C) ve SIGTERM sinyalleri için handler ekle
def setup_exit_handlers():
    """Çıkış sinyalleri için handler'ları ayarlar"""
    def signal_handler(sig, frame):
        global _is_shutting_down
        
        if _is_shutting_down:
            logger.warning(f"İkinci sinyal alındı {sig}, zorla çıkılıyor...")
            sys.exit(1)
            
        logger.info(f"Sinyal alındı: {sig}, client bağlantısı kapatılıyor...")
        _cleanup_on_exit()
        time.sleep(1)  # Kapanma işlemi için biraz bekle
        sys.exit(0)
    
    # Sinyalleri kaydet
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Çıkış sinyal işleyicileri ayarlandı")
    except Exception as e:
        logger.error(f"Sinyal işleyicileri ayarlanırken hata: {e}")

# Uygulama başlangıcında signal handler'ları ayarla
setup_exit_handlers()

async def get_client() -> Optional[TelegramClient]:
    """
    Telegram client nesnesini döndürür. Eğer bağlantı yoksa bağlantı kurar.
    MemorySession kullanarak veritabanı kilitlenme sorunlarını önler.
    
    Returns:
        Optional[TelegramClient]: Bağlantı kurulmuş client nesnesi veya None
    """
    global _client, _is_shutting_down
    
    if _is_shutting_down:
        logger.warning("Uygulama kapanıyor, yeni client oluşturma isteği engellendi")
        return None
    
    if _client and _client.is_connected():
        return _client
        
    async with _client_lock:
        # Lock içinde tekrar kontrol et (başka bir thread bağlantı kurmuş olabilir)
        if _client and _client.is_connected():
            return _client
            
        try:
            logger.info("Telegram client bağlantısı kuruluyor...")
            
            # Kullanılan oturum türünü belirle
            session_type = os.getenv("TELEGRAM_SESSION_TYPE", "memory").lower()
            session = None
            
            if session_type == "memory":
                # Bellek tabanlı geçici oturum (çalışma süresi boyunca)
                logger.info("Bellek tabanlı oturum (MemorySession) kullanılıyor")
                session = create_memory_session()
            elif session_type == "string":
                # String tabanlı oturum (.env içinde SESSION_STRING değeri olmalı)
                session_string = os.getenv("SESSION_STRING")
                if session_string:
                    logger.info("String tabanlı oturum (StringSession) kullanılıyor")
                    session = create_string_session(session_string)
                else:
                    logger.warning("SESSION_STRING değeri bulunamadı, bellek tabanlı oturuma geçiliyor")
                    session = create_memory_session()
            elif session_type == "postgres":
                # PostgreSQL tabanlı oturum
                logger.info("PostgreSQL tabanlı oturum (PostgresSession) kullanılıyor")
                session = create_postgres_session(settings.SESSION_NAME)
            else:
                # Varsayılan dosya tabanlı oturum (SQLite)
                logger.info("Dosya tabanlı oturum kullanılıyor")
                session = create_session(settings.SESSION_NAME)
            
            # API_HASH değerini SecretStr türünden string'e dönüştür
            api_hash = settings.API_HASH.get_secret_value() if hasattr(settings.API_HASH, 'get_secret_value') else str(settings.API_HASH)
            
            # Client oluştur
            _client = TelegramClient(
                session,
                settings.API_ID,
                api_hash,
                proxy=settings.PROXY if hasattr(settings, "PROXY") else None,
                connection_retries=settings.TG_CONNECTION_RETRIES,
                retry_delay=settings.TG_RETRY_DELAY,
                auto_reconnect=True,
                request_retries=settings.TG_REQUEST_RETRIES,
                flood_sleep_threshold=settings.TG_FLOOD_SLEEP_THRESHOLD
            )
            
            # Bağlantı kur
            await _client.connect()
            
            # Memory session için otomatik oturum açma veya yeni oturum oluşturma gerekebilir
            if not await _client.is_user_authorized() and isinstance(session, (MemorySession, StringSession)) and session_type != "string":
                # Mevcut .session dosyasına erişmeyi dene
                file_session_path = os.path.join(settings.SESSIONS_DIR, f"{settings.SESSION_NAME}.session")
                if os.path.exists(file_session_path):
                    logger.info(f"Memory Session için mevcut oturum dosyasından verileri alıyoruz: {file_session_path}")
                    try:
                        # AuthKey okuma
                        file_client = TelegramClient(file_session_path, settings.API_ID, api_hash)
                        await file_client.connect()
                        
                        if await file_client.is_user_authorized():
                            me = await file_client.get_me()
                            logger.info(f"Dosya tabanlı oturumdan kullanıcı bilgileri alındı: {me.first_name} (@{me.username})")
                            
                            # Session bilgilerini taşı
                            logger.info("Oturum bilgilerini bellek tabanlı oturuma aktarıyorum...")
                            # AuthKey ve diğer bilgileri al
                            auth_key = file_client.session.auth_key
                            # AuthKey ve diğer bilgileri _client'a aktar
                            _client.session.auth_key = auth_key
                            _client.session.save()
                            
                            # Kontrolü doğrula
                            if await _client.is_user_authorized():
                                logger.info("Oturum bilgileri başarıyla aktarıldı!")
                            else:
                                logger.warning("Oturum bilgileri aktarıldı ancak yetkilendirme başarısız.")
                        
                        await file_client.disconnect()
                    except Exception as e:
                        logger.error(f"Dosya tabanlı oturumdan veri aktarımı hatası: {e}")
                        
                # Otomatik giriş yapmayı dene
                if not await _client.is_user_authorized() and settings.PHONE:
                    logger.info("Otomatik oturum açmayı deniyorum...")
                    try:
                        phone = settings.PHONE.get_secret_value() if hasattr(settings.PHONE, 'get_secret_value') else settings.PHONE
                        
                        # Kod gönder
                        await _client.send_code_request(phone)
                        logger.info(f"{phone} numarasına doğrulama kodu gönderildi")
                        
                        # Eğer TELEGRAM_CODE çevre değişkeni varsa kullan
                        code = os.getenv("TELEGRAM_CODE")
                        if code:
                            logger.info("Doğrulama kodu çevre değişkeninden alındı, giriş yapılıyor...")
                            try:
                                await _client.sign_in(phone, code)
                                logger.info("Otomatik giriş başarılı!")
                            except SessionPasswordNeededError:
                                # 2FA şifresi gerekiyor
                                password = os.getenv("TELEGRAM_2FA_PASSWORD")
                                if password:
                                    await _client.sign_in(password=password)
                                    logger.info("2FA ile otomatik giriş başarılı!")
                                else:
                                    logger.error("2FA şifresi gerekiyor ancak TELEGRAM_2FA_PASSWORD değişkeni yok!")
                        else:
                            logger.info("Otomatik giriş için TELEGRAM_CODE değişkeni bulunamadı")
                    except Exception as e:
                        logger.error(f"Otomatik giriş hatası: {e}")
            
            # Giriş yapıldı mı kontrol et
            if not await _client.is_user_authorized():
                logger.error("Telegram hesabına giriş yapılmamış! Yeniden oturum açmaya çalışılıyor...")
                
                # Mevcut .session dosyalarını kontrol et
                session_files = []
                session_dir = settings.SESSIONS_DIR
                for file in os.listdir(session_dir):
                    if file.endswith(".session"):
                        session_files.append(os.path.join(session_dir, file))
                
                if session_files:
                    logger.info(f"{len(session_files)} oturum dosyası bulundu, bunları deniyorum...")
                    success = False
                    
                    for session_file in session_files:
                        try:
                            session_name = os.path.basename(session_file).replace(".session", "")
                            logger.info(f"Deneniyor: {session_name}")
                            
                            tmp_client = TelegramClient(session_name, settings.API_ID, api_hash)
                            await tmp_client.connect()
                            
                            if await tmp_client.is_user_authorized():
                                me = await tmp_client.get_me()
                                logger.info(f"Başarılı oturum bulundu: {session_name} - {me.first_name} (@{me.username})")
                                
                                # Bu oturumu kullan
                                _client = tmp_client
                                success = True
                                break
                            else:
                                logger.warning(f"Oturum dosyası {session_name} yetkilendirilmemiş")
                                await tmp_client.disconnect()
                        except Exception as e:
                            logger.error(f"Oturum dosyası {session_file} denenirken hata: {e}")
                    
                    if not success:
                        logger.error("Hiçbir oturum dosyası yetkilendirilmemiş!")
                        await _client.disconnect()
                        _client = None
                        return None
                else:
                    logger.error("Kullanılabilir oturum dosyası bulunamadı!")
                    await _client.disconnect()
                    _client = None
                    
                    # Otomatik telegram_login.py çalıştırma
                    logger.info("Otomatik oturum açma scripti çalıştırılıyor...")
                    try:
                        import subprocess
                        cmd = [sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "utilities", "telegram_login.py")]
                        subprocess.Popen(cmd)
                        logger.info(f"telegram_login.py çalıştırıldı, lütfen oturumu tamamlayın ve botu yeniden başlatın")
                    except Exception as e:
                        logger.error(f"Otomatik oturum açma scripti çalıştırılamadı: {e}")
                    
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
    """Client bağlantısını kapatır"""
    global _client
    
    if _client:
        try:
            await _client.disconnect()
            logger.info("Telegram client bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"Client bağlantısı kapatılırken hata: {e}")
        finally:
            _client = None 