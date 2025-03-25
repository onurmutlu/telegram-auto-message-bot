"""
Mesaj gönderen bot sınıfı
"""
import asyncio
import random
import logging 
import json
from datetime import datetime
import threading
from typing import List, Set, Dict, Any, Optional, Union
from pathlib import Path

from telethon import TelegramClient, errors, events
from colorama import Fore, Style, init
from tabulate import tabulate

from config.settings import Config
from database.user_db import UserDatabase
from bot.base import BaseBot

init(autoreset=True)
logger = logging.getLogger(__name__)

class MemberMessageBot(BaseBot):
    """
    Telegram gruplarına otomatik mesaj gönderen ve özel mesajları yöneten bot sınıfı
    """
    def __init__(self, api_id: int, api_hash: str, phone: str, 
                 group_links: List[str], user_db: UserDatabase, config=None, debug_mode: bool = False):
        super().__init__(api_id, api_hash, phone, user_db, config)
        
        self.group_links = group_links
        self.processed_groups: Set[int] = set()
        self.responded_users: Set[int] = set()
        self.sent_count = 0
        self.start_time = datetime.now()
        self.last_message_time = None
        
        # Mesajları yükle
        self._load_message_templates()
        
        # Rate limiting için parametreler
        self.pm_delays = {
            'min_delay': 60,     # Min bekleme süresi (saniye)
            'max_delay': 120,    # Max bekleme süresi (saniye)
            'burst_limit': 3,    # Art arda gönderim limiti
            'burst_delay': 600,  # Burst limit sonrası bekleme (10 dk)
            'hourly_limit': 10   # Saatlik maksimum mesaj
        }
        
        # Rate limiting için durum takibi
        self.pm_state = {
            'burst_count': 0,
            'hourly_count': 0,
            'hour_start': datetime.now(),
            'last_pm_time': None,
            'consecutive_errors': 0
        }
        
        # Hata veren grupların hafızadaki kopyası
        self.error_groups: Set[int] = set()
        self.error_reasons: Dict[int, str] = {}
        
        # Başlangıçta veritabanından hata veren grupları yükle
        self._load_error_groups()
        
        self.debug_mode = debug_mode  # Tekrarlanan kullanıcı aktivitelerini gösterip göstermeme
        
        # Aktiviteleri takip etmek için yeni set
        self.displayed_users = set()
        
        # Performans ayarları
        self.bulk_update_size = 10  # Bulk veritabanı güncellemeleri için
        self.connection_retries = 3  # Bağlantı hatası durumunda tekrar deneme sayısı
        self.retry_delay = 5  # Saniye cinsinden her tekrar deneme arasındaki bekleme
        
        # Bellek optimizasyonu
        self.max_cached_users = 1000  # Bellekte saklanacak maksimum kullanıcı sayısı
        self.cache_cleanup_interval = 3600  # Saniye cinsinden önbellek temizleme aralığı
        
        # Terminal çıktıları
        self.terminal_format.update({
            'user_activity_new': f"{Fore.CYAN}👁️ Yeni kullanıcı aktivitesi: {{}}{Style.RESET_ALL}",
            'user_activity_exists': f"{Fore.BLUE}🔄 Tekrar aktivite: {{}}{Style.RESET_ALL}",
            'user_invite_success': f"{Fore.GREEN}✅ Davet gönderildi: {{}}{Style.RESET_ALL}",
            'user_invite_fail': f"{Fore.RED}❌ Davet başarısız: {{}} ({{}}){Style.RESET_ALL}",
            'user_already_invited': f"{Fore.YELLOW}⚠️ Zaten davet edildi: {{}}{Style.RESET_ALL}"
        })
        
    def _load_message_templates(self):
        """Mesaj şablonlarını JSON dosyalarından yükler"""
        try:
            # Grup mesajlarını yükle
            messages_data = Config.load_messages()
            self.messages = messages_data.get('group_messages', [])
            
            # Davet mesajlarını yükle
            invites_data = Config.load_invites()
            self.invite_messages = invites_data.get('invites', [])
            self.invite_outros = invites_data.get('invites_outro', [])
            self.redirect_messages = invites_data.get('redirect_messages', [])
            
            # Flörtöz yanıtları yükle
            responses_data = Config.load_responses()
            self.flirty_responses = responses_data.get('flirty_responses', [])
            
            logger.info("Mesaj şablonları yüklendi")
        except Exception as e:
            logger.error(f"Mesaj şablonları yükleme hatası: {str(e)}")
            # Varsayılan değerler
            self.messages = ["Merhaba! 👋", "Nasılsınız? 🌟"]
            self.invite_messages = ["Grubumuza bekleriz: t.me/{} 👍"]
            self.invite_outros = ["\n\nDiğer gruplarımız 👇\n"]
            self.redirect_messages = ["Gruplarımızda görüşelim! 🙂"]
            self.flirty_responses = ["Teşekkürler! 😊", "Merhaba! 👋"]
    
    async def start(self):
        """Botu başlatır ve görevleri oluşturur"""
        tasks = []
        try:
            logger.info("Bot başlatılıyor...")
            
            # Client başlat
            await self.client.start(phone=self.phone)
            logger.info("🚀 Bot aktif edildi!")
            
            # Grup hata kayıtlarını yönet
            await self._manage_error_groups()
            
            # Periyodik temizleme görevi oluştur
            asyncio.create_task(self._periodic_cleanup())
            
            # Komut dinleyiciyi başlat
            command_task = asyncio.create_task(self.command_listener())
            tasks.append(command_task)
            
            # Mesaj işleyicileri ayarla
            self._setup_message_handlers()
            
            # Grup mesaj görevi
            group_task = asyncio.create_task(self._process_group_messages())
            tasks.append(group_task)
            
            # Özel davet görevi
            invite_task = asyncio.create_task(self._process_personal_invites())
            tasks.append(invite_task)
            
            # Ana görevleri bekle
            await asyncio.gather(*tasks)
            
        except asyncio.CancelledError:
            logger.info("Bot görevleri iptal edildi")
        except Exception as e:
            logger.error(f"Bot çalışma hatası: {str(e)}", exc_info=True)
        finally:
            # Tüm görevleri temizle
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    
            # Bağlantıyı kapat
            await self._cleanup()
    
    async def _manage_error_groups(self):
        """Başlangıçta grup hata kayıtlarını yönetir"""
        error_groups = self.db.get_error_groups()
        if not error_groups:
            logger.info("Hata veren grup kaydı bulunmadı")
            return
        
        # Konsola hata gruplarını göster
        print(f"\n{Fore.YELLOW}⚠️ {len(error_groups)} adet hata veren grup kaydı bulundu:{Style.RESET_ALL}")
        
        error_table = []
        for group_id, group_title, error_reason, error_time, retry_after in error_groups:
            error_table.append([group_id, group_title, error_reason, retry_after])
        
        print(tabulate(error_table, headers=["Grup ID", "Grup Adı", "Hata", "Yeniden Deneme"], tablefmt="grid"))
        
        # Kullanıcıya sor
        print(f"\n{Fore.CYAN}Hata kayıtlarını ne yapmak istersiniz?{Style.RESET_ALL}")
        print(f"{Fore.GREEN}1){Style.RESET_ALL} Kayıtları koru (varsayılan)")
        print(f"{Fore.GREEN}2){Style.RESET_ALL} Tümünü temizle (yeniden deneme)")
        
        try:
            selection = input("\nSeçiminiz (1-2): ").strip() or "1"
            
            if selection == "2":
                cleared = self.db.clear_all_error_groups()
                self.error_groups.clear()
                self.error_reasons.clear()
                logger.info(f"Tüm hata kayıtları temizlendi ({cleared} kayıt)")
                print(f"{Fore.GREEN}✅ {cleared} adet hata kaydı temizlendi{Style.RESET_ALL}")
            else:
                logger.info("Hata kayıtları korundu")
                print(f"{Fore.CYAN}ℹ️ Hata kayıtları korundu{Style.RESET_ALL}")
        except Exception as e:
            logger.error(f"Hata kayıtları yönetim hatası: {str(e)}")
    
    def _setup_message_handlers(self):
        """Telethon mesaj işleyicilerini ayarlar"""
        @self.client.on(events.NewMessage(incoming=True))
        async def message_handler(event):
            try:
                # Özel mesaj mı?
                if event.is_private:
                    await self._handle_private_message(event)
                # Grup mesajı mı?
                else:
                    # Yanıt mı?
                    if (event.is_reply):
                        await self._handle_group_reply(event)
                    # Normal mesaj mı?
                    else:
                        await self._track_active_users(event)
            except Exception as e:
                logger.error(f"Mesaj işleme hatası: {str(e)}")
    
    async def _process_group_messages(self):
        """Gruplara düzenli mesaj gönderir"""
        while self.is_running:
            if not self.is_paused:
                try:
                    # Her turda önce süresi dolmuş hataları temizle
                    cleared_errors = self.db.clear_expired_error_groups()
                    if cleared_errors > 0:
                        logger.info(f"{cleared_errors} adet süresi dolmuş hata kaydı temizlendi")
                        # Hafızadaki hata listesini de güncelle
                        self._load_error_groups()
                    
                    current_time = datetime.now().strftime("%H:%M:%S")
                    logger.info(f"🔄 Yeni tur başlıyor: {current_time}")
                    
                    # Grupları al - DİNAMİK GRUP LİSTESİ
                    groups = await self._get_groups()
                    logger.info(f"📊 Aktif Grup: {len(groups)} | ⚠️ Devre Dışı: {len(self.error_groups)}")
                    
                    # Mesaj gönderimleri için sayaç
                    tur_mesaj_sayisi = 0
                    
                    # Her gruba mesaj gönder
                    for group in groups:
                        if not self.is_running or self.is_paused:
                            break
                            
                        success = await self._send_message_to_group(group)
                        if success:
                            tur_mesaj_sayisi += 1
                            logger.info(f"✅ Mesaj gönderildi: {group.title}")
                        
                        # Mesajlar arasında bekle
                        await asyncio.sleep(random.randint(8, 15))
                    
                    # Tur istatistiklerini göster
                    logger.info(f"✉️ Turda: {tur_mesaj_sayisi} | 📈 Toplam: {self.sent_count}")
                    
                    # Tur sonrası bekle
                    wait_time = 8 * 60  # 8 dakika
                    logger.info(f"⏳ Bir sonraki tur için {wait_time//60} dakika bekleniyor...")
                    await self.wait_with_countdown(wait_time)
                    
                except Exception as e:
                    logger.error(f"Grup mesaj döngüsü hatası: {str(e)}", exc_info=True)
                    await asyncio.sleep(60)
            else:
                # Duraklatıldıysa her saniye kontrol et
                await asyncio.sleep(1)
    
    async def _process_personal_invites(self):
        """Özel davetleri işler"""
        while self.is_running:
            if not self.is_paused:
                try:
                    # Saatte bir çalışsın
                    await asyncio.sleep(3600)
                    
                    # Davet edilecek kullanıcıları al
                    users_to_invite = self.db.get_users_to_invite(limit=5)
                    if not users_to_invite:
                        logger.info("📪 Davet edilecek kullanıcı bulunamadı")
                        continue
                        
                    logger.info(f"📩 {len(users_to_invite)} kullanıcıya davet gönderiliyor...")
                    
                    # Her kullanıcıya davet gönder
                    for user_id, username in users_to_invite:
                        # Rate limiting ve diğer kontrolleri yap
                        if self.pm_state['hourly_count'] >= self.pm_delays['hourly_limit']:
                            logger.warning("⚠️ Saatlik mesaj limiti doldu!")
                            break
                            
                        # Özel mesaj gönder
                        invite_message = self._create_invite_message()
                        if await self._send_personal_message(user_id, invite_message):
                            self.db.mark_as_invited(user_id)
                            logger.info(f"✅ Davet gönderildi: {username or user_id}")
                        
                        # Davetler arasında bekle
                        await asyncio.sleep(random.randint(60, 120))
                        
                except Exception as e:
                    logger.error(f"Özel davet hatası: {str(e)}", exc_info=True)
                    await asyncio.sleep(300)
            else:
                await asyncio.sleep(1)
    
    async def _get_groups(self) -> List:
        """Aktif grupları getirir - her seferinde yeni liste oluşturur"""
        groups = []
        try:
            # Mevcut grupları ve hata veren grupları kaydet
            async for dialog in self.client.iter_dialogs():
                # Sadece grupları al
                if dialog.is_group:
                    # Eğer hata verenler arasında değilse listeye ekle
                    if dialog.id not in self.error_groups:
                        groups.append(dialog)
                    else:
                        logger.debug(
                            f"Grup atlandı (hata kayıtlı): {dialog.title} (ID:{dialog.id})",
                            extra={
                                'group_id': dialog.id,
                                'group_title': dialog.title,
                                'error_reason': self.error_reasons.get(dialog.id, "Bilinmeyen hata")
                            }
                        )
            
            logger.info(f"Toplam {len(groups)} aktif grup bulundu")
        except Exception as e:
            logger.error(f"Grup getirme hatası: {str(e)}")
        
        return groups
    
    async def _send_message_to_group(self, group) -> bool:
        """Gruba mesaj gönderir"""
        try:
            message = random.choice(self.messages)
            
            # Mesaj gönderimi öncesi log
            logger.debug(
                f"Mesaj gönderiliyor: Grup={group.title} (ID:{group.id})",
                extra={
                    'group_id': group.id,
                    'group_title': group.title,
                    'message': message[:50] + ('...' if len(message) > 50 else '')
                }
            )
            
            # Konsol çıktısı
            print(f"{Fore.MAGENTA}📨 Gruba Mesaj: '{group.title}' grubuna mesaj gönderiliyor{Style.RESET_ALL}")
            
            # Mesajı gönder
            await self.client.send_message(group.id, message)
            
            # İstatistikleri güncelle
            self.sent_count += 1
            self.processed_groups.add(group.id)
            self.last_message_time = datetime.now()
            
            # Başarılı gönderim logu
            logger.info(
                f"Mesaj başarıyla gönderildi: {group.title} (ID:{group.id})",
                extra={
                    'group_id': group.id, 
                    'group_title': group.title,
                    'message_id': self.sent_count,
                    'timestamp': self.last_message_time.strftime('%H:%M:%S')
                }
            )
            
            return True
            
        except errors.FloodWaitError as e:
            # Flood Wait hatası için özel işlem
            wait_time = e.seconds + random.randint(5, 15)  # Ekstra bekleme ekle
            logger.warning(
                f"Flood wait hatası: {wait_time} saniye bekleniyor ({group.title} - ID:{group.id})",
                extra={
                    'error_type': 'FloodWaitError',
                    'group_id': group.id,
                    'group_title': group.title,
                    'wait_time': wait_time
                }
            )
            await asyncio.sleep(wait_time)
            return False
        except (errors.ChatWriteForbiddenError, errors.UserBannedInChannelError) as e:
            # Erişim engelleri için kalıcı olarak devre dışı bırak
            error_reason = f"Erişim engeli: {str(e)}"
            self._mark_error_group(group, error_reason)
            
            # Veritabanına da kaydet - 8 saat sonra yeniden dene
            self.db.add_error_group(group.id, group.title, error_reason, retry_hours=8)
            
            logger.error(
                f"Grup erişim hatası: {group.title} (ID:{group.id}) - {error_reason}",
                extra={
                    'error_type': e.__class__.__name__,
                    'group_id': group.id,
                    'group_title': group.title,
                    'error_message': str(e),
                    'action': 'devre_dışı_bırakıldı',
                    'retry_after': '8 saat'
                }
            )
            return False
            
        except Exception as e:
            # Diğer hatalar için de hata grubuna ekle
            if "The channel specified is private" in str(e):
                error_reason = f"Erişim engeli: {str(e)}"
                self._mark_error_group(group, error_reason)
                self.db.add_error_group(group.id, group.title, error_reason, retry_hours=8)
                logger.error(f"Grup erişim hatası: {group.title} (ID:{group.id}) - {error_reason}")
            else:
                # Geçici hata olabilir
                logger.error(
                    f"Grup mesaj hatası: {group.title} (ID:{group.id}) - {str(e)}",
                    extra={
                        'error_type': e.__class__.__name__,
                        'group_id': group.id,
                        'group_title': group.title,
                        'error_message': str(e)
                    }
                )
            
            if "Too many requests" in str(e):
                await asyncio.sleep(60)  # Rate limiting için uzun süre bekle
            else:
                await asyncio.sleep(5)  # Diğer hatalar için kısa bekle
            return False
    
    async def _send_personal_message(self, user_id: int, message: str) -> bool:
        """Kullanıcıya özel mesaj gönderir"""
        try:
            # Akıllı gecikme uygula
            await self._smart_delay()
            
            # Mesaj gönder
            await self.client.send_message(user_id, message)
            
            # İstatistikleri güncelle
            self.pm_state['burst_count'] += 1
            self.pm_state['hourly_count'] += 1
            self.pm_state['consecutive_errors'] = 0
            self.pm_state['last_pm_time'] = datetime.now()
            
            return True
            
        except errors.FloodWaitError as e:
            logger.warning(f"⚠️ Flood wait: {e.seconds} saniye bekleniyor")
            await asyncio.sleep(e.seconds)
            self.pm_state['consecutive_errors'] += 1
        except Exception as e:
            logger.error(f"Özel mesaj hatası: {str(e)}")
            self.pm_state['consecutive_errors'] += 1
            await asyncio.sleep(30)
            
        return False
    
    async def _smart_delay(self) -> None:
        """Gelişmiş akıllı gecikme sistemi"""
        try:
            current_time = datetime.now()
            
            # Saatlik limit sıfırlama
            if (current_time - self.pm_state['hour_start']).total_seconds() >= 3600:
                self.pm_state['hourly_count'] = 0
                self.pm_state['hour_start'] = current_time
                logger.debug("Saatlik sayaç sıfırlandı")
            
            # Ardışık hata oranına göre gecikme artışı
            if self.pm_state['consecutive_errors'] > 0:
                # Her ardışık hata için gecikmeyi iki kat artır (exp backoff)
                error_delay = min(300, 5 * (2 ** self.pm_state['consecutive_errors']))
                logger.info(f"⚠️ {self.pm_state['consecutive_errors']} ardışık hata nedeniyle {error_delay} saniye ek bekleme")
                await asyncio.sleep(error_delay)
            
            # Burst kontrolü - art arda gönderim sınırı
            if self.pm_state['burst_count'] >= self.pm_delays['burst_limit']:
                logger.info(f"⏳ Art arda gönderim limiti aşıldı: {self.pm_delays['burst_delay']} saniye bekleniyor")
                await asyncio.sleep(self.pm_delays['burst_delay'])
                self.pm_state['burst_count'] = 0
            
            # Son mesajdan bu yana geçen süre
            if self.pm_state['last_pm_time']:
                time_since_last = (current_time - self.pm_state['last_pm_time']).total_seconds()
                min_delay = self.pm_delays['min_delay']
                
                # Henüz minimum süre geçmemişse bekle
                if time_since_last < min_delay:
                    wait_time = min_delay - time_since_last
                    logger.debug(f"Son mesajdan bu yana {time_since_last:.1f}s geçti, {wait_time:.1f}s daha bekleniyor")
                    await asyncio.sleep(wait_time)
            
            # Doğal görünmesi için rastgele gecikme
            human_delay = random.randint(3, 10)  # İnsan gibi yazma gecikmesi
            await asyncio.sleep(human_delay)
            
        except Exception as e:
            logger.error(f"Akıllı gecikme hesaplama hatası: {str(e)}")
            # Hata durumunda güvenli varsayılan bekleme
            await asyncio.sleep(60)
    
    def _mark_error_group(self, group, reason: str) -> None:
        """Hata veren grubu işaretler"""
        self.error_groups.add(group.id)
        self.error_reasons[group.id] = reason
        logger.warning(f"⚠️ Grup devre dışı bırakıldı - {group.title}: {reason}")
    
    def _create_invite_message(self) -> str:
        """Davet mesajı oluşturur"""
        # Rastgele davet mesajı ve outro seç
        random_invite = random.choice(self.invite_messages)
        outro = random.choice(self.invite_outros)
        
        # Grup bağlantılarını oluştur
        group_links = "\n".join([f"• t.me/{link}" for link in self.group_links])
        
        # Mesajı formatla
        return f"{random_invite.format(self.group_links[0])}{outro}{group_links}"
    
    async def _handle_private_message(self, event) -> None:
        """Özel mesajları yanıtlar"""
        try:
            user = await event.get_sender()
            if user is None:
                logger.debug("Özel mesaj için kullanıcı bilgisi alınamadı")
                return
                
            user_id = user.id
            
            # Bot veya yönetici mi kontrol et - güvenli kontroller
            is_bot = hasattr(user, 'bot') and user.bot
            is_admin = hasattr(user, 'admin_rights') and user.admin_rights
            is_creator = hasattr(user, 'creator') and user.creator
            
            if is_bot or is_admin or is_creator:
                logger.info(f"❌ Özel mesaj atlandı: {getattr(user, 'username', None) or user_id} (Bot/Yönetici)")
                return
            
            # Daha önce davet edilmiş mi?
            if self.db.is_invited(user_id):
                # Yönlendirme mesajı gönder
                redirect = random.choice(self.redirect_messages)
                await event.reply(redirect)
                logger.info(f"↩️ Kullanıcı gruba yönlendirildi: {user.username or user_id}")
                return
            
            # Davet mesajı gönder
            invite_message = self._create_invite_message()
            await event.reply(invite_message)
            
            # Kullanıcıyı işaretle
            self.db.mark_as_invited(user_id)
            logger.info(f"✅ Grup daveti gönderildi: {user.username or user_id}")
            
        except Exception as e:
            logger.error(f"Özel mesaj yanıtlama hatası: {str(e)}")
    
    async def _handle_group_reply(self, event) -> None:
        """Grup yanıtlarını işler"""
        try:
            # Yanıtlanan mesajı al
            replied_msg = await event.get_reply_message()
            
            # Yanıtlanan mesaj bizim mesajımız mı?
            if replied_msg and replied_msg.sender_id == (await self.client.get_me()).id:
                # Flörtöz yanıt gönder
                flirty_response = random.choice(self.flirty_responses)
                await event.reply(flirty_response)
                logger.info(f"💬 Flörtöz yanıt gönderildi: {event.chat.title}")
                
        except Exception as e:
            logger.error(f"Grup yanıt hatası: {str(e)}")
    
    async def _track_active_users(self, event) -> None:
        """Aktif kullanıcıları takip eder"""
        try:
            user = await event.get_sender()
            if not user:
                logger.debug("Kullanıcı bilgisi alınamadı")
                return
                
            user_id = getattr(user, 'id', None)
            if not user_id:
                logger.debug("Kullanıcı ID'si alınamadı")
                return
                
            username = getattr(user, 'username', None)
            user_info = f"@{username}" if username else f"ID:{user_id}"
            
            # Bot veya yönetici mi kontrol et - güvenli kontrollerle
            is_bot = hasattr(user, 'bot') and user.bot
            is_admin = hasattr(user, 'admin_rights') and user.admin_rights
            is_creator = hasattr(user, 'creator') and user.creator
            
            if is_bot or is_admin or is_creator:
                if user_info not in self.displayed_users:
                    logger.debug(f"Bot/Admin kullanıcısı atlandı: {user_info}")
                return
            
            # Kullanıcı daha önce gösterildi mi?
            if user_info in self.displayed_users:
                # Loglama seviyesini düşür
                if self.debug_mode:
                    print(self.terminal_format['user_activity_exists'].format(user_info))
                return
                
            # Yeni kullanıcıyı göster ve listeye ekle
            self.displayed_users.add(user_info)
            
            # Veritabanı kontrolü
            was_invited = self.db.is_invited(user_id)
            was_recently_invited = self.db.was_recently_invited(user_id, 4)
            
            invite_status = ""
            if was_invited:
                invite_status = " (✓ Davet edildi)"
            elif was_recently_invited:
                invite_status = " (⏱️ Son 4 saatte davet edildi)" 
            
            # Konsol çıktısı
            print(self.terminal_format['user_activity_new'].format(
                f"{user_info}{invite_status}"
            ))
            
            # Kullanıcıyı veritabanına ekle
            self.db.add_user(user_id, username)
            
        except Exception as e:
            logger.error(f"Kullanıcı takip hatası: {str(e)}")
    
    async def _invite_user(self, user_id: int, username: Optional[str]) -> bool:
        """Kullanıcıya özel davet mesajı gönderir"""
        try:
            # Kullanıcı bilgisini log
            user_info = f"@{username}" if username else f"ID:{user_id}"
            
            # Daha önce davet edilmiş mi?
            if self.db.is_invited(user_id) or self.db.was_recently_invited(user_id, 4):
                print(self.terminal_format['user_already_invited'].format(user_info))
                logger.debug(f"Zaten davet edilmiş kullanıcı atlandı: {user_info}")
                return False
            
            logger.debug(
                f"Kullanıcı davet ediliyor: {user_info}",
                extra={
                    'user_id': user_id,
                    'username': username
                }
            )
            
            # Davet mesajını oluştur ve gönder
            message = self._create_invite_message()
            await self.client.send_message(user_id, message)
            
            # Veritabanını güncelle
            self.db.update_last_invited(user_id)
            
            # Başarılı işlem logu
            logger.info(
                f"Davet başarıyla gönderildi: {user_info}",
                extra={
                    'user_id': user_id,
                    'username': username,
                    'invite_time': datetime.now().strftime('%H:%M:%S')
                }
            )
            
            # Konsol çıktısı
            print(self.terminal_format['user_invite_success'].format(user_info))
            
            return True
            
        except errors.FloodWaitError as e:
            # Flood Wait hatası
            self.pm_state['consecutive_errors'] += 1
            wait_time = e.seconds + random.randint(10, 30)
            
            print(self.terminal_format['user_invite_fail'].format(user_info, f"FloodWait: {wait_time}s"))
            
            logger.warning(
                f"Kullanıcı davet FloodWait hatası: {wait_time} saniye bekleniyor ({user_info})",
                extra={
                    'error_type': 'FloodWaitError',
                    'user_id': user_id,
                    'username': username,
                    'wait_time': wait_time
                }
            )
            await asyncio.sleep(wait_time)
            return False
            
        except (errors.UserIsBlockedError, errors.UserIdInvalidError, errors.PeerIdInvalidError) as e:
            # Kalıcı hatalar - bu kullanıcıyı işaretleyerek atlayabiliriz
            print(self.terminal_format['user_invite_fail'].format(user_info, f"Kalıcı hata: {e.__class__.__name__}"))
            
            logger.error(
                f"Kullanıcı davet hatası (kalıcı): {user_info} - {str(e)}",
                extra={
                    'error_type': e.__class__.__name__,
                    'user_id': user_id,
                    'username': username,
                    'error_message': str(e),
                    'action': 'kalıcı_engel_işaretlendi'
                }
            )
            # Kullanıcıyı veritabanında işaretle
            self.db.mark_user_blocked(user_id)
            return False
            
        except Exception as e:
            # Diğer hatalar
            self.pm_state['consecutive_errors'] += 1
            print(self.terminal_format['user_invite_fail'].format(user_info, f"Hata: {e.__class__.__name__}"))
            
            logger.error(
                f"Kullanıcı davet hatası: {user_info} - {str(e)}",
                extra={
                    'error_type': e.__class__.__name__,
                    'user_id': user_id,
                    'username': username,
                    'error_message': str(e)
                }
            )
            await asyncio.sleep(30)  # Genel hata durumunda bekle
            return False
    
    def show_status(self):
        """Bot durumunu detaylı gösterir"""
        super().show_status()  # Temel durum raporunu çalıştır
        
        # Ek olarak davetlerle ilgili bilgiler
        print(f"\n{Fore.CYAN}📨 DAVET İSTATİSTİKLERİ{Style.RESET_ALL}")
        
        davet_stats = [
            ["Saatlik Gönderim Limiti", f"{self.pm_state['hourly_count']}/{self.pm_delays['hourly_limit']}"],
            ["Art Arda Gönderim Sayısı", f"{self.pm_state['burst_count']}/{self.pm_delays['burst_limit']}"],
            ["Ardışık Hatalar", self.pm_state['consecutive_errors']],
        ]
        
        if self.pm_state['last_pm_time']:
            davet_stats.append(["Son Davet Zamanı", self.pm_state['last_pm_time'].strftime('%H:%M:%S')])
        
        print(tabulate(davet_stats, headers=["Özellik", "Değer"], tablefmt="grid"))

    def _load_error_groups(self):
        """Veritabanından hata veren grupları yükler"""
        error_groups = self.db.get_error_groups()
        for group_id, group_title, error_reason, _, _ in error_groups:
            self.error_groups.add(group_id)
            self.error_reasons[group_id] = error_reason
            
        if self.error_groups:
            logger.info(f"{len(self.error_groups)} adet hata veren grup yüklendi")

    async def _periodic_cleanup(self):
        """Periyodik temizleme işlemleri yapar"""
        while self.is_running:
            try:
                await asyncio.sleep(600)  # 10 dakikada bir çalıştır
                
                # Süresi dolmuş hataları temizle
                cleared_errors = self.db.clear_expired_error_groups()
                if cleared_errors > 0:
                    logger.info(f"{cleared_errors} adet süresi dolmuş hata kaydı temizlendi")
                    # Hafızadaki hata listesini de güncelle
                    self._load_error_groups()
                    
                # Aktivite listesini belirli bir boyutta tut
                if len(self.displayed_users) > 500:  # Örnek limit
                    logger.info(f"Aktivite takip listesi temizleniyor ({len(self.displayed_users)} -> 100)")
                    # En son eklenen 100 kullanıcıyı tut
                    self.displayed_users = set(list(self.displayed_users)[-100:])
                    
            except Exception as e:
                logger.error(f"Periyodik temizleme hatası: {str(e)}")
    
    async def shutdown(self):
        """Bot'u düzgün şekilde kapatır ve final istatistiklerini gösterir"""
        try:
            # Çalışma istatistikleri
            print(f"\n{Fore.CYAN}=== BOT ÇALIŞMA İSTATİSTİKLERİ ==={Style.RESET_ALL}")
            
            # Oturum süresi
            uptime = datetime.now() - self.start_time
            hours, remainder = divmod(uptime.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            print(f"{Fore.GREEN}▶ Çalışma süresi:{Style.RESET_ALL} {int(hours)}:{int(minutes):02}:{int(seconds):02}")
            
            # Mesaj istatistikleri
            print(f"{Fore.GREEN}▶ Toplam gönderilen mesaj:{Style.RESET_ALL} {self.sent_count}")
            
            # Hata istatistikleri
            print(f"{Fore.GREEN}▶ Hata veren grup sayısı:{Style.RESET_ALL} {len(self.error_groups)}")
            
            # Veritabanı istatistikleri
            stats = self.db.get_database_stats()
            print(f"{Fore.GREEN}▶ Toplam kullanıcı sayısı:{Style.RESET_ALL} {stats['total_users']}")
            print(f"{Fore.GREEN}▶ Davet edilen kullanıcı sayısı:{Style.RESET_ALL} {stats['invited_users']}")
            print(f"{Fore.CYAN}==========================================={Style.RESET_ALL}\n")
            
        except Exception as e:
            logger.error(f"İstatistik gösterme hatası: {str(e)}")
        
        # Client bağlantısını kapat
        if hasattr(self, 'client') and self.client:
            await self.client.disconnect()
            logger.info("Client bağlantısı kapatıldı")