"""
Telegram botu çekirdek işlevleri
"""
import asyncio
import signal
import random
import logging
import threading
from datetime import datetime
from pathlib import Path
import os
import sys
from typing import List, Set, Dict, Any, Optional, Union
import json

from telethon import TelegramClient, errors
from colorama import Fore, Style, init
from tabulate import tabulate

from bot.utils.error_handler import ErrorHandler
from bot.handlers import MessageHandlers
from bot.tasks import BotTasks
from database.user_db import UserDatabase
from config.settings import Config

init(autoreset=True)
logger = logging.getLogger(__name__)

class TelegramBot:
    """
    Telegram gruplarına otomatik mesaj gönderen ve özel mesajları yöneten bot
    """
    def __init__(self, api_id: int, api_hash: str, phone: str, 
                 group_links: List[str], user_db: UserDatabase, config=None, debug_mode: bool = False):
        """Bot sınıfını başlat"""
        # Temel ayarlar
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.group_links = group_links
        self.db = user_db
        self.config = config or Config.load_config()
        self.session_file = Path(self.config.session_file)
        
        # Durum değişkenleri
        self.is_running = False
        self.is_paused = False
        self.processed_groups: Set[int] = set()
        self.responded_users: Set[int] = set()
        self.sent_count = 0
        self.start_time = None
        self.last_message_time = None
        
        # Aktivite takibi için eklenen değişkenler
        self.displayed_users = set()  # Gösterilen kullanıcıları takip et
        self.user_activity_cache = {}  # Kullanıcı aktivitelerini önbellekte tut
        self.user_activity_explained = False  # Aktivite açıklaması gösterildi mi
        
        # Tekrarlanan hata takibi
        self.error_message_cache = {}  # Son hata mesajları ve sayıları
        self.flood_wait_active = False  # FloodWait durumu aktif mi
        self.flood_wait_end_time = None  # FloodWait'in sona ereceği zaman
        
        # Durdurmak ve duraklatmak için güçlendirilmiş mekanizmalar
        self._shutdown_event = asyncio.Event()
        self._pause_event = asyncio.Event()  # Duraklatma için yeni event
        self._cleanup_lock = threading.Lock()
        self._force_shutdown_flag = False
        
        # Timeout değerleri
        self.shutdown_timeout = 10  # Saniye cinsinden görevlerin kapanması için bekleme süresi
        
        # Hata yönetimi
        self.error_counter = {}
        self.error_groups: Set[int] = set()
        self.error_reasons: Dict[int, str] = {}
        
        # Aktif görevler listesi
        self.active_tasks = []
        
        # Rate limiting için parametreler
        self.pm_delays = {
            'min_delay': 60,     # Min bekleme süresi (saniye)
            'max_delay': 120,    # Max bekleme süresi (saniye)
            'burst_limit': 3,    # Art arda gönderim limiti
            'burst_delay': 600,  # Burst limit sonrası bekleme (10 dk)
            'hourly_limit': 10,  # Saatlik maksimum mesaj
            'davet_interval': 30  # Dakika cinsinden davet aralığı (daha sık)
        }
        
        # Rate limiting için durum takibi
        self.pm_state = {
            'burst_count': 0,
            'hourly_count': 0,
            'hour_start': datetime.now(),
            'last_pm_time': None,
            'consecutive_errors': 0
        }
        
        # Debug modu
        self.debug_mode = debug_mode
        
        # Terminal çıktı formatları
        self.terminal_format = {
            'user_activity_new': f"{Fore.CYAN}👁️ Yeni kullanıcı aktivitesi: {{}}{Style.RESET_ALL}",
            'user_activity_exists': f"{Fore.BLUE}🔄 Tekrar aktivite: {{}}{Style.RESET_ALL}",
            'user_activity_reappear': f"{Fore.GREEN}🔙 Uzun süre sonra görüldü: {{}}{Style.RESET_ALL}",
            'user_invite_success': f"{Fore.GREEN}✅ Davet gönderildi: {{}}{Style.RESET_ALL}",
            'user_invite_fail': f"{Fore.RED}❌ Davet başarısız: {{}} ({{}}){Style.RESET_ALL}",
            'user_already_invited': f"{Fore.YELLOW}⚠️ Zaten davet edildi: {{}}{Style.RESET_ALL}",
            'telethon_update': f"{Fore.MAGENTA}📡 Telethon güncelleme: {{}}{Style.RESET_ALL}"
        }
        
        # Açıklamalar
        self.explanations = {
            'user_activity_new': "Gruplarda tespit edilen ve henüz veritabanında olmayan yeni bir kullanıcı",
            'telethon_update': "Telethon kütüphanesinin gruplardan aldığı güncelleme bilgisi",
            'flood_wait': "Telegram API'den çok fazla istek yaptığınız için bekleme süresi uygulanıyor"
        }
        
        # Client nesnesini oluştur
        self.client = TelegramClient(
            str(self.session_file),
            self.api_id, 
            self.api_hash,
            connection_retries=None,  # Sonsuz yeniden deneme
            retry_delay=1,            # 1 saniye bekle
            auto_reconnect=True,      # Otomatik yeniden bağlanma
            request_retries=5         # İstek yeniden deneme sayısı
        )
        
        # Alt bileşenler
        self.error_handler = ErrorHandler(self)
        self.message_handlers = None  # Daha sonra init_components'da oluşturulacak
        self.tasks = None  # Daha sonra init_components'da oluşturulacak
        
    def init_components(self):
        """Alt bileşenleri başlat - sınıf referans çevrimini önlemek için"""
        self.message_handlers = MessageHandlers(self)
        self.tasks = BotTasks(self)
    
    async def start(self):
        """Botu başlatır"""
        self.is_running = True
        self.start_time = datetime.now()
        tasks = []  # Görev listesi
        
        try:
            # Alt bileşenleri başlat
            self.init_components()
            
            # Sinyal işleyicileri ayarla
            self._setup_signal_handlers()
            
            # Temizleme işaretini sıfırla
            self._shutdown_event.clear()
            
            # Mesaj şablonlarını yükle
            self._load_message_templates()
            
            # Veritabanından hata veren grupları yükle
            self._load_error_groups()
            
            # Client başlat
            await self.client.start(phone=self.phone)
            logger.info("🚀 Bot aktif edildi!")
            
            # Grup hata kayıtlarını yönet
            await self.tasks.manage_error_groups()
            
            # Mesaj işleyicileri ayarla - önemli: diğer görevlerden önce!
            self.message_handlers.setup_handlers()
            
            # Periyodik temizleme görevi
            cleanup_task = asyncio.create_task(self.tasks.periodic_cleanup())
            tasks.append(cleanup_task)
            
            # Komut dinleyici görevi
            command_task = asyncio.create_task(self.tasks.command_listener())
            tasks.append(command_task)
            
            # Grup mesaj görevi - öncelikli
            group_task = asyncio.create_task(self.tasks.process_group_messages())
            tasks.append(group_task)
            
            # Özel davet görevi - daha sık çalışacak
            invite_task = asyncio.create_task(self.tasks.process_personal_invites())
            tasks.append(invite_task)
            
            # Aktivite ve açıklamalar
            if not self.user_activity_explained:
                # İlk başlangıçta açıklamalar göster
                self._show_explanations()
                self.user_activity_explained = True
            
            # Görevleri aktif olarak kaydet
            self.active_tasks = tasks
            
            # Ana görevleri bekle
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except asyncio.CancelledError:
            logger.info("Bot görevleri iptal edildi")
        except Exception as e:
            logger.error(f"Bot çalışma hatası: {str(e)}", exc_info=True)
        finally:
            # İşaret olayını ayarla - diğer görevlerin durmasını sağlar
            self._shutdown_event.set()
            
            # Kapanış işlemleri
            await self._cleanup_on_exit(tasks)
    
    def _show_explanations(self):
        """Kullanıcıya konsol mesajlarının açıklamalarını göster"""
        print(f"\n{Fore.CYAN}=== KONSOL MESAJLARI AÇIKLAMALARI ==={Style.RESET_ALL}")
        print(f"{Fore.GREEN}👁️ Yeni kullanıcı aktivitesi:{Style.RESET_ALL} Henüz veritabanında olmayan yeni bir kullanıcı")
        print(f"{Fore.BLUE}🔄 Tekrar aktivite:{Style.RESET_ALL} Veritabanında olan ve yakın zamanda görülmüş kullanıcı")
        print(f"{Fore.GREEN}🔙 Uzun süre sonra görüldü:{Style.RESET_ALL} Veritabanında olan ancak uzun süredir görülmeyen kullanıcı")
        print(f"{Fore.MAGENTA}📡 Telethon güncelleme:{Style.RESET_ALL} Telegram API'den gelen grup güncellemeleri")
        print(f"{Fore.YELLOW}⏳ FloodWait hatası:{Style.RESET_ALL} Telegram API rate limiti, belirtilen süre bekleniyor")
        print(f"{Fore.RED}❌ Hata mesajları:{Style.RESET_ALL} Tekrarlayan hatalar için sayaç gösterilir\n")
    
    async def _cleanup_on_exit(self, tasks):
        """Çıkış sırasında temizlik işlemleri"""
        # Kilitleme ile çoklu temizlemeleri önle
        with self._cleanup_lock:
            if not self.is_running:
                return  # Zaten temizlendi
                
            self.is_running = False
            logger.info("Bot kapatılıyor...")
            
            # Tüm görevleri iptal et
            for task in tasks:
                if task and not task.done() and not task.cancelled():
                    task.cancel()
                    
            # Görevlerin iptalinin tamamlanması için kısa bir süre bekle
            await asyncio.sleep(1)
            
            # Client nesnesini kapat
            if self.client and self.client.is_connected():
                await self.client.disconnect()
                logger.info("Telethon bağlantısı kapatıldı")
            
            # İstatistikleri göster
            self._show_final_stats()
    
    def _show_final_stats(self):
        """Kapatılırken istatistikleri göster"""
        try:
            if not self.start_time:
                return
                
            uptime = datetime.now() - self.start_time
            hours, remainder = divmod(uptime.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{int(hours)}:{int(minutes):02}:{int(seconds):02}"
            
            # Veritabanı istatistikleri
            try:
                stats = self.db.get_database_stats()
            except Exception:
                stats = {'total_users': 'N/A', 'invited_users': 'N/A'}
            
            # Tablo verilerini hazırla
            print(f"\n{Fore.CYAN}=== BOT ÇALIŞMA İSTATİSTİKLERİ ==={Style.RESET_ALL}")
            
            stats_table = [
                ["Çalışma süresi", uptime_str],
                ["Toplam gönderilen mesaj", self.sent_count],
                ["Hata veren grup sayısı", len(self.error_groups)],
                ["Toplam kullanıcı sayısı", stats['total_users']],
                ["Davet edilen kullanıcı", stats['invited_users']]
            ]
            
            print(tabulate(stats_table, headers=["Metrik", "Değer"], tablefmt="grid"))
        except Exception as e:
            logger.error(f"İstatistik gösterme hatası: {str(e)}")
    
    def _load_message_templates(self):
        """Mesaj şablonlarını JSON dosyalarından yükler"""
        try:
            # Grup mesajlarını yükle
            messages_data = Config.load_messages()
            
            # Doğrudan liste formatı ile çalış
            if isinstance(messages_data, list):
                self.messages = messages_data
            else:
                # Geriye uyumluluk için get() ile çalış
                self.messages = messages_data if isinstance(messages_data, list) else []
            
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
            self.invite_messages = ["Bizim gruba da beklerim: t.me/{}"]
            self.invite_outros = ["\n\nDiğer gruplarımız da burada 👇\n"]
            self.redirect_messages = ["Gruplarda konuşalım, özelden konuşmayalım."]
            self.flirty_responses = ["Teşekkür ederim! 😊"]
    
    def create_invite_message(self) -> str:
        """Davet mesajı oluşturur"""
        # Rastgele davet mesajı ve outro seç
        random_invite = random.choice(self.invite_messages)
        outro = random.choice(self.invite_outros)
        
        # Grup bağlantılarını oluştur
        group_links = "\n".join([f"• t.me/{link}" for link in self.group_links])
        
        # Mesajı formatla
        return f"{random_invite.format(self.group_links[0])}{outro}{group_links}"
    
    def _load_error_groups(self):
        """Veritabanından hata veren grupları yükler"""
        error_groups = self.db.get_error_groups()
        for group_id, group_title, error_reason, _, _ in error_groups:
            self.error_groups.add(group_id)
            self.error_reasons[group_id] = error_reason
            
        if self.error_groups:
            logger.info(f"{len(self.error_groups)} adet hata veren grup yüklendi")
    
    def mark_error_group(self, group, reason: str) -> None:
        """Hata veren grubu işaretler"""
        self.error_groups.add(group.id)
        self.error_reasons[group.id] = reason
        logger.warning(f"⚠️ Grup devre dışı bırakıldı - {group.title}: {reason}")
    
    async def interruptible_sleep(self, seconds):
        """
        Kesintiye uğrayabilen gelişmiş bekleme fonksiyonu
        Bot kapatılırsa veya duraklatılırsa hemen yanıt verir
        """
        step = 0.5  # Yarım saniye adımlarla (daha hızlı yanıt)
        for _ in range(int(seconds / step)):
            # Kapatma kontrolü
            if not self.is_running or self._shutdown_event.is_set():
                logger.debug("Interruptible sleep: Shutdown detected")
                return
                
            # Duraklatma kontrolü
            if self.is_paused:
                logger.debug("Interruptible sleep: Pause detected")
                await self.check_paused()
                
            await asyncio.sleep(step)
        
        # Kalan süre için (0-0.5 saniye arası)
        remainder = seconds % step
        if remainder > 0 and self.is_running and not self._shutdown_event.is_set():
            if not self.is_paused:
                await asyncio.sleep(remainder)
            else:
                await self.check_paused()
    
    async def smart_delay(self) -> None:
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
                await self.interruptible_sleep(error_delay)
            
            # Burst kontrolü - art arda gönderim sınırı
            if self.pm_state['burst_count'] >= self.pm_delays['burst_limit']:
                logger.info(f"⏳ Art arda gönderim limiti aşıldı: {self.pm_delays['burst_delay']} saniye bekleniyor")
                await self.interruptible_sleep(self.pm_delays['burst_delay'])
                self.pm_state['burst_count'] = 0
            
            # Son mesajdan bu yana geçen süre
            if self.pm_state['last_pm_time']:
                time_since_last = (current_time - self.pm_state['last_pm_time']).total_seconds()
                min_delay = self.pm_delays['min_delay']
                
                # Henüz minimum süre geçmemişse bekle
                if time_since_last < min_delay:
                    wait_time = min_delay - time_since_last
                    logger.debug(f"Son mesajdan bu yana {time_since_last:.1f}s geçti, {wait_time:.1f}s daha bekleniyor")
                    await self.interruptible_sleep(wait_time)
            
            # Doğal görünmesi için rastgele gecikme
            human_delay = random.randint(3, 10)  # İnsan gibi yazma gecikmesi
            await self.interruptible_sleep(human_delay)
            
        except Exception as e:
            self.error_handler.log_error("Akıllı gecikme hatası", str(e))
            # Hata durumunda güvenli varsayılan bekleme
            await self.interruptible_sleep(60)
    
    async def send_personal_message(self, user_id: int, message: str) -> bool:
        """Kullanıcıya özel mesaj gönderir"""
        try:
            # Shutdown kontrolü
            if self._shutdown_event.is_set():
                return False
                
            # Akıllı gecikme uygula
            await self.smart_delay()
            
            # Mesaj gönder
            await self.client.send_message(user_id, message)
            
            # İstatistikleri güncelle
            self.pm_state['burst_count'] += 1
            self.pm_state['hourly_count'] += 1
            self.pm_state['consecutive_errors'] = 0
            self.pm_state['last_pm_time'] = datetime.now()
            
            return True
            
        except errors.FloodWaitError as e:
            self.error_handler.handle_flood_wait(
                "FloodWaitError", 
                f"Özel mesaj için {e.seconds} saniye bekleniyor",
                {'wait_time': e.seconds}
            )
            await asyncio.sleep(e.seconds)
            self.pm_state['consecutive_errors'] += 1
        except Exception as e:
            self.error_handler.log_error("Özel mesaj hatası", str(e))
            self.pm_state['consecutive_errors'] += 1
            await asyncio.sleep(30)
            
        return False
    
    async def invite_user(self, user_id: int, username: Optional[str]) -> bool:
        """Kullanıcıya özel davet mesajı gönderir"""
        try:
            # Shutdown kontrolü
            if self._shutdown_event.is_set():
                logger.debug("Bot kapatılıyor, davet işlemi iptal")
                return False
                
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
            message = self.create_invite_message()
            await self.client.send_message(user_id, message)
            
            # Veritabanını güncelle
            self.db.mark_as_invited(user_id)
            
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
            
            self.error_handler.handle_flood_wait(
                "FloodWaitError",
                f"Kullanıcı davet için {wait_time} saniye bekleniyor ({user_info})",
                {'wait_time': wait_time}
            )
            await asyncio.sleep(wait_time)
            return False
            
        except (errors.UserIsBlockedError, errors.UserIdInvalidError, errors.PeerIdInvalidError) as e:
            # Kalıcı hatalar - bu kullanıcıyı işaretleyerek atlayabiliriz
            print(self.terminal_format['user_invite_fail'].format(user_info, f"Kalıcı hata: {e.__class__.__name__}"))
            
            self.error_handler.log_error(
                "Davet kalıcı hata",
                f"{user_info} - {str(e)}",
                {
                    'error_type': e.__class__.__name__,
                    'user_id': user_id,
                    'username': username,
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
            
            self.error_handler.log_error(
                "Davet hatası",
                f"{user_info} - {str(e)}",
                {
                    'user_id': user_id,
                    'username': username
                }
            )
            await asyncio.sleep(30)  # Genel hata durumunda bekle
            return False
            
    def _setup_signal_handlers(self):
        """Sinyal işleyicileri ayarla"""
        # Sinyal işleyicileri (Ctrl+C, Terminate)
        try:
            # Unix/Linux/macOS sinyalleri
            if hasattr(signal, 'SIGTERM'):
                signal.signal(signal.SIGTERM, self._signal_handler)
            if hasattr(signal, 'SIGINT'):
                signal.signal(signal.SIGINT, self._signal_handler)
                
            # Windows için Python KeyboardInterrupt ele alır
        except Exception as e:
            logger.error(f"Sinyal işleyici ayarlama hatası: {str(e)}")
    
    def _signal_handler(self, sig, frame):
        """Sinyal işleyicisi"""
        signal_name = "SIGTERM" if sig == signal.SIGTERM else "SIGINT" if sig == signal.SIGINT else str(sig)
        print(f"\n{Fore.YELLOW}⚠️"
              f" {signal_name} sinyali alındı, bot kapatılıyor...{Style.RESET_ALL}")
        
        # Kapatma işlemini başlat
        self.shutdown()
    
    def shutdown(self):
        """Bot kapatma işlemini başlatır"""
        try:
            # İşlem zaten başladı mı kontrol et
            if self._shutdown_event.is_set() or not self.is_running:
                logger.debug("Kapatma işlemi zaten başlatılmış, atlanıyor")
                return
                    
            # İşaret olayını ayarla - tüm görevlerin duracağını işaretler  
            self._shutdown_event.set()
            
            # Durum değişkenini güncelle
            self.is_running = False
            
            print(f"\n{Fore.YELLOW}⚠️ Bot kapatma işlemi başlatıldı, tüm görevler sonlanıyor...{Style.RESET_ALL}")
            
            # Zamanlayıcı ile acil kapatma - 10 saniye sonra zorla kapatma
            import threading
            shutdown_timeout = 10  # 10 saniye
            emergency_timer = threading.Timer(shutdown_timeout, self._emergency_shutdown)
            emergency_timer.daemon = True  # Daemon thread
            emergency_timer.start()
            logger.debug(f"Acil kapatma zamanlayıcısı başlatıldı: {shutdown_timeout} saniye")
            
            # Ana thread'den çağrıldığında asyncio ile işlemleri programla
            if threading.current_thread() is threading.main_thread():
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Event loop çalışıyorsa, task olarak ekle
                    asyncio.create_task(self._safe_shutdown())
                else:
                    # Event loop çalışmıyorsa, yeni bir loop başlat
                    asyncio.run(self._safe_shutdown())
                        
        except Exception as e:
            logger.error(f"Kapatma işlemi başlatma hatası: {str(e)}")
            # Acil durumda zorla kapat
            self._emergency_shutdown()

    async def _safe_shutdown(self):
        """Tüm görevleri güvenli bir şekilde kapatır"""
        try:
            logger.info("Güvenli kapatma işlemi başlatıldı")
            
            # İlk olarak aktif görevleri iptal et
            await self._cancel_active_tasks()
            
            # Görevlerin iptalinin tamamlanması için bekle
            await asyncio.sleep(1)
            
            # Telethon client'ını kapat
            if self.client and self.client.is_connected():
                logger.info("Telethon bağlantısı kapatılıyor...")
                try:
                    # Timeout ile bağlantıyı kapat
                    try:
                        await asyncio.wait_for(
                            self.client.disconnect(), 
                            timeout=3.0
                        )
                        logger.info("Telethon bağlantısı kapatıldı")
                    except asyncio.TimeoutError:
                        logger.warning("Telethon bağlantısı kapatma zaman aşımı")
                except Exception as e:
                    logger.error(f"Telethon kapatma hatası: {str(e)}")
            
            # İstatistikleri göster
            self._show_final_stats()
            
            print(f"\n{Fore.GREEN}✅ Bot güvenli bir şekilde kapatıldı{Style.RESET_ALL}")
            
            # Program sonlanmadıysa 2 saniye sonra zorla kapat
            import threading
            threading.Timer(2.0, self._emergency_shutdown).start()
            
        except Exception as e:
            logger.error(f"Güvenli kapatma hatası: {str(e)}")
            self._emergency_shutdown()
    
    def _emergency_shutdown(self):
        """Acil durum kapatma işlevi - son çare olarak kullanılır"""
        try:
            logger.critical("ACİL KAPATMA İŞLEMİ BAŞLATILDI!")
            print(f"\n{Fore.RED}⚠️ ACİL KAPATMA - Program zorla sonlandırılıyor!{Style.RESET_ALL}")
            
            # Kapatma bayrağını ayarla
            self.is_running = False
            
            # Tüm thread'lerin durumu
            active_threads = threading.enumerate()
            logger.critical(f"Aktif thread sayısı: {len(active_threads)}")
            
            # Kritik thread'leri logla
            for thread in active_threads:
                try:
                    if thread.name != "MainThread" and not thread.daemon:
                        logger.critical(f"Kritik aktif thread: {thread.name}, daemon: {thread.daemon}")
                except:
                    pass
            
            # Çıkış öncesi son temizlik
            try:
                # Telethon referansını temizle
                if hasattr(self, 'client') and self.client:
                    self.client = None
                    
                # Veritabanı bağlantısını kapat
                if hasattr(self, 'db') and self.db:
                    try:
                        self.db.close_connection()
                    except:
                        pass
                        
                # Son çıkış log mesajını yazdır
                sys.stdout.flush()
                
            except:
                pass
                
            # Sistemden çık - OS level (garantili çalışır)
            print(f"{Fore.RED}Program zorla sonlandırılıyor!{Style.RESET_ALL}")
            os._exit(1)  # Bu komut her durumda çalışır ve programı ANINDA sonlandırır
            
        except Exception as e:
            print(f"ACİL KAPATMA HATASI: {str(e)}")
            os._exit(1)  # Yine de çık
    
    # Duraklatma yönetimi güçlendirildi
    def toggle_pause(self):
        """Botu duraklat/devam ettir - güçlendirilmiş versiyon"""
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            self._pause_event.set()
            status = "duraklatıldı ⏸️"
            print(f"\n{Fore.YELLOW}⏸️ Bot {status} - Tüm görevler duruluyor...{Style.RESET_ALL}")
        else:
            self._pause_event.clear()
            status = "devam ediyor ▶️"
            print(f"\n{Fore.GREEN}▶️ Bot {status} - Görevler devam ediyor...{Style.RESET_ALL}")
            
        logger.info(f"Bot {status}")
    
    # Duraklatma durumu kontrolü için yardımcı fonksiyon
    async def check_paused(self):
        """Bot duraklatıldıysa, duraklatma sona erene kadar bekle"""
        if self.is_paused:
            print(f"{Fore.YELLOW}⏸️ Görev duraklatıldı, devam etmesi için bekliyor...{Style.RESET_ALL}")
            await self._pause_event.wait()
            print(f"{Fore.GREEN}▶️ Görev devam ediyor...{Style.RESET_ALL}")

    # Görevleri iptal etme işlevi güçlendirildi
    async def _cancel_active_tasks(self):
        """Aktif görevleri iptal et - güçlendirilmiş versiyon"""
        try:
            logger.info("Aktif görevler iptal ediliyor...")
            cancelled_count = 0
            
            # Tüm aktif görevleri iptal et
            for i, task in enumerate(self.active_tasks):
                if task and not task.done() and not task.cancelled():
                    task_name = task.get_name() if hasattr(task, "get_name") else f"Task-{i}"
                    logger.info(f"İptal ediliyor: {task_name}")
                    task.cancel()
                    cancelled_count += 1
            
            if cancelled_count > 0:
                # İptal edilen görevlere yanıt vermesi için biraz bekle
                logger.info(f"{cancelled_count} görev iptal edildi, yanıt vermesi bekleniyor...")
                await asyncio.sleep(2)
                
                # Hala sonlanmamış görevleri zorla iptal et
                pending_tasks = [t for t in self.active_tasks if not t.done() and not t.cancelled()]
                if pending_tasks:
                    logger.warning(f"{len(pending_tasks)} görev hala yanıt vermiyor, zorla iptal ediliyor...")
                    for task in pending_tasks:
                        # Tekrar iptal et ve bekleme
                        task.cancel()
                        
                    # Son kez bekle
                    await asyncio.sleep(1)
            else:
                logger.info("İptal edilecek aktif görev bulunamadı")
                
            # İptal edilemeyen görevler için son durum
            stuck_tasks = [t for t in self.active_tasks if not t.done() and not t.cancelled()]
            if stuck_tasks:
                logger.error(f"{len(stuck_tasks)} görev kilitlendi ve iptal edilemedi!")
                if self._force_shutdown_flag:
                    logger.critical("Zorla kapatma bayrağı ayarlandı, program sonlandırılacak!")
                    print(f"\n{Fore.RED}⚠️ ZORLA KAPATMA - Program sonlandırılıyor!{Style.RESET_ALL}")
                    # 1 saniyelik bir gecikme ile sistemden çık
                    threading.Timer(1, lambda: os._exit(1)).start()
            
        except Exception as e:
            logger.error(f"Görev iptal hatası: {str(e)}", exc_info=True)
            
    def show_status(self):
        """Bot durumunu gösterir"""
        status = "Çalışıyor ▶️" if not self.is_paused else "Duraklatıldı ⏸️"
        
        print(f"\n{Fore.CYAN}=== BOT DURUM BİLGİSİ ==={Style.RESET_ALL}")
        print(f"{Fore.GREEN}▶ Durum:{Style.RESET_ALL} {status}")
        print(f"{Fore.GREEN}▶ Telefon:{Style.RESET_ALL} {self.phone}")
        
        if self.start_time:
            uptime = datetime.now() - self.start_time
            hours, remainder = divmod(uptime.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{int(hours)}:{int(minutes):02}:{int(seconds):02}"
            print(f"{Fore.GREEN}▶ Çalışma Süresi:{Style.RESET_ALL} {uptime_str}")
        
        print(f"{Fore.GREEN}▶ Gönderilen Mesaj:{Style.RESET_ALL} {self.sent_count}")
        
        # PM ve davet durumu
        print(f"\n{Fore.CYAN}=== DAVET DURUM BİLGİSİ ==={Style.RESET_ALL}")
        print(f"{Fore.GREEN}▶ Saatlik Limit:{Style.RESET_ALL} {self.pm_state['hourly_count']}/{self.pm_delays['hourly_limit']}")
        print(f"{Fore.GREEN}▶ Art Arda Limit:{Style.RESET_ALL} {self.pm_state['burst_count']}/{self.pm_delays['burst_limit']}")
        
        # FloodWait durumu
        if self.flood_wait_active and self.flood_wait_end_time:
            remaining = (self.flood_wait_end_time - datetime.now()).total_seconds()
            if remaining > 0:
                print(f"{Fore.YELLOW}▶ FloodWait:{Style.RESET_ALL} {int(remaining)} saniye kaldı")
            else:
                print(f"{Fore.GREEN}▶ FloodWait:{Style.RESET_ALL} Tamamlandı")
        
    def clear_console(self):
        """Konsol ekranını temizler"""
        import os
        # İşletim sistemine göre uygun komut
        if os.name == 'posix':  # Unix/Linux/MacOS
            os.system('clear')
        elif os.name == 'nt':  # Windows
            os.system('cls')
            
    def _print_help(self):
        """Komutlarla ilgili yardım mesajını gösterir"""
        help_text = f"""
{Fore.CYAN}=== BOT KOMUTLARI ==={Style.RESET_ALL}
{Fore.GREEN}p{Style.RESET_ALL} - Botu duraklat/devam ettir
{Fore.GREEN}s{Style.RESET_ALL} - Bot durumunu göster
{Fore.GREEN}c{Style.RESET_ALL} - Konsolu temizle
{Fore.GREEN}h{Style.RESET_ALL} - Bu yardım mesajını göster
{Fore.GREEN}q{Style.RESET_ALL} - Botu durdur ve çık
{Fore.GREEN}Ctrl+C{Style.RESET_ALL} - Botu durdur ve çık
        """
        print(help_text)