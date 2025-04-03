"""
# ============================================================================ #
# Dosya: core.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/core.py
# İşlev: Telegram Bot Merkezi Sınıfı
#
# Amaç: Telegram bot uygulamasının temel işlevlerini yönetmek ve koordine etmek.
#       Bu sınıf, Telegram API'ye bağlantı, oturum yönetimi, grup yönetimi, otomatik mesajlaşma,
#       olay dinleme, hata yönetimi, asenkron görev yönetimi ve kullanıcı arayüzü gibi temel
#       bileşenleri içerir.
#
# Build: 2025-04-01-05:30:00
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, Telegram bot uygulamasının merkezi sınıfını içerir:
# - Telegram API'ye bağlantı ve oturum yönetimi
# - Grup yönetimi ve otomatik mesajlaşma altyapısı
# - Olay dinleme ve işleme mekanizmaları 
# - Hata yönetimi ve akıllı geri çekilme stratejileri
# - Asenkron işlem desteği ve görev yönetimi
# - Kullanıcı arayüzü ve konsol komutları
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""
import asyncio
import logging
import os
import signal
import sys
import threading
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Set, Dict, Any, Optional, Union

from telethon import TelegramClient, errors, events
from colorama import Fore, Style, init
from tabulate import tabulate

# Bot modüllerini import et
from bot.handlers.group_handler import GroupHandler
from bot.handlers.message_handler import MessageHandler
from bot.handlers.user_handler import UserHandler
from bot.utils.error_handler import ErrorHandler
from database.user_db import UserDatabase
from config.settings import Config
from bot.tasks import BotTasks  # BotTasks import edildi
from bot.services.group_service import GroupService as GroupMessageService
from bot.services.dm_service import DirectMessageService
from bot.services.reply_service import ReplyService as AutoReplyService
from bot.services.user_service import UserService
from bot.handlers.handlers import MessageHandlers
from bot.services.service_factory import ServiceFactory
from bot.services.service_manager import ServiceManager

# Colorama başlat
init(autoreset=True)
logger = logging.getLogger(__name__)

class TelegramBot:
    """
    Telegram bot merkezi sınıfı
    
    Tüm bot işlevlerini ve özelliklerini içerir:
    - Telethon client oluşturma ve yönetme
    - Grup mesajlama ve özel mesajlaşma
    - Olay dinleme ve işleme
    - Hata yönetimi ve loglama
    - Kullanıcı arayüzü
    """
    def __init__(self, api_id: int, api_hash: str, phone: str, 
                 group_links: List[str], user_db: UserDatabase, config=None, debug_mode: bool = False,
                 admin_groups: List[str] = None, target_groups: List[str] = None):
        """
        Bot merkezi sınıfını başlatır
        """
        # Temel ayarlar
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.group_links = group_links  # group_links'i ekleyin
        self.db = user_db
        self.config = config or Config.load_config()
        self.admin_groups = admin_groups or []
        self.target_groups = target_groups or []
        
        # Session dosya yolu
        self.session_file = getattr(self.config, "SESSION_PATH", "session/member_session")
        
        # Durum değişkenleri
        self.is_running = False
        self.is_paused = False
        self.debug_mode = debug_mode
        self.processed_groups: Set[int] = set()
        self.responded_users: Set[int] = set()
        self.sent_count = 0
        self._start_time = datetime.now().timestamp()
        self.start_time = None  # Başlangıç zamanı (başlatıldığında atanacak)
        self.last_message_time = None
        
        # Aktivite takibi için değişkenler
        self.displayed_users = set()
        self.user_activity_cache = {}
        self.user_activity_explained = False
        
        # Hata takibi
        self.error_message_cache = {}
        self.flood_wait_active = False
        self.flood_wait_end_time = None
        
        # Asenkron kontrol mekanizmaları
        self._shutdown_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._cleanup_lock = threading.Lock()
        self._force_shutdown_flag = False
        
        # Timeout değerleri
        self.shutdown_timeout = 10
        
        # Hata yönetimi
        self.error_counter = {}
        self.error_groups: Set[int] = set()
        self.error_reasons: Dict[int, str] = {}
        
        # Aktif görevler listesi
        self.active_tasks = []
        
        # Rate limiting parametreleri
        self.pm_delays = {
            'min_delay': 60,     # Min bekleme süresi (saniye)
            'max_delay': 120,    # Max bekleme süresi (saniye)
            'burst_limit': 3,    # Art arda gönderim limiti
            'burst_delay': 600,  # Burst limit sonrası bekleme (10 dk)
            'hourly_limit': 10,  # Saatlik maksimum mesaj
            'davet_interval': 30 # Dakika cinsinden davet aralığı
        }
        
        # Rate limiting durum takibi
        self.pm_state = {
            'burst_count': 0,
            'hourly_count': 0,
            'hour_start': datetime.now(),
            'last_pm_time': None,
            'consecutive_errors': 0
        }
        
        # Terminal çıktı formatları
        self.terminal_format = {
            'info': f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {{}}",
            'warning': f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {{}}",
            'error': f"{Fore.RED}[ERROR]{Style.RESET_ALL} {{}}",
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
        
        # Session dizini oluştur
        session_path = Path(self.session_file).parent
        if not session_path.exists():
            session_path.mkdir(parents=True, exist_ok=True)
        
        # Client nesnesi
        self.client = TelegramClient(
            str(self.session_file),
            self.api_id, 
            self.api_hash,
            device_model="Telegram Auto Bot",
            system_version="Python 3.9",
            app_version="v3.4.0",
            connection_retries=None,  # Sonsuz yeniden deneme
            retry_delay=1,            # 1 saniye bekle
            auto_reconnect=True,      # Otomatik yeniden bağlanma
            request_retries=5         # İstek yeniden deneme sayısı
        )
        
        # Alt bileşenler
        self.error_handler = ErrorHandler(self)
        
        # Handler ve servis nesneleri
        self.message_handlers = None
        self.group_handler = None
        self.message_handler = None
        self.user_handler = None
        self.bot_tasks = None
        
        # Şablon koleksiyonları
        self.messages = []
        self.invite_templates = {}
        self.response_templates = {}
        self.invite_messages = []
        self.invite_outros = []
        self.redirect_messages = []
        self.flirty_responses = []
        
        # Sinyal işleyicileri
        self._setup_signal_handlers()
        
        self.monitor_bot = None
        
        # Servis fabrikası ve yöneticisi
        self.service_factory = ServiceFactory(self.client, self.config, self.db, shutdown_event=self._shutdown_event)
        self.service_manager = ServiceManager(self.service_factory)
        
        # Servisler için hazırlık - merkezi servis havuzu
        self.services = {}
    
    def set_monitor_bot(self, monitor_bot):
        """
        Debug/izleme botunu TelegramBot'a bağlar.
        
        Args:
            monitor_bot: İzleme botu örneği
        """
        self.monitor_bot = monitor_bot
        logger.info("İzleme botu bağlandı")
    
    def send_debug_message(self, message):
        """Önemli mesajları izleme botuna gönder"""
        if self.monitor_bot:
            # Asenkron olarak mesaj gönder
            asyncio.create_task(self.monitor_bot.send_message_to_devs(message))
        
    def init_handlers(self):
        """Handler ve servis nesnelerini başlatır"""
        # Handler nesnelerini oluştur
        self.message_handlers = MessageHandlers(self)
        self.group_handler = GroupHandler(self)
        self.message_handler = MessageHandler(self)
        self.user_handler = UserHandler(self)
        self.bot_tasks = BotTasks(self)

        # /start komutu için handler ekle
        self.client.add_event_handler(self.start_command, events.NewMessage(pattern='(?i)/start'))
        
    async def start_command(self, event):
        """
        /start komutunu işler ve kullanıcı ID'sini loglar.
        """
        user_id = event.message.sender_id
        logger.info(f"/start komutu alındı. Kullanıcı ID: {user_id}")
        await event.respond(f"Merhaba! Kullanıcı ID'niz: {user_id}")
        
    # Bot sınıfının ana metodları
    async def start(self, interactive=True):
        """Bot'u başlatır ve Telegram'a bağlanır."""
        logger.info("Bot başlatılıyor...")
        
        try:
            # Telegram'a bağlan
            await self.client.connect()
            
            # Oturum yetkilendirilmiş mi?
            if not await self.client.is_user_authorized():
                if interactive:
                    # Kod isteği gönder
                    await self.client.send_code_request(self.phone)
                    # (kullanıcıdan telefon kodu alınır)
                    # ...
                else:
                    raise Exception("Telegram hesabı yetkilendirilmemiş ve interaktif mod kapalı")
                    
            # Bot'u çalışır olarak işaretle
            self.is_running = True
            self._start_time = datetime.now().timestamp()
            
            # Olay işleyicilerini kaydet
            self._register_event_handlers()
            
            # Tek bir yerde servis başlatma
            await self.init_services()
            
            logger.info("Bot başarıyla başlatıldı!")
        except Exception as e:
            logger.error(f"Bot başlatılamadı: {e}")
            await self._safe_shutdown()
            raise

    async def _authenticate_user(self):
        """Telegram'da yetkilendirme işlemi"""
        logger.info("Telegram doğrulaması başlatılıyor...")
        print(f"{Fore.YELLOW}Telegram doğrulama kodu gerekli!{Style.RESET_ALL}")
        
        # Doğrulama kodu gönder
        await self.client.send_code_request(self.phone)
        
        # Kullanıcıdan kodu iste
        code = input(f"{Fore.CYAN}Telefonunuza gelen kodu girin:{Style.RESET_ALL} ")
        
        try:
            # Doğrulama kodu ile giriş yap
            await self.client.sign_in(self.phone, code)
            print(f"{Fore.GREEN}✅ Telegram doğrulaması başarılı!{Style.RESET_ALL}")
        except errors.SessionPasswordNeededError:
            # İki adımlı doğrulama gerekiyor
            print(f"{Fore.YELLOW}📱 İki faktörlü doğrulama etkin!{Style.RESET_ALL}")
            password = input(f"{Fore.CYAN}Telegram hesap şifrenizi girin:{Style.RESET_ALL} ")
            await self.client.sign_in(password=password)
            print(f"{Fore.GREEN}✅ İki faktörlü doğrulama başarılı!{Style.RESET_ALL}")

    def shutdown(self):
        """Bot kapatma işlemini başlatır"""
        try:
            # İşlem zaten başladı mı kontrol et
            if self._shutdown_event.is_set() or not self.is_running:
                logger.debug("Kapatma işlemi zaten başlatılmış")
                return
                    
            self._shutdown_event.set()
            self.is_running = False
            
            print(f"\n{Fore.YELLOW}⚠️ Bot kapatma işlemi başlatıldı{Style.RESET_ALL}")
            
            # Acil kapatma zamanlayıcısı
            emergency_timer = threading.Timer(self.shutdown_timeout, self._emergency_shutdown)
            emergency_timer.daemon = True
            emergency_timer.start()
            
            # Ana thread kontrolü
            if threading.current_thread() is threading.main_thread():
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._safe_shutdown())
                else:
                    asyncio.run(self._safe_shutdown())
                        
        except Exception as e:
            logger.error(f"Kapatma işlemi başlatma hatası: {str(e)}")
            self._emergency_shutdown()

    async def _safe_shutdown(self):
        """
        Bot'u güvenli şekilde kapatmak için tüm bağlantıları ve veritabanlarını kapatır.
        """
        logger.info("Güvenli kapatma işlemi başlatıldı")
        
        # Aktif görevleri iptal et
        try:
            logger.info("Aktif görevler iptal ediliyor...")
            # Görevleri iptal etme kodu...
        except Exception as e:
            logger.error(f"Görev iptal hatası: {e}")
        
        # Bağlantıyı kapat
        try:
            logger.info("Telethon bağlantısı kapatılıyor...")
            if self.client and hasattr(self.client, 'is_connected'):
                if await self.client.is_connected():
                    await self.client.disconnect()
            logger.info("Telethon bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"Bağlantı kapatma hatası: {e}")
        
        # Veritabanını kapat
        if self.db:
            try:
                self.db.close()
            except Exception as e:
                logger.error(f"Veritabanı kapatma hatası: {e}")
        
        # Servisleri durdur
        await self.service_manager.stop_services()
        
        # Bot'u durdur
        self.is_running = False  # Bu satırı ekleyin/düzeltin
        
        print("\n✅ Bot güvenli bir şekilde kapatıldı")

    async def _cleanup_on_exit(self):
        """Çıkış sırasında temizlik işlemleri"""
        try:
            logger.info("Kapanış işlemleri başlatılıyor...")

            # Görevleri iptal et
            await self._cancel_active_tasks()

            # Client'ı kapat
            if self.client and self.client.is_connected():
                await self.client.disconnect()
                logger.info("Telethon bağlantısı kapatıldı")

            # İstatistikleri göster
            self._show_final_stats()

        except Exception as e:
            logger.error(f"Kapanış hatası: {str(e)}", exc_info=True)
        finally:
            self.is_running = False
            logger.info("Bot kapatıldı.")

    async def _cancel_active_tasks(self):
        """Aktif görevleri iptal et"""
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
                
                # Hala sonlanmamış görevleri kontrol et
                pending_tasks = [t for t in self.active_tasks if not t.done() and not t.cancelled()]
                if pending_tasks:
                    logger.warning(f"{len(pending_tasks)} görev hala yanıt vermiyor")
                    # Son kez bekle
                    await asyncio.sleep(1)
            else:
                logger.info("İptal edilecek aktif görev bulunamadı")
                
        except Exception as e:
            logger.error(f"Görev iptal hatası: {str(e)}", exc_info=True)

    # Yardımcı metotlar
    def toggle_pause(self):
        """Botu duraklat/devam ettir"""
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            self._pause_event.set()
            status = "duraklatıldı ⏸️"
            print(f"\n{Fore.YELLOW}⏸️ Bot {status}{Style.RESET_ALL}")
        else:
            self._pause_event.clear()
            status = "devam ediyor ▶️" 
            print(f"\n{Fore.GREEN}▶️ Bot {status}{Style.RESET_ALL}")
        
        logger.info(f"Bot {status}")
        
    async def check_paused(self):
        """Duraklama durumunu kontrol eder"""
        if self.is_paused:
            logger.debug("Bot duraklatıldı, bekleniyor...")
            await asyncio.sleep(5)
            return True
        return False
        
    def show_status(self):
        """Bot durumunu ve istatistikleri gösterir"""
        if not self.is_running:
            print(f"{Fore.RED}Bot çalışmıyor!{Style.RESET_ALL}")
            return
            
        # Çalışma süresi hesapla
        uptime = datetime.now() - self.start_time if self.start_time else timedelta(0)
        hours, remainder = divmod(uptime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(hours)}s {int(minutes)}dk {int(seconds)}sn"
        
        # Grup sayıları
        total_groups = len(self.processed_groups)
        error_groups = len(self.error_groups)
        active_groups = total_groups - error_groups
        
        # Aktivite bilgisi
        activity_count = len(self.displayed_users)
        invited_count = len(self.responded_users)
        
        # Tablo verilerini hazırla
        status_data = [
            ["Bot Durumu", f"{'Duraklatıldı ⏸️' if self.is_paused else 'Aktif ▶️'}"],
            ["Çalışma Süresi", uptime_str],
            ["Toplam Grup", total_groups],
            ["Aktif Grup", active_groups],
            ["Hatalı Grup", error_groups],
            ["Tespit Edilen Kullanıcı", activity_count],
            ["Davet Gönderilen", invited_count],
            ["Mesaj Gönderilen", self.sent_count]
        ]
        
        # Tabloyu oluştur ve yazdır
        print("\n" + "=" * 50)
        print(f"{Fore.CYAN}BOT DURUM RAPORU{Style.RESET_ALL}")
        print(tabulate(status_data, tablefmt="fancy_grid", colalign=("right", "left")))
        print("=" * 50)
        
        # Rate limit durumları
        if self.flood_wait_active:
            remaining = (self.flood_wait_end_time - datetime.now()).total_seconds()
            print(f"{Fore.YELLOW}⚠️ FloodWait aktif: {int(remaining)} saniye kaldı{Style.RESET_ALL}")
        
        # Saatlik limit durumu
        hourly_remain = self.pm_delays['hourly_limit'] - self.pm_state['hourly_count']
        print(f"{Fore.CYAN}ℹ️ Bu saatte kalan mesaj limiti: {hourly_remain}{Style.RESET_ALL}")
        
        # Servis durumlarını göster
        service_status = self.service_manager.get_service_status()
        print(f"\n{Fore.CYAN}=== SERVİS DURUMLARI ==={Style.RESET_ALL}")
        for name, status in service_status.items():
            running = status.get("running", False)
            status_color = Fore.GREEN if running else Fore.RED
            status_text = "✅ Aktif" if running else "❌ Durduruldu"
            last_activity = status.get("last_activity", "Bilinmiyor")
            print(f"{Fore.WHITE}{name:<10}: {status_color}{status_text:<10} {Fore.YELLOW}Son aktivite: {last_activity}")
        
    def clear_console(self):
        """Terminal ekranını temizler"""
        # Platform bağımsız ekran temizleme
        os.system('cls' if os.name == 'nt' else 'clear')
        self._print_help(short=True)
        print(f"{Fore.GREEN}✅ Konsol temizlendi{Style.RESET_ALL}")
        
    def _print_help(self, short=False):
        """Yardım mesajını yazdırır"""
        # Başlık
        print(f"\n{Fore.CYAN}=== TELEGRAM BOT KOMUTLARI ==={Style.RESET_ALL}")
        
        # Komut tablosu
        commands = [
            ["q", "Çıkış", "Botu kapatır"],
            ["p", "Duraklat/Devam", "Bot işlemlerini duraklatır veya devam ettirir"],
            ["s", "Durum", "Bot durumunu ve istatistikleri gösterir"],
            ["c", "Temizle", "Konsol ekranını temizler"],
            ["h", "Yardım", "Bu yardım mesajını gösterir"]
        ]
        
        if not short:
            print(tabulate(commands, headers=["Komut", "İşlev", "Açıklama"], tablefmt="simple"))
            print(f"\n{Fore.YELLOW}Bot komut satırı aktif, komut girişi için >>> işaretinden sonra yazın{Style.RESET_ALL}")
        else:
            # Kısa komut listesi
            cmd_list = [f"{cmd} ({desc})" for cmd, desc, _ in commands]
            print(f"Komutlar: {' | '.join(cmd_list)}")
    
    def _show_explanations(self):
        """Terminal çıktı açıklamalarını gösterir"""
        print(f"\n{Fore.CYAN}=== TERMİNAL MESAJ AÇIKLAMALARI ==={Style.RESET_ALL}")
        
        explanations = [
            ["👁️", "Yeni kullanıcı aktivitesi", "Gruplarda ilk kez tespit edilen kullanıcı"],
            ["🔄", "Tekrar aktivite", "Son 24 saat içinde tekrar görülen kullanıcı"],
            ["🔙", "Uzun süre sonra görüldü", "Uzun süre sonra tekrar aktif olan kullanıcı"],
            ["✅", "Davet başarılı", "Kullanıcıya başarıyla davet gönderildi"],
            ["❌", "Davet başarısız", "Kullanıcıya davet gönderimi başarısız oldu"],
            ["⚠️", "Zaten davet edildi", "Kullanıcı zaten davet edilmiş"],
            ["📡", "Telethon güncelleme", "Telegram API güncellemesi"],
            ["⌛", "FloodWait", "Telegram API rate limit uyarısı"]
        ]
        
        print(tabulate(explanations, headers=["İkon", "Mesaj Tipi", "Açıklama"], tablefmt="simple"))
        print("-" * 50)
    
    def _show_final_stats(self):
        """Kapanış istatistiklerini gösterir"""
        if not self.start_time:
            return
            
        # Çalışma süresi
        end_time = datetime.now()
        total_time = end_time - self.start_time
        hours, remainder = divmod(total_time.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # İstatistikler
        stats = [
            ["Çalışma Süresi", f"{int(hours)}s {int(minutes)}dk {int(seconds)}sn"],
            ["İşlenen Grup Sayısı", len(self.processed_groups)],
            ["Tespit Edilen Kullanıcı", len(self.displayed_users)],
            ["Gönderilen Mesaj", self.sent_count]
        ]
        
        print("\n" + "=" * 50)
        print(f"{Fore.CYAN}BOT KAPANIŞ İSTATİSTİKLERİ{Style.RESET_ALL}")
        print(tabulate(stats, tablefmt="fancy_grid", colalign=("right", "left")))
        print("=" * 50)
    
    def _load_message_templates(self):
        """Mesaj şablonlarını yükler"""
        try:
            logger.info("Mesaj şablonları yükleniyor...")
            
            # JSON dosyalarından şablonları yükle
            self.messages = self.config.load_message_templates()
            self.invite_templates = self.config.load_invite_templates()
            self.response_templates = self.config.load_response_templates()

            # Şablonları ilgili listelere aktar
            self.invite_messages = self.invite_templates.get('invites', [])
            self.invite_outros = self.invite_templates.get('invites_outro', [])
            self.redirect_messages = self.invite_templates.get('redirect_messages', [])
            self.flirty_responses = self.response_templates.get('flirty', [])

            logger.info("Mesaj şablonları başarıyla yüklendi")
            
        except Exception as e:
            logger.error(f"Mesaj şablonları yükleme hatası: {str(e)}")
            # Varsayılan bir şablon ayarla
            self.invite_templates = {'default': "Merhaba, grubumuz: {link}"}
    
    def _load_error_groups(self):
        """Veritabanından hata veren grupları yükler"""
        try:
            # Hata veren grupları veritabanından al
            error_groups = self.db.get_error_groups()
            
            # Set'i temizle ve yeni değerleri ekle
            self.error_groups.clear()
            self.error_reasons.clear()
            
            for group_id, group_title, error_reason, error_time, retry_after in error_groups:
                self.error_groups.add(int(group_id))
                self.error_reasons[int(group_id)] = error_reason
            
            logger.info(f"{len(self.error_groups)} hatalı grup yüklendi")
            
        except Exception as e:
            logger.error(f"Hata veren grupları yükleme hatası: {str(e)}")
    
    def _setup_signal_handlers(self):
        """Sinyal işleyicilerini ayarlar"""
        try:
            # UNIX sinyalleri
            if hasattr(signal, 'SIGINT'):
                signal.signal(signal.SIGINT, self._handle_shutdown_signal)
            if hasattr(signal, 'SIGTERM'):
                signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
            
            # Windows için (sadece SIGINT ve SIGBREAK mevcut)
            if hasattr(signal, 'SIGBREAK'):
                signal.signal(signal.SIGBREAK, self._handle_shutdown_signal)
                
            logger.debug("Sinyal işleyicileri ayarlandı")
            
        except Exception as e:
            logger.error(f"Sinyal işleyici ayarlama hatası: {str(e)}")
    
    def _handle_shutdown_signal(self, signum, frame):
        """Kapatma sinyallerini işler"""
        signal_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else f"Signal {signum}"
        print(f"\n{Fore.YELLOW}⚠️ {signal_name} sinyali alındı, bot kapatılıyor...{Style.RESET_ALL}")
        logger.info(f"{signal_name} sinyali alındı, kapanış başlatılıyor")
        
        if self.is_running and not self._shutdown_event.is_set():
            self.shutdown()
    
    def _format_uptime(self):
        """
        Bot'un çalışma süresini insan tarafından okunabilir formata dönüştürür.
        
        Returns:
            str: "Xg Ys Zd Ws" formatında çalışma süresi (gün, saat, dakika, saniye)
        """
        uptime_seconds = self._calculate_uptime()
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return f"{int(days)}g {int(hours)}s {int(minutes)}d {int(seconds)}sn"

    def _calculate_uptime(self):
        """
        Bot'un çalışma süresini saniye cinsinden hesaplar.
        
        Returns:
            float: Çalışma süresi (saniye)
        """
        if self._start_time <= 0:
            return 0
            
        return datetime.now().timestamp() - self._start_time

    def _register_event_handlers(self):
        """
        Telegram istemcisine olay işleyicilerini kaydeder.
        """
        from telethon import events
        
        # Temel komutlar için pattern'lar - bu desenlerin doğru ayarlandığından emin olun
        # Eğer RegExp kullanıyorsa şunu deneyin: r'(?i)\/start'
        start_pattern = r'(?i)/start'
        help_pattern = r'(?i)/help'
        status_pattern = r'(?i)/status'
        
        # Temel komut işleyicileri
        if hasattr(self, 'start_command'):
            self.client.add_event_handler(
                self.start_command, 
                events.NewMessage(pattern=start_pattern)  # pattern=... şeklinde belirtin
            )
        
        if hasattr(self, 'help_command'):
            self.client.add_event_handler(
                self.help_command,
                events.NewMessage(pattern=help_pattern)
            )
        
        if hasattr(self, 'status_command'):
            self.client.add_event_handler(
                self.status_command,
                events.NewMessage(pattern=status_pattern)
            )
        
        # Özel mesaj ve grup mesaj işleyicileri...
        # (diğer işleyiciler aynı kalabilir)

    async def help_command(self, event):
        """
        /help komutuna yanıt olarak bot komutları hakkında bilgi verir.
        
        Args:
            event: Telegram mesaj olayı
        """
        help_text = (
            "📱 **Telegram Bot Komutları:**\n\n"
            "/start - Bot'u başlat\n"
            "/help - Bu yardım mesajını görüntüle\n"
            "/status - Bot durumunu görüntüle\n"
        )
        
        await event.respond(help_text)
        
    async def status_command(self, event):
        """
        /status komutuna yanıt olarak bot durumunu görüntüler.
        
        Args:
            event: Telegram mesaj olayı
        """
        uptime = self._format_uptime()
        status_text = (
            "🤖 **Bot Durum Raporu:**\n\n"
            f"Çalışma Süresi: {uptime}\n"
            f"Aktif: {'✅ Evet' if self.is_running else '❌ Hayır'}\n"
            f"İşlenen Gruplar: {len(self.target_groups)}\n"
        )
        
        await event.respond(status_text)

    async def start_command(self, event):
        """
        /start komutuna yanıt verir.
        """
        welcome_text = (
            "👋 **Hoş Geldiniz!**\n\n"
            "Bot aktif ve çalışıyor. Komutlar için /help yazabilirsiniz.\n"
        )
        await event.respond(welcome_text)
        
    async def _emergency_shutdown(self):
        """
        Acil durumda bot'un güvenli bir şekilde kapatılmasını sağlar.
        """
        try:
            logger.info("Acil durum kapatma işlemi başlatıldı")
            
            # Aktif servisleri durdur
            self.is_running = False
            
            # Tüm işleri iptal et
            if hasattr(self, '_tasks') and self._tasks:
                for task in self._tasks:
                    if not task.done():
                        task.cancel()
            
            # Bağlantıyı kapat
            if hasattr(self, 'client') and self.client:
                if await self.client.is_connected():
                    await self.client.disconnect()
            
            # Veritabanını kapat
            if hasattr(self, 'db') and self.db:
                self.db.close_connection()
            
            logger.info("Acil durum kapatma tamamlandı")
        except Exception as e:
            logger.error(f"Acil durum kapatma sırasında hata: {e}")

    async def on_private_message(self, event):
        """
        Özel mesajları işleyen metod.
        
        Args:
            event: Telegram mesaj olayı
        """
        if hasattr(self, 'dm_service'):
            await self.dm_service.process_message(event)
        else:
            logger.warning("dm_service bulunamadı, özel mesaj işlenemiyor")

    def _is_private_chat(self, event):
        """
        Etkinliğin özel mesajlaşma olup olmadığını kontrol eder.
        
        Args:
            event: Telegram etkinlik nesnesi
        
        Returns:
            bool: Özel mesajlaşma ise True
        """
        return event.is_private

    def _is_group_chat(self, event):
        """
        Etkinliğin grup mesajlaşması olup olmadığını kontrol eder.
        
        Args:
            event: Telegram etkinlik nesnesi
        
        Returns:
            bool: Grup mesajlaşması ise True
        """
        return not event.is_private

    async def on_group_message(self, event):
        """
        Grup mesajlarını işleyen metod.
        
        Args:
            event: Telegram mesaj olayı
        """
        if hasattr(self, 'reply_service'):
            await self.reply_service.process_message(event)
        else:
            logger.debug("reply_service bulunamadı, grup mesajı işlenemiyor")

    async def init_services(self):
        """Tüm servisleri başlatır"""
        try:
            # Grup keşfi yap
            await self.discover_groups()

            # GROUP SERVICE
            from bot.services.group_service import GroupService
            self.group_service = GroupService(self.client, self.config, self.db, self._shutdown_event)
            # Hedef grupları geçir
            self.group_service.set_target_groups(self.target_groups)
            self.services["group"] = self.group_service
            
            # DM SERVICE
            from bot.services.dm_service import DirectMessageService
            self.dm_service = DirectMessageService(self.client, self.config, self.db, self._shutdown_event)
            self.services["dm"] = self.dm_service
            
            # REPLY SERVICE
            from bot.services.reply_service import ReplyService
            self.reply_service = ReplyService(self.client, self.config, self.db, self._shutdown_event)
            self.services["reply"] = self.reply_service
            
            # UserService oluşturma kısmını düzelt
            try:
                from bot.services.user_service import UserService
                # !! DÜZELTME: self.db ve self.config parametrelerinin sırası ve client eklenmesi
                self.user_service = UserService(self.client, self.config, self.db, self._shutdown_event)
                self.services["user"] = self.user_service
            except (ImportError, AttributeError) as e:
                logger.error(f"UserService yüklenemedi: {e}")
            
            # Servisleri başlat
            await self._start_all_services()
            
            logger.info("✅ Tüm servisler başarıyla başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"❌ Servis başlatma hatası: {str(e)}", exc_info=True)
            return False

    async def _start_all_services(self):
        """Tüm servisleri başlatır"""
        for name, service in self.services.items():
            try:
                if hasattr(service, 'start'):
                    await service.start()
                    logger.info(f"✅ {name} servisi başlatıldı")
                elif hasattr(service, 'run'):
                    # Run metodu varsa task olarak başlat
                    asyncio.create_task(service.run())
                    logger.info(f"✅ {name} servisi (run metodu) başlatıldı")
            except Exception as e:
                logger.error(f"❌ {name} servisi başlatılamadı: {str(e)}")

    async def discover_groups(self):
        """Kullanıcının üye olduğu tüm grupları tespit eder"""
        logger.info("Grup keşfi başlatılıyor...")
        
        try:
            dialogs = await self.client.get_dialogs()
            discovered = []
            
            for dialog in dialogs:
                if dialog.is_group or dialog.is_channel:
                    group_id = dialog.id
                    group_name = dialog.title
                    
                    # Gruba ekle ve veritabanına kaydet
                    if group_id not in self.target_groups and group_id not in self.admin_groups:
                        self.target_groups.append(group_id)
                        discovered.append(f"{group_name} ({group_id})")
                        
                        # Veritabanına kaydet (eğer db şeması destekliyorsa)
                        if hasattr(self.db, 'add_group'):
                            self.db.add_group(group_id, group_name)
            
            # Servislere bildirme
            if self.group_service:
                self.group_service.target_groups = self.target_groups
                
            logger.info(f"{len(discovered)} yeni grup keşfedildi: {', '.join(discovered)}")
            return True
            
        except Exception as e:
            logger.error(f"Grup keşif hatası: {e}")
            return False

    def enable_debug_mode(self):
        """Debug modunu etkinleştir."""
        import logging
        import sys
        from colorama import init, Fore, Back, Style
        
        # Colorama başlat
        init(autoreset=True)
        
        # Log seviyesini DEBUG'a ayarla
        for logger_name in ('bot', 'telethon', 'database'):
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG)
        
        # Debug ekranı göster
        print(f"{Fore.YELLOW}{Style.BRIGHT}🐞 DEBUG MODU ETKİN 🐞")
        print(f"{Fore.YELLOW}════════════════════════════════")
        print(f"{Fore.GREEN}• API ID: {self.api_id}")
        print(f"{Fore.GREEN}• Telefon: {self.phone[:6]}******")
        print(f"{Fore.GREEN}• Admin grupları: {self.admin_groups}")
        print(f"{Fore.GREEN}• Hedef grupları: {self.target_groups}")
        print(f"{Fore.YELLOW}════════════════════════════════")
        
        # Her mesaj gönderme denemesini console'da göster
        def debug_send_message_wrapper(original_func):
            async def wrapper(entity, message, *args, **kwargs):
                print(f"{Fore.CYAN}📤 MESAJ GÖNDERME DENEME: {entity}")
                print(f"{Fore.WHITE}Mesaj: {message[:30]}...")
                try:
                    result = await original_func(entity, message, *args, **kwargs)
                    print(f"{Fore.GREEN}✅ Başarılı!")
                    return result
                except Exception as e:
                    print(f"{Fore.RED}❌ Hata: {str(e)}")
                    raise
                    
            return wrapper
        
        # Client'ın send_message metodunu wrap et
        self.client.send_message = debug_send_message_wrapper(self.client.send_message)
        
        return True