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
from datetime import datetime
from typing import Dict, Any, List, Optional
from telethon import errors

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
    
    def __init__(self, client: Any, config: Any, db: Any, stop_event: asyncio.Event):
        """
        GroupService sınıfının başlatıcısı.
        
        Args:
            client: Telethon istemcisi
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
            stop_event: Durdurma sinyali için asyncio.Event nesnesi
        """
        super().__init__("group", client, config, db, stop_event)
        
        # Mesaj şablonları
        with open('data/messages.json', 'r', encoding='utf-8') as f:
            import json
            self.messages = json.load(f)
            
        # Grup yönetimi
        self.active_groups = {}
        self.error_groups = {}
        self.error_groups_set = set()
        self.error_reasons = {}
        self.last_message_times = {}
        self.group_activity_levels = {}
        
        # İstatistikler
        self.total_sent = 0
        self.sent_count = 0
        self.error_count = 0
        
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
                
    def set_services(self, services: Dict[str, Any]) -> None:
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
            
        Returns:
            None
        """
        self.services = services
        
    async def initialize(self) -> bool:
        """
        Servisi başlatmadan önce hazırlar.
        
        Returns:
            bool: Başarılı ise True
        """
        await super().initialize()
        
        logger.info("Grup servisi başlatılıyor...")
        
        # Hedef grupları veritabanından yükle
        target_groups = await self._run_async_db_method(self.db.get_target_groups)
        loaded_count = 0
        
        for group in target_groups:
            group_id = group.get('id')
            if group_id:
                self.active_groups[group_id] = group
                loaded_count += 1
                
        logger.info(f"Hedef gruplar yüklendi: {loaded_count} grup")
        
        # İstatistikleri yükle
        if hasattr(self.db, 'get_total_messages_sent'):
            self.total_sent = await self._run_async_db_method(self.db.get_total_messages_sent)
            
        return True
        
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
            
    async def run(self) -> None:
        """
        Servisin ana çalışma döngüsü.
        
        Returns:
            None
        """
        logger.info("Grup mesaj döngüsü başlatıldı")
        
        # GroupHandler'daki process_group_messages() metodunu buraya taşı
        # Bu çözümü uzun olduğu için yeni bir metoda taşıyorum
        await self.process_group_messages()
    
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
        
        while self.running:
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
                
    async def _get_groups(self) -> List[Any]:
        """
        Bot'un üye olduğu aktif grupları tespit eder.
        
        Returns:
            List[Any]: Aktif grupların listesi
        """
        groups = []
        try:
            # Veritabanından grupları çek (TDLib tarafından keşfedilen gruplar dahil)
            if hasattr(self.db, 'get_active_message_groups'):
                db_groups = await self._run_async_db_method(self.db.get_active_message_groups)
                
                if db_groups:
                    for group in db_groups:
                        # Retry_after süresi dolmuş mu kontrol et
                        retry_time = group.get('retry_after')
                        if retry_time:
                            retry_datetime = datetime.strptime(retry_time, '%Y-%m-%d %H:%M:%S')
                            if datetime.now() < retry_datetime:
                                logger.debug(f"Grup atlanıyor (bekleme süresi): {group['name']} (ID:{group['group_id']})")
                                continue
                        
                        # Mesaj gönderebiliyor muyuz kontrol et
                        if group.get('can_send_messages', True):
                            try:
                                # Grup varlığını doğrula
                                entity = await self.client.get_entity(group['group_id'])
                                groups.append(entity)
                            except Exception as entity_err:
                                logger.warning(f"Grup varlığı alınamadı: {group['name']} (ID:{group['group_id']}) - {str(entity_err)}")
                
            # Telethon üzerinden mevcut diyaloglar
            async for dialog in self.client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    # Hata gruplarını ve yeni keşfedilen grupları atla (zaten yukarıda eklendi)
                    if dialog.id in self.error_groups_set or any(g.id == dialog.id for g in groups):
                        continue
                        
                    groups.append(dialog)
            
            logger.info(f"✅ Toplam {len(groups)} aktif grup bulundu")
                    
        except errors.FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"⚠️ Grupları getirirken flood wait hatası: {wait_time}s bekleniyor")
            await asyncio.sleep(wait_time + 5)
        except Exception as e:
            logger.error(f"Grup getirme hatası: {str(e)}")
        
        return groups
        
    async def _prioritize_groups(self, groups: List[Any]) -> List[Any]:
        """
        Grupları aktivite durumuna göre önceliklendirir.
        
        Args:
            groups: Gruplar listesi
            
        Returns:
            List[Any]: Önceliklendirilmiş gruplar listesi
        """
        # GroupHandler'daki metodu taşı
        # Bu metot grupları aktivite durumuna göre sıralar
        prioritized = sorted(
            groups,
            key=lambda g: self.group_activity_levels.get(g.id, 0),
            reverse=True
        )
        return prioritized
        
    async def _send_message_to_group(self, group: Any) -> bool:
        """
        Bir gruba mesaj gönderir.
        
        Args:
            group: Grup nesnesi
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Mesaj seç
            message = self._select_message()
            
            # Mesajı gönder
            await self.client.send_message(group.id, message)
            
            # İstatistikleri güncelle
            self.sent_count += 1
            self.total_sent += 1
            
            # Son gönderim zamanını güncelle
            self.last_message_times[group.id] = datetime.now()
            
            logger.info(f"Mesaj gönderildi: {group.title}")
            return True
            
        except Exception as e:
            logger.error(f"Mesaj gönderme hatası: {str(e)}")
            self._handle_group_error(group.id, str(e))
            return False
            
    def _select_message(self) -> str:
        """
        Rastgele bir mesaj seçer.
        
        Returns:
            str: Seçilen mesaj
        """
        if not self.messages or not self.messages.get('group'):
            return "👋"
            
        return random.choice(self.messages['group'])
        
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
            self.error_groups[group_id] = {'count': 0, 'last_error': None}
            self.error_groups_set.add(group_id)
            
        self.error_groups[group_id]['count'] += 1
        self.error_groups[group_id]['last_error'] = datetime.now()
        error_count = self.error_groups[group_id]['count']
        
        # Hata nedeni kaydet
        self.error_reasons[group_id] = error
        
        # Hata sayısı maksimum deneme sayısını geçerse grubu devre dışı bırak
        if error_count >= self.max_retries:
            logger.warning(f"Grup {group_id} çok fazla hata verdi, devre dışı bırakılıyor")
            if group_id in self.active_groups:
                del self.active_groups[group_id]
                
    async def _interruptible_sleep(self, seconds: int) -> None:
        """
        Kesilebilir bir bekleme gerçekleştirir.
        
        Args:
            seconds: Beklenecek saniye
            
        Returns:
            None
        """
        for _ in range(seconds):
            if self.stop_event.is_set() or self.shutdown_event.is_set():
                break
            await asyncio.sleep(1)
            
    # Event işleyicileri
    
    async def on_new_user(self, user_id: int, username: str, chat_id: int) -> None:
        """
        Yeni bir kullanıcı olayını işler.
        
        Args:
            user_id: Kullanıcı ID
            username: Kullanıcı adı
            chat_id: Sohbet ID
            
        Returns:
            None
        """
        logger.info(f"Yeni kullanıcı olayı alındı: {user_id} (@{username}) -> {chat_id}")
        
        # Grup aktivite seviyesini artır
        if chat_id not in self.group_activity_levels:
            self.group_activity_levels[chat_id] = 0
        self.group_activity_levels[chat_id] += 1
            
    # Kullanışlı metodlar
    
    async def discover_groups(self) -> int:
        """
        Botun üye olduğu grupları otomatik olarak tespit eder ve veritabanına kaydeder.
        
        Returns:
            int: Keşfedilen grup sayısı
        """
        logger.info("Grup keşfi başlatılıyor...")
        discovered_count = 0
        
        try:
            async for dialog in self.client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    # Grup bilgilerini al
                    group_info = {
                        'id': dialog.id,
                        'title': dialog.title,
                        'entity_type': 'group' if dialog.is_group else 'channel',
                        'discovery_date': datetime.now(),
                        'active': True
                    }
                    
                    # Veritabanına kaydet
                    if hasattr(self.db, 'add_group'):
                        await self._run_async_db_method(self.db.add_group, **group_info)
                        
                    # Aktif gruplara ekle
                    self.active_groups[dialog.id] = group_info
                    
                    discovered_count += 1
                        
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
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'group_id': group_id,
                    'join_date': datetime.now()
                }
                
                # Veritabanına kaydet
                if hasattr(self.db, 'add_group_member'):
                    await self._run_async_db_method(self.db.add_group_member, **user_data)
                    saved_count += 1
                        
            logger.info(f"Grup {group_id} için {saved_count} üye kaydedildi")
            return saved_count
            
        except Exception as e:
            logger.warning(f"Grup üyeleri kaydedilemedi: {str(e)}")
            return saved_count
            
    async def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndürür.
        
        Returns:
            Dict: Servis durum bilgileri
        """
        status = await super().get_status()
        status.update({
            'active_groups_count': len(self.active_groups),
            'error_groups_count': len(self.error_groups),
            'is_paused': self.is_paused,
            'sent_count': self.sent_count,
            'total_sent': self.total_sent
        })
        return status
        
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servisin istatistiklerini döndürür.
        
        Returns:
            Dict: Servis istatistikleri
        """
        return {
            'total_sent': self.total_sent,
            'active_groups_count': len(self.active_groups),
            'error_groups_count': len(self.error_groups),
            'error_count': self.error_count
        }