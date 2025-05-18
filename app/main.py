#!/usr/bin/env python3
# Test amaçlı basit bir uygulama
import os
import sys
import time
import asyncio
import logging
import signal
import platform
from typing import List, Dict, Any, Optional

from telethon import TelegramClient, errors  # errors modülünü içe aktar
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_session
from app.services.base import BaseService
# EngagementService gelecekte eklenecek
# from app.services.messaging.engagement_service import EngagementService
from app.services.messaging.dm_service import DirectMessageService
from app.services.messaging.promo_service import PromoService
from app.services.analytics.activity_service import ActivityService
from app.services.monitoring.health_service import HealthService
# from app.services.monitoring.health_monitor import HealthMonitor

# Yapılandırma değerlerini almak için yardımcı fonksiyon
def get_secret_or_str(val):
    if hasattr(val, 'get_secret_value'):
        return val.get_secret_value().strip()
    if isinstance(val, str):
        return val.strip()
    return str(val)

print("Bot başlatılıyor...")
print(f"Python sürümü: {sys.version}")
print(f"Çalışma dizini: {os.getcwd()}")
print("Test uygulaması çalışıyor...")

# Ortamdan temel bilgileri oku ve göster
api_id = os.getenv("API_ID", "Tanımsız")
api_hash = os.getenv("API_HASH", "Tanımsız")
session_name = os.getenv("SESSION_NAME", "Tanımsız")
phone = os.getenv("PHONE", "Tanımsız")
db_name = os.getenv("DB_NAME", "Tanımsız")

print("\n--- Ortam Bilgileri ---")
print(f"API ID: {api_id}")
print(f"API HASH: {api_hash[:5]}...{api_hash[-5:] if len(api_hash) > 10 else ''}")
# API_HASH değerinin doğruluğunu kontrol et
expected_hash = get_secret_or_str(settings.API_HASH)
if api_hash != expected_hash:
    print(f"\n⚠️ UYARI: API_HASH değeri beklenen değerden farklı!")
    print(f"  Okunan:   {api_hash}")
    print(f"  Beklenen: {expected_hash}")
    print("  Bu sorun kimlik doğrulama hatalarına neden olabilir.")
    # API_HASH değerini düzelt
    print("  API_HASH değeri düzeltiliyor...")
    os.environ["API_HASH"] = expected_hash
    api_hash = expected_hash
    print("  ✅ API_HASH değeri düzeltildi.\n")
print(f"Session adı: {session_name}")
print(f"Telefon numarası: {phone}")
print(f"Veritabanı adı: {db_name}")
print("----------------------\n")

# Loglama yapılandırması
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_output.log")
    ]
)

logger = logging.getLogger(__name__)

# Renklendirme için ANSI kodları
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'



class TelegramBot:
    """
    Telegram botu ana sınıfı.
    - Tüm servisleri başlatır ve yönetir
    - Telegram bağlantısını sağlar
    - Graceful shutdown sürecini yönetir
    """

    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.db: Optional[AsyncSession] = None
        self.services: Dict[str, BaseService] = {}
        self.tasks: List[asyncio.Task] = []
        self.running = False
        self.shutdown_event = asyncio.Event()

        try:
            # Benzersiz bir oturum adı oluştur (eski oturum dosyalarıyla çakışmasını önlemek için)
            original_session_name = settings.SESSION_NAME
            # Sabit bir oturum adı kullanıyoruz - API kimlik doğrulama sorunlarını önlemek için
            unique_session_name = original_session_name
            
            # Eski oturum dosyalarını temizleme - tamamen devre dışı
            # Oturum dosyalarını silmek, API kimlik doğrulamasının tekrar yapılmasına ve
            # doğrulama hatalarının oluşma olasılığını artırır.
            
            # Mevcut oturum dosyalarını kullan
            logger.info(f"Oturum adı: {unique_session_name} (Sabit oturum adı kullanılıyor)")
            
            # Mevcut oturum dosyalarını kontrol et
            for ext in ['.session', '.session-journal']:
                if os.path.exists(f"{original_session_name}{ext}"):
                    logger.info(f"Mevcut oturum dosyası: {original_session_name}{ext}")
                    
            # Sistem bilgilerini al 
            device_info = f"Python {platform.python_version()} on {platform.system()} {platform.release()}"
            logger.info(f"TelegramClient başlatılmadan önce - API_ID: {settings.API_ID} (Tip: {type(settings.API_ID)})")
            logger.info(f"TelegramClient başlatılmadan önce - API_HASH: '{get_secret_or_str(settings.API_HASH)[:4]}...{get_secret_or_str(settings.API_HASH)[-4:]}' (Tip: {type(get_secret_or_str(settings.API_HASH))})")
            logger.info(f"TelegramClient başlatılmadan önce - SESSION_NAME: {unique_session_name}")
            logger.info(f"Cihaz bilgisi: {device_info}")
            
            self.client = TelegramClient(
                unique_session_name, 
                settings.API_ID, 
                get_secret_or_str(settings.API_HASH),
                proxy=None,
                connection_retries=int(settings.TG_CONNECTION_RETRIES),
                device_model=device_info,
                system_version=platform.release(),
                app_version='1.0',
                lang_code='tr',
                system_lang_code='tr'
            )
            logger.info("TelegramClient başarıyla başlatıldı.")
        except Exception as e:
            logger.error(f"TelegramClient başlatılırken hata: {e}", exc_info=True)

    async def initialize(self):
        """Bot sistemini başlat."""
        logger.info("Initializing Telegram Bot")
        
        try:
            # Veritabanı bağlantısı
            self.db = next(get_session())
            
            # Veritabanı bağlantısını test et
            try:
                query_result = self.db.execute(text("SELECT 1 as result"))
                row = query_result.fetchone()
                if not row or row.result != 1:
                    logger.warning("Veritabanı bağlantı testi başarısız oldu")
            except Exception as db_error:
                logger.error(f"Veritabanı bağlantı hatası: {str(db_error)}")
            
            # Servisleri başlat
            await self._initialize_services()
            
            # Sinyalleri kaydet (Ctrl+C ve sistem sinyalleri)
            self._register_signal_handlers()
            
            logger.info("Telegram Bot initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Bot initialization error: {str(e)}", exc_info=True)
            return False

    async def _initialize_services(self):
        """Tüm servisleri başlat."""
        # Activity Service
        activity_service = ActivityService(db=self.db)
        self.services["activity"] = activity_service
        
        # Health Service
        health_service = HealthService(client=self.client, service_manager=self, db=self.db)
        self.services["health"] = health_service
        
        # Sorunlu servisleri şimdilik başlatma
        # Engagement service gelecekte eklenecek
        # engagement_service = EngagementService(client=self.client, db=self.db)
        # self.services["engagement"] = engagement_service
        
        # DM Service - aktifleştirildi
        dm_service = DirectMessageService(client=self.client, db=self.db)
        self.services["dm"] = dm_service
        
        # Promo Service - aktifleştirildi
        promo_service = PromoService(client=self.client, db=self.db)
        self.services["promo"] = promo_service
        
        # Tüm servisleri başlat
        for name, service in self.services.items():
            try:
                logger.info(f"Initializing service: {name}")
                await service.initialize()
            except Exception as e:
                logger.error(f"Error initializing service {name}: {str(e)}", exc_info=True)

    async def start(self):
        """Telegram oturumunu ve aktif servis döngülerini başlat."""
        if not self.client:
            logger.error("Telegram client başlatılamadı. Oturum açılamıyor.")
            return

        try:
            logger.info("Telegram Bot başlatılıyor...")
            connection_attempts = 0
            max_connection_attempts = 3
            
            # İstemci bağlantısını birkaç kez deneyerek kur
            while connection_attempts < max_connection_attempts:
                connection_attempts += 1
                
                if not self.client.is_connected():
                    logger.info(f"Bağlantı kuruluyor... (Deneme {connection_attempts}/{max_connection_attempts})")
                    try:
                        await self.client.connect()
                        # Bağlantı durumunu kontrol et
                        if self.client.is_connected():
                            logger.info("Bağlantı başarıyla kuruldu!")
                            # Bağlantı sonrası kısa bir bekleme ekleyelim
                            await asyncio.sleep(3)
                            break
                        else:
                            logger.warning("Bağlantı kurulamadı, tekrar deneniyor...")
                            await asyncio.sleep(5)  # Yeni deneme öncesi bekleme süresini artıralım
                    except Exception as conn_err:
                        logger.error(f"Bağlantı hatası: {conn_err}")
                        # Daha uzun bir bekleme süresi
                        await asyncio.sleep(5)
                        # Bağlantı istisna durumunda, client nesnesini yeniden oluşturalım
                        if connection_attempts < max_connection_attempts:
                            try:
                                logger.info("TelegramClient yeniden oluşturuluyor...")
                                # Eski client nesnesini düzgünce kapatalım
                                if self.client and self.client.is_connected():
                                    await self.client.disconnect()
                                
                                # Yeni client oluşturalım
                                device_info = f"Python {platform.python_version()} on {platform.system()} {platform.release()}"
                                self.client = TelegramClient(
                                    unique_session_name, 
                                    settings.API_ID, 
                                    get_secret_or_str(settings.API_HASH),
                                    proxy=None,
                                    connection_retries=int(settings.TG_CONNECTION_RETRIES),
                                    device_model=device_info,
                                    system_version=platform.release(),
                                    app_version='1.0',
                                    lang_code='tr',
                                    system_lang_code='tr'
                                )
                                logger.info("TelegramClient yeniden oluşturuldu.")
                            except Exception as recreate_err:
                                logger.error(f"TelegramClient yeniden oluşturma hatası: {recreate_err}")
                else:
                    logger.info("İstemci zaten bağlı.")
                    break
            
            # Son bağlantı durumunu kontrol et
            if not self.client.is_connected():
                logger.warning("Telegram API'ye bağlantı kurulamadı, Health Service ile bağlantı kurulmaya çalışılacak.")
                try:
                    # Health servisi başlat
                    health_service = HealthService(client=self.client, service_manager=self, db=self.db)
                    await health_service.initialize()
                    # Force connect çağır
                    conn_result = await health_service.force_connect()
                    if conn_result.get("connected", False):
                        logger.info("Health servisi ile bağlantı başarıyla kuruldu!")
                    else:
                        logger.error(f"Health servisi ile bağlantı kurulamadı: {conn_result.get('error', 'Bilinmeyen hata')}")
                        logger.error("Telegram API'ye bağlantı kurulamadı. Bot başlatılamıyor.")
                        return
                except Exception as health_err:
                    logger.error(f"Health servisi ile bağlantı denemesi sırasında hata: {health_err}")
                    logger.error("Telegram API'ye bağlantı kurulamadı. Bot başlatılamıyor.")
                    return

            # Force user mode
            phone_to_use = settings.PHONE.get_secret_value() if hasattr(settings.PHONE, 'get_secret_value') else settings.PHONE
            bot_token_to_use = None  # Ensure bot token is not used for user mode

            logger.info(f"Phone to use: {phone_to_use}")
            logger.info(f"Bot token to use: {bot_token_to_use}")

            if not phone_to_use and not bot_token_to_use:
                logger.error("Ne bot token ne de telefon numarası ayarlanmamış. Lütfen .env dosyasını kontrol edin.")
                return

            # Simplified user mode login
            logger.info("Kullanıcı modu ile başlatılıyor.")
            
            # Oturum durumunu kontrol et
            is_authorized = False
            try:
                # Önce bağlantı durumunu son kez kontrol edelim
                if not self.client.is_connected():
                    logger.warning("Yetkilendirme öncesi bağlantı kurulamadı, yeniden deneniyor...")
                    await self.client.connect()
                    await asyncio.sleep(3)  # Bağlantı kurulduktan sonra kısa bir bekleme
                
                # Şimdi yetkilendirme durumunu kontrol edelim
                is_authorized = await self.client.is_user_authorized()
                logger.info(f"Kullanıcı yetkilendirme durumu: {'Yetkilendirilmiş' if is_authorized else 'Yetkilendirilmemiş'}")
            except Exception as auth_check_err:
                logger.error(f"Yetkilendirme durumu kontrol edilirken hata: {auth_check_err}")
                # Yetkilendirme kontrolü sırasında hata oluşursa, oturumu tekrar başlatmayı deneyelim
                try:
                    logger.info("Yetkilendirme hatası nedeniyle yeniden bağlanılıyor...")
                    await self.client.disconnect()
                    await asyncio.sleep(2)
                    await self.client.connect()
                    await asyncio.sleep(3)
                    is_authorized = await self.client.is_user_authorized()
                    logger.info(f"Yeniden bağlantı sonrası yetkilendirme durumu: {'Yetkilendirilmiş' if is_authorized else 'Yetkilendirilmemiş'}")
                except Exception as reconnect_err:
                    logger.error(f"Yeniden bağlantı hatası: {reconnect_err}")
                    # Eğer bu işlem de başarısız olursa, yeni oturum oluşturmayı deneyeceğiz
                    is_authorized = False
            
            if not is_authorized:
                logger.info(f"client.send_code_request çağrılmadan önce - PHONE: {phone_to_use}")
                logger.info(f"client.send_code_request çağrılmadan önce - Client API ID: {self.client.api_id}")
                
                # Ensure client is connected before sending code request
                if not self.client.is_connected():
                    logger.info("Yeniden bağlanılıyor...")
                    await self.client.connect()
                
                logger.info(f"API ID used by client: {self.client.api_id}")
                # API HASH'i loglarken dikkatli olalım, tamamını loglamak güvenlik riski oluşturabilir.
                # Sadece bir kısmını veya var olup olmadığını loglayabiliriz.
                logger.info(f"API HASH used by client is set: {bool(self.client.api_hash)}")

                try:
                    # Bağlantı kurulduktan sonra kısa bir bekleme
                    logger.info("Bağlantı sonrası 5 saniye bekleniyor...")
                    await asyncio.sleep(5)
                    
                    # En güncel API ID ve HASH değerlerini kullandığımızdan emin olalım
                    logger.info(f"Telefon numarasına ({phone_to_use}) kod gönderiliyor...")
                    logger.info(f"API ID: {self.client.api_id}, API HASH ayarlandı mı: {bool(self.client.api_hash)}")
                    
                    code_attempt = 0
                    max_code_attempts = 3
                    while code_attempt < max_code_attempts:
                        code_attempt += 1
                        try:
                            result = await self.client.send_code_request(phone_to_use)
                            logger.info(f"Kod gönderildi. Sonuç tipi: {result.type}")
                            break
                        except Exception as code_err:
                            logger.error(f"Kod gönderme hatası (Deneme {code_attempt}/{max_code_attempts}): {code_err}")
                            if code_attempt >= max_code_attempts:
                                raise
                            await asyncio.sleep(5)
                    
                    code = await self.prompt_for_code()
                    logger.info("Kod alındı, giriş yapılıyor...")
                    
                    signin_attempt = 0
                    max_signin_attempts = 3
                    while signin_attempt < max_signin_attempts:
                        signin_attempt += 1
                        try:
                            me = await self.client.sign_in(phone=phone_to_use, code=code)
                            logger.info(f"Giriş başarılı: {me.first_name} (ID: {me.id})")
                            break
                        except errors.SessionPasswordNeededError:
                            logger.info("İki faktörlü kimlik doğrulama (2FA) gerekli.")
                            password_attempt = 0
                            max_password_attempts = 3
                            while password_attempt < max_password_attempts:
                                password_attempt += 1
                                try:
                                    password = await self.prompt_for_password()
                                    me = await self.client.sign_in(password=password)
                                    logger.info(f"2FA ile giriş başarılı: {me.first_name if me else 'Unknown'} (ID: {me.id if me else 'Unknown'})")
                                    break
                                except Exception as password_err:
                                    logger.error(f"2FA ile giriş hatası (Deneme {password_attempt}/{max_password_attempts}): {password_err}")
                                    if password_attempt >= max_password_attempts:
                                        raise
                            break
                        except Exception as signin_err:
                            logger.error(f"Giriş yapma hatası (Deneme {signin_attempt}/{max_signin_attempts}): {signin_err}")
                            if signin_attempt >= max_signin_attempts:
                                raise
                            await asyncio.sleep(3)
                except errors.PhoneNumberInvalidError:
                    logger.error("Geçersiz telefon numarası. Lütfen .env dosyasını kontrol edin.")
                    return
                except errors.ApiIdInvalidError as e:
                    logger.error(f"API ID/HASH geçersiz: {e}")
                    logger.error(f"Kullanılan API ID: {self.client.api_id}, Kullanılan API HASH ayarlandı mı: {bool(self.client.api_hash)}")
                    return
                except Exception as e:
                    logger.error(f"Oturum açma sırasında beklenmedik hata: {e}", exc_info=True)
                    return
            else:
                logger.info("Kullanıcı zaten yetkilendirilmiş.")
                
                # Yetkilendirme doğrulama
                try:
                    me = await self.client.get_me()
                    if me:
                        logger.info(f"Mevcut oturumda kullanıcı: {me.first_name} (ID: {me.id})")
                    else:
                        logger.warning("get_me() None döndürdü, ancak oturum yetkilendirilmiş görünüyor.")
                except Exception as me_error:
                    logger.error(f"Kullanıcı bilgileri alınırken hata: {me_error}")

            # Son bağlantı kontrolü
            if not self.client.is_connected():
                logger.error("Telegram botu bağlantısı beklenmedik şekilde kapandı.")
                return

            logger.info("Telegram Bot başarıyla bağlandı.")
            
            # Kullanıcı bilgilerini al
            try:
                self.me = None
                get_me_attempt = 0
                max_get_me_attempts = 3
                
                while get_me_attempt < max_get_me_attempts:
                    get_me_attempt += 1
                    try:
                        # Bağlantı durumunu kontrol et
                        if not self.client.is_connected():
                            logger.warning(f"get_me öncesi bağlantı kopmuş, yeniden bağlanılıyor (Deneme {get_me_attempt}/{max_get_me_attempts})...")
                            await self.client.connect()
                            await asyncio.sleep(2)
                            
                        self.me = await self.client.get_me()
                        if self.me:
                            logger.info(f"Başarıyla {self.me.first_name} olarak giriş yapıldı (ID: {self.me.id}).")
                            # BOT_USERNAME'i güvenli bir şekilde ayarla
                            try:
                                username = self.me.username if hasattr(self.me, 'username') and self.me.username else ""
                                settings.BOT_USERNAME = username
                                logger.info(f"BOT_USERNAME ayarlandı: {username}")
                            except Exception as username_err:
                                logger.warning(f"BOT_USERNAME ayarlanamadı: {username_err}")
                                # Devam et, bu kritik değil
                            break
                        else:
                            logger.warning(f"get_me() None döndürdü (Deneme {get_me_attempt}/{max_get_me_attempts}).")
                            await asyncio.sleep(3)
                    except Exception as me_error:
                        logger.error(f"Kullanıcı bilgileri alınırken hata (Deneme {get_me_attempt}/{max_get_me_attempts}): {me_error}")
                        await asyncio.sleep(3)
                
                # Eğer tüm denemeler başarısız olduysa, yine de devam edelim
                if not self.me:
                    logger.warning("Kullanıcı bilgileri alınamadı, bot bu bilgiler olmadan devam edecek.")
                    # me bilgisi olmadan da devam etmeliyiz, bu kritik bir hata değil
                
            except Exception as me_error:
                logger.error(f"Kullanıcı bilgileri işlenirken beklenmedik hata: {me_error}")
                logger.warning("Kullanıcı bilgileri olmadan devam ediliyor...")
                # Hatayı yükseltme, botu başlatmaya devam et
                self.me = None

            logger.info("Starting Telegram Bot")
            
            # Banner göster
            self._show_banner()

            # CLI menüsünü göster
            self._show_cli_menu()
            
            # Servislerin çalışma döngülerini başlat
            self.tasks = []
            
            # Sağlık servisini başlat
            health_task = asyncio.create_task(
                self.services["health"].start_monitoring(),
                name="health_monitor"
            )
            self.tasks.append(health_task)
            
            # Aktivite servisini başlat
            activity_task = asyncio.create_task(
                self._run_service_safely("activity"),
                name="activity_service"
            )
            self.tasks.append(activity_task)
            
            self.running = True
            logger.info("Bot services started successfully")
            
            # PID dosyasını oluştur
            self._create_pid_file()
            
            print(f"{Colors.GREEN}Bot başarıyla başlatıldı! Arkaplanda çalışıyor...{Colors.ENDC}")
            print(f"Bot durumunu kontrol etmek için: {Colors.BOLD}python -m app.cli status{Colors.ENDC}")
            print(f"Botu durdurmak için: {Colors.BOLD}python -m app.cli stop{Colors.ENDC}")
            
            # Kapatma sinyali bekle
            await self.shutdown_event.wait()
        except Exception as e:
            logger.error(f"Error starting bot: {str(e)}", exc_info=True)
            await self.cleanup()

    async def prompt_for_code(self):
        """Kullanıcıdan doğrulama kodunu al."""
        code = input("Lütfen Telegram doğrulama kodunu girin: ")
        return code.strip()

    async def prompt_for_password(self):  # prompt_for_password async olmalı
        """Kullanıcıdan 2FA şifresini al."""
        password = input("Lütfen Telegram 2FA şifrenizi girin: ")
        return password.strip()

    def _show_banner(self):
        """Bot banner'ını göster."""
        banner = f"""
{Colors.BLUE}╔════════════════════════════════════════════════════╗
║ {Colors.GREEN}      _______    _                                 {Colors.BLUE}║
║ {Colors.GREEN}     |__   __|  | |                                {Colors.BLUE}║
║ {Colors.GREEN}        | | ___ | | ___  __ _ _ __ __ _ _ __ ___   {Colors.BLUE}║
║ {Colors.GREEN}        | |/ _ \| |/ _ \/ _` | '__/ _` | '_ ` _ \  {Colors.BLUE}║
║ {Colors.GREEN}        | | (_) | |  __/ (_| | | | (_| | | | | | | {Colors.BLUE}║
║ {Colors.GREEN}        |_|\___/|_|\___|\__, |_|  \__,_|_| |_| |_| {Colors.BLUE}║
║ {Colors.GREEN}                         __/ |                     {Colors.BLUE}║
║ {Colors.GREEN}                        |___/                      {Colors.BLUE}║
║ {Colors.GREEN}                                                   {Colors.BLUE}║
║ {Colors.GREEN}      Bot v{settings.VERSION if hasattr(settings, 'VERSION') else '4.0.0'}{" " * 36}{Colors.BLUE}║
╚════════════════════════════════════════════════════╝{Colors.ENDC}
"""
        print(banner)
        
    def _show_cli_menu(self):
        """CLI menüsünü göster."""
        print(f"\n{Colors.BOLD}{Colors.BLUE}Bot CLI Arayüzü{Colors.ENDC}")
        print("----------------------------------------")
        print(f"1. {Colors.GREEN}Bot Durumu{Colors.ENDC}       : python -m app.cli status")
        print(f"2. {Colors.GREEN}Botu Durdur{Colors.ENDC}      : python -m app.cli stop")
        print(f"3. {Colors.GREEN}Şablonları Güncelle{Colors.ENDC}: python -m app.cli templates")
        print(f"4. {Colors.GREEN}Veritabanı Onarımı{Colors.ENDC} : python -m app.cli repair")
        print(f"5. {Colors.GREEN}Yeni Oturum{Colors.ENDC}      : python -m app.cli session")
        print("----------------------------------------\n")

    async def _run_service_safely(self, service_name):
        """Bir servisi güvenli bir şekilde çalıştır."""
        service = self.services.get(service_name)
        if not service:
            logger.error(f"Service {service_name} not found")
            return
        
        try:
            # Servisin start metodu varsa çağır
            if hasattr(service, "start") and callable(service.start):
                await service.start()
            # Veya run metodu varsa çağır
            elif hasattr(service, "run") and callable(service.run):
                await service.run()
            # Veya servisin özel metodunu çağır
            elif hasattr(service, f"start_{service_name}") and callable(getattr(service, f"start_{service_name}")):
                await getattr(service, f"start_{service_name}")()
        except Exception as e:
            logger.error(f"Error running service {service_name}: {str(e)}", exc_info=True)

    def _create_pid_file(self):
        """PID dosyasını oluştur."""
        try:
            pid = os.getpid()
            pid_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".bot_pids")
            
            # Dosya varsa, içeriğini oku
            existing_pids = []
            if os.path.exists(pid_file):
                with open(pid_file, "r") as f:
                    existing_pids = [line.strip() for line in f.readlines() if line.strip()]
            
            # Mevcut PID'i ekle
            if str(pid) not in existing_pids:
                existing_pids.append(str(pid))
            
            # Dosyayı yaz
            with open(pid_file, "w") as f:
                f.write("\n".join(existing_pids))
            
            logger.info(f"PID file created with PID: {pid}")
        except Exception as e:
            logger.error(f"Error creating PID file: {str(e)}")

    def _register_signal_handlers(self):
        """Sistem sinyallerini kaydet."""
        # SIGINT (Ctrl+C) ve SIGTERM için handler
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_signal)
    
    def _handle_signal(self, sig, frame):
        """Sinyal geldiğinde düzgün kapatma işlemini başlat."""
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        if not self.shutdown_event.is_set():
            asyncio.create_task(self.cleanup())
            self.shutdown_event.set()

    def get_services(self):
        """
        Bot tarafından yönetilen servisleri döndürür.
        
        Returns:
            Dict[str, BaseService]: Servis adı ve servis nesnesi eşleşmeleri
        """
        return self.services
        
    async def run(self):
        """Bot'u çalıştır."""
        try:
            # Client kontrol et ve gerekirse tekrar bağlan
            if not self.client:
                logger.error("Telegram client başlatılmadı. Önce initialize() çağırın.")
                return
                
            if not self.client.is_connected():
                logger.info("Telegram'a bağlanılıyor...")
                try:
                    await self.client.connect()
                    logger.info("Bağlantı başarılı!")
                except Exception as conn_error:
                    logger.error(f"Bağlantı hatası: {str(conn_error)}")
                    return
            
            # Tüm servisleri başlat
            active_tasks = []
            for name, service in self.services.items():
                if hasattr(service, 'start'):
                    try:
                        task = asyncio.create_task(service.start())
                        active_tasks.append(task)
                        logger.info(f"Started service: {name}")
                    except Exception as e:
                        logger.error(f"Error starting service {name}: {str(e)}")
            
            # Bot kapanana kadar bekle
            try:
                await self.shutdown_event.wait()
            except asyncio.CancelledError:
                logger.info("Bot run task cancelled")
            finally:
                # Tüm görevleri temizle
                for task in active_tasks:
                    task.cancel()
                
                if active_tasks:
                    await asyncio.gather(*active_tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Bot çalıştırma hatası: {str(e)}", exc_info=True)
                
    async def cleanup(self):
        """Bot'u ve servislerini kapat."""
        # Servisleri durdur
        for name, service in self.services.items():
            if hasattr(service, 'stop'):
                try:
                    await service.stop()
                    logger.info(f"Stopped service: {name}")
                except Exception as e:
                    logger.error(f"Error stopping service {name}: {str(e)}")
        
        # TelegramClient'ı kapat
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            logger.info("Bot disconnected from Telegram")

    async def get_status(self) -> Dict[str, Any]:
        """Bot durumunu döndür."""
        status = {
            "running": self.running,
            "client_connected": self.client is not None and self.client.is_connected() if self.client else False,
            "services": {}
        }
        
        # Servislerin durumunu ekle
        for name, service in self.services.items():
            if hasattr(service, "get_status") and callable(service.get_status):
                try:
                    service_status = await service.get_status()
                    status["services"][name] = service_status
                except Exception as e:
                    status["services"][name] = {"error": str(e)}
            else:
                status["services"][name] = {"running": getattr(service, "running", False)}
        
        return status

async def main():
    """Ana çalışma fonksiyonu."""
    bot = TelegramBot()
    success = await bot.initialize()
    if success:
        await bot.start()
    else:
        logger.error("Bot initialization failed")

if __name__ == "__main__":
    # Windows'ta multiprocessing için gerekli
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Ana döngüyü başlat
    asyncio.run(main())
