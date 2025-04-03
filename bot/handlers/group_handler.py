"""
# ============================================================================ #
# Dosya: group_handler.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/handlers/group_handler.py
# İşlev: Telegram bot için grup mesaj yönetimi ve otomatik mesaj gönderimi.
#
# Build: 2025-04-01-02:45:00
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, bot'un üye olduğu gruplara otomatik mesaj gönderim mekanizmasını içerir.
# Temel özellikleri:
# - Aktif grupların dinamik olarak tespit edilmesi
# - Hata yönetimi ve hata veren grupların geçici olarak devre dışı bırakılması
# - Farklı gruplara düzenli ve otomatik mesaj gönderimi
# - Anti-spam korumalı mesaj akışı kontrolü ve akıllı gecikme mekanizmaları
# - Grup bazlı hata takibi ve otomatik yeniden deneme sistemi
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import random
import logging
from datetime import datetime
from colorama import Fore, Style
from rich import box
from rich.console import Console
from rich.table import Table
import rich
import threading

from telethon import errors

logger = logging.getLogger(__name__)

class GroupHandler:
    def __init__(self, client, config, db, stop_event=None):
        """
        GroupHandler sınıfının başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
            stop_event: Durdurma sinyali için threading.Event nesnesi
        """
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = stop_event if stop_event else threading.Event()
        
        # Bot özellikleri
        self.is_running = True
        self.is_paused = False
        self.messages_sent = 0
        self.messages_failed = 0
        self.last_run = datetime.now()
        self.error_groups = set()
        self.error_reasons = {}
        self.sent_count = 0
        self.processed_groups = set()
        self.last_message_time = datetime.now()
        self.last_sent_time = {}
        
        # Mesaj şablonları
        self.messages = []
        if hasattr(self.config, 'message_templates'):
            self.messages = self.config.message_templates
        
        # Debug için loglama düzeyini artır
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        # Konsolda debug mesajlarını görmek için handler ekleyin
        if not self.logger.handlers:
            console = logging.StreamHandler()
            console.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console.setFormatter(formatter)
            self.logger.addHandler(console)
        
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
    
    async def process_group_messages(self):
        """Gruplara düzenli mesaj gönderme ana döngüsü."""
        from bot.utils.progress import ProgressManager
        from bot.utils.terminal import console
        
        progress_mgr = ProgressManager()
        
        while self.is_running:
            if not self.is_paused:
                try:
                    # Durdurma sinyalini kontrol et
                    if self.stop_event and self.stop_event.is_set():
                        break
                    
                    current_time = datetime.now()
                    self.logger.info(f"🔄 Yeni mesaj turu başlıyor: {current_time.strftime('%H:%M:%S')}")
                    
                    # Grupları al 
                    with console.status("[bold green]Gruplar alınıyor..."):
                        groups = await self._get_groups()
                    
                    # İlerleme çubuğu oluştur
                    progress, task_id = progress_mgr.create_progress_bar(
                        total=len(groups),
                        description="Grup Mesaj Gönderimi"
                    )
                    
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
                            await asyncio.sleep(5)
                    
                    # Özet göster
                    console.print(f"[green]✉️ Bu turda: {self.sent_count} mesaj | 📈 Toplam: {self.total_sent}[/green]")
                    
                    # Bir sonraki tura kadar bekle
                    wait_time = 300  # 5 dakika
                    console.print(f"[cyan]⏳ Sonraki tur: {wait_time//60} dakika sonra...[/cyan]")
                    await self._interruptible_sleep(wait_time)
                    
                except Exception as e:
                    self.logger.error(f"Grup mesaj döngüsü hatası: {str(e)}")
                    console.print(f"[red]Hata: {str(e)}[/red]")
                    await asyncio.sleep(30)
            else:
                await asyncio.sleep(1)

    async def _prioritize_groups(self, groups):
        """
        Grupları önceliklendirme - aktivite düzeyine göre
        
        Args:
            groups: Gruplar listesi
        
        Returns:
            list: Önceliklendirilmiş gruplar listesi
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

    def _create_batches(self, items, batch_size=3):
        """Liste elemanlarını batch'lere böl"""
        for i in range(0, len(items), batch_size):
            yield items[i:i+batch_size]

    async def _get_groups(self):
        """Bot'un üye olduğu aktif grupları tespit eder."""
        groups = []
        try:
            # Mevcut grupları ve hata veren grupları kaydet
            # self.bot.client yerine self.client kullan
            dialogs = await self.client.get_dialogs()
            for dialog in dialogs:
                if dialog.is_group:
                    # self.bot.error_groups yerine self.error_groups kullan
                    if dialog.id not in self.error_groups:
                        groups.append(dialog)
            
            # Geri kalan kodu değiştirmeden bırak
            if not groups:
                print(f"{Fore.RED}⚠️ Hiç aktif grup bulunamadı!{Style.RESET_ALL}")
            else:
                print(f"{Fore.GREEN}✅ Toplam {len(groups)} aktif grup bulundu{Style.RESET_ALL}")
                
        except errors.FloodWaitError as e:
            print(f"{Fore.RED}⚠️ Grupları getirirken flood wait hatası: {e.seconds}s bekleniyor{Style.RESET_ALL}")
            await asyncio.sleep(e.seconds)
            return []
        except Exception as e:
            print(f"{Fore.RED}⚠️ Grup getirme hatası: {str(e)}{Style.RESET_ALL}")
            return []
        
        return groups
    
    async def _send_message_to_group(self, group):
        """Belirtilen gruba otomatik mesaj gönderir."""
        try:
            # self.bot.messages yerine self.messages kullan
            if not self.messages:
                self.logger.error("Hiç mesaj şablonu bulunamadı!")
                return False
                
            message = random.choice(self.messages)
            
            # Daha az log üret - debug level'a çek
            self.logger.debug(f"📨 Gruba Mesaj: '{group.title}' grubuna mesaj gönderiliyor...")
            
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
            self.processed_groups.add(group.id)
            self.last_message_time = datetime.now()
            
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
            return False

    async def _update_group_stats(self, group_id, group_title):
        """Grup istatistiklerini asenkron olarak güncelle"""
        try:
            self.db.update_group_stats(group_id, group_title)
            self.db.mark_message_sent(group_id, datetime.now())
        except Exception as e:
            self.logger.error(f"Grup istatistikleri güncelleme hatası: {e}")

    async def _handle_flood_wait(self, group, wait_time):
        """Flood wait hatalarını ayrı bir görevde işle"""
        try:
            await asyncio.sleep(wait_time)
            self.logger.info(f"⏱️ {group.title} için bekleme tamamlandı")
        except Exception as e:
            self.logger.error(f"Flood wait işleme hatası: {e}")
    
    def _mark_error_group(self, group, reason: str):
        """Hata veren grupları işaretleyerek devre dışı bırakır."""
        # self.bot.error_groups, self.bot.error_reasons yerine self özelliklerini kullan
        self.error_groups.add(group.id)
        self.error_reasons[group.id] = reason
        self.logger.warning(f"⚠️ Grup devre dışı bırakıldı - {group.title}: {reason}")
    
    async def _interruptible_sleep(self, duration):
        """
        Kapanış sinyali gelirse uyandırılabilen uyku fonksiyonu.
        """
        try:
            await asyncio.sleep(duration)
        except asyncio.CancelledError:
            logger.debug("Uyku iptal edildi")

    async def _determine_next_schedule(self, group_id):
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
                optimal_interval = self.db.get_group_optimal_interval(group_id)
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

    def process_group_message(self, message):
        # Grup mesajlarını işle
        print(f"Grup mesajı alındı: {message.text}")
        # self.bot.send_message yerine self.client.send_message kullanın
        self.client.send_message(message.chat.id, "Grup mesajı işleniyor...")

    async def collect_group_members(self):
        """
        Kullanıcının üye olduğu tüm gruplardan üyeleri toplayıp veritabanına kaydeder.
        Adminler, kurucular ve botlar hariç tutulur.
        """
        from bot.utils.progress import ProgressManager
        
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
                                batch_count = (len(filtered_members) + batch_size - 1) // batch_size
                                
                                batch_progress, batch_task = progress_mgr.create_progress_bar(
                                    total=len(filtered_members), 
                                    description=f"Veritabanına ekleniyor"
                                )
                                
                                with batch_progress:
                                    for i in range(0, len(filtered_members), batch_size):
                                        batch = filtered_members[i:i+batch_size]
                                        batch_members_added = 0
                                        
                                        for member in batch:
                                            if hasattr(self.db, 'add_or_update_user'):
                                                # Kaynak grup bilgisini de ekle
                                                user_data = {
                                                    'user_id': member.id,
                                                    'username': member.username,
                                                    'first_name': member.first_name,
                                                    'last_name': member.last_name,
                                                    'source_group': str(group.title)
                                                }
                                                self.db.add_or_update_user(user_data)
                                                total_members += 1
                                                batch_members_added += 1
                                            
                                            # İlerleme çubuğunu güncelle
                                            batch_progress.update(batch_task, advance=1)
                                        
                                        # Her batch sonrası biraz bekle
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