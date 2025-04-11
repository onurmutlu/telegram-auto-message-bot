"""
# ============================================================================ #
# Dosya: group_handler.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/handlers/group_handler.py
# İşlev: Telegram bot için grup mesaj yönetimi ve otomatik mesaj gönderimi.
#
# Amaç: Bu modül, bot'un üye olduğu gruplara otomatik mesaj gönderim 
# mekanizmasını, grup üyelerini toplama, grup aktivitelerini izleme ve
# mesaj gönderim zamanlamalarını otomatik olarak ayarlama işlevlerini yönetir.
#
# Temel Özellikler:
# - Aktif grupların dinamik olarak tespit edilmesi
# - Hata yönetimi ve hata veren grupların geçici olarak devre dışı bırakılması
# - Farklı gruplara düzenli ve otomatik mesaj gönderimi
# - Anti-spam korumalı mesaj akışı kontrolü ve akıllı gecikme mekanizmaları
# - Grup bazlı hata takibi ve otomatik yeniden deneme sistemi
# - Adaptif mesaj gönderim sıklığı (grup aktivitesine göre)
# - Grup üyelerinin veritabanına toplu olarak kaydedilmesi
# - İlerleme çubuklarıyla zengin konsol arayüzü
#
# Build: 2025-04-08-23:15:00
# Versiyon: v3.5.0
# ============================================================================ #
#
# Değişiklik Geçmişi:
# v3.5.0 (2025-04-08) - İki process_group_messages metodu birleştirildi
#                      - Console ve rich tabanlı kullanıcı arayüzü iyileştirildi 
#                      - Asenkron hata ve FloodWait yönetimi geliştirildi
#                      - Gereksiz log mesajları optimize edildi
#                      - İstatistik toplama ve raporlama mekanizmaları eklendi
#                      - Kapsamlı dokümantasyon güncellemesi
# v3.4.0 (2025-04-01) - Grup aktivite seviyesi tespiti eklendi
#                      - Üye toplama işlemleri paralel hale getirildi
#                      - Mesaj gönderim performansı iyileştirildi
# v3.3.0 (2025-03-15) - İlk sürüm
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import random
import logging
from datetime import datetime, timedelta
from colorama import Fore, Style
from rich import box
from rich.console import Console
from rich.table import Table
import rich
import threading
from typing import List, Dict, Optional, Set, Any, Union, Tuple

from telethon.tl.types import Channel, User, Message
from telethon.errors import FloodWaitError, ChatAdminRequiredError, ChannelPrivateError

from telethon import errors
from bot.services.group_service import GroupService
from bot.services.user_service import UserService
from bot.utils.db_setup import Database
from bot.utils.progress import ProgressManager

import json

logger = logging.getLogger(__name__)

class GroupHandler:
    """
    Telegram gruplarına otomatik mesaj gönderimi ve yönetimi için ana sınıf.
    
    Bu sınıf, Telegram botunun üye olduğu gruplara otomatik mesaj gönderimini,
    grup üyelerini toplamayı, grup aktivitelerini izlemeyi ve hata durumlarını
    yönetmeyi sağlar.
    
    Attributes:
        client: Telethon istemcisi
        config: Uygulama yapılandırması
        db: Veritabanı bağlantısı
        group_service: Grup işlemleri için servis nesnesi
        user_service: Kullanıcı işlemleri için servis nesnesi
        messages: Gruplara gönderilecek mesaj şablonları
        responses: Grup yanıtları için şablonlar
        invites: Davet mesajları için şablonlar
        active_groups: Aktif grup bilgilerinin tutulduğu sözlük
        error_groups: Hata veren grupların bilgilerinin tutulduğu sözlük
        last_message_times: Son mesaj gönderim zamanlarının tutulduğu sözlük
        group_activity_levels: Grup aktivite seviyelerinin tutulduğu sözlük
        is_running: Servisin çalışıp çalışmadığı
        is_paused: Servisin duraklatılıp duraklatılmadığı
        stop_event: Durdurma sinyali için asyncio.Event nesnesi
        console: Rich konsol nesnesi
        total_sent: Toplam gönderilen mesaj sayısı
        logger: Loglama nesnesi
    """
    
    def __init__(self, client: Any, config: Any, db: Database):
        """
        GroupHandler sınıfının başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
        """
        self.client = client
        self.config = config
        self.db = db
        self.group_service = GroupService(db)
        self.user_service = UserService(db)
        
        # Mesaj şablonlarını yükle
        with open('data/messages.json', 'r', encoding='utf-8') as f:
            self.messages = json.load(f)
            
        with open('data/responses.json', 'r', encoding='utf-8') as f:
            self.responses = json.load(f)
            
        with open('data/invites.json', 'r', encoding='utf-8') as f:
            self.invites = json.load(f)
        
        # Grup ve mesaj veri yapıları    
        self.active_groups: Dict[int, Dict] = {}
        self.error_groups: Dict[int, Dict] = {}
        self.error_groups_set: Set[int] = set()  # Hızlı arama için
        self.last_message_times: Dict[int, datetime] = {}
        self.group_activity_levels: Dict[int, str] = {}  # 'high', 'medium', 'low'
        
        # Çalışma durumu değişkenleri
        self.is_running = True
        self.is_paused = False
        self.pause_event = asyncio.Event()
        self.shutdown_event = asyncio.Event()
        self.stop_event = asyncio.Event()
        
        # İstatistik değişkenleri
        self.total_messages_sent = 0
        self.error_count = 0
        self.messages_sent = 0
        self.messages_failed = 0
        self.last_run = datetime.now()
        self.error_reasons: Dict[int, str] = {}
        self.sent_count = 0
        self.total_sent = 0
        self.processed_groups: Set[int] = set()
        self.last_message_time = datetime.now()
        self.last_sent_time: Dict[int, datetime] = {}
        
        # Rich konsol ve log yapılandırması
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.console = Console()
        
        # Konsolda debug mesajlarını görmek için handler ekleyin
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # Yapılandırma ayarlarını al
        self.batch_size = 3
        self.batch_interval = 3
        self.min_message_interval = 60
        self.max_retries = 5
        self.prioritize_active = True
        
        # Config'den ayarları yükle (varsa)
        if hasattr(config, 'group_messaging'):
            msg_config = config.group_messaging
            self.batch_size = msg_config.get('batch_size', 3)
            self.batch_interval = msg_config.get('batch_interval', 3)
            self.min_message_interval = msg_config.get('min_message_interval', 60)
            self.max_retries = msg_config.get('max_retries', 5)
            self.prioritize_active = msg_config.get('prioritize_active_groups', True)
            
        logger.info("GroupHandler başlatıldı")
    
    async def initialize(self) -> None:
        """
        Grup işleyicisini başlatır ve hedef grupları veritabanından yükler.
        
        Returns:
            None
        """
        logger.info("Grup işleyici başlatılıyor...")
        
        # Hedef grupları veritabanından yükle
        target_groups = await self.group_service.get_target_groups()
        loaded_count = 0
        
        for group in target_groups:
            self.active_groups[group['group_id']] = {
                'name': group['name'],
                'last_message': group.get('last_message'),
                'error_count': 0,
                'is_active': True
            }
            loaded_count += 1
            
        logger.info(f"Hedef gruplar yüklendi: {loaded_count} grup")
        
        # İstatistikleri sıfırla
        if hasattr(self.db, 'get_total_messages_sent'):
            self.total_sent = await self._run_async_db_method(self.db.get_total_messages_sent) or 0
        
    async def start(self) -> bool:
        """
        Servisi başlatır ve gerekli kaynakları hazırlar.
        
        Returns:
            bool: Başarılı ise True
        """
        self.is_running = True
        self.is_paused = False
        
        # Aktif grup sayısını kontrol et
        if not self.active_groups:
            logger.warning("Hiç aktif grup bulunamadı! Grup keşfi çalıştırın.")
            
        # Hataları temizle - opsiyonel
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
        logger.info("Grup işleyici durduruluyor...")
        self.is_running = False
        self.shutdown_event.set()
        self.stop_event.set()
        
        # Aktif görevleri iptal et - future için
        # TODO: Aktif görevleri iptal et
        
        logger.info("Grup işleyici durduruldu")
        
    async def pause(self) -> None:
        """
        Servisi geçici olarak duraklatır.
        
        Returns:
            None
        """
        if not self.is_paused:
            self.is_paused = True
            self.pause_event.set()
            logger.info("Grup işleyici duraklatıldı")

    async def resume(self) -> None:
        """
        Duraklatılmış servisi devam ettirir.
        
        Returns:
            None
        """
        if self.is_paused:
            self.is_paused = False
            self.pause_event.clear()
            logger.info("Grup işleyici devam ettiriliyor")

    #
    # GRUP KEŞFI VE YÖNETIMI
    #
        
    async def discover_groups(self) -> int:
        """
        Botun üye olduğu grupları otomatik olarak tespit eder ve veritabanına kaydeder.
        
        Returns:
            int: Keşfedilen grup sayısı
        """
        logger.info("Grup keşfi başlatılıyor...")
        discovered_count = 0
        
        try:
            # Botun üye olduğu tüm grupları al
            async for dialog in self.client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    group = dialog.entity
                    
                    # Grup bilgilerini al
                    try:
                        group_info = await self.client.get_entity(group.id)
                        if isinstance(group_info, Channel):
                            # Grup üye sayısını kontrol et
                            if getattr(group_info, 'participants_count', 0) >= self.config.MIN_GROUP_SIZE:
                                # Grubu veritabanına kaydet
                                await self.group_service.add_target_group(
                                    group_id=group.id,
                                    name=group.title,
                                    member_count=getattr(group_info, 'participants_count', 0)
                                )
                                
                                # Aktif gruplara ekle
                                if group.id not in self.active_groups:
                                    self.active_groups[group.id] = {
                                        'name': group.title,
                                        'last_message': None,
                                        'error_count': 0,
                                        'is_active': True
                                    }
                                    discovered_count += 1
                                    
                                logger.info(f"Yeni grup keşfedildi: {group.title} ({getattr(group_info, 'participants_count', '?')} üye)")
                                
                                # Grup üyelerini kaydet
                                await self._save_group_members(group.id)
                    except Exception as e:
                        logger.warning(f"Grup bilgileri alınamadı: {group.title} - {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"Grup keşfi sırasında hata: {str(e)}")
            
        logger.info(f"Grup keşfi tamamlandı: {discovered_count} yeni grup eklendi")
        return discovered_count
            
    async def _save_group_members(self, group_id: int) -> int:
        """
        Belirtilen grubun üyelerini veritabanına kaydeder.
        
        Args:
            group_id: Grup ID
            
        Returns:
            int: Kaydedilen üye sayısı
        """
        saved_count = 0
        try:
            async for user in self.client.iter_participants(group_id):
                if isinstance(user, User) and not user.bot and not user.deleted:
                    result = await self.user_service.add_user(
                        user_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        source_group=str(group_id)
                    )
                    if result:
                        saved_count += 1
                        
                    # Her 50 kullanıcıda bir biraz bekle (rate limiting)
                    if saved_count % 50 == 0:
                        await asyncio.sleep(0.5)
                        
            logger.info(f"Grup {group_id} için {saved_count} üye kaydedildi")
            return saved_count
            
        except Exception as e:
            logger.warning(f"Grup üyeleri kaydedilemedi: {str(e)}")
            return saved_count
            
    async def process_group_messages(self) -> None:
        """
        Gruplara düzenli mesaj gönderme ana döngüsü.
        
        Bu metot, botun grup mesaj gönderim döngüsünü yönetir. Botun aktif olduğu
        gruplara, belirli aralıklarla otomatik mesajlar gönderir. Grup aktivitelerine
        göre adaptif olarak mesaj gönderme sıklığını ayarlar ve ilerleme durumunu
        konsola yansıtır.
        
        Returns:
            None
        """
        progress_mgr = ProgressManager()
        
        logger.info("Grup mesaj döngüsü başlatıldı")
        
        while self.is_running:
            if not self.is_paused:
                try:
                    # Durdurma sinyalini kontrol et
                    if self.stop_event.is_set() or self.shutdown_event.is_set():
                        break
                    
                    current_time = datetime.now()
                    logger.info(f"🔄 Yeni mesaj turu başlıyor: {current_time.strftime('%H:%M:%S')}")
                    
                    # Grupları al 
                    with self.console.status("[bold green]Gruplar alınıyor..."):
                        groups = await self._get_groups()
                        
                    if not groups:
                        logger.warning("Aktif grup bulunamadı. Bir sonraki tura geçiliyor.")
                        await self._interruptible_sleep(60)
                        continue
                    
                    # Grupları önceliklendiriyorsa önceliklendir
                    if self.prioritize_active:
                        groups = await self._prioritize_groups(groups)
                    
                    # İlerleme çubuğu oluştur
                    progress, task_id = progress_mgr.create_progress_bar(
                        total=len(groups),
                        description="Grup Mesaj Gönderimi"
                    )
                    
                    # Başlangıç değerlerini sıfırla
                    self.sent_count = 0
                    
                    with progress:
                        for group in groups:
                            # Mesaj gönderme
                            result = await self._send_message_to_group(group)
                            
                            # İlerlemeyi güncelle
                            if result:
                                progress_mgr.update_progress(
                                    progress, task_id, advance=1,
                                    message=f"Mesaj gönderildi: {group.title}"
                                )
                            else:
                                progress_mgr.update_progress(
                                    progress, task_id, advance=1,
                                    message=f"Hata: {group.title}"
                                )
                                
                            # Gruplar arası bekleme
                            if not self.stop_event.is_set():
                                await asyncio.sleep(5)
                    
                    # Özet göster
                    self.console.print(f"[green]✉️ Bu turda: {self.sent_count} mesaj | 📈 Toplam: {self.total_sent}[/green]")
                    
                    # Bir sonraki tura kadar bekle
                    wait_time = 300  # 5 dakika
                    self.console.print(f"[cyan]⏳ Sonraki tur: {wait_time//60} dakika sonra...[/cyan]")
                    await self._interruptible_sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"Grup mesaj döngüsü hatası: {str(e)}", exc_info=True)
                    self.console.print(f"[red]Hata: {str(e)}[/red]")
                    await asyncio.sleep(30)
            else:
                await asyncio.sleep(1)

    def _handle_group_error(self, group_id: int, error: str) -> None:
        """
        Grup hatalarını yönetir ve hata sayacını artırır.
        
        Args:
            group_id: Hata veren grubun ID'si
            error: Hata mesajı
            
        Returns:
            None
        """
        if group_id not in self.error_groups:
            self.error_groups[group_id] = {
                'count': 0,
                'time': datetime.now()
            }
            
        self.error_groups[group_id]['count'] += 1
        error_count = self.error_groups[group_id]['count']
        
        # Hata nedeni kaydet
        self.error_reasons[group_id] = error
        
        # Maksimum hata sayısı aşılırsa grubu devre dışı bırak
        if hasattr(self.config, 'MAX_ERROR_COUNT') and error_count >= self.config.MAX_ERROR_COUNT:
            if group_id in self.active_groups:
                self.active_groups[group_id]['is_active'] = False
                logger.warning(f"Grup devre dışı bırakıldı (çok fazla hata): {self.active_groups[group_id]['name']}")
            
            # Veritabanında grubu hata durumunda işaretle
            if hasattr(self.db, 'mark_group_error'):
                self.db.mark_group_error(group_id, error)
                
        # İstatistik güncelle
        self.error_count += 1
            
    #
    # MESAJ GÖNDERME METODLARI
    #
            
    async def _send_message_to_group(self, group: Any) -> bool:
        """
        Belirtilen gruba otomatik mesaj gönderir.
        
        Args:
            group: Telethon grup nesnesi
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Mesaj şablonlarını kontrol et
            if not self.messages:
                self.logger.error("Hiç mesaj şablonu bulunamadı!")
                return False
                
            message = random.choice(self.messages)
            
            # Daha az log üret - debug level'a çek
            self.logger.debug(f"📨 '{group.title}' grubuna mesaj gönderiliyor...")
            
            # Telethon client ayarlarında optimizasyon
            await self.client.send_message(
                group.id,
                message,
                schedule=None,
                link_preview=False,  # Önizleme kapatıldı - daha hızlı gönderim
                silent=True,  # Bildirim göndermeyi devre dışı bırak - daha az sunucu yükü
                clear_draft=False  # Taslağı temizlemeye gerek yok - performans artışı
            )
            
            # İstatistikleri güncelle
            self.sent_count += 1
            self.total_sent += 1
            self.processed_groups.add(group.id)
            self.last_message_time = datetime.now()
            self.last_sent_time[group.id] = datetime.now()
            
            # Gereksiz mesajları debug level'a çek
            self.logger.debug(f"✅ Mesaj gönderildi: {group.title}")
            
            # Veritabanı istatistiklerini güncelle - asenkron yap
            if hasattr(self.db, 'update_group_stats'):
                asyncio.create_task(self._update_group_stats(group.id, group.title))
                
            return True
            
        except errors.FloodWaitError as e:
            wait_time = e.seconds + random.randint(2, 5)  # Daha az ek bekleme
            self.logger.warning(f"⚠️ Flood wait hatası: {wait_time}s bekleniyor ({group.title})")
            asyncio.create_task(self._handle_flood_wait(group, wait_time))
            return False
            
        except Exception as e:
            self.logger.error(f"⚠️ Grup mesaj hatası: {group.title} - {str(e)}")
            self._mark_error_group(group, str(e))
            return False
            
    async def handle_group_message(self, event: Any) -> None:
        """
        Grup mesajlarını dinler ve bot mention edildiğinde yanıtlar.
        
        Args:
            event: Telethon mesaj olayı
            
        Returns:
            None
        """
        # Mesaj kontrolü
        if not event.message or not event.message.text:
            return
            
        # Bot mention edildi mi kontrol et
        if event.message.mentioned:
            response = await self._get_random_response()
            try:
                await event.reply(response)
                logger.info(f"Mention yanıtı gönderildi: {response[:20]}...")
            except Exception as e:
                logger.error(f"Yanıt gönderilemedi: {str(e)}")
                
    async def handle_private_message(self, event: Any) -> None:
        """
        Özel mesajları dinler ve davet mesajıyla yanıtlar.
        
        Args:
            event: Telethon mesaj olayı
            
        Returns:
            None
        """
        if not event.message or not event.message.text:
            return
            
        try:
            # Davet mesajını gönder
            invite_message = await self._get_invite_message()
            await event.reply(invite_message)
            logger.info("DM yanıtı gönderildi")
        except Exception as e:
            logger.error(f"DM yanıtı gönderilemedi: {str(e)}")
    
    async def process_group_message(self, message: Any) -> None:
        """
        Gelen grup mesajlarını işler.
        
        Args:
            message: Telethon mesaj nesnesi
            
        Returns:
            None
        """
        try:
            # Mesaj kontrolü 
            if not hasattr(message, 'text') or not message.text:
                return
                
            chat_id = getattr(message, 'chat_id', None)
            if not chat_id:
                return
                
            # Bu mesaja otomatik yanıt vermenin gerekli olup olmadığını kontrol et
            if self._should_auto_respond(message):
                response = await self._get_random_response()
                await self.client.send_message(chat_id, response)
                logger.info(f"Grup mesajına otomatik yanıt gönderildi: {chat_id}")
                
            # Grup aktivite istatistiklerini güncelle
            if hasattr(self.db, 'update_group_activity'):
                self.db.update_group_activity(chat_id)
                
        except Exception as e:
            logger.error(f"Grup mesajı işleme hatası: {str(e)}")
            
    def _should_auto_respond(self, message: Any) -> bool:
        """
        Bir mesaja otomatik yanıt verilmesi gerekip gerekmediğini kontrol eder.
        
        Args:
            message: Telethon mesaj nesnesi
            
        Returns:
            bool: Otomatik yanıt verilmesi gerekiyorsa True
        """
        # Şu anki implementasyonda sadece mention durumunda yanıt veriyoruz
        return hasattr(message, 'mentioned') and message.mentioned
    
    #
    # GRUP AKTİVİTE VE MESAJ ZAMANLAMA
    #
            
    async def _calculate_message_interval(self, group_id: int) -> int:
        """
        Grup aktivite seviyesine göre mesaj aralığını hesaplar.
        
        Args:
            group_id: Grup ID
            
        Returns:
            int: Saniye cinsinden mesaj aralığı
        """
        activity_level = self.group_activity_levels.get(group_id, 'medium')
        
        if activity_level == 'high':
            return random.randint(3, 5) * 60  # 3-5 dakika
        elif activity_level == 'medium':
            return random.randint(5, 7) * 60  # 5-7 dakika
        else:
            return random.randint(7, 8) * 60  # 7-8 dakika
            
    async def _update_group_activity(self, group_id: int) -> str:
        """
        Grup aktivite seviyesini günceller.
        
        Args:
            group_id: Grup ID
            
        Returns:
            str: Aktivite seviyesi ('high', 'medium', 'low')
        """
        try:
            # Veritabanında aktivite bilgisi var mı kontrol et
            if hasattr(self.db, 'get_group_activity_level'):
                activity = self.db.get_group_activity_level(group_id)
                if activity:
                    self.group_activity_levels[group_id] = activity
                    return activity
                    
            # Yoksa son 1 saatteki mesaj sayısını al
            messages = await self.client.get_messages(group_id, limit=100)
            message_count = len([m for m in messages if m.date > datetime.now() - timedelta(hours=1)])
            
            if message_count > 50:
                level = 'high'
            elif message_count > 20:
                level = 'medium'
            else:
                level = 'low'
                
            # Aktivite seviyesini güncelle
            self.group_activity_levels[group_id] = level
            
            # Veritabanında sakla 
            if hasattr(self.db, 'update_group_activity_level'):
                self.db.update_group_activity_level(group_id, level)
                
            return level
                
        except Exception as e:
            logger.debug(f"Grup aktivite seviyesi güncellenemedi: {str(e)}")
            return 'medium'  # Varsayılan seviye
            
    async def _determine_next_schedule(self, group_id: int) -> int:
        """
        Bir grup için adaptif mesaj gönderim zamanını belirler.
        
        Args:
            group_id: Grup ID'si
            
        Returns:
            int: Sonraki gönderime kadar beklenecek süre (saniye)
        """
        try:
            # Veritabanından optimal aralığı sorgula
            if hasattr(self.db, 'get_group_optimal_interval'):
                optimal_interval = await self._run_async_db_method(self.db.get_group_optimal_interval, group_id)
            else:
                # Varsayılan değer
                optimal_interval = 60  # dakika
                
            # Biraz rastgelelik ekle (%20 varyasyon)
            variation_factor = random.uniform(0.8, 1.2)
            next_interval = int(optimal_interval * variation_factor)
            
            # Saniyeye çevir
            next_seconds = next_interval * 60
            
            # Makul bir aralıkta olduğundan emin ol
            return max(15 * 60, min(next_seconds, 6 * 60 * 60))  # 15dk - 6sa arası
            
        except Exception as e:
            logger.error(f"Sonraki gönderim zamanı hesaplama hatası: {e}")
            return 60 * 60  # Varsayılan: 1 saat
    
    #
    # MESAJ ŞABLONLARİ
    #
            
    async def _get_random_message(self) -> str:
        """
        Rastgele bir mesaj şablonu seçer.
        
        Returns:
            str: Seçilen mesaj
        """
        return random.choice(self.messages)
        
    async def _get_random_response(self) -> str:
        """
        Rastgele bir yanıt mesajı seçer.
        
        Returns:
            str: Seçilen yanıt mesajı
        """
        return random.choice(self.responses)
        
    async def _get_invite_message(self) -> str:
        """
        Davet mesajını oluşturur ve formatlayarak döndürür.
        
        Returns:
            str: Formatlanmış davet mesajı
        """
        # Rastgele parçaları seç
        invite = random.choice(self.invites['invites'])
        outro = random.choice(self.invites['invites_outro'])
        redirect = self.invites['redirect_message']
        
        # Footer oluştur
        footer = f"\n\nℹ️ Bilgi ve menü için: @{self.config.SUPER_USERS[0]}"
        
        # Hedef grupları al
        target_groups = self.config.TARGET_GROUPS
        groups_text = "\n".join([f"👉 {group}" for group in target_groups])
        
        # Mesajı birleştir
        return f"{invite}\n\n{groups_text}\n\n{outro}\n{redirect}{footer}"
    
    #
    # YARDIMCI METODLAR
    #

    async def _prioritize_groups(self, groups: List[Any]) -> List[Any]:
        """
        Grupları önceliklendirme - aktivite düzeyine göre.
        
        Args:
            groups: Gruplar listesi
        
        Returns:
            List[Any]: Önceliklendirilmiş gruplar listesi
        """
        # Etkinliği yüksek grupları önceliklendir
        prioritized = []
        normal = []
        
        for group in groups:
            # Grubun aktivite düzeyi kontrolü
            if hasattr(self.db, 'get_group_activity_level'):
                activity_level = self.db.get_group_activity_level(group.id)
                if activity_level == "high":
                    prioritized.append(group)
                else:
                    normal.append(group)
            else:
                # Aktivite bilgisi yoksa normal olarak değerlendir
                normal.append(group)
        
        # Önce öncelikli gruplar, sonra normal gruplar
        return prioritized + normal

    def _create_batches(self, items: List[Any], batch_size: int = 3) -> List[List[Any]]:
        """
        Liste elemanlarını batch'lere böler.
        
        Args:
            items: Parçalanacak liste
            batch_size: Parça büyüklüğü
            
        Returns:
            List[List[Any]]: Parçalanmış liste
        """
        result = []
        for i in range(0, len(items), batch_size):
            result.append(items[i:i+batch_size])
        return result

    async def _get_groups(self) -> List[Any]:
        """
        Bot'un üye olduğu aktif grupları tespit eder.
        
        Returns:
            List[Any]: Aktif grupların listesi
        """
        groups = []
        try:
            # Mevcut grupları ve hata veren grupları kaydet
            dialogs = await self.client.get_dialogs()
            for dialog in dialogs:
                if dialog.is_group:
                    # Hata veren grupları atla
                    if dialog.id not in self.error_groups_set:
                        groups.append(dialog)
            
            # Log mesajı
            if not groups:
                logger.warning("⚠️ Hiç aktif grup bulunamadı!")
            else:
                logger.info(f"✅ Toplam {len(groups)} aktif grup bulundu")
                
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"⚠️ Grupları getirirken flood wait hatası: {wait_time}s bekleniyor")
            await asyncio.sleep(wait_time)
            return []
        except Exception as e:
            logger.error(f"⚠️ Grup getirme hatası: {str(e)}")
            return []
        
        return groups

    async def _update_group_stats(self, group_id: int, group_title: str) -> None:
        """
        Grup istatistiklerini asenkron olarak günceller.
        
        Args:
            group_id: Grup ID
            group_title: Grup adı
            
        Returns:
            None
        """
        try:
            if hasattr(self.db, 'update_group_stats'):
                await self._run_async_db_method(self.db.update_group_stats, group_id, group_title)
            
            if hasattr(self.db, 'mark_message_sent'):
                await self._run_async_db_method(self.db.mark_message_sent, group_id, datetime.now())
        except Exception as e:
            logger.error(f"Grup istatistikleri güncelleme hatası: {e}")

    async def _handle_flood_wait(self, group: Any, wait_time: int) -> None:
        """
        Flood wait hatalarını ayrı bir görevde işler.
        
        Args:
            group: Telethon grup nesnesi
            wait_time: Bekleme süresi (saniye)
            
        Returns:
            None
        """
        try:
            await asyncio.sleep(wait_time)
            logger.info(f"⏱️ {group.title} için bekleme tamamlandı")
        except Exception as e:
            logger.error(f"Flood wait işleme hatası: {e}")
    
    def _mark_error_group(self, group: Any, reason: str) -> None:
        """
        Hata veren grupları işaretleyerek devre dışı bırakır.
        
        Args:
            group: Telethon grup nesnesi
            reason: Hata nedeni
            
        Returns:
            None
        """
        self.error_groups_set.add(group.id)
        self.error_reasons[group.id] = reason
        logger.warning(f"⚠️ Grup devre dışı bırakıldı - {group.title}: {reason}")
        
        # Veritabanında da işaretle
        if hasattr(self.db, 'mark_group_error'):
            self.db.mark_group_error(group.id, reason)
    
    async def _interruptible_sleep(self, duration: int) -> None:
        """
        Kapanış sinyali gelirse uyandırılabilen uyku fonksiyonu.
        
        Args:
            duration: Bekleme süresi (saniye)
            
        Returns:
            None
        """
        try:
            # Küçük parçalar halinde bekleyerek sık sık kontrol et
            for _ in range(min(duration, 300)):  # En fazla 5 dakika
                if self.stop_event.is_set() or self.shutdown_event.is_set():
                    break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.debug("Uyku iptal edildi")
            
    async def _run_async_db_method(self, method: Any, *args, **kwargs) -> Any:
        """
        Veritabanı metodunu async olup olmadığını kontrol ederek çağırır.
        
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
    
    #
    # TOPLU ÜYE TOPLAMA
    #
    
    async def collect_group_members(self) -> int:
        """
        Kullanıcının üye olduğu tüm gruplardan üyeleri toplayıp veritabanına kaydeder.
        Adminler, kurucular ve botlar hariç tutulur.
        
        Returns:
            int: Toplanan toplam üye sayısı
        """
        progress_mgr = ProgressManager()
        self.console.print("[bold cyan]╔══════════════════════════════════════════════════╗")
        self.console.print("[bold cyan]║               GRUP ÜYELERİ TOPLAMA               ║")
        self.console.print("[bold cyan]╚══════════════════════════════════════════════════╝")
        
        logger.info("🔍 Grup üyeleri toplanıyor...")
        
        try:
            # Kullanıcının üye olduğu tüm diyalogları al
            with progress_mgr.console.status("[bold green]Gruplar alınıyor...") as status:
                all_dialogs = await self.client.get_dialogs()
            
            # Sadece grupları ve kanalları filtrele
            groups = [d for d in all_dialogs if d.is_group or d.is_channel]
            
            if not groups:
                progress_mgr.console.print("[yellow]⚠️ Hiç grup bulunamadı! Lütfen birkaç gruba üye olun.[/yellow]")
                return 0
            
            # Grupları göster
            progress_mgr.console.print("")
            table = progress_mgr.console.Table(title="BULUNAN GRUPLAR", show_header=True, header_style="bold magenta")
            table.add_column("#", style="dim", width=4)
            table.add_column("Grup Adı", style="cyan")
            table.add_column("Üye Sayısı", justify="right")
            
            for i, group in enumerate(groups):
                try:
                    participant_count = await self.client.get_participants(group, limit=1)
                    participant_count = "?" if not participant_count else participant_count.total
                except:
                    participant_count = "?"
                    
                table.add_row(f"{i+1}", f"{group.title}", f"{participant_count}")
                
            progress_mgr.console.print(table)
            
            total_members = 0
            successful_groups = 0
            
            # Çoklu ilerleme çubuğu oluştur
            progress, task_id = progress_mgr.create_progress_bar(
                total=len(groups), 
                description="Grup İşleme"
            )
            
            with progress:
                for idx, group in enumerate(groups):
                    try:
                        group_name = group.title
                        progress_mgr.update_progress(progress, task_id, advance=0, 
                                                  message=f"Grup işleniyor: {group_name}")
                        
                        # Grup istatistiklerini veritabanında kaydet/güncelle
                        if hasattr(self.db, 'update_group_stats'):
                            self.db.update_group_stats(group.id, group.title)
                        
                        # Üyeleri alma işlemi için ayrı bir ilerleme çubuğu
                        member_progress, member_task = progress_mgr.create_progress_bar(
                            total=100,  # Başlangıçta toplam bilinmiyor
                            description=f"Üyeler alınıyor: {group_name}"
                        )
                        
                        try:
                            with member_progress:
                                # Grup üyelerini al
                                all_members = []
                                # Sayfa sayfa üyeleri al
                                offset = 0
                                limit = 100
                                while True:
                                    members_page = await self.client.get_participants(
                                        group, offset=offset, limit=limit
                                    )
                                    if not members_page:
                                        break
                                    all_members.extend(members_page)
                                    offset += len(members_page)
                                    
                                    # İlerleme çubuğunu güncelle
                                    member_progress.update(member_task, completed=offset, total=max(offset+1, 100))
                                    
                                    # Her 100 üyede bir biraz bekle
                                    if offset % 100 == 0:
                                        await asyncio.sleep(1)
                                
                                # Adminleri ve kurucuyu bul
                                admins_list = []
                                try:
                                    from telethon.tl.types import ChannelParticipantsAdmins
                                    admins = await self.client.get_participants(group, filter=ChannelParticipantsAdmins)
                                    admins_list = [admin.id for admin in admins]
                                except Exception as e:
                                    logger.warning(f"Admin listesi alınamadı: {group.title} - {str(e)}")
                                
                                # Filtrelenmiş üye listesi (adminler, kurucular ve botlar hariç)
                                filtered_members = [member for member in all_members 
                                                   if not member.bot and not member.deleted and member.id not in admins_list]
                                
                                progress_mgr.console.print(f"[green]► '{group.title}' grubundan {len(filtered_members)} üye bulundu (toplam {len(all_members)}, {len(admins_list)} admin)[/green]")
                                
                                # Üyeleri veritabanına ekle - toplu işlem
                                batch_size = 50
                                
                                batch_progress, batch_task = progress_mgr.create_progress_bar(
                                    total=len(filtered_members), 
                                    description=f"Veritabanına ekleniyor"
                                )
                                
                                with batch_progress:
                                    # Toplu işleme var mı kontrol et
                                    if hasattr(self.user_service, 'add_users_batch'):
                                        # Kullanıcıları grupla (her 50 kullanıcı bir batch)
                                        user_batches = []
                                        current_batch = []
                                        
                                        for member in filtered_members:
                                            user_data = {
                                                'user_id': member.id,
                                                'username': member.username,
                                                'first_name': member.first_name,
                                                'last_name': member.last_name,
                                                'source_group': str(group.title)
                                            }
                                            current_batch.append(user_data)
                                            
                                            if len(current_batch) >= batch_size:
                                                user_batches.append(current_batch)
                                                current_batch = []
                                                
                                        # Son batch'i ekle
                                        if current_batch:
                                            user_batches.append(current_batch)
                                            
                                        # Her batch'i işle
                                        for batch in user_batches:
                                            success, error = await self.user_service.add_users_batch(batch)
                                            total_members += success
                                            
                                            # İlerleme çubuğunu güncelle  
                                            batch_progress.update(batch_task, advance=len(batch))
                                            await asyncio.sleep(0.5)
                                            
                                    else:
                                        # Toplu işleme yoksa tek tek ekle
                                        batch_members_added = 0
                                        for i, member in enumerate(filtered_members):
                                            user_data = {
                                                'user_id': member.id,
                                                'username': member.username,
                                                'first_name': member.first_name,
                                                'last_name': member.last_name,
                                                'source_group': str(group.title)
                                            }
                                            
                                            if hasattr(self.db, 'add_or_update_user'):
                                                self.db.add_or_update_user(user_data)
                                                total_members += 1
                                                batch_members_added += 1
                                            
                                            # İlerleme çubuğunu güncelle
                                            batch_progress.update(batch_task, advance=1)
                                            
                                            # Her 50 kullanıcıda bir bekle
                                            if i % batch_size == 0 and i > 0:
                                                await asyncio.sleep(0.5)
                                
                                successful_groups += 1
                                
                        except errors.FloodWaitError as e:
                            wait_time = e.seconds
                            logger.warning(f"⏳ FloodWaitError: {wait_time} saniye bekleniyor")
                            progress_mgr.console.print(f"[red]⚠️ Hız sınırı aşıldı - {wait_time} saniye bekleniyor[/red]")
                            await asyncio.sleep(wait_time)
                            
                        except Exception as e:
                            logger.error(f"Grup üyelerini getirme hatası: {group.title} - {str(e)}")
                            progress_mgr.console.print(f"[red]✗ Üye toplama hatası: {group.title} - {str(e)}[/red]")
                        
                        # Ana ilerleme çubuğunu güncelle
                        progress_mgr.update_progress(progress, task_id, advance=1)
                        
                        # Her grup arasında bekle
                        await asyncio.sleep(3)
                        
                    except Exception as e:
                        logger.error(f"Grup işleme hatası: {str(e)}")
                        progress_mgr.console.print(f"[red]✗ Genel hata: {group.title} - {str(e)}[/red]")
                        progress_mgr.update_progress(progress, task_id, advance=1)
                        continue
            
            # Özet tablosu
            summary_table = progress_mgr.console.Table(title="TOPLAMA ÖZETI", show_header=False, box=rich.box.DOUBLE)
            summary_table.add_column("Metrik", style="cyan")
            summary_table.add_column("Değer", style="green")
            
            summary_table.add_row("Taranan Gruplar", f"{successful_groups}/{len(groups)}")
            summary_table.add_row("Toplanan Üyeler", f"{total_members}")
            summary_table.add_row("İşlem Süresi", f"{progress.tasks[task_id].elapsed:.1f} saniye")
            
            progress_mgr.console.print(summary_table)
            
            logger.info(f"📊 Toplam {total_members} üye veritabanına eklendi/güncellendi")
            return total_members
            
        except Exception as e:
            logger.error(f"Üye toplama hatası: {str(e)}")
            progress_mgr.console.print(f"[red]✗✗✗ Üye toplama sürecinde kritik hata: {str(e)}[/red]")
            return 0
            
    #
    # DURUM VE İSTATISTİKLER
    #
            
    def get_status(self) -> Dict[str, Any]:
        """
        Servisin durumunu döndürür.
        
        Returns:
            Dict[str, Any]: Servis durumu
        """
        return {
            "running": self.is_running,
            "paused": self.is_paused,
            "active_groups": len(self.active_groups),
            "error_groups": len(self.error_groups_set),
            "messages_sent": self.sent_count,
            "total_sent": self.total_sent,
            "last_message_time": self.last_message_time.strftime("%H:%M:%S") if self.last_message_time else "Hiç",
            "error_count": self.error_count
        }
        
    def get_statistics(self) -> Dict[str, Any]:
        """
        Servis istatistiklerini döndürür.
        
        Returns:
            Dict[str, Any]: İstatistikler
        """
        # Aktif grupları say
        active_count = sum(1 for g in self.active_groups.values() if g['is_active'])
        
        # Hata nedenleri analiz et
        error_types = {}
        for reason in self.error_reasons.values():
            error_type = reason.split(':')[0] if ':' in reason else reason
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        # İstatistikleri topla
        return {
            "total_groups": len(self.active_groups),
            "active_groups": active_count,
            "inactive_groups": len(self.active_groups) - active_count,
            "error_groups": len(self.error_groups_set),
            "messages_sent_total": self.total_sent,
            "messages_sent_session": self.sent_count,
            "messages_failed": self.messages_failed,
            "error_count": self.error_count,
            "error_types": error_types,
            "last_run": self.last_run.strftime("%H:%M:%S"),
            "last_message_time": self.last_message_time.strftime("%H:%M:%S") if self.last_message_time else "Hiç",
            "running_since": (datetime.now() - self.last_run).total_seconds() // 60
        }