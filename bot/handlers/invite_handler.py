"""
# ============================================================================ #
# Dosya: invite_handler.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/handlers/invite_handler.py
# İşlev: Telegram bot için davet yönetimi ve gönderimi.
#
# Amaç: Bu modül, Telegram botunun veritabanındaki bekleyen davetleri işler, 
# hedef kullanıcılara yapılandırılabilir mesajlar göndererek gruplara katılımı 
# teşvik eder. Rate limiting, hata yönetimi ve konfigüre edilebilir 
# parametrelerle davet süreçlerinin etkin kontrolünü sağlar.
#
# Temel Özellikler:
# - Bekleyen davetleri alma ve işleme
# - Akıllı rate limiting ve flood koruması
# - Kişiselleştirilmiş davet mesajları gönderme
# - Kapsamlı hata yönetimi ve raporlama
# - ServiceManager ile entegre yaşam döngüsü
# - İşlem istatistikleri ve durum takibi
#
# Build: 2025-04-08-23:45:00
# Versiyon: v3.5.0
# ============================================================================ #
#
# Değişiklik Geçmişi:
# v3.5.0 (2025-04-08) - ServiceManager ile uyumlu hale getirildi
#                      - Yaşam döngüsü metotları eklendi (initialize, start, stop, run)
#                      - Davet mesajı şablonları geliştirildi
#                      - Adaptif rate limiter entegrasyonu
#                      - Gelişmiş hata yakalama ve işleme mekanizmaları
#                      - İstatistik toplama ve durum raporlama eklendi
# v3.4.0 (2025-04-01) - İlk kapsamlı versiyon
# v3.3.0 (2025-03-15) - İlk sürüm
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import random
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union, Tuple

# Telethon kütüphaneleri
from telethon import errors

# Renkli konsol çıktıları için
from colorama import Fore, Style

# Proje içi modüller
from bot.utils.rate_limiter import RateLimiter
from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter

logger = logging.getLogger(__name__)

class InviteHandler:
    """
    Telegram bot için davet işleme ve yönetim sınıfı.
    
    Bu sınıf, bekleyen davetleri alır, işler ve hedef kullanıcılara mesajlar
    gönderir. ServiceManager ile uyumlu olarak çalışır ve bot'un diğer
    bileşenleriyle entegre olarak çalışabilir.
    
    Attributes:
        bot: Ana bot nesnesi
        client: Telethon istemcisi
        db: Veritabanı bağlantısı
        config: Yapılandırma nesnesi
        invite_limiter: Davet gönderim hız sınırlayıcı
        adaptive_limiter: Adaptif hız sınırlayıcı
        is_running: Servisin çalışıp çalışmadığını belirten bayrak
        is_paused: Servisin duraklatılmış olup olmadığını gösteren bayrak
        stop_event: Durdurma sinyali için kullanılan Event nesnesi
        message_templates: Davet mesajı şablonları
        stats: İstatistik verileri
    """
    
    def __init__(self, bot, stop_event=None):
        """
        InviteHandler sınıfını başlatır.
        
        Args:
            bot: Ana bot nesnesi
            stop_event: Durdurma sinyali için asyncio.Event nesnesi (opsiyonel)
        """
        self.bot = bot
        self.client = self.bot.client if hasattr(self.bot, 'client') else None
        self.db = self.bot.db if hasattr(self.bot, 'db') else None
        self.config = self.bot.config if hasattr(self.bot, 'config') else None
        
        # Durdurma ve kontrol mekanizmaları
        self.is_running = False
        self.is_paused = False
        self.stop_event = stop_event or asyncio.Event()
        
        # Rate limiter yapılandırması - çevre değişkenlerinden veya varsayılan değerlerden
        max_requests = int(os.environ.get('INVITE_MAX_REQUESTS', '5'))
        time_window = int(os.environ.get('INVITE_TIME_WINDOW', '300'))
        
        # Basit ve adaptif rate limiter'lar
        self.invite_limiter = RateLimiter(max_requests=max_requests, time_window=time_window)
        self.adaptive_limiter = AdaptiveRateLimiter(
            initial_rate=5,       # Dakikada 5 davet
            initial_period=60,    # 60 saniye periyot
            error_backoff=1.5,    # Hata durumunda 1.5x yavaşlama
            max_jitter=2.0        # Maksimum 2 saniyelik rastgele gecikme
        )
        
        # Davet mesaj şablonları
        self.message_templates = self._load_message_templates()
        
        # İstatistikler
        self.stats = {
            "invites_sent": 0,
            "invites_failed": 0,
            "last_successful_invite": None,
            "error_count": 0,
            "flood_wait_encountered": 0,
            "start_time": None
        }
        
        # Çalışma parametreleri
        self.batch_size = int(os.environ.get('INVITE_BATCH_SIZE', '5'))
        self.min_delay_seconds = int(os.environ.get('INVITE_MIN_DELAY', '3'))
        self.max_delay_seconds = int(os.environ.get('INVITE_MAX_DELAY', '10'))
        self.cooldown_minutes = int(os.environ.get('INVITE_COOLDOWN_MINUTES', '30'))
        
        logger.info("InviteHandler başlatıldı")
        
    async def initialize(self) -> bool:
        """
        Servisi başlatmak için gerekli hazırlıkları yapar.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Mesaj şablonlarını kontrol et
            if not self.message_templates:
                self.message_templates = self._load_message_templates()
            
            # Veritabanı bağlantısını kontrol et
            if not self.db:
                logger.error("Veritabanı bağlantısı bulunamadı")
                return False
                
            # İstatistikleri sıfırla
            self.stats["start_time"] = datetime.now()
            
            # Son davet istatistiklerini yükle
            if hasattr(self.db, 'get_invite_stats'):
                invite_stats = await self._run_async_db_method(self.db.get_invite_stats)
                if invite_stats:
                    self.stats["invites_sent"] = invite_stats.get('total_sent', 0)
            
            logger.info("InviteHandler başarıyla initialize edildi")
            return True
            
        except Exception as e:
            logger.error(f"InviteHandler initialize hatası: {str(e)}", exc_info=True)
            return False
            
    async def start(self) -> bool:
        """
        Servisin çalışmasını başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            self.is_running = True
            self.is_paused = False
            
            # Aktif rate limiter'ı başlat
            if hasattr(self.adaptive_limiter, 'reset'):
                self.adaptive_limiter.reset()
                
            logger.info("InviteHandler başarıyla başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"InviteHandler start hatası: {str(e)}")
            return False
            
    async def stop(self) -> None:
        """
        Servisi güvenli bir şekilde durdurur.
        """
        logger.info("InviteHandler durduruluyor...")
        self.is_running = False
        self.stop_event.set()
        logger.info("InviteHandler durduruldu")

    async def pause(self) -> None:
        """
        Servisi geçici olarak duraklatır.
        """
        if not self.is_paused:
            self.is_paused = True
            logger.info("InviteHandler duraklatıldı")

    async def resume(self) -> None:
        """
        Duraklatılmış servisi devam ettirir.
        """
        if self.is_paused:
            self.is_paused = False
            logger.info("InviteHandler devam ettiriliyor")
    
    async def run(self) -> None:
        """
        Ana servis döngüsü - periyodik olarak bekleyen davetleri işler.
        
        Bu metot, servis durdurulana kadar çalışır ve belirli aralıklarla
        bekleyen davetleri kontrol eder ve işler.
        """
        logger.info("InviteHandler ana döngüsü başlatıldı")
        
        try:
            while not self.stop_event.is_set() and self.is_running:
                if not self.is_paused:
                    try:
                        # Davet işleme
                        await self.process_invites()
                    except Exception as e:
                        self.stats["error_count"] += 1
                        logger.error(f"Davet işleme hatası: {str(e)}")
                        
                    # Bir sonraki kontrol için bekle
                    try:
                        await asyncio.wait_for(self.stop_event.wait(), timeout=30)
                    except asyncio.TimeoutError:
                        pass  # Normal timeout, devam et
                else:
                    # Duraklatılmış ise her 1 saniyede bir kontrol et
                    await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            logger.info("InviteHandler ana görevi iptal edildi")
        except Exception as e:
            logger.error(f"InviteHandler ana döngü hatası: {str(e)}", exc_info=True)
            
    async def process_invites(self) -> int:
        """
        Sistemdeki davetleri işler ve ilgili kullanıcılara davet mesajları gönderir.
        
        Returns:
            int: Başarıyla gönderilen davet sayısı
        """
        if not self.is_running or self.is_paused:
            return 0
            
        total_sent = 0
        
        try:
            # Kapatılma sinyali kontrol et
            if self.stop_event.is_set():
                return 0
                
            # Davet listesini al
            invites = await self._get_pending_invites()
            if not invites:
                return 0
                
            logger.info(f"📨 İşlenecek davet sayısı: {len(invites)}")
            
            # Her davet için işlem yap
            for invite in invites:
                # Kapatılma sinyali kontrol et
                if not self.is_running or self.is_paused or self.stop_event.is_set():
                    break
                
                # Rate limiter kontrolü
                wait_time = self.adaptive_limiter.get_wait_time()
                if (wait_time > 0):
                    logger.info(f"⏱️ Rate limit nedeniyle {wait_time:.1f} saniye bekleniyor")
                    await asyncio.sleep(wait_time)
                    
                # Davet işleme
                success = await self._process_invite(invite)
                if success:
                    total_sent += 1
                    self.stats["invites_sent"] += 1
                    self.stats["last_successful_invite"] = datetime.now()
                    logger.info(f"✅ Davet gönderildi: {self._get_user_display(invite)}")
                else:
                    self.stats["invites_failed"] += 1
                
                # Rate limiter'ı güncelle
                self.adaptive_limiter.mark_used()
                
                # Davetler arasında bekle - rastgele süre
                delay = random.randint(self.min_delay_seconds, self.max_delay_seconds)
                await self._interruptible_sleep(delay)
            
            return total_sent
            
        except errors.FloodWaitError as e:
            wait_seconds = e.seconds
            self.stats["flood_wait_encountered"] += 1
            
            # Rate limiter'ı güncelle
            self.adaptive_limiter.register_error(e)
            
            logger.warning(f"⚠️ FloodWaitError: {wait_seconds} saniye bekleniyor")
            await asyncio.sleep(wait_seconds)
            return total_sent
            
        except Exception as e:
            self.stats["error_count"] += 1
            logger.error(f"Davet işleme hatası: {str(e)}")
            await asyncio.sleep(10)  # Hata durumunda bekle
            return total_sent
    
    async def _get_pending_invites(self) -> List[Any]:
        """
        Bekleyen davetleri veritabanından alır.
        
        Returns:
            List[Any]: Davet edilecek kullanıcı listesi
        """
        try:
            # Veritabanında özel bir metot varsa kullan
            if hasattr(self.db, 'get_users_for_invite'):
                return await self._run_async_db_method(
                    self.db.get_users_for_invite, 
                    limit=self.batch_size, 
                    cooldown_minutes=self.cooldown_minutes
                ) or []
            
            # Genel kullanıcı alma metodu varsa kullan
            elif hasattr(self.db, 'get_users_to_invite'):
                return await self._run_async_db_method(
                    self.db.get_users_to_invite,
                    self.batch_size
                ) or []
                
            # UserService üzerinden erişim
            elif hasattr(self.bot, 'user_service') and hasattr(self.bot.user_service, 'get_users_to_invite'):
                return await self.bot.user_service.get_users_to_invite(
                    limit=self.batch_size,
                    cooldown_hours=self.cooldown_minutes / 60
                ) or []
                
            # Veritabanı metodu yoksa fallback olarak boş liste
            logger.warning("Davet edilecek kullanıcıları getirmek için bir metot bulunamadı")
            return []
            
        except Exception as e:
            logger.error(f"Bekleyen davetleri alma hatası: {str(e)}")
            return []
    
    async def _process_invite(self, invite: Any) -> bool:
        """
        Bir daveti işler ve kullanıcıya davet mesajı gönderir.
        
        Args:
            invite: Davet edilecek kullanıcı bilgileri
            
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            # Kullanıcı kimliğini ve adını çıkart - farklı formatları destekle
            user_id, username, first_name = self._extract_user_info(invite)
            
            if not user_id:
                logger.warning("Geçersiz davet verisi - kullanıcı ID'si eksik")
                return False
                
            # Davet mesajını kişiselleştir ve gönder
            invite_message = self._create_invite_message(first_name or "Kullanıcı")
            
            # Kullanıcıya mesaj göndermeyi dene
            await self._send_message_to_user(user_id, invite_message)
            
            # Veritabanında işaretle
            await self._mark_user_invited(user_id)
            
            # Başarıyı logla
            user_display = self._get_user_display(invite)
            logger.info(f"✅ Davet başarıyla gönderildi: {user_display}")
            
            return True
            
        except errors.FloodWaitError as e:
            # Flood hatası - yukarıda yakalanacak
            raise
            
        except errors.UserIsBlockedError:
            # Kullanıcı botu engellemiş
            user_display = self._get_user_display(invite)
            logger.debug(f"Kullanıcı botu engellemiş: {user_display}")
            
            # Veritabanında işaretle
            if hasattr(self.db, 'mark_user_blocked'):
                await self._run_async_db_method(self.db.mark_user_blocked, self._get_user_id(invite))
                
            return False
            
        except (errors.UserIdInvalidError, errors.PeerIdInvalidError):
            # Geçersiz kullanıcı ID'si
            user_display = self._get_user_display(invite)
            logger.debug(f"Geçersiz kullanıcı ID'si: {user_display}")
            return False
            
        except Exception as e:
            self.stats["error_count"] += 1
            user_display = self._get_user_display(invite)
            logger.error(f"Davet işleme hatası: {user_display} - {str(e)}")
            return False
    
    def _create_invite_message(self, name: str = "Kullanıcı") -> str:
        """
        Kişiselleştirilmiş davet mesajı oluşturur.
        
        Args:
            name: Kullanıcının adı
            
        Returns:
            str: Oluşturulan davet mesajı
        """
        try:
            if hasattr(self.bot, '_create_invite_message'):
                return self.bot._create_invite_message(name)
                
            # Rastgele şablon seç
            template = random.choice(self.message_templates)
            
            # Gruplar listesini oluştur
            groups = ""
            target_groups = []
            if hasattr(self.config, 'TARGET_GROUPS'):
                target_groups = self.config.TARGET_GROUPS
            elif hasattr(self.bot, 'config') and hasattr(self.bot.config, 'TARGET_GROUPS'):
                target_groups = self.bot.config.TARGET_GROUPS
                
            if target_groups:
                groups = "\n".join([f"👉 {group}" for group in target_groups])
            
            # Super users bilgisi
            super_users = []
            if hasattr(self.config, 'SUPER_USERS'):
                super_users = self.config.SUPER_USERS
            elif hasattr(self.bot, 'config') and hasattr(self.bot.config, 'SUPER_USERS'):
                super_users = self.bot.config.SUPER_USERS
                
            footer = ""
            if super_users and super_users[0]:
                footer = f"\n\nℹ️ Bilgi ve menü için: @{super_users[0]}"
            
            # Mesajda isim değişkenini değiştir
            message = template.replace("{name}", name)
            
            # Grup bilgisini ekle
            full_message = f"{message}\n\n{groups}{footer}"
            
            return full_message
            
        except Exception as e:
            logger.error(f"Davet mesajı oluşturma hatası: {str(e)}")
            return f"Merhaba {name}! Telegram gruplarımıza katılabilirsiniz."
    
    def _load_message_templates(self) -> List[str]:
        """
        Davet mesajı şablonlarını yükler.
        
        Returns:
            List[str]: Davet şablonları listesi
        """
        try:
            # Şablon dosyası kontrolü 
            template_paths = [
                "data/invites.json",
                "data/invite_templates.json",
                "data/templates/invite_messages.json",
                "config/templates.json"
            ]
            
            import json
            for path in template_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            if "invite_templates" in data:
                                templates = data["invite_templates"]
                                if templates:
                                    logger.info(f"{len(templates)} davet şablonu {path} dosyasından yüklendi")
                                    return templates
                            elif "invites" in data:
                                templates = data["invites"]
                                if templates:
                                    logger.info(f"{len(templates)} davet şablonu {path} dosyasından yüklendi")
                                    return templates
                            elif "first_invite" in data:
                                templates = data["first_invite"]
                                if templates:
                                    logger.info(f"{len(templates)} davet şablonu {path} dosyasından yüklendi")
                                    return templates
                        elif isinstance(data, list):
                            if data:
                                logger.info(f"{len(data)} davet şablonu {path} dosyasından yüklendi")
                                return data
                                
            # Bottan şablonları almayı dene
            if hasattr(self.bot, 'invite_templates'):
                return self.bot.invite_templates
                
        except Exception as e:
            logger.error(f"Davet şablonları yüklenemedi: {str(e)}")
        
        # Varsayılan davet şablonları
        default_templates = [
            "Merhaba {name}! Grubuma katılmak ister misin?",
            "Selam {name}! Telegram gruplarımıza bekliyoruz!",
            "Merhaba, sohbet gruplarımıza göz atmak ister misin?",
            "Selam {name}! Gruplarımıza davetlisin!",
            "Merhaba, yeni sohbet arkadaşları arıyorsan gruplarımıza bekleriz."
        ]
        logger.info(f"{len(default_templates)} varsayılan davet şablonu kullanılıyor")
        return default_templates
    
    async def _send_message_to_user(self, user_id: int, message: str) -> None:
        """
        Kullanıcıya doğrudan mesaj gönderir.
        
        Args:
            user_id: Mesaj gönderilecek kullanıcı ID'si
            message: Gönderilecek mesaj
            
        Raises:
            FloodWaitError: Telegram hız sınırı hatası
        """
        await self.client.send_message(
            user_id,
            message,
            link_preview=False
        )
    
    async def _mark_user_invited(self, user_id: int) -> bool:
        """
        Kullanıcının davet edildiğini veritabanında işaretler.
        
        Args:
            user_id: Davet edilen kullanıcı ID'si
            
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            # UserService üzerinden
            if hasattr(self.bot, 'user_service') and hasattr(self.bot.user_service, 'mark_user_invited'):
                return await self.bot.user_service.mark_user_invited(user_id)
                
            # Veritabanı üzerinden
            if hasattr(self.db, 'mark_as_invited'):
                return await self._run_async_db_method(self.db.mark_as_invited, user_id)
            elif hasattr(self.db, 'mark_user_invited'):
                return await self._run_async_db_method(self.db.mark_user_invited, user_id)
            elif hasattr(self.db, 'update_last_invited'):
                return await self._run_async_db_method(self.db.update_last_invited, user_id)
                
            logger.warning(f"Kullanıcı davet işaretlemek için metot bulunamadı: {user_id}")
            return False
            
        except Exception as e:
            logger.error(f"Kullanıcı davet işaretleme hatası: {str(e)}")
            return False
    
    #
    # YARDIMCI METODLAR
    #
    
    def _extract_user_info(self, invite: Any) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        """
        Davet nesnesinden kullanıcı bilgilerini çıkarır.
        
        Args:
            invite: Davet bilgileri içeren nesne
            
        Returns:
            Tuple[Optional[int], Optional[str], Optional[str]]: 
                Kullanıcı ID'si, kullanıcı adı ve ilk ad
        """
        # Farklı veri formatlarını destekle
        
        # 1. Dict formatı
        if isinstance(invite, dict):
            user_id = invite.get('user_id')
            username = invite.get('username')
            first_name = invite.get('first_name', 'Kullanıcı')
            return user_id, username, first_name
            
        # 2. Tuple formatı (user_id, username)
        elif isinstance(invite, tuple) and len(invite) >= 2:
            user_id = invite[0]
            username = invite[1]
            first_name = invite[2] if len(invite) > 2 else 'Kullanıcı'
            return user_id, username, first_name
            
        # 3. Nesne formatı
        elif hasattr(invite, 'user_id'):
            user_id = invite.user_id
            username = getattr(invite, 'username', None)
            first_name = getattr(invite, 'first_name', 'Kullanıcı')
            return user_id, username, first_name
            
        # 4. Doğrudan ID (int veya str)
        elif isinstance(invite, (int, str)):
            return int(invite) if str(invite).isdigit() else None, None, 'Kullanıcı'
        
        # Desteklenmeyen format
        logger.warning(f"Desteklenmeyen davet veri formatı: {type(invite)}")
        return None, None, None
    
    def _get_user_id(self, invite: Any) -> Optional[int]:
        """
        Davet nesnesinden kullanıcı ID'sini çıkarır.
        
        Args:
            invite: Davet bilgileri içeren nesne
            
        Returns:
            Optional[int]: Kullanıcı ID'si veya None
        """
        user_id, _, _ = self._extract_user_info(invite)
        return user_id
        
    def _get_user_display(self, invite: Any) -> str:
        """
        Davet nesnesiyle ilişkili kullanıcı için görüntü adı oluşturur.
        
        Args:
            invite: Davet bilgileri içeren nesne
            
        Returns:
            str: Kullanıcı görüntü adı
        """
        user_id, username, first_name = self._extract_user_info(invite)
        
        if username:
            return f"@{username}"
        elif first_name and first_name != "Kullanıcı":
            return f"{first_name} ({user_id})"
        else:
            return f"ID:{user_id}"
            
    async def _interruptible_sleep(self, seconds: int) -> None:
        """
        Durdurulabilir bekleme yapar.
        
        Args:
            seconds: Beklenecek saniye sayısı
        """
        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass  # Bekleme süresi doldu, normal davranış
            
    async def _run_async_db_method(self, method: Any, *args, **kwargs) -> Any:
        """
        Veritabanı metodunu asenkron olup olmadığını kontrol ederek çağırır.
        
        Args:
            method: Çağrılacak metod
            *args: Metoda geçirilecek pozisyonel argümanlar
            **kwargs: Metoda geçirilecek anahtar kelime argümanları
            
        Returns:
            Any: Metodun dönüş değeri
        """
        # Asenkron metod mu kontrol et
        if asyncio.iscoroutinefunction(method):
            return await method(*args, **kwargs)
        else:
            return method(*args, **kwargs)
            
    def get_status(self) -> Dict[str, Any]:
        """
        Servisin durumunu döndürür.
        
        Returns:
            Dict[str, Any]: Servis durum bilgileri
        """
        return {
            "running": self.is_running,
            "paused": self.is_paused,
            "invites_sent": self.stats["invites_sent"],
            "invites_failed": self.stats["invites_failed"],
            "error_count": self.stats["error_count"],
            "last_invite": self.stats["last_successful_invite"].strftime("%H:%M:%S") if self.stats["last_successful_invite"] else "Hiç"
        }
        
    def get_statistics(self) -> Dict[str, Any]:
        """
        Servis istatistiklerini döndürür.
        
        Returns:
            Dict[str, Any]: İstatistik bilgileri
        """
        uptime_seconds = (datetime.now() - self.stats["start_time"]).total_seconds() if self.stats["start_time"] else 0
        
        return {
            "running": self.is_running,
            "paused": self.is_paused,
            "start_time": self.stats["start_time"].strftime("%Y-%m-%d %H:%M:%S") if self.stats["start_time"] else None,
            "uptime_hours": uptime_seconds / 3600,
            "invites_sent": self.stats["invites_sent"],
            "invites_failed": self.stats["invites_failed"],
            "error_count": self.stats["error_count"],
            "flood_wait_encountered": self.stats["flood_wait_encountered"],
            "last_successful_invite": self.stats["last_successful_invite"].strftime("%Y-%m-%d %H:%M:%S") if self.stats["last_successful_invite"] else None,
            "current_rate": self.adaptive_limiter.current_rate if hasattr(self.adaptive_limiter, 'current_rate') else None,
            "templates_count": len(self.message_templates)
        }