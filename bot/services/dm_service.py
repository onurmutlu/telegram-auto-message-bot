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
#
# Değişiklik Geçmişi:
# v3.5.0 (2025-04-07) - was_recently_invited için timestamp kontrolü düzeltildi
#                      - Güçlendirilmiş hata yönetimi ve loglama eklendi
#                      - AdaptiveRateLimiter efektif kullanımı optimize edildi
#                      - _process_user() sınıf içine entegre edildi
# v3.4.2 (2025-03-25) - Çift mesaj gönderimini önleyici kontroller eklendi
# v3.4.0 (2025-03-10) - Otomatik grup keşfi iyileştirildi
# v3.3.0 (2025-02-15) - Gelişmiş hız sınırlama mekanizması eklendi
#
# Geliştirici Notları:
#   - Rate limiter'ı daha agresif ayarlayarak günlük mesaj sınırlamasına dikkat edin
#   - Grup keşfi ve mesaj gönderimi için ideal saat aralığı: 10:00-22:00
#   - .env dosyasında DM_FOOTER_MESSAGE ve DM_RESPONSE_TEMPLATE değişkenleri yapılandırılabilir
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""
import os
import sys
import json
import logging
import random
import asyncio
from colorama import Fore, Style, init
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple, TYPE_CHECKING, Union
from pathlib import Path

from telethon import errors
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

# Colorama başlatma
init(autoreset=True)

# Logger yapılandırması
logger = logging.getLogger(__name__)


class DirectMessageService(BaseService):
    """
    Telegram bot için direkt mesaj yönetim servisi.
    
    Başlıca işlevleri:
    - Gelen özel mesajları işleme ve yanıtlama
    - Kullanıcılara otomatik davet mesajları gönderme
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
        """
        DirectMessageService sınıfını başlatır.
        
        Args:
            client: Telegram istemcisi
            config: Bot yapılandırma nesnesi
            db: Veritabanı nesnesi
            stop_event (optional): Servis durdurma sinyali
        """
        # Temel bileşenler
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = stop_event if stop_event else asyncio.Event()
        
        # Durum takibi
        self.running = True
        self.processed_dms = 0
        self.invites_sent = 0
        self.last_activity = datetime.now()
        
        # Kullanıcı yanıt takibi - bu oturum için
        self.responded_users: Set[int] = set()
        
        # Ayarları yükleme
        self._load_settings()
        
        # Rate limiter başlat
        self._setup_rate_limiter()
        
        # Mesaj şablonları
        self._load_templates()
        
        # Error Groups takibi
        self.error_groups = set()
        
        logger.info("DM servisi başlatıldı")
    
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
        self.super_users: List[str] = [s.strip() for s in os.getenv("SUPER_USERS", "").split(',') 
                                      if s and s.strip()]
        
        # Grup linkleri
        self.group_links: List[str] = self._parse_group_links()
        logger.info(f"Loaded {len(self.group_links)} group links.")
        
        # Debug modu
        self.debug = os.getenv("DEBUG", "false").lower() == "true"

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

    #
    # DURUM YÖNETİMİ
    #
    
    def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndürür.
        
        Returns:
            Dict: Servis durum bilgisi
        """
        rate_limiter_status = {}
        if hasattr(self.rate_limiter, 'get_status'):
            rate_limiter_status = self.rate_limiter.get_status()  # Bu satır eksikti

        return {
            'running': self.running,
            'processed_dms': self.processed_dms,
            'invites_sent': self.invites_sent,
            'last_activity': self.last_activity.strftime("%Y-%m-%d %H:%M:%S"),
            'rate_limiter': rate_limiter_status,
            'recent_users_count': len(self.responded_users),
            'cooldown_minutes': self.invite_cooldown_minutes
        }
    
    def resume(self) -> bool:
        if not self.running:
            self.running = True
            logger.info("DM servisi aktif edildi")
            return True
        return False
    
    def pause(self) -> bool:
        if self.running:
            self.running = False
            logger.info("DM servisi duraklatıldı")
            return True
        return False
    
    def debug_links(self) -> None:
        """Grup linklerini ve mesaj şablonlarını debug amaçlı gösterir."""
        print("\n===== DM SERVİSİ BAĞLANTI KONTROLÜ =====")
        
        # Linkleri göster
        links = self._parse_group_links()
        print(f"\nHam grup linkleri ({len(links)}):")
        for i, link in enumerate(links):
            print(f"  {i+1}. {link}")
        
        # Formatlı linkleri göster
        formatted_links = self._get_formatted_group_links()
        print(f"\nFormatlı grup linkleri ({len(formatted_links)}):")
        for i, link in enumerate(formatted_links):
            print(f"  {i+1}. {link}")
        
        # Örnek mesajı göster
        print("\nÖrnek davet mesajı:")
        invite_template = self._choose_invite_template()
        group_links_str = "\n\nGruplarımız:\n" + "\n".join([f"• {link}" for link in formatted_links]) if formatted_links else "Üzgünüm, şu anda aktif grup linki bulunmamaktadır."
        super_users_str = ""
        if self.super_users:
            valid_super_users = [f"• @{su}" for su in self.super_users if su]
            if valid_super_users:
                 super_users_str = "\n\nADMIN onaylı arkadaşlarıma menü için yazabilirsin:\n" + "\n".join(valid_super_users)
        
        full_message = f"{invite_template}{group_links_str}{super_users_str}"
        print(f"\n{full_message}\n")
        print("=======================================")
    
    def _get_invite_stats(self) -> Dict[str, int]:
        """
        Davet istatistiklerini alır.
        
        Returns:
            Dict[str, int]: Günlük, haftalık ve aylık davet sayıları
        """
        try:
            today = 0
            week = 0
            month = 0
            
            # Metot mevcutsa çağır
            if hasattr(self.db, 'get_invite_count'):
                today = self.db.get_invite_count(1)
                week = self.db.get_invite_count(7)
                month = self.db.get_invite_count(30)
            else:
                logger.error("Davet durumu kontrol edilemedi - 'get_invite_count' metodu yok.")
                
            return {
                'today': today,
                'week': week,
                'month': month
            }
        except Exception as e:
            logger.error(f"Davet istatistikleri alınırken hata: {str(e)}")
            return {'today': 0, 'week': 0, 'month': 0}

    #
    # MESAJ ŞABLONLARI VE FORMATLAMALAR
    #
    
    def _parse_group_links(self) -> List[str]:
        """
        Grup bağlantılarını çevre değişkenlerinden veya yapılandırmadan ayrıştırır.
        
        Returns:
            List[str]: Grup linkleri listesi
        """
        env_links = os.environ.get("GROUP_LINKS", "")
        admin_links = os.environ.get("ADMIN_GROUPS", "")
        logger.debug(f"Çevre değişkeninden okunan GROUP_LINKS: '{env_links}'")
        logger.debug(f"Çevre değişkeninden okunan ADMIN_GROUPS: '{admin_links}'")
        links_str = env_links if env_links else admin_links
        
        if links_str:
            links = [link.strip() for link in links_str.split(",") if link.strip()]
            logger.debug(f"Çevre değişkenlerinden {len(links)} link bulundu")
            return links
        
        # Config'den al
        group_links_config = self.config.get_setting('group_links', [])
        admin_groups_config = self.config.get_setting('admin_groups', [])
        
        if group_links_config:
             logger.debug(f"config'den {len(group_links_config)} GROUP_LINKS bulundu")
             return group_links_config
        elif admin_groups_config:
             logger.debug(f"config'den {len(admin_groups_config)} ADMIN_GROUPS bulundu")
             return admin_groups_config

        logger.warning("⚠️ Hiçbir yerde grup linki bulunamadı!")
        default_links = ["https://t.me/omegleme", "https://t.me/sosyalcip", "https://t.me/sohbet"]
        logger.info(f"Varsayılan {len(default_links)} link kullanılıyor")
        return default_links

    def _get_formatted_group_links(self) -> List[str]:
        """
        Grup linklerini isimlerle birlikte formatlayan metot.
        
        Returns:
            List[str]: Formatlı grup linkleri
        """
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
            else:
                if "t.me/" in clean_link:
                    # t.me linklerinden grup adını çıkar
                    parts = clean_link.split("/")
                    group_name = parts[-1] if len(parts) > 1 else "Grup"
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
                formatted_link = f"@{clean_link}"
                
            # Sonuç formatlama
            formatted_links.append(f"{display_name}: {formatted_link}")
                
        return formatted_links

    def _load_templates(self) -> None:
        """Mesaj şablonlarını yükler."""
        try:
            base_dir = Path(__file__).resolve().parent.parent.parent 
            data_dir = base_dir / "data"
            invites_path = data_dir / "invites.json"
            responses_path = data_dir / "responses.json"
            
            logger.info(f"Şablon dosyaları: {invites_path}, {responses_path}")
            
            # Varsayılan şablonlar
            self.invite_templates = [
                "Merhaba! Grubuma katılmak ister misin?",
                "Selam! Telegram gruplarımıza bekliyoruz!"
            ]
            self.redirect_templates = [
                "Merhaba! Sizi zaten davet etmiştik. İşte gruplarımız:"
            ]
            self.flirty_messages = [
                "Selam! Nasılsın?",
                "Merhaba! Bugün nasıl geçiyor?"
            ]
            
            # Davet mesajlarını yükle
            if os.path.exists(str(invites_path)):
                with open(invites_path, 'r', encoding='utf-8') as f:
                    invites_data = json.load(f)
                    if isinstance(invites_data, list):
                        self.invite_templates = invites_data
                    elif isinstance(invites_data, dict) and 'invites' in invites_data:
                        self.invite_templates = invites_data['invites']
                    else:
                        logger.warning("Geçersiz davet şablonu formatı, varsayılanlar kullanılıyor")
            
            # Yanıt mesajlarını yükle
            if os.path.exists(str(responses_path)):
                with open(responses_path, 'r', encoding='utf-8') as f:
                    responses_data = json.load(f)
                    if isinstance(responses_data, dict):
                        if 'redirects' in responses_data:
                            self.redirect_templates = responses_data['redirects']
                        if 'flirty' in responses_data:
                            self.flirty_messages = responses_data['flirty']
            
            logger.info(f"Yüklenen şablonlar: {len(self.invite_templates)} davet, "
                       f"{len(self.redirect_templates)} yönlendirme, "
                       f"{len(self.flirty_messages)} flirty")
                
        except Exception as e:
            logger.error(f"Şablonlar yüklenirken hata: {str(e)}", exc_info=True)
    
    def _load_json_data(self, file_path: str, key: str = None, 
                       default: Any = None, config_attr: str = None) -> Any:
        """
        JSON dosyasından veri yükler veya varsayılan değerleri döndürür.
        
        Args:
            file_path: JSON dosya yolu
            key: JSON içindeki anahtar (opsiyonel)
            default: Varsayılan değer (opsiyonel)
            config_attr: Config nesnesi üzerindeki özellik adı (opsiyonel)
            
        Returns:
            Any: Yüklenen veri veya varsayılan değer
        """
        if config_attr and hasattr(self.config, config_attr):
            config_value = getattr(self.config, config_attr)
            if config_value:
                return config_value
        
        result = default or []
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if key and key in data:
                        result = data[key]
                    else:
                        result = data
            except Exception as e:
                logger.warning(f"{file_path} dosyası yüklenemedi: {str(e)}")
        
        return result
    
    def _choose_invite_template(self) -> str:
        """
        Rastgele bir davet şablonu seçer.
        
        Returns:
            str: Seçilen davet mesajı
        """
        templates = getattr(self, 'invite_templates', None)
        if not templates:
            return "Merhaba! Grubumuza katılmak ister misin?"
        if isinstance(templates, dict):
            return random.choice(list(templates.values())) if templates else "Merhaba! Grubumuza katılmak ister misin?"
        return random.choice(templates) if templates else "Merhaba! Grubumuza katılmak ister misin?"

    def _choose_flirty_message(self) -> str:
        """
        Rastgele bir flirty mesaj seçer.
        
        Returns:
            str: Seçilen flirty mesaj
        """
        templates = getattr(self, 'flirty_messages', None)
        if not templates:
             return "Selam! Nasılsın?"
        return random.choice(templates) if templates else "Selam! Nasılsın?"

    #
    # ANA SERVİS DÖNGÜSÜ
    #
    
    async def run(self) -> None:
        """Ana servis döngü - Periyodik görevler için."""
        logger.info("DirectMessageService ana döngü başlatıldı")
        
        try:
            # Ana döngü - sadece periyodik istatistik loglama
            while not self.stop_event.is_set():
                if not self.running:
                    await asyncio.sleep(60)  # Duraklatılmışsa bekle
                    continue

                # Periyodik istatistik loglaması
                now = datetime.now()
                last_log_time = getattr(self, '_last_log_time', now - timedelta(hours=1))
                if (now - last_log_time).total_seconds() > 1800:
                    self._last_log_time = now
                    invite_stats = self._get_invite_stats()
                    logger.info(f"DM servisi durum: İşlenen DM={self.processed_dms}, " +
                               f"Gönderilen davet={self.invites_sent}, " +
                               f"Bugün={invite_stats['today']}, Hafta={invite_stats['week']}")
                
                await asyncio.sleep(60)
        
        except asyncio.CancelledError:
            logger.info("DM servis görevi (run) iptal edildi")
        except Exception as e:
            logger.error(f"DM servis (run) hatası: {str(e)}", exc_info=True)

    #
    # MESAJ İŞLEME
    #
    
    async def process_message(self, event) -> None:
        """
        Gelen özel mesajı işler ve yanıt verir.
        
        Args:
            event: Telegram mesaj olayı
        """
        self.processed_dms += 1
        sender = None
        try:
            sender = await event.get_sender()
            if not sender or sender.bot:
                 return # Bot mesajlarını ve geçersiz gönderenleri yoksay

            user_id = sender.id
            username = getattr(sender, 'username', None)
            first_name = getattr(sender, 'first_name', "")
            
            user_info = f"@{username}" if username else f"ID:{user_id}"
            logger.info(f"📨 DM alındı: {user_info} - {event.text[:50]}...")
            
            # Rate limiting kontrolü
            wait_time = self.rate_limiter.get_wait_time()
            if (wait_time > 0):
                logger.warning(f"Rate limit aşıldı, {wait_time:.1f}s bekleniyor: {user_info}")
                await asyncio.sleep(wait_time)
                if (self.rate_limiter.get_wait_time() > 0):
                     logger.warning("Bekleme sonrası hala hız sınırı aktif, mesaj işlenemiyor.")
                     return
            
            # Kullanıcıyı veritabanına ekle/güncelle
            user_data = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': getattr(sender, 'last_name', ""),
                'is_bot': False
            }
            if hasattr(self.db, 'add_or_update_user'):
                self.db.add_or_update_user(user_data)
            else:
                logger.error("Veritabanı nesnesinde 'add_or_update_user' metodu bulunamadı.")

            # Kullanıcının daha önce davet edilip edilmediğini kontrol et
            has_been_invited = self._check_user_invited(user_id)

            # Eğer mesaj bir soru veya sohbet başlatma amaçlıysa yönlendirici bir yanıt ver
            message_text = event.text.lower() if event.text else ""
            if self._is_conversation_starter(message_text):
                await self._send_conversation_response(event)
                return

            # Kullanıcının davet edilip edilmediğine göre farklı mesajlar gönder
            if has_been_invited:
                await self._send_redirect_message(event)
            else:
                invite_sent = await self._send_invite_message(event)
                if invite_sent:
                    self._mark_user_invited(user_id)
                    logger.info(f"✅ Davet yanıtı gönderildi ve kaydedildi: {user_info}")
                else:
                    logger.warning(f"Davet mesajı gönderilemedi: {user_info}")
            
            # Rate limiter'ı güncelle ve son aktivite zamanını kaydet
            self.rate_limiter.mark_used()
            self.last_activity = datetime.now()
            
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"FloodWaitError DM işlerken: {wait_time} saniye bekleniyor")
            self.rate_limiter.register_error(e)
            await asyncio.sleep(wait_time + 1)
        except Exception as e:
            logger.error(f"DM işleme hatası: {str(e)}", exc_info=True)
            if not isinstance(e, (errors.UserPrivacyRestrictedError, errors.UserNotMutualContactError)):
                self.rate_limiter.register_error(e)
    
    def _is_conversation_starter(self, message_text: str) -> bool:
        """
        Mesajın bir sohbet başlatıcı olup olmadığını kontrol eder.
        
        Args:
            message_text: Kontrol edilecek mesaj
            
        Returns:
            bool: Sohbet başlatıcı ise True
        """
        if not message_text or len(message_text) < 3:
            return False
            
        # Soru işaretleri ve anahtar kelimeler
        return ('?' in message_text or 
                any(word in message_text for word in [
                    'merhaba', 'selam', 'nasıl', 'naber', 'hello', 'hi', 'hey'
                ]))
    
    async def _send_conversation_response(self, event) -> None:
        """
        Sohbet başlatan kullanıcıya yanıt verir.
        
        Args:
            event: Telegram mesaj olayı
        """
        try:
            # .env'den yönlendirme mesajını çek
            dm_response_template = os.environ.get(
                "DM_RESPONSE_TEMPLATE", 
                "Merhaba! Şu anda yoğunum, lütfen arkadaşlarımdan birine yazarak destek alabilirsin:"
            )
            
            # Super user listesi ve footer
            super_users_text = ""
            if self.super_users:
                valid_super_users = [f"• @{su}" for su in self.super_users if su]
                if valid_super_users:
                    super_users_text = f"\n\n{self.dm_footer_message}\n" + "\n".join(valid_super_users)
                    
            await event.respond(f"{dm_response_template}{super_users_text}")
            self.rate_limiter.mark_used()
        except Exception as e:
            logger.error(f"Konuşma yanıtı gönderirken hata: {str(e)}", exc_info=True)
    
    def _check_user_invited(self, user_id: int) -> bool:
        """
        Kullanıcının daha önce davet edilip edilmediğini kontrol eder.
        
        Args:
            user_id: Kontrol edilecek kullanıcı ID'si
            
        Returns:
            bool: Kullanıcı daha önce davet edildi ise True
        """
        try:
            # Veritabanındaki davet sayısı kontrol metodu varsa kullan
            if hasattr(self.db, 'get_invite_count'):
                invite_count = self.db.get_invite_count(user_id)
                return bool(invite_count and invite_count > 0)
            
            # Alternatif olarak was_recently_invited metodunu kontrol et
            if hasattr(self.db, 'was_recently_invited'):
                return self.db.was_recently_invited(user_id, self.invite_cooldown_minutes)
            elif hasattr(self.db, 'check_recently_invited'):
                return self.db.check_recently_invited(user_id, self.invite_cooldown_minutes)
            
            logger.error("Davet durumu kontrol edilemedi - ilgili veritabanı metotları eksik")
            return False
        except Exception as e:
            logger.error(f"Kullanıcı davet kontrolü hatası: {str(e)}")
            return False
    
    def _mark_user_invited(self, user_id: int) -> bool:
        """
        Kullanıcıyı veritabanında davet edildi olarak işaretler.
        
        Args:
            user_id: İşaretlenecek kullanıcı ID'si
            
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            if hasattr(self.db, 'mark_user_invited'):
                self.db.mark_user_invited(user_id)
                self.invites_sent += 1
                self.responded_users.add(user_id)
                return True
            else:
                logger.warning(f"Davet gönderildi ama veritabanında işaretlenemedi (metod yok): {user_id}")
                self.invites_sent += 1
                self.responded_users.add(user_id)
                return False
        except Exception as e:
            logger.error(f"Kullanıcı davet kaydı hatası: {str(e)}")
            return False
    
    #
    # DAVET GÖNDERİM
    #
    
    async def _send_invite_message(self, event) -> bool:
        """
        Kullanıcıya davet mesajı gönderir.
        
        Args:
            event: Telegram mesaj olayı
            
        Returns:
            bool: Mesaj gönderildiyse True
        """
        success = False
        try:
            sender = await event.get_sender()
            user_name = getattr(sender, 'first_name', "Kullanıcı")
            
            # Şablon mesajı seç
            invite_template = self._choose_invite_template()
            
            # t.me/{} formatını düzelt - gerçek grup ismi veya varsayılan değer koy
            formatted_invite = invite_template
            if "{}" in invite_template:
                # Grup bağlantılarını al
                group_links = self._parse_group_links()
                # Varsayılan değer
                default_group = "@" + "sohbet"  # Varsayılan değer
                
                # Eğer grup linkleri varsa ilk grubu kullan
                if group_links and len(group_links) > 0:
                    if group_links[0].startswith("t.me/"):
                        first_group = group_links[0]
                    else:
                        first_group = f"@{group_links[0]}" if not group_links[0].startswith('@') else group_links[0]
                    # {} kısmını replace et
                    formatted_invite = invite_template.replace("{}", first_group)
                else:
                    # Grup yoksa varsayılan değeri kullan
                    formatted_invite = invite_template.replace("{}", default_group)
            
            # Grup bağlantıları oluştur
            formatted_links = self._get_formatted_group_links()
            links_text = ""
            if formatted_links:
                links_text = "\n\nGruplarımız:\n" + "\n".join([f"• {link}" for link in formatted_links])
            else:
                links_text = "\n\nÜzgünüm, şu anda aktif grup linki bulunmamaktadır."
            
            # Super users ve yönlendirme mesajını ekle (.env'den çek)
            footer_message = os.environ.get("DM_FOOTER_MESSAGE", "Menü için müsait olan arkadaşlarıma yazabilirsin:")
            super_users_text = ""
            if self.super_users:
                valid_super_users = [f"• @{su}" for su in self.super_users if su]
                if valid_super_users:
                    super_users_text = f"\n\n{footer_message}\n" + "\n".join(valid_super_users)
            
            # Tüm mesajı birleştir
            full_message = f"{formatted_invite}{links_text}{super_users_text}"
            
            # Mesajı gönder
            await event.respond(full_message)
            logger.info(f"Davet mesajı gönderildi: {sender.id}")
            success = True
        except errors.FloodWaitError as e:
            logger.warning(f"FloodWaitError davet gönderirken: {e.seconds}s")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            logger.error(f"Davet mesajı gönderirken hata: {str(e)}", exc_info=True)
        return success

    async def _send_redirect_message(self, event) -> bool:
        """
        Zaten davet edilmiş kullanıcıya yönlendirme mesajı gönderir.
        
        Args:
            event: Telegram mesaj olayı
            
        Returns:
            bool: Mesaj gönderildiyse True
        """
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
            await event.respond(redirect_message + links_text)
            logger.info(f"Redirect mesajı gönderildi: {sender.id}")
            success = True
        except errors.FloodWaitError as e:
            logger.warning(f"FloodWaitError redirect gönderirken: {e.seconds}s")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            logger.error(f"Redirect mesajı gönderirken hata: {str(e)}", exc_info=True)
        return success
    
    #
    # BULK PROCESSING
    #
    
    async def process_dm_users(self) -> None:
        """Periyodik olarak veritabanından kullanıcıları çekip DM gönderir."""
        logger.info("DM işleme servisi (process_dm_users) başlatıldı")
        
        while not self.stop_event.is_set():
            try:
                if not self.running:
                    await asyncio.sleep(60)  # Duraklatılmışsa bekle
                    continue
                    
                logger.info(f"🔄 DM işleme döngüsü başladı (Toplam gönderilen: {self.invites_sent})")
                
                # Büyükçe bir kullanıcı batch'i işle
                batch_limit = self.config.get_setting('dm_batch_limit', 10)
                sent_in_batch = await self._process_user_batch(limit=batch_limit)
                logger.info(f"Batch tamamlandı, {sent_in_batch} davet gönderildi.")
                
                if sent_in_batch > 0:
                    logger.info(f"Başarılı gönderimler: {sent_in_batch}")
                    await asyncio.sleep(random.uniform(30, 60))  # Başarılı gönderimler sonrası daha uzun bekle
                
                # Eğer mesaj gönderilemediyse daha kısa bekle
                if sent_in_batch == 0:
                    wait_seconds = min(wait_seconds, 300)  # Max 5 dakika bekle
                    logger.debug(f"Mesaj gönderimi yapılamadı, {wait_seconds // 60} dakika bekleniyor")
                
                if sent_in_batch > 0:
                    self.last_activity = datetime.now()
                
                # Bekleme süresi - daha dinamik
                wait_seconds = self.config.get_setting('dm_process_interval_minutes', 5) * 60
                
                # Eğer mesaj gönderilemediyse daha kısa bekle
                if sent_in_batch == 0:
                    wait_seconds = min(wait_seconds, 120)  # En fazla 2 dk
                    
                logger.debug(f"⏳ {wait_seconds // 60} dakika sonra process_dm_users tekrar çalışacak")
                await asyncio.sleep(wait_seconds)
                
            except asyncio.CancelledError:
                logger.info("process_dm_users görevi iptal edildi.")
                break
            except Exception as e:
                logger.error(f"DM işleme (process_dm_users) hatası: {str(e)}", exc_info=True)
                await asyncio.sleep(120)  # Hata sonrası 2 dk bekle

    async def _process_user_batch(self, limit: int = 10) -> int:
        """
        Belirtilen limit kadar kullanıcıya DM gönderir.
        
        Args:
            limit: İşlenecek maksimum kullanıcı sayısı
            
        Returns:
            int: Başarıyla gönderilmiş mesaj sayısı
        """
        from colorama import Fore, Style
        sent_count_in_batch = 0
        
        try:
            # Veritabanı metodu kontrolü
            if not hasattr(self.db, 'get_users_for_invite'):
                logger.error("Veritabanı nesnesinde get_users_for_invite metodu bulunamadı!")
                return 0
                
            # Daha fazla kullanıcı çek (3 katı) - bazıları işlenemeyeceği için
            users_to_invite = self.db.get_users_for_invite(
                limit=limit*3, 
                cooldown_minutes=self.invite_cooldown_minutes
            )
            
            if not users_to_invite:
                logger.debug("Davet edilecek yeni kullanıcı bulunamadı.")
                return 0
                
            logger.info(f"{len(users_to_invite)} kullanıcı havuzu hazırlandı (limit: {limit})")
            
            # Kullanıcıları karıştır - randomizasyon
            random.shuffle(users_to_invite)
            
            # Başarılı gönderim sayacı
            successful_sends = 0
            
            # Her kullanıcıyı işle
            for user in users_to_invite:
                # Durdurma kontrolü
                if self.stop_event.is_set():
                    break
                    
                # Limit kontrolü
                if successful_sends >= limit:
                    break
                
                # Kullanıcı bilgilerini çıkar
                user_id, username, first_name = self._extract_user_info(user)
                
                # Kullanıcı geçersizse atla
                if not user_id:
                    continue
                
                # Bu oturumda zaten yanıt verilmiş mi kontrol et
                if user_id in self.responded_users:
                    logger.debug(f"Bu kullanıcıya ({user_id}) daha önce yanıt verildi, geçiliyor")
                    continue
                
                # Veritabanı üzerinden yakın zamanda davet edilmiş mi kontrol et
                if self._was_recently_invited(user_id):
                    logger.debug(f"Bu kullanıcı ({user_id}) yakın zamanda davet edilmiş, atlanıyor")
                    continue

                # User entity kontrolü
                user_entity = await self._get_user_entity(user_id, username)
                if not user_entity:
                    logger.debug(f"Kullanıcı varlığı alınamadı: {user_id}")
                    continue
                
                # Mesajları gönder
                try:
                    # İlk mesaj öncesi bekleme
                    wait_before_message = random.uniform(5, 15)
                    logger.debug(f"İlk mesaj öncesi {wait_before_message:.1f}s bekleniyor...")
                    await asyncio.sleep(wait_before_message)
                    
                    # Flirty mesaj gönder
                    flirty_message = self._choose_flirty_message()
                    await self.client.send_message(user_entity, flirty_message)
                    self.rate_limiter.mark_used()
                    
                    # Mesajlar arası bekleme
                    wait_between = random.uniform(8, 15)
                    logger.debug(f"Mesajlar arası {wait_between:.1f}s bekleniyor...")
                    await asyncio.sleep(wait_between)
                    
                    # Davet mesajını oluştur
                    invite_message = self._choose_invite_template()
                    formatted_links = self._get_formatted_group_links()
                    group_links_str = "\n\nGruplarımız:\n" + "\n".join([f"• {link}" for link in formatted_links]) if formatted_links else ""
                    
                    # Super users ekle
                    super_users_str = ""
                    if self.super_users:
                        valid_super_users = [f"• @{su}" for su in self.super_users if su]
                        if valid_super_users:
                            super_users_str = "\n\nADMIN onaylı arkadaşlarıma menü için yazabilirsin:\n" + "\n".join(valid_super_users)
                            
                    # Birleşik mesaj
                    full_message = f"{invite_message}{group_links_str}{super_users_str}"
                    
                    # Davet mesajı gönder
                    await self.client.send_message(user_entity, full_message)
                    self.rate_limiter.mark_used()
                    
                    # İşaretleme ve takip
                    if hasattr(self.db, 'mark_user_invited'):
                        self.db.mark_user_invited(user_id)
                    self.responded_users.add(user_id)
                    self.invites_sent += 1
                    sent_count_in_batch += 1
                    
                    # Log
                    logger.info(f"✅ Davet gönderildi: {username or user_id}")
                    print(f"{Fore.GREEN}✅ Davet gönderildi: {username or user_id}{Style.RESET_ALL}")
                    
                    # Başarı sayacını artır
                    successful_sends += 1
                    
                    # Sonraki kullanıcıya geçmeden önce bekle
                    batch_wait = random.uniform(15, 25)
                    logger.debug(f"Kullanıcılar arası {batch_wait:.1f}s bekleniyor...")
                    await asyncio.sleep(batch_wait)
                    
                except errors.FloodWaitError as e:
                    # Rate limit hataları için bekle
                    wait_time_flood = e.seconds
                    logger.warning(f"⚠️ FloodWaitError: {wait_time_flood} saniye bekleniyor")
                    print(f"{Fore.RED}⚠️ FloodWaitError: {wait_time_flood} saniye bekleniyor{Style.RESET_ALL}")
                    self.rate_limiter.register_error(e)
                    await asyncio.sleep(wait_time_flood + 1)
                    break  # Bu batch'i durdur
                    
                except (errors.UserPrivacyRestrictedError, errors.UserNotMutualContactError) as privacy_err:
                    # Gizlilik kısıtlamaları
                    logger.warning(f"Gizlilik kısıtlaması: {user_id} / @{username} - {privacy_err}")
                    if hasattr(self.db, 'mark_user_uncontactable'):
                        self.db.mark_user_uncontactable(user_id, str(privacy_err))
                    continue  # Sonraki kullanıcıya geç

                except Exception as send_err:
                    # Diğer gönderim hataları
                    error_msg = str(send_err)
                    logger.error(f"Kullanıcıya davet gönderirken hata: {user_id} - {error_msg}", exc_info=True)
                    print(f"{Fore.RED}❌ Kullanıcıya davet gönderilirken hata: {user_id} - {error_msg[:60]}{Style.RESET_ALL}")
                    self.rate_limiter.register_error(send_err)
                    
                    # Too many requests için daha uzun bekleme
                    if "Too many requests" in error_msg:
                        wait_time_tmr = random.randint(180, 300)
                        logger.warning(f"Too many requests hatası: {wait_time_tmr} saniye bekleniyor")
                        print(f"{Fore.RED}⚠️ Too many requests hatası - {wait_time_tmr} saniye bekleniyor{Style.RESET_ALL}")
                        await asyncio.sleep(wait_time_tmr)
                        break  # Bu batch'i durdur
                    else:
                        await asyncio.sleep(random.uniform(3, 7))
                        continue  # Sonraki kullanıcıya geç
            
        except Exception as batch_err:
            # Batch hazırlama hatası
            logger.error(f"Kullanıcı toplu işleme hatası: {str(batch_err)}", exc_info=True)
            print(f"{Fore.RED}❌ Kullanıcı toplu işleme hatası: {str(batch_err)}{Style.RESET_ALL}")
            
        return sent_count_in_batch

    def _extract_user_info(self, user: Union[tuple, dict, Any]) -> Tuple[Optional[int], Optional[str], str]:
        """
        Farklı formatlardaki kullanıcı verilerinden ID, kullanıcı adı ve ad çıkarır.
        
        Args:
            user: Kullanıcı verisi (tuple veya dict)
            
        Returns:
            Tuple: (user_id, username, first_name)
        """
        user_id = None
        username = None
        first_name = 'Kullanıcı'
        
        try:
            if isinstance(user, tuple):
                user_id = user[0] if len(user) > 0 else None
                username = user[1] if len(user) > 1 else None
                first_name = user[2] if len(user) > 2 else 'Kullanıcı'
            elif isinstance(user, dict):
                user_id = user.get('user_id')
                username = user.get('username')
                first_name = user.get('first_name', 'Kullanıcı')
            else:
                logger.warning(f"Beklenmeyen kullanıcı veri tipi: {type(user)}")
        except Exception as e:
            logger.error(f"Kullanıcı verisi çıkarılırken hata: {str(e)}")
            
        return user_id, username, first_name

    def _was_recently_invited(self, user_id: int) -> bool:
        """
        Kullanıcının yakın zamanda davet edilip edilmediğini kontrol eder.
        
        Args:
            user_id: Kontrol edilecek kullanıcı ID'si
            
        Returns:
            bool: Yakın zamanda davet edildiyse True
        """
        try:
            # Önce metot varsa kullan
            if hasattr(self.db, 'was_recently_invited'):
                return self.db.was_recently_invited(user_id, self.invite_cooldown_minutes)
            elif hasattr(self.db, 'check_recently_invited'):
                return self.db.check_recently_invited(user_id, self.invite_cooldown_minutes)
            
            # Manuel kontrol
            elif hasattr(self.db, 'conn') and hasattr(self.db, 'cursor'):
                try:
                    cooldown = datetime.now() - timedelta(minutes=self.invite_cooldown_minutes)
                    cooldown_timestamp = cooldown.timestamp()
                    
                    self.db.cursor.execute(
                        """
                        SELECT 1 FROM users 
                        WHERE user_id = ? AND last_invited IS NOT NULL AND last_invited > ?
                        """, 
                        (user_id, cooldown_timestamp)
                    )
                    
                    return bool(self.db.cursor.fetchone())
                except Exception as db_err:
                    logger.error(f"Veritabanı sorgusu hatası: {str(db_err)}")
        except Exception as e:
            logger.error(f"recently_invited kontrolü hatası: {str(e)}")
            
        return False

    async def _get_user_entity(self, user_id: int, username: Optional[str] = None):
        """
        Kullanıcı ID'si veya kullanıcı adı ile kullanıcı entitysini alır.
        
        Args:
            user_id: Kullanıcı ID'si
            username: Kullanıcı adı (opsiyonel)
            
        Returns:
            User: Telethon kullanıcı nesnesi veya None
        """
        try:
            if username:
                # Önce kullanıcı adı ile dene
                try:
                    return await self.client.get_entity(username)
                except:
                    pass
                    
            # Sonra ID ile dene
            return await self.client.get_entity(int(user_id))
            
        except (ValueError, TypeError) as e:
            logger.error(f"Geçersiz kullanıcı ID'si/adı: {user_id}/{username} - {e}")
        except errors.UsernameInvalidError:
            logger.warning(f"Geçersiz kullanıcı adı: @{username}")
        except errors.PeerIdInvalidError:
            logger.warning(f"Kullanıcı ID bulunamadı: {user_id}")
        except Exception as e:
            logger.warning(f"Kullanıcı bulunamadı: {user_id} / @{username} - {str(e)}")
            
        return None
    
    async def _process_user(self, user: Dict[str, Any]) -> bool:
        """
        Tek bir kullanıcıyı işler ve DM gönderir.
        
        Args:
            user: Kullanıcı bilgileri sözlüğü
            
        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            # User bir dict olarak beklenir
            if not isinstance(user, dict):
                logger.warning(f"Beklenmeyen kullanıcı veri tipi: {type(user)}")
                return False
                
            # Gerekli alanları kontrol et
            if "user_id" not in user:
                logger.warning(f"Geçersiz kullanıcı verisi, user_id eksik: {user}")
                return False
                
            user_id = user["user_id"]
            first_name = user.get("first_name", "Kullanıcı")
            username = user.get("username", "")
            
            # Bu oturumda zaten yanıt verilmiş mi kontrol et
            if user_id in self.responded_users:
                logger.debug(f"Bu kullanıcıya ({user_id}) daha önce yanıt verildi, geçiliyor")
                return False
            
            # Veritabanında yakın zamanda davet edilmiş mi kontrol et
            if self._was_recently_invited(user_id):
                logger.debug(f"Bu kullanıcı ({user_id}) yakın zamanda davet edilmiş, atlanıyor")
                return False

            # User entity kontrolü
            user_entity = await self._get_user_entity(user_id, username)
            if not user_entity:
                logger.debug(f"Kullanıcı varlığı alınamadı: {user_id}")
                return False
                
            # Flirty mesaj gönder
            flirty_message = self._choose_flirty_message()
            await self.client.send_message(user_entity, flirty_message)
            self.rate_limiter.mark_used()
            
            # Kısa bekle
            await asyncio.sleep(random.uniform(8, 15))
            
            # Davet mesajını oluştur ve gönder
            invite_message = self._choose_invite_template()
            formatted_links = self._get_formatted_group_links()
            group_links_str = "\n\nGruplarımız:\n" + "\n".join([f"• {link}" for link in formatted_links]) if formatted_links else ""
            super_users_str = ""
        
            
            # Davet mesajını oluştur ve gönder
            invite_message = self._choose_invite_template()
            formatted_links = self._get_formatted_group_links()
            group_links_str = "\n\nGruplarımız:\n" + "\n".join([f"• {link}" for link in formatted_links]) if formatted_links else ""
            super_users_str = ""
            
            if self.super_users:
                valid_super_users = [f"• @{su}" for su in self.super_users if su]
                if valid_super_users:
                    super_users_str = "\n\nADMIN onaylı arkadaşlarıma menü için yazabilirsin:\n" + "\n".join(valid_super_users)
                    
            full_message = f"{invite_message}{group_links_str}{super_users_str}"
            await self.client.send_message(user_entity, full_message)
            self.rate_limiter.mark_used()
            
            # Veritabanını güncelle ve istatistikleri tut
            if hasattr(self.db, 'mark_user_invited'):
                self.db.mark_user_invited(user_id)
                
            self.responded_users.add(user_id)
            self.invites_sent += 1
            logger.info(f"✅ Tekli işlemde davet gönderildi: {username or user_id}")
            
            return True
            
        except errors.FloodWaitError as e:
            logger.warning(f"FloodWaitError (_process_user): {e.seconds} saniye bekleniyor")
            self.rate_limiter.register_error(e)
            await asyncio.sleep(e.seconds + 1)
            return False
        except Exception as e:
            logger.error(f"Kullanıcı işleme hatası ({user.get('user_id')}): {str(e)}", exc_info=True)
            return False
    
    #
    # GRUP KEŞFETME VE ÜYE TOPLAMA
    #
    
    async def collect_group_members(self) -> int:
        """
        Kullanıcının tüm gruplarını keşfeder ve üyeleri veritabanına kaydeder.
        
        Returns:
            int: Veritabanına kaydedilen toplam üye sayısı
        """
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║               GRUP ÜYELERİ TOPLAMA               ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        logger.info("🔍 Kullanıcının katıldığı gruplar keşfediliyor...")
        
        try:
            # Tüm konuşmaları getir
            dialogs = await self.client.get_dialogs(limit=None) 
            
            # Admin gruplarını çıkar
            admin_groups = self._get_admin_group_ids()
            
            # Grupları keşfet ve kaydet
            discovered_groups = await self._discover_groups(dialogs, admin_groups)
            
            # Hedef grupları al
            target_groups = await self._get_target_groups(discovered_groups)
            
            # Üyeleri topla
            total_members_added = await self._collect_members_from_groups(target_groups)
            
            # Özet bilgileri göster
            self._display_collection_summary(total_members_added, len(target_groups))
            
            return total_members_added
            
        except Exception as e:
            logger.error(f"Üye toplama genel hatası: {str(e)}", exc_info=True)
            print(f"{Fore.RED}✗✗✗ Üye toplama sürecinde kritik hata: {str(e)}{Style.RESET_ALL}")
            return 0
    
    def _get_admin_group_ids(self) -> Set[int]:
        """
        Admin grup ID'lerini çevre değişkenlerinden alır.
        
        Returns:
            Set[int]: Admin grup ID'leri
        """
        admin_groups_raw = os.environ.get("ADMIN_GROUPS", "")
        admin_group_ids = set()
        
        if admin_groups_raw:
            for g in admin_groups_raw.split(','):
                g_strip = g.strip()
                if g_strip and g_strip.startswith('-100'):
                    try:
                        admin_group_ids.add(int(g_strip))
                    except ValueError:
                        logger.warning(f"Geçersiz admin grup ID formatı: {g_strip}")
        
        return admin_group_ids
    
    async def _discover_groups(self, dialogs, admin_group_ids) -> List[Dict[str, Any]]:
        """
        Kullanıcının katıldığı grupları keşfeder ve veritabanına kaydeder.
        
        Args:
            dialogs: Kullanıcının tüm konuşmaları
            admin_group_ids: Admin grup ID'leri
            
        Returns:
            List[Dict[str, Any]]: Keşfedilen gruplar
        """
        # Metodun geri kalanı değişmedi...
    
    async def _get_target_groups(self, discovered_groups) -> List[Tuple[int, str]]:
        """
        Veritabanından veya yapılandırmadan hedef grup listesini çeker.
        
        Args:
            discovered_groups: Keşfedilen gruplar
            
        Returns:
            List[Tuple[int, str]]: Hedef gruplar
        """
        target_groups = []
        try:
            # Try database first
            if hasattr(self.db, 'get_all_target_groups'):
                target_groups_data = None
                try:
                    if asyncio.iscoroutinefunction(self.db.get_all_target_groups):
                        target_groups_data = await self.db.get_all_target_groups()
                    else:
                        target_groups_data = self.db.get_all_target_groups()
                    
                    if target_groups_data:
                        target_groups = [(g['group_id'], g.get('title', g.get('name', f"Grup {g['group_id']}"))) 
                                         for g in target_groups_data if 'group_id' in g]
                        if target_groups:
                             logger.debug(f"Veritabanından {len(target_groups)} hedef grup alındı.")
                             return target_groups
                except Exception as db_err:
                     logger.error(f"Veritabanından hedef grup alınırken hata: {db_err}")

            # Fallback to environment variable or config
            target_groups_set = set()
            env_targets = os.environ.get("TARGET_GROUPS", "")
            if env_targets:
                for g in env_targets.split(','):
                    if g and g.strip():
                        target_groups_set.add(g.strip())
            
            if not target_groups_set:
                 config_targets = self.config.get_setting('target_groups', [])
                 if config_targets:
                     for g in config_targets:
                         if g and isinstance(g, str) and g.strip():
                             target_groups_set.add(g.strip())
                
            raw_groups = list(target_groups_set)
            
            if raw_groups:
                 logger.debug(f"Yapılandırma/Çevre değişkenlerinden {len(raw_groups)} hedef grup alındı.")
                 resolved_groups = []
                 for group_ref in raw_groups:
                      try:
                           entity = await self.client.get_entity(group_ref) 
                           resolved_groups.append((entity.id, getattr(entity, 'title', f"Grup {entity.id}")))
                      except ValueError:
                           logger.warning(f"Hedef grup referansı çözümlenemedi: {group_ref}")
                      except Exception as e:
                           logger.error(f"Hedef grup alınırken hata ({group_ref}): {e}")
                 return resolved_groups
            
        except Exception as e:
            logger.error(f"Hedef grupları alırken genel hata: {str(e)}", exc_info=True)

        logger.warning("Hedef grup bulunamadı.")
        return []

    async def _collect_members_from_groups(self, target_groups) -> int:
        """
        Hedef gruplardan üyeleri toplar ve veritabanına kaydeder.
        
        Args:
            target_groups: Hedef gruplar
            
        Returns:
            int: Toplam eklenen üye sayısı
        """
        total_members_added = 0
        successful_groups = 0
        group_count = len(target_groups)
        if group_count == 0:
            logger.warning("Hedef grup bulunamadı, üye toplama işlemi yapılamıyor.")
            return 0

        print(f"\n{Fore.CYAN}[ÜYE TOPLAMA İLERLEMESİ]{Style.RESET_ALL}")
        
        for idx, (group_id, group_name) in enumerate(target_groups):
            if self.stop_event.is_set():
                logger.info("Üye toplama durduruldu.")
                break

            try:
                group = None
                group_title = group_name 
                try:
                    group = await self.client.get_entity(group_id)
                    group_title = getattr(group, 'title', group_name) 
                    print(f"\n{Fore.CYAN}Processing Group: {group_title} ({group_id}){Style.RESET_ALL}")
                except ValueError:
                    print(f"{Fore.RED}✗ Grup ID'si geçersiz: {group_id}{Style.RESET_ALL}")
                    continue
                except errors.ChannelPrivateError:
                    print(f"{Fore.RED}✗ Özel kanal/grup, üyeler alınamıyor: {group_name} ({group_id}){Style.RESET_ALL}")
                    continue
                except Exception as e:
                    print(f"{Fore.RED}✗ Grup alınamadı: {group_name} ({group_id}) - {e}{Style.RESET_ALL}")
                    continue
                
                progress = int((idx + 1) / group_count * 30)
                print(f"\r{Fore.CYAN}[{'█' * progress}{' ' * (30-progress)}] {((idx+1)/group_count*100):.1f}% ({idx+1}/{group_count}) - {group_title[:20]}{Style.RESET_ALL}", end="")
                
                if hasattr(self.db, 'update_group_stats'):
                    try:
                        if asyncio.iscoroutinefunction(self.db.update_group_stats):
                            await self.db.update_group_stats(group.id, group_title)
                        else:
                            self.db.update_group_stats(group.id, group_title)
                    except Exception as db_err:
                        logger.error(f"Grup istatistikleri güncellenirken hata ({group_title}): {db_err}")

                
                members_in_group = 0
                try:
                    async for member in self.client.iter_participants(group, limit=None): 
                        if self.stop_event.is_set(): break 

                        if member.bot or member.deleted:
                            continue  
                            
                        if hasattr(self.db, 'add_or_update_user'):
                            user_data = {
                                'user_id': member.id,
                                'username': member.username,
                                'first_name': member.first_name,
                                'last_name': member.last_name,
                                'source_group': group_title 
                            }
                            try:
                                if asyncio.iscoroutinefunction(self.db.add_or_update_user):
                                    await self.db.add_or_update_user(user_data)
                                else:
                                    self.db.add_or_update_user(user_data)
                                total_members_added += 1
                                members_in_group += 1
                            except Exception as db_err:
                                logger.error(f"Kullanıcı veritabanına eklenirken/güncellenirken hata ({member.id}): {db_err}")

                        
                        # Optional: Add a small sleep within the inner loop for very large groups
                        # await asyncio.sleep(0.01) 

                    if not self.stop_event.is_set():
                        print(f" - {members_in_group} üye işlendi.")
                        successful_groups += 1
                    
                except errors.FloodWaitError as e:
                    wait_time = e.seconds
                    logger.warning(f"⏳ FloodWaitError (get_participants): {wait_time} saniye bekleniyor - Grup: {group_title}")
                    print(f"\n{Fore.RED}⚠️ Hız sınırı (üye çekerken) - {wait_time} saniye bekleniyor{Style.RESET_ALL}")
                    await asyncio.sleep(wait_time + 1)
                    continue 
                    
                except errors.ChatAdminRequiredError:
                    print(f"\n{Fore.RED}✗ Yönetici yetkisi gerekli: {group_title}{Style.RESET_ALL}")
                    continue
                except errors.ChannelPrivateError:
                    print(f"\n{Fore.RED}✗ Özel kanal/grup, üyeler alınamıyor: {group_title}{Style.RESET_ALL}")
                    continue
                except Exception as e:
                    logger.error(f"Grup üyelerini getirme hatası: {group_title} - {str(e)}", exc_info=True)
                    print(f"\n{Fore.RED}✗ Üye toplama hatası: {group_title} - {str(e)}{Style.RESET_ALL}")
                
                group_wait = random.uniform(5, 15) 
                logger.debug(f"Gruplar arası {group_wait:.1f}s bekleniyor...")
                await asyncio.sleep(group_wait)
                
            except Exception as e:
                logger.error(f"Grup işleme genel hatası: {group_id} - {str(e)}", exc_info=True)
                print(f"\n{Fore.RED}✗ Genel hata: {group_id} - {str(e)}{Style.RESET_ALL}")
                await asyncio.sleep(random.uniform(2, 5)) 
                continue
        
        return total_members_added

    def _display_collection_summary(self, total_members_added, group_count):
        """
        Üye toplama işlemi sonrası özet bilgileri gösterir.
        
        Args:
            total_members_added: Toplam eklenen üye sayısı
            group_count: Toplam grup sayısı
        """
        print() 
        print(f"\n{Fore.CYAN}╔══════════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║                   TOPLAMA ÖZETI                  ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╠══════════════════════════════════════════════════╣{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║ Taranan Gruplar: {group_count:<3}                         ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║ Toplanan Üyeler: {total_members_added:<6}                         ║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════╝{Style.RESET_ALL}")
        
        logger.info(f"📊 Toplam {total_members_added} üye veritabanına eklendi/güncellendi")
    
    async def auto_discover_groups(self):
        """Kullanıcının katıldığı grupları periyodik olarak keşfeder"""
        logger.info("Otomatik grup keşfi başlatılıyor...")
        
        while not self.stop_event.is_set():
            try:
                if not self.running:
                     await asyncio.sleep(60)
                     continue

                logger.info("Otomatik grup keşfi çalışıyor...")
                dialogs = await self.client.get_dialogs(limit=None)
                
                admin_groups_raw = os.environ.get("ADMIN_GROUPS", "")
                admin_group_ids = set()
                
                if admin_groups_raw:
                    for g in admin_groups_raw.split(','):
                        g_strip = g.strip()
                        if g_strip and g_strip.startswith('-100'):
                            try:
                                admin_group_ids.add(int(g_strip))
                            except ValueError:
                                logger.warning(f"Geçersiz admin grup ID formatı (otomatik keşif): {g_strip}")
                
                discovered_count = 0
                updated_count = 0
                
                for dialog in dialogs:
                    if self.stop_event.is_set(): break

                    if (dialog.is_group or dialog.is_channel) and dialog.id not in admin_group_ids:
                        entity = dialog.entity
                        participants_count = getattr(entity, 'participants_count', 0) if entity else 0
                        
                        if hasattr(self.db, 'add_discovered_group'):
                             try:
                                 if asyncio.iscoroutinefunction(self.db.add_discovered_group):
                                     added = await self.db.add_discovered_group(dialog.id, dialog.title, participants_count)
                                 else:
                                      added = self.db.add_discovered_group(dialog.id, dialog.title, participants_count)
                                 if added == "added":
                                      discovered_count += 1
                                 elif added == "updated":
                                      updated_count += 1
                             except Exception as db_err:
                                  logger.error(f"Grup veritabanına eklenirken/güncellenirken hata ({dialog.title}): {db_err}")

                log_message = "Otomatik keşif tamamlandı."
                if discovered_count > 0:
                    log_message += f" {discovered_count} yeni grup eklendi."
                if updated_count > 0:
                     log_message += f" {updated_count} grup güncellendi."
                if discovered_count == 0 and updated_count == 0:
                     log_message += " Yeni/güncellenen grup bulunmadı."
                logger.info(log_message)
                
                wait_duration = self.config.get_setting('group_discovery_interval_hours', 6) * 3600
                logger.debug(f"Sonraki otomatik keşif {wait_duration/3600:.1f} saat sonra.")
                await asyncio.sleep(wait_duration)
                
            except asyncio.CancelledError:
                 logger.info("Otomatik grup keşfi görevi iptal edildi.")
                 break
            except Exception as e:
                logger.error(f"Otomatik grup keşfi hatası: {str(e)}", exc_info=True)
                await asyncio.sleep(30 * 60) # Wait 30 mins after error

# Alias tanımlaması
DMService = DirectMessageService