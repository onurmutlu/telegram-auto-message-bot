"""
# ============================================================================ #
# Dosya: group_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/group_service.py
# İşlev: Grup mesajları ve grup yönetimi için servis.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
import random
import traceback
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from telethon import errors
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatWriteForbiddenError, ChatAdminRequiredError, ChatGuestSendForbiddenError, UserBannedInChannelError, ChatRestrictedError
from pathlib import Path
import functools
from dotenv import load_dotenv
from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter
import aiosqlite
import time

from bot.services.base_service import BaseService
from bot.utils.progress_manager import ProgressManager

logger = logging.getLogger(__name__)

class GroupService(BaseService):
    """
    Grup mesajları ve grup yönetimi için servis.
    
    Bu servis, grup mesajları göndermek, grup üye bilgilerini yönetmek
    ve grup aktivitelerini izlemek için kullanılır.
    
    Attributes:
        messages: Gruplara gönderilecek mesaj şablonları
        active_groups: Aktif grup bilgilerinin tutulduğu sözlük
        error_groups: Hata veren grupların bilgilerinin tutulduğu sözlük
        last_message_times: Son mesaj gönderim zamanlarının tutulduğu sözlük
    """
    
    def __init__(self, client, config, db, stop_event=None):
        """
        GroupService sınıfının başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            config: Yapılandırma nesnesi
            db: Veritabanı nesnesi
            stop_event: Durdurma sinyali için event nesnesi
        """
        super().__init__("group", client, config, db, stop_event)
        
        # Mesaj şablonlarını yükle
        self.message_templates = []
        self._load_message_templates()
        
        # Grup mesaj gönderme izleme
        self.last_message_times = {}
        
        # İstatistikler
        self.stats = {
            'total_sent': 0,
            'groups_discovered': 0,
            'last_message_time': None
        }
        
        # Diğer başlatma kodları...
        self.target_groups = []
        self.error_groups = []
        self.error_groups_set = set()
        self.sent_count = 0
        self.total_sent = 0
        
        # .env'den admin gruplarını yükle
        self.admin_groups = self._load_admin_groups()
        
        # Stats değişkenini ekle (eksik olan buydu)
        self.stats.update({
            'messages_sent': 0,
            'messages_failed': 0,
            'total_groups': 0
        })
        
        # Grup yönetimi
        self.active_groups = {}
        self.error_reasons = {}
        self.group_activity_levels = {}
        
        # Yapılandırma ayarları
        self.batch_size = 3
        self.batch_interval = 3
        self.min_message_interval = 60
        self.max_retries = 5
        self.prioritize_active = True
        
        # Durum yönetimi
        self.is_paused = False
        self.shutdown_event = asyncio.Event()
        
        # Rich konsol
        from rich.console import Console
        self.console = Console()
        
        # Config'den ayarları yükle (varsa)
        if hasattr(config, 'group_messaging'):
            group_config = config.group_messaging
            
            if hasattr(group_config, 'batch_size'):
                self.batch_size = group_config.batch_size
                
            if hasattr(group_config, 'batch_interval'):
                self.batch_interval = group_config.batch_interval
                
            if hasattr(group_config, 'min_message_interval'):
                self.min_message_interval = group_config.min_message_interval
                
            if hasattr(group_config, 'max_retries'):
                self.max_retries = group_config.max_retries
                
            if hasattr(group_config, 'prioritize_active'):
                self.prioritize_active = group_config.prioritize_active
                
        # Diğer servislere referans
        self.services = {}
        
        # Hız sınırlayıcıyı yapılandır
        self._setup_rate_limiter()
        
        # Grup aktivite izleme sistemi
        self.group_activity = {}  # grup_id -> aktivite sayacı
        self.message_intervals = {}  # grup_id -> gönderim aralığı (saniye)
        
        # Varsayılan mesaj aralıkları (saniye cinsinden)
        self.high_activity_interval = 300  # 5 dk (aktif gruplar)
        self.medium_activity_interval = 600  # 10 dk (orta aktiviteli gruplar)
        self.low_activity_interval = 1200  # 20 dk (düşük aktiviteli gruplar)
                
    def set_services(self, services):
        """Diğer servislere referansları ayarlar."""
        self.services = services
        logger.debug(f"{self.name} servisi diğer servislere bağlandı")
        
        # Admin grup ID'lerini de başlangıçta belirlemeye çalış
        self.admin_groups_ids = set()
        self.target_groups_ids = set()
        
        # Grupları yükle ve ID'leri belirle
        if 'dm' in self.services and hasattr(self.services['dm'], 'get_groups'):
            try:
                # DM servisinden ID'leri çekmeye çalış
                asyncio.create_task(self._pre_load_group_ids())
            except Exception as e:
                logger.error(f"Grup ID'leri önden yüklerken hata: {str(e)}")

    async def _pre_load_group_ids(self):
        """Grup ID'lerini belirlemeye çalışır"""
        try:
            if 'dm' in self.services and hasattr(self.services['dm'], 'get_groups'):
                groups = await self.services['dm'].get_groups()
                
                for group in groups:
                    group_id = group.get('chat_id') or group.get('id')
                    group_title = group.get('title', '').lower()
                    group_username = group.get('username', '').lower()
                    
                    # Admin grup mu?
                    for admin_name in self.admin_groups:
                        if (group_username and admin_name in group_username) or \
                           (admin_name in group_title):
                            self.admin_groups_ids.add(group_id)
                            break
                    
                    # Target grup mu?
                    for target_name in self.target_groups:
                        if (group_username and target_name in group_username) or \
                           (target_name in group_title):
                            self.target_groups_ids.add(group_id)
                            break
                            
                logger.info(f"Önden yüklenen grup ID'leri: {len(self.admin_groups_ids)} admin, {len(self.target_groups_ids)} target")
        except Exception as e:
            logger.error(f"Grup ID'lerini önden yükleme hatası: {str(e)}")
        
    async def initialize(self) -> bool:
        """GroupService servisini başlatır."""
        # Temel servisi başlat
        await super().initialize()
        
        # Bot modu kontrolünü kaldır
        self._can_use_dialogs = True
        self._can_discover_groups = True
        
        # Grup kategorileri ve aralık tanımları (dakika cinsinden)
        self.admin_group_interval = 2.5  # Admin grupları: 2-3 dk
        self.target_group_interval = 6.5  # Target gruplar: 6-7 dk
        
        # Aktivite bazlı sıklık (dakika)
        self.high_activity_interval = 5    # Yoğun gruplar: 5 dk
        self.medium_activity_interval = 10  # Orta yoğunlukta: 10 dk
        self.low_activity_interval = 15     # Seyrek gruplar: 15 dk
        self.flood_activity_interval = 1    # Flood akışlı gruplar: 1 dk
        
        # Grup listeleri yükleme
        self.admin_groups = set()
        self.target_groups = set()
        
        # Admin/Target grupları .env'den yükle
        admin_groups_str = os.getenv("ADMIN_GROUPS", "")
        target_groups_str = os.getenv("TARGET_GROUPS", "")
        
        for group in admin_groups_str.split(','):
            if group.strip():
                self.admin_groups.add(group.strip().lower())
                
        for group in target_groups_str.split(','):
            if group.strip():
                self.target_groups.add(group.strip().lower())
        
        logger.info(f"Admin grupları yüklendi: {len(self.admin_groups)} grup")
        logger.info(f"Target gruplar yüklendi: {len(self.target_groups)} grup")
        
        # Grup aktivite analizörü başlat
        self.activity_analyzer = self._setup_activity_analyzer()
        
        return True

    def _setup_activity_analyzer(self):
        """Grup aktivite analizörünü hazırlar"""
        return {
            'group_history': {},       # grup_id -> son mesajlar
            'message_rates': {},       # grup_id -> mesaj/dakika oranı
            'last_analysis_time': {},  # grup_id -> son analiz zamanı
            'prime_time_groups': set() # prime time'da olan gruplar
        }

    def _setup_rate_limiter(self):
        """Hız sınırlayıcıyı yapılandırır."""
        self.rate_limiter = AdaptiveRateLimiter(
            initial_rate=0.05,  # Saniyede 0.05 istek (20 saniyede 1 istek)
            period=60,          # 60 saniyelik periyot
            error_backoff=2.0,  # Hata durumunda 2x yavaşlama
            max_jitter=5        # Maksimum 5 saniyelik rastgele gecikme
        )
        
        # İstatistikler
        self.message_send_stats = {
            'rate_limit_hits': 0,
            'total_waits': 0,
            'flood_waits': 0
        }
        
        logger.debug(f"Grup mesaj rate limiter başlatıldı: {0.05}/sn")

    def _load_message_templates(self):
        """Mesaj şablonlarını yükler."""
        
        # Önce klasik yolu dene, sonra alternatif yolları kontrol et
        template_paths = [
            'data/messages.json',
            './data/messages.json',
            '../data/messages.json',
            'data/templates.json',
            './data/templates.json',
            '../data/templates.json'
        ]
        
        loaded = False
        
        # Düzenli mesaj şablonları
        for path_str in template_paths:
            path = Path(path_str)
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # Farklı şablon yapıları için destek
                        if isinstance(data, list):
                            self.message_templates = data
                        elif isinstance(data, dict) and "messages" in data:
                            self.message_templates = data["messages"]
                        else:
                            # Mesaj kategorilerini yükle
                            self.message_templates = []
                            for key, value in data.items():
                                if key == "regular" or key == "default":
                                    self.message_templates = value
                                elif key == "announcements":
                                    self.announcement_templates = value
                                elif key == "promotions" or key == "promos":
                                    self.promotion_templates = value
                                    
                        logger.info(f"Mesaj şablonları başarıyla yüklendi: {path_str} ({len(self.message_templates)} şablon)")
                        loaded = True
                        break
                except Exception as e:
                    logger.warning(f"Mesaj şablonları yüklenirken hata: {path_str} - {str(e)}")
        
        # Announcement ve promo şablonları için ayrı dosyalara bakma
        announcement_paths = ['data/announcements.json', './data/announcements.json']
        for ann_path in announcement_paths:
            try:
                announcement_path = Path(ann_path)
                if announcement_path.exists():
                    with open(announcement_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # Tüm duyuru mesajlarını düzleştir
                        self.announcement_templates = []
                        
                        # "own_groups" kategorisinden duyuruları al
                        if "own_groups" in data:
                            for category, messages in data["own_groups"].items():
                                self.announcement_templates.extend(messages)
                        
                        logger.info(f"Duyuru şablonları başarıyla yüklendi: {ann_path} ({len(self.announcement_templates)} şablon)")
                        break
            except Exception as e:
                logger.warning(f"Duyuru şablonları yüklenirken hata: {ann_path} - {str(e)}")
        
        # Kampanya şablonlarını yükle
        promo_paths = ['data/promos.json', './data/promos.json', 'data/campaigns.json']
        for promo_path_str in promo_paths:
            try:
                promo_path = Path(promo_path_str)
                if promo_path.exists():
                    with open(promo_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # Tüm kampanya mesajlarını düzleştir
                        self.promotion_templates = []
                        
                        # Kampanya kategorilerinden mesajları al
                        # İç içe yapıları destekle
                        if "templates" in data:
                            for category, messages in data["templates"].items():
                                if isinstance(messages, list):
                                    self.promotion_templates.extend(messages)
                        
                        if "campaign_templates" in data:
                            for category, messages in data["campaign_templates"].items():
                                if isinstance(messages, list):
                                    self.promotion_templates.extend(messages)
                        
                        # Doğrudan mesajlar da olabilir
                        for category, messages in data.items():
                            if category not in ["templates", "campaign_templates"] and isinstance(messages, list):
                                self.promotion_templates.extend(messages)
                        
                        logger.info(f"Kampanya şablonları başarıyla yüklendi: {promo_path_str} ({len(self.promotion_templates)} şablon)")
                        break
            except Exception as e:
                logger.warning(f"Kampanya şablonları yüklenirken hata: {promo_path_str} - {str(e)}")
        
        # Varsayılan şablonları kontrolü
        if not hasattr(self, 'message_templates') or not self.message_templates:
            self.message_templates = [
                "Selam grup, nasılsınız?", 
                "Bugün keyifler nasıl?", 
                "Güzel bir gün değil mi?",
                "Arkadaşlar merhaba, bugün neler yapıyorsunuz?",
                "Sohbete katılmak isteyen var mı?"
            ]
            logger.warning("Mesaj şablonları yüklenemedi! Varsayılan mesajlar kullanılıyor!")
            
        # Duyuru şablonlarını kontrol et
        if not hasattr(self, 'announcement_templates') or not self.announcement_templates:
            self.announcement_templates = [
                "📢 DUYURU: Gruplarımız büyümeye devam ediyor!", 
                "📢 Yeni özelliklerimizi keşfetmek ister misiniz?",
                "📢 Bu hafta yeni etkinliklerimiz var, katılın!"
            ]
            logger.warning("Duyuru şablonları yüklenemedi! Varsayılan duyurular kullanılıyor!")
            
        # Kampanya şablonlarını kontrol et
        if not hasattr(self, 'promotion_templates') or not self.promotion_templates:
            self.promotion_templates = [
                "🔥 Özel kampanya: Bu fırsatı kaçırmayın!", 
                "💥 Sınırlı süre teklifi: Hemen bizimle iletişime geçin!",
                "🎯 Size özel indirim: Detaylar için mesaj atın!"
            ]
            logger.warning("Kampanya şablonları yüklenemedi! Varsayılan kampanyalar kullanılıyor!")

    def _register_event_handlers(self):
        """
        Grup mention ve reply yanıtları için event handler'ları kaydeder.
        """
        from telethon import events
        
        # Self mention handler (kullanıcı bot'u etiketlediğinde)
        @self.client.on(events.NewMessage(incoming=True, pattern=r'@\w+'))
        async def handle_mention(event):
            try:
                # Bot'un kendi kullanıcı adını al
                me = await self.client.get_me()
                bot_username = me.username
                
                # Mesaj içeriği
                message_text = event.message.text
                
                # Bot'a mention yapıldı mı kontrol et
                if f'@{bot_username}' in message_text.lower():
                    logger.info(f"Bot mention edildi: {message_text}")
                    
                    # Yanıt ver
                    await self._reply_to_mention(event)
                    
            except Exception as e:
                logger.error(f"Mention handler hatası: {str(e)}")
        
        # Reply handler (kullanıcı bot'un mesajına yanıt verdiğinde)
        @self.client.on(events.NewMessage(incoming=True))
        async def handle_reply(event):
            try:
                # Bir reply mesajı mı?
                if event.message.reply_to and event.message.reply_to.reply_to_msg_id:
                    # Reply edilen mesajı al
                    replied_to = await event.message.get_reply_message()
                    
                    if replied_to:
                        # Bot'un kendi kullanıcı adını al
                        me = await self.client.get_me()
                        
                        # Bot'un mesajına mı yanıt verildi?
                        if replied_to.sender_id == me.id:
                            logger.info(f"Bot'un mesajına yanıt verildi: {event.message.text}")
                            
                            # Yanıt ver
                            await self._reply_to_message(event)
                            
            except Exception as e:
                logger.error(f"Reply handler hatası: {str(e)}")
        
        # Grup mesajlarını takip etmek için dinleyici ekle
        @self.client.on(events.NewMessage)
        async def track_group_messages(event):
            try:
                # Sadece grup mesajlarını izle (özel mesajları değil)
                if hasattr(event.chat, 'id') and not event.is_private and event.chat_id < 0:
                    chat_id = event.chat_id
                    
                    # Grup aktivite analizörüne mesajı kaydet
                    if chat_id not in self.activity_analyzer['group_history']:
                        self.activity_analyzer['group_history'][chat_id] = []
                        
                    # Mesaj bilgilerini kaydet
                    self.activity_analyzer['group_history'][chat_id].append({
                        'time': datetime.now(),
                        'sender_id': event.sender_id,
                        'message_length': len(event.message.text) if event.message.text else 0
                    })
                    
                    # Maks 100 mesaj tut grup başına
                    if len(self.activity_analyzer['group_history'][chat_id]) > 100:
                        self.activity_analyzer['group_history'][chat_id] = \
                            self.activity_analyzer['group_history'][chat_id][-100:]
            except Exception as e:
                logger.debug(f"Grup mesaj izleme hatası: {str(e)}")
                
        # Event handler'ları kaydet
        self.mention_handler = handle_mention
        self.reply_handler = handle_reply
        self.message_tracker = track_group_messages
        
        logger.info("Grup event handler'ları başarıyla kaydedildi")

    async def _reply_to_mention(self, event):
        """
        Bot mention edildiğinde yanıt verir.
        """
        try:
            # Yanıt mesajını hazırla
            reply_texts = [
                "Merhaba! Beni etiketlediniz. Size nasıl yardımcı olabilirim?",
                "Selam! Nasıl yardımcı olabilirim?",
                "Merhaba! Grubumuzla ilgili sorularınız için özel mesaj atabilirsiniz."
            ]
            reply_text = random.choice(reply_texts)
            
            # Yanıt gönder
            await event.reply(reply_text)
            
            logger.info(f"Mention'a yanıt verildi: {reply_text}")
            
        except Exception as e:
            logger.error(f"Mention yanıtlama hatası: {str(e)}")

    async def _reply_to_message(self, event):
        """
        Bot'un mesajına yanıt verildiğinde çalışır.
        """
        try:
            # Yanıt mesajını hazırla
            reply_texts = [
                "Mesajıma yanıt verdiğiniz için teşekkür ederim!",
                "Evet, size nasıl yardımcı olabilirim?",
                "Diğer sorularınız için özel mesaj atabilirsiniz."
            ]
            reply_text = random.choice(reply_texts)
            
            # Yanıt gönder
            await event.reply(reply_text)
            
            logger.info(f"Reply'a yanıt verildi: {reply_text}")
            
        except Exception as e:
            logger.error(f"Reply yanıtlama hatası: {str(e)}")
        
    async def start(self) -> bool:
        """
        Servisi başlatır ve gerekli kaynakları hazırlar.
        
        Returns:
            bool: Başarılı ise True
        """
        self.running = True
        self.is_paused = False
        
        # Aktif grup sayısını kontrol et
        if not self.active_groups:
            logger.warning("Aktif grup bulunamadı. Grup keşfi yapılacak.")
            await self.discover_groups()
            
        # Hataları temizle
        self.error_groups_set.clear()
        self.error_count = 0
        
        logger.info("Grup mesaj servisi başlatıldı")
        return True
    
    async def stop(self) -> None:
        """
        Servisi güvenli bir şekilde durdurur.
        
        Returns:
            None
        """
        logger.info("Grup servisi durduruluyor...")
        self.running = False
        self.shutdown_event.set()
        
        await super().stop()
        logger.info("Grup servisi durduruldu")
        
    async def pause(self) -> None:
        """
        Servisi geçici olarak duraklatır.
        
        Returns:
            None
        """
        if not self.is_paused:
            self.is_paused = True
            logger.info("Grup servisi duraklatıldı")
            
    async def resume(self) -> None:
        """
        Duraklatılmış servisi devam ettirir.
        
        Returns:
            None
        """
        if self.is_paused:
            self.is_paused = False
            logger.info("Grup servisi devam ettiriliyor")
            
    async def run(self):
        """Servis ana çalışma döngüsü"""
        logger.info("Grup servisi başlatılıyor...")
        
        # Servis durumu kontrolü
        self.is_stopped = False
        
        # Ana döngü
        while self.running and not self.stop_event.is_set():
            try:
                # Yeni grupları keşfet (her 10 dakikada bir)
                if await self._should_discover():
                    await self._periodic_discovery()
                    self.last_discovery = datetime.now()
                    
                # Gruplara mesaj gönder (her çevrimde)
                logger.info("Grup mesaj gönderimi başlatılıyor...")
                await self._send_messages_to_groups()
                
                # Grup aktivite metriklerini güncelle
                await self._update_group_activity_metrics()
                
                # Kısa bekle ve tekrar kontrol et
                await asyncio.sleep(10)
                    
            except Exception as e:
                logger.error(f"Grup servisi döngüsü hatası: {str(e)}")
                await asyncio.sleep(30)  # Hata durumunda daha uzun bekle
                
        logger.info("Grup servisi durduruldu.")

    async def _should_discover(self):
        """
        Grup keşfi için gerekli koşulları kontrol eder.
        
        Returns:
            bool: Koşullar sağlanıyorsa True, aksi halde False
        """
        # Örnek koşul: Her 10 dakikada bir keşif yap
        if not hasattr(self, 'last_discovery'):
            return True
        return (datetime.now() - self.last_discovery).total_seconds() >= 600
            
    async def _periodic_discovery(self):
        """Periyodik grup keşfi yapar"""
        try:
            # HATALI: Bir sınıfı fazla parametre ile başlatma
            # new_groups = SomeClass(param1, param2)  # Bu satırı bulun
            
            # DOĞRU: Parametre sayısını azaltın veya sınıfı düzeltin
            # Ya parametre sayısını azaltın:
            # new_groups = SomeClass(param1)
            
            # Ya da direkt discover_groups_aggressive() metodunu çağırın:
            await self.discover_groups_aggressive()
            
            # 10 dakika bekle
            await asyncio.sleep(600)
        except Exception as e:
            logger.error(f"Periyodik keşif hatası: {str(e)}")

    async def discover_groups_aggressive(self):
        """Agresif grup keşfi - daha çok grup bul."""
        try:
            logger.info("Agresif grup keşfi başlatılıyor...")
            
            # Normal discover_groups metodunu çağır
            discovered_groups = await self.discover_groups()
            
            # Tüm gruplardan kullanıcı çekme işlemini başlat
            if discovered_groups:
                # Grupları uygun formata dönüştür
                active_groups = []
                for group in discovered_groups:
                    # chat_id ve group_id tutarlılığını sağla
                    chat_id = group.get('chat_id')
                    if not chat_id:
                        chat_id = group.get('group_id')
                    
                    if not chat_id:
                        logger.warning(f"Grup ID bulunamadı: {group.get('title', 'Bilinmeyen Grup')}")
                        continue
                    
                    active_groups.append({
                        'group_id': chat_id,  # group_id olarak chat_id değerini kullan
                        'chat_id': chat_id,   # chat_id değerini de sakla
                        'title': group.get('title', 'Bilinmeyen Grup'),
                        'name': group.get('title', 'Bilinmeyen Grup')
                    })
                
                # Kullanıcıları çek (arka planda)
                logger.info(f"Agresif keşif: {len(active_groups)} aktif gruptan kullanıcı çekiliyor...")
                asyncio.create_task(self._extract_users_from_groups(active_groups))
            
            logger.info(f"Agresif grup keşfi tamamlandı: {len(discovered_groups)} grup bulundu")
            return discovered_groups
        except Exception as e:
            logger.error(f"Agresif grup keşfi sırasında hata: {str(e)}")
            return []

    def _load_admin_groups(self):
        """
        .env dosyasından admin gruplarını yükler.
        
        Returns:
            List[str]: Admin grup adlarını içeren liste
        """
        import os
        from dotenv import load_dotenv
        
        # .env dosyasını yeniden oku (önemli)
        load_dotenv()
        
        # ADMIN_GROUPS değişkenini al
        admin_groups_str = os.getenv("ADMIN_GROUPS", "")
        logger.info(f"ADMIN_GROUPS çevre değişkeni: '{admin_groups_str}'")
        
        admin_groups = [group.strip() for group in admin_groups_str.split(",") if group.strip()]
        
        if admin_groups:
            logger.info(f".env dosyasından {len(admin_groups)} admin grup yüklendi: {', '.join(admin_groups)}")
        else:
            logger.warning("ADMIN_GROUPS çevre değişkeni tanımlanmamış veya boş")
            
        return admin_groups

    async def _get_active_groups(self) -> List[Dict[str, Any]]:
        """
        Aktif grupları veritabanından getirir.
        
        Returns:
            List[Dict[str, Any]]: Aktif grupların listesi
        """
        logger.debug("Aktif gruplar getiriliyor...")
        
        query = """
        SELECT 
            chat_id, chat_name, join_date, 
            COALESCE(last_message_time, '0001-01-01 00:00:00') as last_message_time,
            last_message_type, 
            error_count, last_error, permanent_error,
            COALESCE(retry_after, '0001-01-01 00:00:00') as retry_after
        FROM groups 
        WHERE 
            (permanent_error IS NULL OR permanent_error != 1) AND
            (retry_after IS NULL OR retry_after < datetime('now'))
        ORDER BY last_message_time ASC
        LIMIT 50
        """
        
        try:
            rows = await self._run_async_db_method(self.db.fetchall, query)
            if not rows:
                logger.warning("Veritabanında aktif grup bulunamadı")
                return []
            
            now = datetime.now()
            active_groups = []
            
            for row in rows:
                # chat_id'nin None olup olmadığını kontrol et
                if row['chat_id'] is None:
                    logger.warning(f"Veritabanında chat_id NULL olan grup bulundu: {row}")
                    continue
                    
                # chat_id'nin tip dönüşümünü güvenli bir şekilde yap
                try:
                    # String ise sayıya çevir
                    if isinstance(row['chat_id'], str):
                        chat_id = int(row['chat_id'])
                    else:
                        chat_id = row['chat_id']
                except (ValueError, TypeError) as e:
                    logger.error(f"Grup chat_id'si dönüştürülemedi: {row['chat_id']} - Hata: {str(e)}")
                    continue
                    
                # Diğer alanları güvenli bir şekilde işle
                chat_name = row['chat_name'] or "Bilinmeyen Grup"
                last_message_time = row['last_message_time'] or "0001-01-01 00:00:00"
                error_count = row['error_count'] or 0
                
                try:
                    # Zaman bilgilerini kontrol et
                    last_msg_time = datetime.fromisoformat(last_message_time.replace('Z', '+00:00'))
                    time_since_last_message = (now - last_msg_time).total_seconds() / 3600  # saat cinsinden
                    
                    # 24 saatten uzun süredir mesaj gönderilmemiş gruplara öncelik ver
                    priority = 5 if time_since_last_message > 24 else 1
                    
                    # Hata sayısına göre önceliği düşür
                    if error_count > 0:
                        priority -= min(error_count, 3)  # En fazla 3 puan düşür
                    
                    active_groups.append({
                        'chat_id': chat_id,
                        'chat_name': chat_name,
                        'priority': max(priority, 1),  # Minimum 1 öncelik
                        'last_message_time': last_message_time,
                        'error_count': error_count
                    })
                    
                except (ValueError, TypeError) as e:
                    logger.error(f"Grup {chat_id} için tarih bilgisi işlenemedi: {last_message_time} - Hata: {str(e)}")
                    # Yine de listeye ekle ama düşük öncelikle
                    active_groups.append({
                        'chat_id': chat_id,
                        'chat_name': chat_name,
                        'priority': 1,  # Düşük öncelik
                        'last_message_time': "0001-01-01 00:00:00",
                        'error_count': error_count
                    })
            
            # Önceliğe göre sırala
            active_groups.sort(key=lambda x: (-x['priority'], x['last_message_time']))
            
            logger.info(f"Toplam {len(active_groups)} aktif grup bulundu")
            return active_groups
            
        except Exception as e:
            logger.error(f"Aktif gruplar getirilirken hata oluştu: {str(e)}")
            return []

    async def _send_messages_to_groups(self):
        """
        Aktif gruplara düzenli olarak mesaj gönderir.
        """
        try:
            if not self.client or not self.client.is_connected():
                logger.error("Mesaj gönderme işlemi başlatılamadı: İstemci bağlı değil")
                return
                
            # Bot durdurulmuş mu kontrol et
            if self.is_stopped:
                logger.debug("Bot durdurulduğu için mesaj gönderme işlemi atlandı")
                return

            active_groups = await self._get_active_groups()
            if not active_groups:
                logger.info("Mesaj gönderilecek aktif grup bulunamadı")
                return
            
            logger.info(f"Toplam {len(active_groups)} aktif gruba mesaj gönderme işlemi başlatılıyor")
            
            for group_data in active_groups:
                if self.is_stopped:
                    logger.warning("Bot durduruldu, mesaj gönderme döngüsü sonlandırılıyor")
                    break
                    
                chat_id = group_data['chat_id']
                chat_name = group_data.get('chat_name', 'Bilinmeyen Grup')
                
                # Rate limiter kontrolü
                if hasattr(self, 'rate_limiter') and self.rate_limiter:
                    if not await self.rate_limiter.can_execute():
                        wait_time = await self.rate_limiter.get_wait_time()
                        logger.warning(f"Rate limit aşıldı, {wait_time} saniye bekleniyor")
                        await asyncio.sleep(wait_time)
                
                # Gruba mesaj göndermeyi dene
                try:
                    result = await self._send_message_to_group(chat_id)
                    
                    if result:
                        logger.info(f"Mesaj başarıyla gönderildi: {chat_name} (ID: {chat_id})")
                        if hasattr(self, 'rate_limiter') and self.rate_limiter:
                            await self.rate_limiter.mark_success()
                    else:
                        logger.warning(f"Mesaj gönderme başarısız: {chat_name} (ID: {chat_id})")
                    
                    # Her mesaj arasında biraz bekle
                    delay = random.uniform(5, 15)
                    logger.debug(f"Bir sonraki mesaj için {delay:.2f} saniye bekleniyor")
                    await asyncio.sleep(delay)
                except Exception as e:
                    logger.error(f"Gruba mesaj gönderirken beklenmeyen hata: {chat_name} (ID: {chat_id}) - {str(e)}")
                    continue
                
        except Exception as e:
            logger.error(f"Gruplara mesaj gönderme işlemi sırasında genel hata: {str(e)}")

    async def _update_group_activity_metrics(self):
        """Grupların aktivite metriklerini günceller"""
        try:
            logger.debug("Grup aktivite metrikleri güncelleniyor...")
            
            # Grupların son mesajlarını kontrol et
            for group_id, history in self.activity_analyzer['group_history'].items():
                # Son 10 dakikalık mesajları filtrele
                now = datetime.now()
                recent_messages = [msg for msg in history 
                                  if (now - msg['time']).total_seconds() < 600]
                
                # Mesaj sayısından oranı hesapla
                if recent_messages:
                    # En eski mesaj ile en yeni mesaj arasındaki süre (dakika)
                    oldest = min(msg['time'] for msg in recent_messages)
                    newest = max(msg['time'] for msg in recent_messages)
                    duration_minutes = max(0.1, (newest - oldest).total_seconds() / 60)
                    
                    # Dakika başına mesaj sayısı
                    rate = len(recent_messages) / duration_minutes
                    self.activity_analyzer['message_rates'][group_id] = rate
                    
                    # Prime time kontrolü
                    if rate > 30:
                        logger.info(f"Prime-time grup tespit edildi! ID: {group_id}, Hız: {rate:.1f} mesaj/dakika")
                        self.activity_analyzer['prime_time_groups'].add(group_id)
                    elif group_id in self.activity_analyzer['prime_time_groups']:
                        self.activity_analyzer['prime_time_groups'].remove(group_id)
                
                # Geçmiş temizliği (10 dk'dan eski mesajları sil)
                self.activity_analyzer['group_history'][group_id] = recent_messages
            
            logger.debug(f"Grup aktivite güncelleme tamamlandı: {len(self.activity_analyzer['message_rates'])} grup")
            
        except Exception as e:
            logger.error(f"Grup aktivite güncelleme hatası: {str(e)}")

    async def _select_message_template(self, group_id, message_type='regular'):
        """
        Mesaj türüne ve gruba göre şablon seçer ve formatlar.
        
        Args:
            group_id: Grup ID'si
            message_type: Mesaj tipi (regular, announcement, promotion, vb.)
            
        Returns:
            str: Formatlanmış mesaj şablonu
        """
        try:
            templates = []
            
            # Mesaj türüne göre şablon seçimi
            if message_type == "announcement" and hasattr(self, 'announcement_templates'):
                templates = self.announcement_templates
            elif message_type == "promotion" and hasattr(self, 'promotion_templates'):
                templates = self.promotion_templates
            else:
                templates = self.message_templates
                
            # Şablon yok ise varsayılan mesaj
            if not templates or len(templates) == 0:
                return "Merhaba! Nasılsınız?"
                
            # Rastgele şablon seç
            selected_template = random.choice(templates)
            
            # Grup bilgisini al (opsiyonel)
            group_info = None
            if hasattr(self.db, 'get_group_by_id'):
                group_info = await self._run_async_db_method(self.db.get_group_by_id, group_id)
                
            # Şablonu formatla
            # Gruba özel değişkenleri ekle
            group_title = group_info.get('title', 'Grup') if group_info else 'Grup'
            
            # Basit formatlama dene
            try:
                message = selected_template.format(
                    group_name=group_title,
                    date=datetime.now().strftime("%d.%m.%Y"),
                    time=datetime.now().strftime("%H:%M")
                )
            except (KeyError, ValueError):
                # Format hatası durumunda şablonu olduğu gibi kullan
                message = selected_template
                
            return message
            
        except Exception as e:
            logger.error(f"Mesaj şablonu seçme hatası: {str(e)}")
            return "Merhaba! Nasılsınız?"

    async def _select_message_by_type(self, message_type, group_id, group_title):
        """Mesaj tipine göre şablon seçer"""
        try:
            if message_type == "announcement" and hasattr(self, 'announcement_templates'):
                templates = self.announcement_templates
            elif message_type == "promotion" and hasattr(self, 'promotion_templates'):
                templates = self.promotion_templates
            else:
                templates = self.message_templates
                
            # Şablon seç ve formatla
            if templates:
                template = random.choice(templates)
                
                # Basit değişiklikler
                message = template.replace("{group_name}", group_title)
                message = message.replace("{time}", datetime.now().strftime("%H:%M"))
                message = message.replace("{date}", datetime.now().strftime("%d.%m.%Y"))
                
                return message
            else:
                # Şablon yoksa varsayılan mesaj
                return "Merhaba! Nasılsınız?"
        except Exception as e:
            logger.error(f"Mesaj şablonu seçme hatası: {str(e)}")
            return "Merhaba! Nasılsınız?"

    async def analyze_group_safety(self, group_id, group_title=None):
        """
        Grubun güvenli olup olmadığını analiz eder
        
        Args:
            group_id: Grup ID
            group_title: Grup başlığı
        
        Returns:
            dict: Güvenlik analiz sonuçları
        """
        try:
            # Veritabanından grup bilgisini al
            group_info = None
            if hasattr(self.db, 'get_group_by_id'):
                group_info = await self._run_async_db_method(self.db.get_group_by_id, group_id)
            
            # Grup başlığını al
            if not group_title:
                if group_info and 'title' in group_info:
                    group_title = group_info['title']
                else:
                    try:
                        entity = await self.client.get_entity(group_id)
                        group_title = entity.title
                    except:
                        group_title = "Bilinmeyen Grup"
            
            # Başlık filtreleri
            blacklist_keywords = [
                "porno", "sex", "adult", "nsfw", "xxx", "+18", "18+", 
                "viagra", "cialis", "porn", "casino", "bahis", "betting",
                "para kazanma", "şansını dene", "siirt"
            ]
            
            title_risk = 0
            for keyword in blacklist_keywords:
                if keyword in group_title.lower():
                    title_risk += 10
                    
            # Diğer riskler
            admin_risk = 0
            content_risk = 0
            
            # Biraz bekleme süresi oluştur
            # self._fetch_group_admins() metodunu kullan
            # Bu metodların implementasyonu burada olmadığı için sonuçları varsayılan olarak döndür
            
            return {
                'group_id': group_id,
                'group_title': group_title,
                'title_risk': title_risk,
                'admin_risk': admin_risk,
                'content_risk': content_risk,
                'total_risk': title_risk + admin_risk + content_risk,
                'is_safe': (title_risk + admin_risk + content_risk) < 30  # 30 puan altında ise güvenli
            }
            
        except Exception as e:
            logger.error(f"Grup güvenlik analizi hatası: {str(e)}")
            return {
                'group_id': group_id,
                'error': str(e),
                'is_safe': False
            }

    async def _get_message_interval(self, group_id, group_title, group_username=None):
        """
        Belirli bir grup için mesaj gönderme aralığını hesaplar
        
        Args:
            group_id: Grup ID
            group_title: Grup başlığı
            group_username: Grup kullanıcı adı (opsiyonel)
        
        Returns:
            int: Mesaj gönderme aralığı (dakika)
        """
        try:
            # Varsayılan değer - orta seviye grup
            interval = self.medium_activity_interval  # 10 dakika
            
            # Grup tipine göre değerlendir
            is_admin_group = False
            is_target_group = False
        
            # Admin grup kontrolü
            if hasattr(self, 'admin_groups_ids') and group_id in self.admin_groups_ids:
                is_admin_group = True
            else:
                # İsimle kontrol et
                for admin_name in getattr(self, 'admin_groups', []):
                    if (group_username and admin_name in group_username.lower()) or \
                       (admin_name in group_title.lower()):
                        is_admin_group = True
                        break
        
            # Target grup kontrolü
            if hasattr(self, 'target_groups_ids') and group_id in self.target_groups_ids:
                is_target_group = True
            else:
                # İsimle kontrol et
                for target_name in getattr(self, 'target_groups', []):
                    if (group_username and target_name in group_username.lower()) or \
                       (target_name in group_title.lower()):
                        is_target_group = True
                        break
        
            # Öncelikle grup kategorisine göre aralık belirle
            if is_admin_group:
                # Admin gruplara yüksek öncelikli mesaj
                interval = getattr(self, 'admin_group_interval', 2)  # 2 dakika
                logger.debug(f"Admin grup tespit edildi: {group_title}")
            elif is_target_group:
                # Hedef gruplara özel sıklık
                interval = getattr(self, 'target_group_interval', 5)  # 5 dakika
                logger.debug(f"Hedef grup tespit edildi: {group_title}")
            else:
                # Aktivite seviyesine göre değerlendir
                activity_level = self._analyze_group_activity(group_id)
        
                if activity_level == "high":
                    interval = getattr(self, 'high_activity_interval', 5)  # 5 dakika
                elif activity_level == "medium":
                    interval = getattr(self, 'medium_activity_interval', 10)  # 10 dakika
                elif activity_level == "low":
                    interval = getattr(self, 'low_activity_interval', 15)  # 15 dakika
                elif activity_level == "flood":
                    interval = getattr(self, 'flood_activity_interval', 1)  # 1 dakika
                
                logger.debug(f"Aktivite seviyesi {activity_level} için aralık: {interval} dk - {group_title}")
            
            # Rastgele varyasyon ekle (+/- %15)
            if interval > 3:  # Küçük aralıklarda varyasyon ekleme
                variation = interval * 0.15
                interval += random.uniform(-variation, variation)
                # Alt sınır kontrolü
                interval = max(1, interval)
            
            return interval
            
        except Exception as e:
            logger.error(f"Mesaj aralığı hesaplama hatası: {str(e)}")
            # Hata durumunda varsayılan aralığı döndür
            return self.medium_activity_interval  # 10 dakika varsayılan

    def _analyze_group_activity(self, group_id):
        """
        Grubun aktivite seviyesini analiz eder
        
        Args:
            group_id: Grup ID
        
        Returns:
            str: "high", "medium", "low" veya "flood"
        """
        try:
            # Grup aktivitesini incele
            if hasattr(self, 'activity_analyzer') and 'message_rates' in self.activity_analyzer:
                rate = self.activity_analyzer['message_rates'].get(group_id, 0)
                
                # 'flood' kontrolü - çok yüksek hızlı gruplar için özel davranış
                if rate > 50:  # Dakikada 50+ mesaj
                    return "flood"
                
                # Aktivite seviyelerini belirle
                if rate > 10:  # Dakikada 10+ mesaj
                    return "high"
                elif rate > 3:  # Dakikada 3-10 mesaj
                    return "medium"
            else:
                return "low"
            
            # Activity analyzer yoksa varsayılan olarak orta seviye
            return "medium"
            
        except Exception as e:
            logger.error(f"Grup aktivite analizi hatası: {str(e)}")
            return "medium"  # Varsayılan değer

    async def discover_groups(self):
        """
        Kullanıcının üye olduğu grupları keşfeder.
        
        Returns:
            List[Dict]: Keşfedilen grupların bilgilerini içeren liste
        """
        try:
            discovered_groups = []
            
            # UserBot modu kontrolü
            if not self._can_use_dialogs:
                logger.warning("Bu hesap normal bot olduğu için grup keşfi sınırlı.")
                return []
            
            # Mevcut diyalogları almaya çalış
            logger.info("Mevcut diyaloglar alınıyor...")
            
            # Diyalogları al (bütün grupları)
            async for dialog in self.client.iter_dialogs():
                try:
                    # Sadece grupları ve kanalları filtrele
                    if dialog.is_group or dialog.is_channel:
                        # Grubun veya kanalın detaylarını al
                        entity = dialog.entity
                        
                        # Başlık kontrolü
                        title = entity.title if hasattr(entity, 'title') else "Başlıksız Grup"
                        
                        # ID kontrolü
                        chat_id = dialog.id
                        
                        # Kullanıcı adı kontrolü
                        username = entity.username if hasattr(entity, 'username') else None
                        
                        # Üye sayısı (mümkünse)
                        try:
                            member_count = entity.participants_count if hasattr(entity, 'participants_count') else None
                        except:
                            member_count = None
                            
                        # Grup bilgilerini kaydet
                        group_info = {
                            'chat_id': chat_id,  # id -> chat_id olarak değiştirildi
                            'group_id': chat_id,  # group_id alanını da ekleyelim
                            'title': title,
                            'username': username,
                            'access_hash': entity.access_hash if hasattr(entity, 'access_hash') else None,
                            'member_count': member_count,
                            'discovery_time': datetime.now().isoformat()
                        }
                        
                        discovered_groups.append(group_info)
                        
                        # Veritabanına ekle (opsiyonel - fonksiyon varsa)
                        if hasattr(self.db, 'add_group'):
                            try:
                                # Burada chat_id uygun şekilde geçiriliyor
                                response = await self._run_async_db_method(self.db.add_group, 
                                                                   chat_id, 
                                                                   title,
                                                                   username=username)
                                if response:
                                    logger.debug(f"Grup veritabanına eklendi: {title} (#{chat_id})")
                            except Exception as db_error:
                                logger.error(f"Grup DB ekleme hatası: {str(db_error)}")
                        # Veritabanına direkt SQL ile ekle
                        else:
                            try:
                                # groups tablosuna SQL ile insert
                                # chat_id'nin NULL olmamasını sağlayalım
                                query = """
                                INSERT OR REPLACE INTO groups (chat_id, title, member_count, is_active) 
                                VALUES (?, ?, ?, 1)
                                """
                                params = (chat_id, title, member_count or 0)
                                
                                await self._run_async_db_method(self.db.cursor.execute, query, params)
                                await self._run_async_db_method(self.db.conn.commit)
                                
                                logger.debug(f"Grup SQL ile eklendi: {title} (#{chat_id})")
                            except Exception as sql_error:
                                logger.error(f"Grup SQL ile eklenirken hata: {str(sql_error)}")
                        except Exception as e:
                            logger.error(f"Grup işleme hatası: {str(e)}")
                            continue
                            
                except Exception as dialog_error:
                    logger.error(f"Dialog işleme hatası: {str(dialog_error)}")
                    continue
            
            # Sonuçları log
            logger.info(f"{len(discovered_groups)} grup keşfedildi")
            
            # Sınıfın global değişkenini güncelle
            if hasattr(self, 'stats'):
                self.stats['groups_discovered'] = len(discovered_groups)
                
            # Başarılı ise güncelle
            if hasattr(self, 'last_discovery_time'):
                self.last_discovery_time = datetime.now()
            
            return discovered_groups
            
        except Exception as e:
            logger.error(f"Grup keşfi sırasında hata: {str(e)}")
            return []

    async def _extract_users_from_groups(self, groups, progress=None, group_user_limit=500):
        """
        Belirtilen gruplardan kullanıcıları çeker ve veritabanına kaydeder.
        
        Args:
            groups: Kullanıcıları çekilecek grupların listesi
            progress: Rich Progress nesnesi
            group_user_limit: Her gruptan çekilecek maksimum kullanıcı sayısı
        
        Returns:
            tuple: Başarılı grupların sayısı, hata olan grupların sayısı
        """
        users_saved = []
        error_groups = 0
        extracted_users = 0
        success_groups = 0
        tasks = []

        try:
            for group in groups:
                # Önce group_id, sonra chat_id, son olarak id alanlarını kontrol et
                group_id = group.get('group_id')
            
                # Eğer group_id yoksa chat_id'yi kontrol et
                if group_id is None:
                    group_id = group.get('chat_id')
            
                # Eğer chat_id de yoksa id'yi kontrol et (eski kod için geriye uyumluluk)
                if group_id is None:
                    group_id = group.get('id')
                
                # Grup ID kontrolü
                if not group_id:
                    group_title = group.get('title', 'Bilinmeyen Grup')
                    group_name = group.get('name', group_title)
                    logger.warning(f"Geçersiz grup ID: Grup adı: {group_name} - {group}")
                    error_groups += 1
                    if progress:
                        progress.update(task, advance=1)
                    continue
                
                try:
                    # Grubu işle
                    group_title = group.get('title', group.get('name', 'Bilinmeyen Grup'))
                    logger.info(f"Grup işleniyor: {group_title} (ID: {group_id})")
                    users = await self._get_group_members_aggressive(group_id)
                    
                    # Telegram hatalarını kontrol et ve grubu güncelle
                    await self._update_group_success(group_id)
                    
                    # Kullanıcıları veritabanına kaydet
                    saved_count = await self._save_users_from_group(users)
                    
                    # İstatistikleri güncelle
                    users_saved.append(saved_count)
                    extracted_users += len(users)
                    success_groups += 1
                    
                except errors.ChatAdminRequiredError:
                    logger.warning(f"Admin yetkisi gerekli: {group_id}")
                    await self._update_group_error(group_id, "ChatAdminRequiredError", permanent=True)
                    error_groups += 1
                    
                except errors.ChannelPrivateError:
                    logger.warning(f"Özel kanal: {group_id}")
                    await self._update_group_error(group_id, "ChannelPrivateError", permanent=True)
                    error_groups += 1
                    
                except FloodWaitError as e:
                    wait_time = e.seconds
                    logger.warning(f"FloodWaitError: {wait_time} saniye beklenmeli - Grup: {group_id}")
                    await self._update_group_error(group_id, f"FloodWaitError: {wait_time}s", retry_after=wait_time)
                    if wait_time > 60:
                        # 1 dakikadan fazla beklemek gerekiyorsa, işlemi durdur
                        logger.error(f"FloodWaitError çok uzun ({wait_time}s), işlem durduruluyor")
                        raise
                    await asyncio.sleep(wait_time)
                    error_groups += 1
                    
                except Exception as e:
                    logger.error(f"Gruptan kullanıcı çekerken hata: {group_id} - {str(e)}")
                    await self._update_group_error(group_id, str(e))
                    error_groups += 1
                    
                finally:
                    # İlerlemeyi güncelle
                    if progress:
                        progress.update(task, advance=1)
            
            logger.info(f"Toplam çekilen kullanıcı sayısı: {extracted_users}")
            logger.info(f"Kaydedilen kullanıcılar: {sum(users_saved)}")
            
            return success_groups, error_groups
            
        except Exception as e:
            logger.error(f"Genel hata: {str(e)}")
            return success_groups, error_groups

    async def _get_group_members_aggressive(self, group_id):
        """
        Belirtilen gruptan kullanıcıları agresif şekilde çeker.
        
        Args:
            group_id: Kullanıcıların çekileceği grup ID'si
            
        Returns:
            list: Gruptaki kullanıcıların listesi
        """
        # Grup ID kontrolü
        if not group_id:
            logger.error("Grup ID None veya boş. Kullanıcılar çekilemiyor.")
            return []
            
        # String ise integer'a çevir
        if isinstance(group_id, str) and group_id.isdigit():
            group_id = int(group_id)
        
        users = []
        offset = 0
        limit = 100
        all_participants = []
        
        try:
            # Grup entity'sini al
            try:
                entity = await self.client.get_entity(group_id)
                if not entity:
                    logger.warning(f"Grup entity bulunamadı: {group_id}")
                    return []
                    
                # Entity tipini kontrol et
                if not hasattr(entity, 'title'):
                    logger.warning(f"Geçersiz grup entity tipi: {type(entity).__name__} (ID: {group_id})")
                    return []
                    
                logger.info(f"Grup kullanıcıları çekiliyor: '{entity.title}' (ID: {group_id})")
            except ValueError as ve:
                logger.error(f"Geçersiz grup ID: {group_id} - {str(ve)}")
                return []
            except TypeError as te:
                logger.error(f"Grup ID tipi hatası: {group_id} ({type(group_id)}) - {str(te)}")
                return []
            except Exception as e:
                logger.error(f"Grup entity alım hatası: {group_id} - {str(e)}")
                return []
            
            # Farklı filtrelerle katılımcı çekmeyi dene
            filter_types = [
                None,  # Filtre yok
                ChannelParticipantsRecent(),  # Son aktif olanlar
                ChannelParticipantsAdmins(),  # Adminler
            ]
            
            success = False
            for filter_type in filter_types:
                if success:
                    break
                    
                try:
                    filter_name = filter_type.__class__.__name__ if filter_type else "None"
                    logger.debug(f"Filtre deneniyor: {filter_name}")
                    
                    while True:
                        # Rate limit kontrolü
                        if not self.rate_limiter.can_execute():
                            wait_time = self.rate_limiter.get_wait_time()
                            logger.warning(f"Üye çekme için rate limit aşıldı. {wait_time:.1f} saniye bekleniyor.")
                            await asyncio.sleep(wait_time)
                        
                        try:
                            participants = await self.client(GetParticipantsRequest(
                                channel=entity,
                                filter=filter_type,
                                offset=offset,
                                limit=limit,
                                hash=0
                            ))
                            
                            # Başarılı istek
                            self.rate_limiter.mark_success()
                            
                            if not participants.users:
                                break
                                
                            all_participants.extend(participants.users)
                            offset += len(participants.users)
                            
                            # Yeterli sayıda kullanıcı çekildiyse durabilir
                            if len(all_participants) >= 500:  # Maksimum kullanıcı sayısı
                                logger.info(f"Maksimum kullanıcı sayısına ulaşıldı: {len(all_participants)}")
                                break
                                
                        except errors.FloodWaitError as flood_error:
                            wait_time = flood_error.seconds
                            logger.warning(f"FloodWaitError: {wait_time} saniye beklenmeli")
                            self.rate_limiter.register_error("FloodWaitError", wait_time)
                            await asyncio.sleep(min(wait_time, 60))  # Maksimum 60 saniye bekle
                            continue
        
                except Exception as e:
                    logger.error(f"Kullanıcı çekme hatası ({filter_name}): {str(e)}")
                    self.rate_limiter.register_error("OtherError")
                    break
                    
                if all_participants:
                    success = True
                    logger.info(f"Filtre ile başarılı şekilde kullanıcılar çekildi: {filter_name}")
                    
            # Çekilen kullanıcıları işle
            for user in all_participants:
                if user.bot:
                    continue  # Botları atla
                    
                # Kullanıcı verilerini hazırla
                user_data = {
                    'id': user.id,
                    'username': user.username if user.username else None,
                    'first_name': user.first_name if hasattr(user, 'first_name') else None,
                    'last_name': user.last_name if hasattr(user, 'last_name') and user.last_name else None,
                    'phone': user.phone if hasattr(user, 'phone') and user.phone else None,
                    'group_id': group_id,
                    'group_title': entity.title if hasattr(entity, 'title') else "Bilinmeyen Grup",
                }
                users.append(user_data)
                
            logger.info(f"Toplam {len(users)} kullanıcı çekildi (grup: {group_id})")
            return users
            
        except errors.ChannelPrivateError:
            logger.warning(f"Grup {group_id} özel bir kanal. Kullanıcılar çekilemiyor.")
            return []
            
        except errors.ChatAdminRequiredError:
            logger.warning(f"Grup {group_id} için admin yetkileri gerekli.")
            return []
                    
        except Exception as e:
            logger.error(f"Grup kullanıcıları çekme hatası: {group_id} - {str(e)}")
            return []

    async def _send_message_to_group(self, group_id: Union[int, str], message_type: str = None) -> bool:
        """
        Belirtilen gruba mesaj gönderir.
        
        :param group_id: Grubun ID'si (int veya str olabilir)
        :param message_type: Gönderilecek mesaj türü
        :return: Mesaj başarıyla gönderildi mi (boolean)
        """
        # Rate limit kontrolü
        if not self.rate_limiter.can_execute():
            wait_time = self.rate_limiter.get_wait_time()
            logger.warning(f"Rate limit aşıldı. {wait_time:.2f} saniye bekleniyor")
            return False
            
        # group_id kontrolü
        if group_id is None or (isinstance(group_id, str) and not group_id.strip()):
            logger.error("Grup ID'si None veya boş")
            return False
            
        # group_id'yi int'e çevir (eğer string ise)
        if isinstance(group_id, str):
            try:
                group_id = int(group_id)
            except ValueError:
                logger.error(f"Geçersiz grup ID formatı: {group_id}")
                return False
                
        # Mesaj türünü seç
        message_types = list(self.message_templates.keys())
        if not message_type or message_type not in message_types:
            message_type = random.choice(message_types)
            
        message_text = self.message_templates[message_type]
        
        logger.debug(f"Gruba mesaj gönderiliyor: {group_id}, mesaj türü: {message_type}")
        
        try:
            # Mesajı gönder
            await self.client.send_message(group_id, message_text)
            
            # Başarı durumunu kaydet
            self.rate_limiter.mark_success()
            
            # Veritabanını güncelle
            async with aiosqlite.connect(self.db_path) as db:
                now = int(time.time())
                await db.execute(
                    "UPDATE groups SET last_message_time = ?, message_count = message_count + 1 WHERE group_id = ?",
                    (now, group_id)
                )
                await db.commit()
                
            logger.info(f"Mesaj başarıyla gönderildi: Grup {group_id}, Tür: {message_type}")
            return True
            
        except FloodWaitError as e:
            self.rate_limiter.register_error()
            wait_seconds = e.seconds
            
            # Veritabanını güncelle
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE groups SET last_error = ?, retry_after = ? WHERE group_id = ?",
                    (f"FloodWaitError: {wait_seconds}s bekle", now + wait_seconds, group_id)
                )
                await db.commit()
                
            logger.warning(f"FloodWaitError: Grup {group_id} için {wait_seconds} saniye beklenmeli")
            return False
            
        except errors.ChannelPrivateError:
            self.rate_limiter.register_error()
            
            # Veritabanını güncelle
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE groups SET active = 0, permanent_error = 'Kanal özel', last_error = ? WHERE group_id = ?",
                    (f"ChannelPrivateError: Kanal özel", group_id)
                )
                await db.commit()
                
            logger.warning(f"Grup {group_id} artık özel veya erişilemez. Devre dışı bırakıldı.")
            return False
            
        except errors.ChatWriteForbiddenError:
            self.rate_limiter.register_error()
            
            # Veritabanını güncelle
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE groups SET active = 0, permanent_error = 'Yazma izni yok', last_error = ? WHERE group_id = ?",
                    (f"ChatWriteForbiddenError: Yazma izni yok", group_id)
                )
                await db.commit()
                
            logger.warning(f"Grup {group_id}'de yazma izni yok. Devre dışı bırakıldı.")
            return False
            
        except errors.ChatAdminRequiredError:
            self.rate_limiter.register_error()
            
            # Veritabanını güncelle
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE groups SET active = 0, permanent_error = 'Admin izni gerekli', last_error = ? WHERE group_id = ?",
                    (f"ChatAdminRequiredError: Admin izni gerekli", group_id)
                )
                await db.commit()
                
            logger.warning(f"Grup {group_id} için admin izni gerekli. Devre dışı bırakıldı.")
            return False
            
        except Exception as e:
            self.rate_limiter.register_error()
            error_message = str(e)
            
            # Veritabanını güncelle
            async with aiosqlite.connect(self.db_path) as db:
                now = int(time.time())
                await db.execute(
                    "UPDATE groups SET last_error = ? WHERE group_id = ?",
                    (error_message[:100], group_id)  # Hata mesajını 100 karakter ile sınırla
                )
                await db.commit()
                
            logger.error(f"Grup {group_id}'e mesaj gönderilirken hata oluştu: {error_message}")
            return False