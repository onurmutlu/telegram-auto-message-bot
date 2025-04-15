# -*- coding: utf-8 -*-
"""
# ============================================================================ #
# Dosya: dm_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/dm_service.py
# İşlev: Telegram bot için direkt mesajlaşma servisi.
#
# Amaç: Bot ile kullanıcılar arasındaki özel mesajlaşmayı yönetir,
# otomatik davet gönderimi yapar ve grupları keşfederek kullanıcı havuzu oluşturur.
#
# Temel Özellikler:
# - Gelen özel mesajları otomatik yanıtlama
# - Veritabanındaki kullanıcılara düzenli davet mesajları gönderme
# - Periyodik grup keşfi ve üye toplama
# - Akıllı hız sınırlama ve hata yönetimi
# - Şablon tabanlı mesaj sistemi
#
# Build: 2025-04-07-22:00:00
# Versiyon: v3.5.0
# ============================================================================ #
"""
import asyncio
import json
import logging
import os
import platform
import ctypes
import random
import re
import time
import traceback
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, Union, TYPE_CHECKING

from colorama import Fore, Style, init
init(autoreset=True)

# TDLib wrapper'ını doğru şekilde import et
try:
    from tdlib import Client as TdClient
    TDLIB_AVAILABLE = True
except ImportError:
    TDLIB_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("TDLib Python wrapper bulunamadı. DM servisi TDLib özellikleri devre dışı.")

from telethon import errors, events
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest

from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter
from bot.services.base_service import BaseService

# Type checking için gerekli importlar
if TYPE_CHECKING:
    from telethon import TelegramClient
    from telethon.tl.types import User, Message
    from config.config import Config
    from database.user_db import UserDatabase
    from asyncio import Event

# Logger yapılandırması
logger = logging.getLogger(__name__)

class DirectMessageService(BaseService):
    """
    Özel mesajlaşma ve davet işlemlerini yöneten servis.
    
    Bu servis, kullanıcılara özel mesaj gönderme, davet yönetimi ve grup keşfi 
    işlevlerini sağlar.
    
    Temel özellikleri:
    - Özel mesaj gönderimi ve yanıtlama
    - Grupları keşfederek kullanıcı havuzu oluşturma
    - İnteraktif botlarla Telegram gruplarını yönetme
    
    Attributes:
        client: Telegram API istemcisi
        config: Bot yapılandırma ayarları
        db: Veritabanı bağlantısı
        stop_event: Servisi durdurmak için event
        running: Servisin çalışma durumu
        invites_sent: Gönderilen davet sayısı
        processed_dms: İşlenen özel mesaj sayısı
        rate_limiter: Hız sınırlayıcı
        group_links: Grup bağlantı listesi
        super_users: Yetkili kullanıcı listesi
        responded_users: Bu oturumda yanıt verilen kullanıcı seti
    """

    def __init__(self, client, config, db, stop_event=None):
        super().__init__("dm", client, config, db, stop_event)
        
        # Durum takibi
        self.running = True
        self.processed_dms = 0
        self.invites_sent = 0
        self.last_activity = datetime.now()
        
        # Kullanıcı yanıt takibi - bu oturum için
        self.responded_users: Set[int] = set()
        
        # TDLib özelliklerini başlat
        self.use_tdlib = False
        self.td_client = None
        self.tdlib = None
        
        # TDLib'yi başlat
        if self._init_tdlib():
            logger.info("TDLib entegrasyonu etkinleştirildi")
        else:
            logger.warning("TDLib entegrasyonu olmadan başlatılıyor...")

        # TDLib entegrasyonu mevcut mu kontrol et
        if not TDLIB_AVAILABLE:
            logger.warning("TDLib entegrasyonu bulunamadı, DM servisi TDLib özellikleri olmadan çalışacak")
            self.have_tdlib = False
        else:
            self.have_tdlib = True
            # TDLib için gerekli parametreleri hazırla
            self.api_id = getattr(self.config.telegram, 'api_id', int(os.environ.get('API_ID', 0)))
            self.api_hash = getattr(self.config.telegram, 'api_hash', os.environ.get('API_HASH', ''))
            self.phone = getattr(self.config.telegram, 'phone', os.environ.get('PHONE', ''))
            
            # TDLib client referansı
            self.tdlib_client = None
            
            # TDLib asenkron API için yapılar
            self.requests = {}  # Request ID -> Future eşlemesi
        
        # Kullanıcı profil yöneticisi
        from bot.utils.user_profiler import UserProfiler
        self.user_profiler = UserProfiler(db, config)
        
        # Ayarları yükleme
        self._load_settings()
        
        # Rate limiter başlat
        self._setup_rate_limiter()
        
        # Mesaj şablonları
        self._load_templates()
        
        # Error Groups takibi
        self.error_groups = set()
        
        # Servis referansları
        self.services = {}

        # Entity önbelleği
        self.entity_cache = {}  # user_id -> entity
        
        logger.info("DM servisi başlatıldı")
    
    def _find_tdjson_path(self) -> Optional[str]:
        """
        Sistem platformuna göre TDLib JSON kütüphanesini bul
        
        Returns:
            str: Bulunan kütüphane yolu veya None
        """
        system = platform.system().lower()
        
        # Varsayılan yol listesi
        paths = []
        
        if system == 'darwin':  # macOS
            paths = [
                '/usr/local/lib/libtdjson.dylib',
                '/opt/homebrew/lib/libtdjson.dylib',
                '/usr/lib/libtdjson.dylib',
                'libtdjson.dylib'
            ]
        elif system == 'linux':
            paths = [
                '/usr/local/lib/libtdjson.so',
                '/usr/lib/libtdjson.so',
                'libtdjson.so'
            ]
        elif system == 'windows':
            paths = [
                'C:\\Program Files\\TDLib\\bin\\tdjson.dll',
                'C:\\TDLib\\bin\\tdjson.dll',
                'tdjson.dll'
            ]
            
        # Çevresel değişken kontrol et
        if 'TDJSON_PATH' in os.environ:
            paths.insert(0, os.environ['TDJSON_PATH'])
            
        # Yolları dene
        for path in paths:
            try:
                # Dinamik olarak kütüphaneyi yüklemeyi dene
                ctypes.CDLL(path)
                logger.info(f"TDLib JSON kütüphanesi bulundu: {path}")
                return path
            except OSError:
                # Bu yolda kütüphane bulunamadı, bir sonrakini dene
                continue
                
        return None

    def _init_tdlib(self):
        """TDLib başlatma ve bağlantı işlemleri"""
        try:
            import ctypes
            import json
            import uuid
            import time
            
            # TDLib kütüphanesini bul ve yükle
            lib_path = self._find_tdjson_path()
            if not lib_path:
                logger.error("TDLib kütüphanesi bulunamadı, TDLib özellikleri devre dışı")
                self.use_tdlib = False
                return False
                
            # Kütüphaneyi yükle
            try:
                self.tdlib = ctypes.CDLL(lib_path)
                logger.info(f"TDLib kütüphanesi başarıyla yüklendi: {lib_path}")
            except Exception as e:
                logger.error(f"TDLib kütüphanesi yüklenemedi: {str(e)}")
                self.use_tdlib = False
                return False
                
            # TDLib fonksiyonlarını tanımla
            self.tdlib.td_json_client_create.restype = ctypes.c_void_p
            self.tdlib.td_json_client_send.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            self.tdlib.td_json_client_receive.argtypes = [ctypes.c_void_p, ctypes.c_double]
            self.tdlib.td_json_client_receive.restype = ctypes.c_char_p
            self.tdlib.td_json_client_execute.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            self.tdlib.td_json_client_execute.restype = ctypes.c_char_p
            self.tdlib.td_json_client_destroy.argtypes = [ctypes.c_void_p]
            
            # TDLib istemcisi oluştur
            self.td_client = self.tdlib.td_json_client_create()
            
            # TDLib için işlemci fonksiyonları ekle - HATA KORUMASINI GÜÇLENDİR
            self.tdlib_send = lambda query: self.tdlib.td_json_client_send(
                self.td_client, 
                json.dumps(query).encode('utf-8')
            )
            
            # None kontrolü ekleyerek hata düzeltildi
            self.tdlib_receive = lambda timeout: (
                json.loads(
                    result.decode('utf-8')
                ) if (result := self.tdlib.td_json_client_receive(self.td_client, timeout)) is not None else None
            )
            
            self.tdlib_execute = lambda query: json.loads(
                self.tdlib.td_json_client_execute(self.td_client, json.dumps(query).encode('utf-8')).decode('utf-8')
            )
            
            # TDLib kimlik bilgileri
            self.tdlib_client_id = str(uuid.uuid4())
            
            # TDLib başlatma
            self._tdlib_setup_authentication()
            
            # TDLib hazır
            self.use_tdlib = True
            logger.info("TDLib başarıyla başlatıldı ve hazır")
            return True
            
        except Exception as e:
            logger.error(f"TDLib başlatma hatası: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            self.use_tdlib = False
            return False

    def _tdlib_setup_authentication(self):
        """TDLib kimlik doğrulama ayarlarını yapar"""
        # Temel parametre ayarları
        self.tdlib_send({
            '@type': 'setTdlibParameters',
            'parameters': {
                'use_test_dc': False,
                'database_directory': './tdlib-db',
                'use_message_database': True,
                'use_secret_chats': True,
                'api_id': self.config.telegram.api_id,
                'api_hash': self.config.telegram.api_hash,
                'system_language_code': 'tr',
                'device_model': 'Python TDLib',
                'application_version': '1.0',
                'enable_storage_optimizer': True
            }
        })
        
        # Telefon numarası veya bot token ile kimlik doğrulama
        if hasattr(self.config.telegram, 'phone'):
            self.tdlib_send({
                '@type': 'setAuthenticationPhoneNumber',
                'phone_number': self.config.telegram.phone
            })
        elif hasattr(self.config.telegram, 'bot_token'):
            self.tdlib_send({
                '@type': 'checkAuthenticationBotToken',
                'token': self.config.telegram.bot_token
            })
        
        # Yanıtları işle
        start_time = time.time()
        timeout = 10.0  # 10 saniye timeout
        
        while time.time() - start_time < timeout:
            try:
                result = self.tdlib_receive(0.1)
                # Sonuç None ise, döngüyü atla
                if not result:
                    continue
                    
                if result.get('@type') == 'updateAuthorizationState':
                    auth_state = result.get('authorization_state', {}).get('@type')
                    
                    if auth_state == 'authorizationStateReady':
                        logger.info("TDLib başarıyla yetkilendirildi")
                        return True
                        
                    elif auth_state == 'authorizationStateWaitPhoneNumber':
                        if not hasattr(self.config.telegram, 'phone'):
                            logger.error("TDLib için telefon numarası gerekli")
                            return False
                            
                        self.tdlib_send({
                            '@type': 'setAuthenticationPhoneNumber',
                            'phone_number': self.config.telegram.phone
                        })
                        
                    elif auth_state == 'authorizationStateWaitCode':
                        logger.error("Doğrulama kodu gerekli - otomatik doğrulama yapılamıyor")
                        return False
                        
            except Exception as e:
                logger.error(f"TDLib yanıt işlenirken hata: {str(e)}")
                continue
                    
        logger.warning("TDLib yetkilendirme zaman aşımına uğradı, sınırlı işlevsellik kullanılacak")
        return False

    async def initialize(self) -> bool:
        """Servisi başlatmadan önce hazırlar."""
        # Önce BaseService'in initialize metodunu çağır
        await super().initialize()
        
        try:
            # Bot'un kendi ID'sini alma - BU ÖNEMLİ
            me = await self.client.get_me()
            self.my_id = me.id
            logger.info(f"Bot ID alındı: {self.my_id}")
        except Exception as e:
            logger.error(f"Bot ID alınamadı: {str(e)}")
            self.my_id = None  # En azından None olarak ayarla
        
        # Diğer başlatma işlemleri...
        
        return True
        # initialize metodunun sonuna ekleyin
        await self.test_templates()
    async def _login_async(self):
        """TDLib istemcisinde asenkron oturum açma"""
        # TDLib gibi senkron bir API'yi asyncio ile kullanmak için
        # executor kullanarak bloke olmayan çağrılar yapıyoruz
        loop = asyncio.get_running_loop()
        
        # Asenkron login
        return await loop.run_in_executor(None, lambda: self.tdlib_client.login())
    
    async def _call_tdlib_method(self, method_name, params=None):
        """TDLib metodunu asenkron çağırır"""
        if not params:
            params = {}
            
        # Unique request id ekle
        request_id = str(uuid.uuid4())
        params['@extra'] = request_id
        
        # Future oluştur ve kaydet
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.requests[request_id] = future
        
        # Metodu çağır (blocking çağrıyı executor'da çalıştır)
        await loop.run_in_executor(
            None,
            lambda: self.tdlib_client.send(method_name, params)
        )
        
        # Yanıtı bekle
        return await future

    async def search_public_chats(self, query):
        """Herkese açık grupları arar"""
        if not hasattr(self, 'have_tdlib') or not self.have_tdlib:
            return []
            
        try:
            result = await self._call_tdlib_method('searchPublicChats', {'query': query})
            if result and isinstance(result, dict) and result.get('@type') == 'chats':
                return result.get('chat_ids', [])
            return []
        except Exception as e:
            logger.error(f"Herkese açık grup arama hatası: {str(e)}")
            return []

    async def start(self) -> bool:
        """Servisi başlatır."""
        # Zaten çalışıyorsa tekrar başlatma
        if self.running:
            return True
        
        self.running = True
        logger.info(f"{self.name} servisi başlatılıyor...")
        
        # Önceki event handler'ları temizle
        try:
            self.client.remove_event_handler(self.on_new_message) 
            self.client.remove_event_handler(self.handle_private_message)
        except Exception:
            pass  # İlk başlatmada handler olmayabilir, hata görmezden gelinebilir
        
        # DÜZELTME: Sadece özel mesajlar için olan handler'ı ekle
        # Bu handler direkt olarak mesajları işler
        self.client.add_event_handler(
            self.handle_private_message,
            events.NewMessage(incoming=True, func=lambda e: e.is_private)
        )
        
        logger.info(f"{self.name} servisi başlatıldı.")
        return True

    async def stop(self) -> None:
        """
        Servisi güvenli bir şekilde durdurur.
        
        Returns:
            None
        """
        if not self.running:
            return
            
        self.running = False
        logger.info(f"{self.name} servisi durdurma sinyali gönderildi")
        
        # Event handler'ları kaldır
        try:
            self.client.remove_event_handler(self.on_new_message)
        except Exception as e:
            logger.error(f"Event handler kaldırma hatası: {str(e)}")
        
        # TDLib istemcisini kapat
        if hasattr(self, 'tdlib_client') and self.tdlib_client:
            try:
                if hasattr(self, 'receive_task') and self.receive_task:
                    self.receive_task.cancel()
                    
                await asyncio.sleep(0.5)  # Kısa bir bekletme
                
                # TDLib istemcisini asenkron olarak kapat
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: self.tdlib_client.stop())
                self.tdlib_client = None
            except Exception as e:
                logger.error(f"TDLib kapatma hatası: {str(e)}")
                
        await super().stop()
    
    async def _receive_loop(self):
        """TDLib'den sürekli yanıt alma döngüsü"""
        if not hasattr(self, 'have_tdlib') or not self.have_tdlib or not self.tdlib_client:
            logger.warning("TDLib istemcisi mevcut değil, alma döngüsü çalıştırılmadı")
            return
            
        while self.running and not self.stop_event.is_set():
            try:
                # TDLib'den güncelleme al
                event = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: self.tdlib_client.receive(timeout=1.0)
                )
                
                if event:
                    await self._process_tdlib_event(event)
                    
                # Her döngü arasında kısa bekleme
                await asyncio.sleep(0.001)  # Event loop tıkanmasını önler
            except asyncio.CancelledError:
                logger.info("TDLib alma döngüsü iptal edildi")
                break
            except Exception as e:
                logger.error(f"TDLib alma döngüsü hatası: {str(e)}")
                await asyncio.sleep(1.0)  # Hata durumunda biraz bekle
    
    async def _process_tdlib_event(self, event):
        """TDLib olayını işle"""
        if not event or not isinstance(event, dict):
            return
            
        # Extra ID ile kaydedilmiş future varsa tamamla
        if '@extra' in event and event['@extra'] in self.requests:
            future = self.requests.pop(event['@extra'])
            if not future.done():
                future.set_result(event)
        elif event.get('@type') == 'error':
            logger.error(f"TDLib hatası: {event.get('message', 'Bilinmeyen hata')}")

    def _load_settings(self):
        """Çevre değişkenlerinden ve yapılandırmadan ayarları yükler."""
        # Mesajlaşma ayarları
        self.dm_footer_message = os.getenv("DM_FOOTER_MESSAGE", 
                                          "Menü için müsait olan arkadaşlarıma yazabilirsin:")
        self.dm_response_template = os.getenv("DM_RESPONSE_TEMPLATE", 
                                             "Merhaba! Şu anda yoğunum, lütfen arkadaşlarımdan birine yazarak destek alabilirsin:")
        
        # Batch ve cooldown ayarları - güvenli dönüştürme
        invite_batch = os.getenv("INVITE_BATCH_SIZE", "50")
        self.invite_batch_size = int(invite_batch.split('#')[0].strip())
        
        invite_cooldown = os.getenv("INVITE_COOLDOWN_MINUTES", "5")
        self.invite_cooldown_minutes = int(invite_cooldown.split('#')[0].strip())
        
        dm_cooldown = os.getenv("DM_COOLDOWN_MINUTES", "5")
        self.dm_cooldown_minutes = int(dm_cooldown.split('#')[0].strip())
        
        # Super users
        self.super_users = [s.strip() for s in os.getenv("SUPER_USERS", "").split(',') 
                            if s and s.strip()]
        
        # Grup linkleri
        self.group_links = self._parse_group_links()
        logger.info(f"Loaded {len(self.group_links)} group links.")
        
        # Debug modu
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
    
    def _parse_group_links(self):
        """Grup bağlantılarını çevre değişkenlerinden veya yapılandırmadan yükler."""
        # Önce çevre değişkeninden deneyelim
        links_str = os.getenv("GROUP_LINKS", "")
        
        # Debug amaçlı log
        logger.debug(f"Çevre değişkeninden okunan GROUP_LINKS: '{links_str}'")
        
        # Admin gruplarını da alalım (genellikle aynı liste)
        admin_groups_str = os.getenv("ADMIN_GROUPS", "")
        logger.debug(f"Çevre değişkeninden okunan ADMIN_GROUPS: '{admin_groups_str}'")
        
        # Virgülle ayrılmış değerleri dizi haline getir
        links = [link.strip() for link in links_str.split(',') if link.strip()]
        
        # Bağlantı sayısını logla
        logger.debug(f"Çevre değişkenlerinden {len(links)} link bulundu")
        
        return links
    
    def _get_formatted_group_links(self):
        """Grup linklerini isimlerle birlikte formatlayan yardımcı metot."""
        links = self._parse_group_links()
        if not links:
            logger.warning("Formatlanacak grup linki bulunamadı!")
            return []
            
        formatted_links = []
        
        for link in links:
            if not link or not isinstance(link, str):
                continue
                
            clean_link = link.strip()
            display_name = None
            
            # İsim belirleme mantığı
            if "omegle" in clean_link.lower():
                display_name = "Omegle Sohbet"
            elif "sosyal" in clean_link.lower():
                display_name = "Sosyal Muhabbet"
            elif "sohbet" in clean_link.lower() and "ask" not in clean_link.lower():
                display_name = "Arkadaşlık Grubu"
            elif "ask" in clean_link.lower() or "aşk" in clean_link.lower():
                display_name = "Aşkım Sohbet"
            elif "duygu" in clean_link.lower():
                display_name = "Duygusal Sohbet"
            elif "t.me/" in clean_link:
                # t.me linklerinden grup adını çıkar
                group_name = clean_link.split("/")[-1]
                display_name = group_name.capitalize()
            elif "@" in clean_link:
                # @ işaretli grup adlarını düzenle
                group_name = clean_link.replace("@", "")
                display_name = group_name.capitalize()
            else:
                # Diğer link formatları için
                display_name = "Telegram Grubu"
                    
            # Bağlantı formatlama
            formatted_link = clean_link
            if "t.me/" not in clean_link and not clean_link.startswith("@"):
                formatted_link = f"@{clean_link.replace('@', '')}"
                
            # Sonuç formatlama
            formatted_links.append(f"{display_name}: {formatted_link}")
                
        return formatted_links

    def _setup_rate_limiter(self):
        """Hız sınırlayıcıyı yapılandırır."""
        # Ana rate limiter
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=self.config.get_setting('dm_rate_limit_initial_rate', 3),  # Başlangıçta daha düşük
            period=self.config.get_setting('dm_rate_limit_period', 60),
            error_backoff=self.config.get_setting('dm_rate_limit_error_backoff', 1.5),
            max_jitter=self.config.get_setting('dm_rate_limit_max_jitter', 2.0)
        )
        
        # Rate limiting state - bu değişkenler artık rate_limiter içinde
        # Geriye dönük uyumluluk için basit bir erişim sağlayalım
        self.pm_state = {
            'burst_count': 0,
            'hourly_count': 0,
            'hour_start': datetime.now(),
            'last_pm_time': None,
            'consecutive_errors': 0
        }
    
    def _load_templates(self):
        """Mesaj şablonlarını yükler."""
        try:
            # Template dosyalarının yolları
            invite_template_path = Path('data/invites.json')
            response_template_path = Path('data/responses.json')
            message_template_path = Path('data/messages.json')
            
            # Yolları logla
            logger.info(f"Şablon dosyaları: {invite_template_path}, {response_template_path}, {message_template_path}")
            
            # Şablonlar için varsayılan değerler
            self.invite_templates = []
            self.redirect_templates = []
            self.flirty_templates = []
            self.group_message_templates = []
            
            # Davet şablonlarını yükle
            if invite_template_path.exists():
                with open(invite_template_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.invite_templates = data.get('invites', [])
                    self.invite_first_templates = data.get('first_invite', [])
                    self.redirect_templates = data.get('redirect_messages', [])
                    self.invite_outros = data.get('invites_outro', [""])
                    
            # Yanıt şablonlarını yükle
            if response_template_path.exists():
                with open(response_template_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.flirty_templates = data.get('flirty', [])
                    
            # Grup mesaj şablonlarını yükle
            if message_template_path.exists():
                with open(message_template_path, 'r', encoding='utf-8') as f:
                    self.group_message_templates = json.load(f)
                    
            # Yüklenen şablon sayılarını göster
            logger.info(f"Yüklenen şablonlar: {len(self.invite_templates)} davet, {len(self.redirect_templates)} yönlendirme, {len(self.flirty_templates)} flirty, {len(self.group_message_templates)} grup mesajı")
        except Exception as e:
            logger.error(f"Şablon yükleme hatası: {str(e)}")
            # Varsayılanlar
            self.invite_templates = ["Merhaba! Grubumuza bekleriz: {}"]
            self.redirect_templates = ["Merhaba! Gruba katılabilirsiniz: {}"]
            self.flirty_templates = ["Merhaba 😊"]
            self.group_message_templates = ["Selam grup!"]
    
    async def on_new_message(self, event):
        """Yeni mesaj olayını işler"""
        try:
            # Sadece özel mesajları ele al (grup mesajlarını değil)
            if not event.is_private:
                return
                
            # İşleme
            sender = await event.get_sender()
            if sender:
                user_data = {
                    'user_id': sender.id,
                    'username': getattr(sender, 'username', None),
                    'first_name': getattr(sender, 'first_name', None),
                    'last_name': getattr(sender, 'last_name', None)
                }
                
                # Kullanıcıyı işle
                await self._process_user(user_data, event=event)
                
        except Exception as e:
            logger.error(f"Özel mesaj işleme hatası: {str(e)}")
    
    async def handle_new_message(self, event):
        """Yeni mesaj olayını işler."""
        try:
            if not event.message or not event.message.text:
                return

            # Önce mesaj loglaması - sorunu teşhis için
            sender = await event.get_sender()
            sender_id = sender.id if sender else "bilinmiyor"
            logger.debug(f"DM alındı: {sender_id} - '{event.message.text[:20]}...'")
            
            # is_private kontrolü - SADECE DM'LERİ İŞLE
            if not event.is_private:
                logger.debug(f"Özel mesaj değil, atlanıyor: {event.chat_id}")
                return
                
            # Bot mention edildi mi?
            if event.message.mentioned:
                await self._handle_mention(event)
                
            # Bot'un mesajına cevap mı?
            elif event.message.reply_to and event.message.reply_to.reply_to_msg_id:
                # Cevap verilen mesajın kime ait olduğunu kontrol et
                replied_msg = await event.message.get_reply_message()
                # my_id değişkeninin varlığını kontrol et
                bot_id = getattr(self, 'my_id', None)
                if replied_msg and replied_msg.sender_id == bot_id:
                    # Bot'un mesajına cevap verilmiş
                    logger.info(f"Bot mesajına cevap işleniyor: {event.message.text}")
                    await self._handle_reply_to_bot(event)
                    
            # Özel komutlar
            elif event.message.text.startswith('/'):
                await self._handle_command(event)
            # DİREK YENİ MESAJ - OTOMATİK CEVAP
            else:
                # Direkt DM'lere otomatik cevap ver
                logger.info(f"Yeni DM alındı, otomatik cevap gönderiliyor: {sender_id}")
                user_data = {
                    'user_id': sender.id,
                    'username': getattr(sender, 'username', None),
                    'first_name': getattr(sender, 'first_name', None),
                    'last_name': getattr(sender, 'last_name', None)
                }
                await self._process_user(user_data, event)
                
        except Exception as e:
            logger.error(f"DM mesajı işleme hatası: {str(e)}")
            logger.debug(traceback.format_exc())  # Stack trace ekleyerek detaylı hata bilgisi

    async def handle_private_message(self, event):
        """Sadece özel mesajları işler"""
        if not event.is_private:
            return  # Sadece özel mesajları işle
            
        try:
            sender = await event.get_sender()
            if sender:
                logger.info(f"Özel mesaj alındı: {sender.id} (@{getattr(sender, 'username', 'bilinmiyor')})")
                
                # Kullanıcı verisini hazırla
                user_data = {
                    'user_id': sender.id,
                    'username': getattr(sender, 'username', None),
                    'first_name': getattr(sender, 'first_name', None),
                    'last_name': getattr(sender, 'last_name', None)
                }
                
                # Kullanıcıyı işle ve otomatik cevap ver
                await self._process_user(user_data, event)
                
        except Exception as e:
            logger.error(f"Özel mesaj işleme hatası: {str(e)}")

    async def _handle_reply_to_bot(self, event):
        """Bot mesajlarına verilen yanıtları işler"""
        try:
            # Yanıt metni analizi
            message_text = event.message.text.lower()
            sender = await event.get_sender()
            
            # Duygu analizi (basit kural tabanlı)
            is_positive = any(word in message_text for word in ["teşekkür", "sağol", "evet", "tamam", "iyi", "güzel"])
            is_question = any(word in message_text for word in ["?", "ne", "nasıl", "nerede", "kim", "ne zaman", "neden"])
            is_greeting = any(word in message_text for word in ["merhaba", "selam", "hey", "hi", "hello"])
            
            # Yanıt türünü belirle
            response_type = 'flirty'  # Varsayılan türü flörtöz olarak ayarla
            
            if is_greeting:
                response_type = 'greeting'
            elif is_question:
                response_type = 'question'
            elif is_positive:
                response_type = 'positive'
                
            # Flörtöz bir yanıt seç (responses.json dosyasından)
            response = self._select_response(response_type)
            
            # Yanıtı gönder
            await event.reply(response)
            if hasattr(self, 'reply_count'):
                self.reply_count += 1
            
            # DM atma denemesi - kullanıcıya özel mesaj gönder
            await self._try_send_dm_to_user(sender)
            
            # Kullanıcı etkileşim profilini güncelle (yeni özellik)
            await self._update_user_interaction_profile(sender.id, message_text)
            
        except Exception as e:
            logger.error(f"Bot mesajına cevap işleme hatası: {str(e)}")

    async def _try_send_dm_to_user(self, user):
        """Bot ile etkileşime giren kullanıcıya DM gönderir"""
        if not user:
            return
            
        try:
            # Kullanıcı bilgileri
            user_id = user.id
            username = getattr(user, 'username', None)
            first_name = getattr(user, 'first_name', None)
            last_name = getattr(user, 'last_name', None)
            
            # Kullanıcı verisi oluştur
            user_data = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name
            }
            
            # Kullanıcı yakın zamanda DM aldı mı kontrol et
            if self.db and hasattr(self.db, 'was_recently_contacted'):
                recent_contact = await self._run_async_db_method(
                    self.db.was_recently_contacted,
                    user_id,
                    self.dm_cooldown_minutes
                )
                
                if recent_contact:
                    logger.debug(f"Kullanıcı {username or user_id} yakın zamanda DM aldı, tekrar gönderilmiyor")
                    return False
            
            # Kullanıcıyı işle ve DM gönder (kendi metodu çağrı)
            await self._process_user(user_data)
            logger.info(f"Etkileşimli kullanıcıya DM gönderildi: {username or user_id}")
            return True
            
        except Exception as e:
            logger.debug(f"Kullanıcıya DM gönderme hatası: {str(e)}")
            return False
    
    async def _process_user(self, user_data, event=None):
        """Tek bir kullanıcıyı işler ve DM gönderir"""
        try:
            user_id = user_data.get('user_id')
            username = user_data.get('username')
            
            if not user_id:
                logger.error("Kullanıcı ID eksik, işlem yapılamıyor")
                return
            
            # Kullanıcıyı veritabanına ekle
            if self.db and hasattr(self.db, 'add_user'):
                try:
                    await self._run_async_db_method(
                        self.db.add_user, 
                        user_id, 
                        username, 
                        user_data.get('first_name'), 
                        user_data.get('last_name')
                    )
                except Exception as db_err:
                    logger.warning(f"Veritabanı işlemi başarısız: {str(db_err)}")
            
            # Eğer direkt mesaj olayı varsa ve henüz cevap verilmediyse, yanıt ver
            if event and user_id:
                logger.info(f"Kullanıcıya otomatik cevap gönderiliyor: {user_id}")
                
                # was_recently_invited kontrolü güvenli yapılıyor
                was_invited = False
                try:
                    if self.db and hasattr(self.db, 'was_recently_invited'):
                        was_invited = await self._run_async_db_method(
                            self.db.was_recently_invited,
                            user_id,
                            self.invite_cooldown_minutes
                        )
                except Exception as check_err:
                    logger.warning(f"Davet kontrolü başarısız: {str(check_err)}")
                    # was_invited = False kalacak
                
                # Uygun yanıt gönder
                success = False
                if was_invited:
                    success = await self._send_redirect_message(event, user_data)
                else:
                    success = await self._send_invite_message(event, user_data)
                    
                # Başarılıysa kullanıcıyı listeye ekle
                if success:
                    self.responded_users.add(user_id)
                    logger.info(f"Yanıt başarılı şekilde gönderildi: {user_id}")
                    self.processed_dms += 1
                else:
                    logger.warning(f"Yanıt gönderilemedi: {user_id}")
                    
        except Exception as e:
            logger.error(f"Kullanıcı işleme hatası: {str(e)}")
            logger.debug(traceback.format_exc())
    
    async def _send_invite_message(self, event, user_data):
        """Kullanıcıya davet mesajı gönderir"""
        success = False
        try:
            sender = await event.get_sender()
            user_id = getattr(sender, 'id', None)
            user_name = getattr(sender, 'first_name', "Kullanıcı")
            
            # Davet şablonu seç ve formatla
            invite_template = self._choose_invite_template()
            invite_message = invite_template.format(user_name=user_name)
            
            # Grup linkleri ekle
            formatted_links = self._get_formatted_group_links()
            links_text = "\n\n" + ("\n".join([f"• {link}" for link in formatted_links]) 
                        if formatted_links else "Üzgünüm, şu anda aktif grup linki bulunmamaktadır.")
            
            # Super users ekle
            super_users_text = ""
            if self.super_users:
                valid_super_users = [f"• @{su}" for su in self.super_users if su]
                if valid_super_users:
                    super_users_text = f"\n\n{self.dm_footer_message}\n" + "\n".join(valid_super_users)
            
            # Tam mesaj oluştur
            full_message = f"{invite_message}{links_text}{super_users_text}"
            
            # Hız sınırlama kontrolü
            if hasattr(self, 'rate_limiter'):
                wait_time = self.rate_limiter.get_wait_time()
                if wait_time > 0:
                    logger.debug(f"Rate limit nedeniyle {wait_time:.1f} saniye bekleniyor")
                    await asyncio.sleep(wait_time)
            
            # Mesajı gönder
            await event.respond(full_message)
            logger.info(f"Davet mesajı gönderildi: {user_id}")
            self.invites_sent += 1
            success = True
            
            # Rate limiter'ı güncelle
            self.rate_limiter.mark_used()
            
            # Veritabanını güncelle
            if user_id and self.db and hasattr(self.db, 'mark_user_invited'):
                await self._run_async_db_method(self.db.mark_user_invited, user_id)
                
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"FloodWaitError davet gönderirken: {wait_time} saniye bekleniyor")
            self.rate_limiter.register_error(e)
            await asyncio.sleep(wait_time + 1)
        except Exception as e:
            logger.error(f"Davet mesajı gönderirken hata: {str(e)}", exc_info=True)
        return success
    
    async def _send_redirect_message(self, event, user_data):
        """Zaten davet edilmiş kullanıcıya yönlendirme mesajı gönderir"""
        success = False
        try:
            sender = await event.get_sender()
            user_name = getattr(sender, 'first_name', "Kullanıcı")
            
            # Redirect templates config veya varsayılanlar
            redirect_templates = getattr(
                self, 
                'redirect_templates',
                [f"Merhaba {user_name}! Sizi zaten davet ettik. Gruplarımıza katılabilirsiniz:"]
            )
            
            # Rastgele şablon seç ve formatla
            redirect_message_template = random.choice(redirect_templates)
            redirect_message = redirect_message_template.format(user_name=user_name)
            
            # Formatlı grup linklerini al
            formatted_links = self._get_formatted_group_links()
            links_text = "\n\n" + ("\n".join([f"• {link}" for link in formatted_links]) 
                        if formatted_links else "Üzgünüm, şu anda aktif grup linki bulunmamaktadır.")
            
            # Mesajı gönder
            await event.respond(f"{redirect_message}{links_text}")
            logger.info(f"Yönlendirme mesajı gönderildi: {sender.id}")
            success = True
            
            # Rate limiter'ı güncelle
            self.rate_limiter.mark_used()

        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"FloodWaitError yönlendirme gönderirken: {wait_time} saniye bekleniyor")
            self.rate_limiter.register_error(e)
            await asyncio.sleep(wait_time + 1)
        except Exception as e:
            logger.error(f"Yönlendirme mesajı gönderirken hata: {str(e)}", exc_info=True)
        return success
    
    def _choose_invite_template(self):
        """Rastgele bir davet şablonu seçer"""
        templates = getattr(self, 'invite_templates', ["Merhaba {user_name}! Grubumuza katılmak ister misiniz?"])
        if not templates:
            return "Merhaba {user_name}! Grubumuza katılmak ister misiniz?"
            
        return random.choice(templates)
    
    async def _run_async_db_method(self, method, *args, **kwargs):
        """Veritabanı metodunu thread-safe biçimde çalıştırır."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: method(*args, **kwargs)
        )
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndürür.
        
        Returns:
            Dict: Servis durum bilgileri
        """
        status = await super().get_status()
        
        # DM servisine özel durumlar
        rate_limiter_status = {}
        if hasattr(self, 'rate_limiter') and hasattr(self.rate_limiter, 'get_status'):
            rate_limiter_status = self.rate_limiter.get_status()
            
        status.update({
            'processed_dms': self.processed_dms,
            'invites_sent': self.invites_sent,
            'last_activity': self.last_activity.strftime("%Y-%m-%d %H:%M:%S"),
            'rate_limiter': rate_limiter_status,
            'recent_users_count': len(self.responded_users),
            'cooldown_minutes': getattr(self, 'invite_cooldown_minutes', 5),
            'tdlib_available': getattr(self, 'have_tdlib', False)
        })
        return status
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servis istatistiklerini döndürür.
        
        Returns:
            Dict: Servis istatistikleri
        """
        return {
            'total_sent': self.invites_sent,
            'responded_users': len(self.responded_users),
            'groups_count': len(self.group_links),
            'super_users_count': len(getattr(self, 'super_users', []))
        }
    
    def set_services(self, services):
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
        """
        self.services = services
        logger.debug(f"{self.name} servisi diğer servislere bağlandı")

    async def send_promotional_message(self, message_template, user_limit=50, cooldown_hours=48):
        """Veritabanındaki kullanıcılara tanıtım mesajı gönderir"""
        # Son gönderimden bu yana cooldown geçti mi kontrol et
        last_promo = await self._run_async_db_method(self.db.get_setting, 'last_promo_time')
        if last_promo:
            last_time = datetime.fromisoformat(last_promo)
            if datetime.now() - last_time < timedelta(hours=cooldown_hours):
                logger.info(f"Tanıtım mesajı cooldown süresi dolmadı: {cooldown_hours} saat")
                return 0
        
        # Aktif kullanıcıları al
        users = await self._run_async_db_method(
            self.db.get_active_users_for_promo,
            user_limit
        )
        
        if not users:
            logger.info("Tanıtım için uygun kullanıcı bulunamadı")
            return 0
        
        sent_count = 0
        for user in users:
            # Rate limiting için aralık bırak
            await asyncio.sleep(self.rate_limiter.get_wait_time() + 1)
            
            # Mesajı gönder
            success = await self._send_promo_to_user(user, message_template)
            if success:
                sent_count += 1
                
            # Rate limiter'ı güncelle
            self.rate_limiter.mark_used()
            
        # Son gönderim zamanını kaydet
        await self._run_async_db_method(self.db.set_setting, 'last_promo_time', 
                                       datetime.now().isoformat())
        
        logger.info(f"Tanıtım mesajı gönderimi tamamlandı: {sent_count}/{len(users)}")
        return sent_count

    async def _update_user_interaction_profile(self, user_id, message_text):
        """
        Kullanıcı etkileşim profilini günceller
        """
        try:
            if hasattr(self.db, 'update_user_interaction'):
                # BURADA DÜZELTME YAPILDI: await kullanıldığından emin olma
                await self._run_async_db_method(
                    self.db.update_user_interaction,
                    user_id,
                    datetime.now(),
                    len(message_text) if message_text else 0
                )
        except Exception as e:
            logger.error(f"Kullanıcı etkileşim profili güncelleme hatası: {str(e)}")

    async def _send_personalized_message(self, event, user_id):
        """
        Kullanıcıya özel mesaj gönderir
        """
        try:
            # Kişiselleştirilmiş mesaj oluştur
            message = self.user_profiler.get_personalized_message(user_id, 'greeting')
            
            # Mesajı gönder
            await event.reply(message)
            
            return True
        except Exception as e:
            logger.error(f"Kişiselleştirilmiş mesaj gönderilirken hata: {str(e)}")
            return False

    async def get_safe_entity(self, user_id, username=None):
        """Kullanıcı entity'sini güvenli şekilde almaya çalışır."""
        try:
            # Önce user_service'i kullanarak dene
            if 'user' in self.services and hasattr(self.services['user'], 'get_safe_entity'):
                entity = await self.services['user'].get_safe_entity(user_id, username)
                if entity:
                    return entity
                    
            # User service yoksa veya çalışmazsa, kendi yöntemini dene
            try:
                return await self.client.get_entity(user_id)
            except ValueError:
                if username:
                    try:
                        return await self.client.get_entity(f"@{username}")
                    except:
                        pass
            return None
            
        except Exception as e:
            logger.error(f"Entity güvenli alma hatası: {str(e)}")
            return None

    async def run(self):
        """DM servisi için ana döngü."""
        logger.info("DM servisi çalışıyor...")
        while self.running and not self.stop_event.is_set():
            try:
                # Periyodik işlemler burada yapılabilir
                await asyncio.sleep(1)  # CPU kullanımını azaltmak için
            except asyncio.CancelledError:
                logger.info("DM servis döngüsü iptal edildi")
                break
            except Exception as e:
                logger.error(f"DM servisi çalışırken hata: {str(e)}")
        
        logger.info("DM servis döngüsü sonlandı")

    async def get_invite_count(self, period="day"):
        """
        Belirli bir zaman diliminde gönderilen davet sayısını getirir.
        
        Args:
            period: Zaman dilimi ('day', 'week', 'month', 'all')
            
        Returns:
            int: Davet sayısı
        """
        try:
            count = 0
            now = datetime.now()
            
            # Veritabanından almaya çalış
            if hasattr(self.db, 'get_invite_count'):
                try:
                    count = await self._run_async_db_method(self.db.get_invite_count, period)
                    return count
                except Exception as e:
                    logger.error(f"Veritabanından davet sayısı alınamadı: {str(e)}")
            
            # Memory istatistiklerinden hesapla
            if hasattr(self, 'invite_stats'):
                if period == "day":
                    return self.invite_stats.get('daily_sent', 0)
                elif period == "all":
                    return self.invite_stats.get('total_sent', 0)
                    
            # Fallback - servislerden sorgula
            if hasattr(self, 'services') and 'invite' in self.services:
                invite_stats = await self.services['invite'].get_statistics()
                if period == "day":
                    return invite_stats.get('daily_sent', 0)
                elif period == "all":
                    return invite_stats.get('total_sent', 0)
                    
            return count
        except Exception as e:
            logger.error(f"Davet sayısı alma hatası: {str(e)}")
            return 0

    # TDLib yardımcı fonksiyonları
    async def tdlib_get_chats(self, limit=100):
        """TDLib ile mevcut sohbetleri alır"""
        if not self.use_tdlib:
            return []
            
        try:
            self.tdlib_send({
                '@type': 'getChats',
                'limit': limit
            })
            
            # Yanıtı bekle
            start_time = time.time()
            timeout = 5.0
            
            while time.time() - start_time < timeout:
                result = self.tdlib_receive(0.1)
                if not result:
                    await asyncio.sleep(0.1)
                    continue
                    
                if result.get('@type') == 'chats':
                    chat_ids = result.get('chat_ids', [])
                    chats = []
                    
                    for chat_id in chat_ids:
                        chat_info = await self.tdlib_get_chat_info(chat_id)
                        if chat_info:
                            chats.append(chat_info)
                            
                    return chats
                    
            return []
            
        except Exception as e:
            logger.error(f"TDLib sohbetleri alırken hata: {str(e)}")
            return []

    async def tdlib_get_chat_info(self, chat_id):
        """TDLib ile sohbet bilgilerini alır"""
        if not self.use_tdlib:
            return None
            
        try:
            self.tdlib_send({
                '@type': 'getChat',
                'chat_id': chat_id
            })
            
            # Yanıtı bekle
            start_time = time.time()
            timeout = 5.0
            
            while time.time() - start_time < timeout:
                result = self.tdlib_receive(0.1)
                if not result:
                    await asyncio.sleep(0.1)
                    continue
                    
                if result.get('@type') == 'chat':
                    return {
                        'id': result.get('id'),
                        'type': result.get('type', {}).get('@type'),
                        'title': result.get('title'),
                        'is_group': result.get('type', {}).get('@type') in ('chatTypeSupergroup', 'chatTypeBasicGroup'),
                        'member_count': result.get('member_count', 0)
                    }
                    
            return None
            
        except Exception as e:
            logger.error(f"TDLib sohbet bilgilerini alırken hata: {str(e)}")
            return None

    async def tdlib_send_message(self, chat_id, text):
        """TDLib ile mesaj gönderir"""
        if not self.use_tdlib:
            return False
            
        try:
            self.tdlib_send({
                '@type': 'sendMessage',
                'chat_id': chat_id,
                'input_message_content': {
                    '@type': 'inputMessageText',
                    'text': {
                        '@type': 'formattedText',
                        'text': text
                    }
                }
            })
            
            # Başarıdan emin olmak için bir sonuç beklemek daha doğru olur
            # ama basitlik için sadece gönderimi işaretliyoruz
            return True
            
        except Exception as e:
            logger.error(f"TDLib mesaj gönderirken hata: {str(e)}")
            return False

    async def test_templates(self):
        """Şablonların doğru yüklendiğini kontrol eder"""
        logger.info("=== ŞABLON DURUMU ===")
        logger.info(f"- Davet şablonları: {len(getattr(self, 'invite_templates', []))}")
        logger.info(f"- Yönlendirme şablonları: {len(getattr(self, 'redirect_templates', []))}")
        logger.info(f"- Flirty şablonları: {len(getattr(self, 'flirty_templates', []))}")
        logger.info(f"- Grup mesaj şablonları: {len(getattr(self, 'group_message_templates', []))}")
        
        # Örnek şablonlar
        if self.invite_templates:
            logger.info(f"Davet örneği: {self.invite_templates[0]}")
        if self.redirect_templates:
            logger.info(f"Yönlendirme örneği: {self.redirect_templates[0]}")
        if hasattr(self, 'flirty_templates') and self.flirty_templates:
            logger.info(f"Flirty örneği: {self.flirty_templates[0]}")
        
        return True

# Alias tanımlaması
DMService = DirectMessageService