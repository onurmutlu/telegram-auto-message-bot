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
                 group_links: List[str], user_db: UserDatabase, config=None):
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
            # Client başlat
            await self.client.start(phone=self.phone)
            logger.info("🚀 Bot aktif edildi!")
            
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
                    if event.is_reply:
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
                    current_time = datetime.now().strftime("%H:%M:%S")
                    logger.info(self.terminal_format['tur_baslangic'].format(current_time))
                    
                    # Grupları al
                    groups = await self._get_groups()
                    logger.info(self.terminal_format['grup_sayisi'].format(len(groups), len(self.error_groups)))
                    
                    # Mesaj gönderimleri için sayaç
                    tur_mesaj_sayisi = 0
                    
                    # Her gruba mesaj gönder
                    for group in groups:
                        if not self.is_running or self.is_paused:
                            break
                            
                        success = await self._send_message_to_group(group)
                        if success:
                            tur_mesaj_sayisi += 1
                            logger.info(self.terminal_format['basari'].format(f"Mesaj gönderildi: {group.title}"))
                        
                        # Mesajlar arasında bekle
                        await asyncio.sleep(random.randint(8, 15))
                    
                    # Tur istatistiklerini göster
                    logger.info(self.terminal_format['mesaj_durumu'].format(tur_mesaj_sayisi, self.sent_count))
                    
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
        """Aktif grupları getirir"""
        groups = []
        try:
            async for dialog in self.client.iter_dialogs():
                # Sadece grupları ve hata vermeyenleri al
                if dialog.is_group and dialog.id not in self.error_groups:
                    groups.append(dialog)
        except Exception as e:
            logger.error(f"Grup getirme hatası: {str(e)}")
        
        return groups
    
    async def _send_message_to_group(self, group) -> bool:
        """Gruba mesaj gönderir"""
        try:
            message = random.choice(self.messages)
            await self.client.send_message(group.id, message)
            # İstatistikleri güncelle
            self.sent_count += 1
            self.processed_groups.add(group.id)
            self.last_message_time = datetime.now()
            
            return True
            
        except errors.FloodWaitError as e:
            # Flood Wait hatası için özel işlem
            wait_time = e.seconds + random.randint(5, 15)  # Ekstra bekleme ekle
            logger.warning(self.terminal_format['uyari'].format(f"Flood wait: {wait_time} saniye bekleniyor ({group.title})"))
            await asyncio.sleep(wait_time)
            return False
        except (errors.ChatWriteForbiddenError, errors.UserBannedInChannelError) as e:
            # Erişim engelleri için kalıcı olarak devre dışı bırak
            self._mark_error_group(group, f"Erişim engeli: {str(e)}")
            return False
        except Exception as e:
            # Geçici hata olabilir, tekrar denenebilir
            logger.error(self.terminal_format['hata'].format(f"Grup mesaj hatası: {str(e)}"))
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
        """Aktif kullanıcıları güvenli şekilde takip eder"""
        try:
            user = await event.get_sender()
            if not user:
                return
                
            user_id = getattr(user, 'id', None)
            if not user_id:
                return
                
            # Bot mu?
            is_bot = getattr(user, 'bot', False)
            # Yönetici mi?
            admin_rights = getattr(user, 'admin_rights', None)
            # Kurucu mu?
            is_creator = getattr(user, 'creator', False) or hasattr(user, 'creator_rights')
            
            if not (is_bot or admin_rights or is_creator):
                username = getattr(user, 'username', None)
                self.db.add_user(user_id, username)
                
        except Exception as e:
            logger.error(f"Kullanıcı takip güvenli kontrol hatası: {str(e)}")
    
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