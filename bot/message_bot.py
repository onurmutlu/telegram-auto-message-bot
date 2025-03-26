"""
Mesaj gönderen bot sınıfı
"""
import asyncio
import random
import logging 
import json
from datetime import datetime
import threading
import signal
from typing import List, Set, Dict, Any, Optional, Union
from pathlib import Path

from telethon import TelegramClient, errors, events
from colorama import Fore, Style, init
from tabulate import tabulate

from config.settings import Config
from database.user_db import UserDatabase
from bot.base import BaseBot
from bot.handlers.message_handler import setup_message_handlers
from bot.handlers.group_handler import GroupHandler
from bot.handlers.user_handler import UserHandler
from bot.utils.rate_limiter import RateLimiter
from bot.utils.error_handler import ErrorHandler

init(autoreset=True)
logger = logging.getLogger(__name__)

class MemberMessageBot(BaseBot):
    """
    Telegram gruplarına otomatik mesaj gönderen ve özel mesajları yöneten bot sınıfı
    """
    def __init__(self, api_id: int, api_hash: str, phone: str, 
                 group_links: List[str], user_db: UserDatabase, config=None, debug_mode: bool = False):
        super().__init__(api_id, api_hash, phone, user_db, config)
        
        # Ana değişkenler
        self.group_links = group_links
        self.processed_groups: Set[int] = set()
        self.sent_count = 0
        self.start_time = datetime.now()
        self.last_message_time = None
        
        # Debug modu
        self.debug_mode = debug_mode
        
        # Handler'lar
        self.group_handler = None
        self.user_handler = None
        self.error_handler = None
        self.rate_limiter = None
        
        # Mesajları yükle
        self._load_message_templates()
        
        # Görev ve thread yönetimi
        self.active_tasks = []
        self._shutdown_event = asyncio.Event()
        self._cleanup_lock = threading.Lock()
        
        # Hata grupları
        self.error_groups: Set[int] = set()
        self.error_reasons: Dict[int, str] = {}
        self._load_error_groups()
        
        # Tekrarlanan mesajları önlemek için
        self.displayed_users = set()
        self.last_error_messages = {}
        self.error_counter = {}
        
        # Client oluştur
        self.client = TelegramClient(
            str(self.session_file),
            self.api_id, 
            self.api_hash,
            connection_retries=None,
            retry_delay=1,
            auto_reconnect=True,
            request_retries=5
        )
        
    def _initialize_components(self):
        """Bileşenleri başlat"""
        # Rate limiter
        self.rate_limiter = RateLimiter()
        
        # Hata yöneticisi
        self.error_handler = ErrorHandler(self)
        
        # Grup ve kullanıcı handler'ları
        self.group_handler = GroupHandler(self)
        self.user_handler = UserHandler(self)
    
    def _load_message_templates(self):
        """Mesaj şablonlarını yükler"""
        try:
            # Grup mesajlarını yükle
            messages_data = Config.load_messages()
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
    
    async def start(self):
        """Botu başlatır"""
        # Bileşenleri başlat
        self._initialize_components()
        
        # Görev listesini temizle
        self.active_tasks = []
        
        try:
            # Client başlat
            await self.client.start(phone=self.phone)
            logger.info("🚀 Bot aktif edildi!")
            
            # Hata veren grupları yönet
            await self.error_handler.manage_error_groups()
            
            # Sinyal yönetimi
            self._setup_signal_handlers()
            
            # Mesaj işleyicileri ayarla
            setup_message_handlers(self)
            
            # Görevleri oluştur
            tasks = []
            
            # Periyodik temizleme görevi
            cleanup_task = asyncio.create_task(self._periodic_cleanup())
            tasks.append(cleanup_task)
            
            # Komut dinleyicisi
            command_task = asyncio.create_task(self.command_listener())
            tasks.append(command_task)
            
            # Grup mesaj görevi - YENİ: Daha sık çalış
            group_task = asyncio.create_task(self.group_handler.process_group_messages())
            tasks.append(group_task)
            
            # Özel davet görevi - YENİ: Daha sık çalış, düşük öncelik
            invite_task = asyncio.create_task(self.user_handler.process_personal_invites())
            tasks.append(invite_task)
            
            # Aktif görevler listesini güncelle
            self.active_tasks = tasks
            
            # Görevleri bekle
            await asyncio.gather(*tasks)
            
        except asyncio.CancelledError:
            logger.info("Bot görevleri iptal edildi")
        except Exception as e:
            logger.error(f"Bot çalışma hatası: {str(e)}", exc_info=True)
        finally:
            # _shutdown_event'i ayarla - diğer görevlerin durmasını sağlar
            self._shutdown_event.set()
            
            # Tüm görevleri temizle
            await self._cancel_all_tasks(self.active_tasks)
            
            # Bağlantıyı kapat
            await self._cleanup()
    
    def _setup_signal_handlers(self):
        """Özel sinyal yönetici ayarları"""
        # Windows'ta çalışmayacak özel sinyaller, ama CTRL+C her OS'ta çalışır
        if hasattr(signal, "SIGTERM"):
            asyncio.get_event_loop().add_signal_handler(
                signal.SIGTERM, lambda: asyncio.create_task(self.shutdown())
            )
        if hasattr(signal, "SIGINT"):
            asyncio.get_event_loop().add_signal_handler(
                signal.SIGINT, lambda: asyncio.create_task(self.shutdown())
            )
    
    async def command_listener(self):
        """Konsoldan komutları dinler"""
        while self.is_running:
            try:
                # Nonblocking input için alternatif bir yöntem
                await asyncio.sleep(0.1)  # Input olmadan CPU kullanımını azalt
                
                if not self.is_running:
                    break
                
                # asyncio kullanarak diğer görevleri engellemeden input al
                cmd = await self._async_input()
                
                if not cmd or not self.is_running:
                    continue
                
                cmd = cmd.strip().lower()
                
                if cmd in ('q', 'quit', 'exit'):
                    print(f"{Fore.YELLOW}⚠️ Bot kapatılıyor... Lütfen bekleyin.{Style.RESET_ALL}")
                    await self.shutdown()
                    break
                elif cmd == 'p':
                    self.toggle_pause()
                elif cmd == 's':
                    self.show_status()
                elif cmd == 'c':
                    self.clear_console()
                elif cmd == 'h':
                    self._print_help()
                    
            except asyncio.CancelledError:
                logger.info("Komut dinleyici iptal edildi")
                break
            except Exception as e:
                logger.error(f"Komut işleme hatası: {e}")
    
    async def _async_input(self):
        """Asenkron input fonksiyonu"""
        # Özel bir async input implementasyonu
        # İşletim sistemi seviyesinde girişleri thread pool içinde bekler
        loop = asyncio.get_event_loop()
        
        # Shutdown esnasında hemen çık
        if self._shutdown_event.is_set():
            return None
            
        try:
            # Thread pool içinde input çalıştır
            # Timeout ekleyerek ctrl+c yakalamayı sağla
            input_future = loop.run_in_executor(None, lambda: input(""))
            
            # 100ms zaman aşımı ile input bekle
            return await asyncio.wait_for(input_future, 0.1)
        except (asyncio.TimeoutError, EOFError):
            # Süre doldu, tekrar dene
            return None
    
    async def _cancel_all_tasks(self, tasks):
        """Tüm görevleri güvenli bir şekilde iptal eder"""
        if not tasks:
            return
            
        logger.info(f"{len(tasks)} görev kapatılıyor...")
        
        # Tüm görevleri iptal et
        for task in tasks:
            if task and not task.done() and not task.cancelled():
                task.cancel()
        
        # İptal edilen görevlerin tamamlanmasını bekle
        await asyncio.sleep(1)
        
        # Görevleri temizle
        for i, task in enumerate(tasks):
            try:
                if not task.done():
                    try:
                        await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        logger.warning(f"Görev #{i} zaman aşımına uğradı, devam ediliyor")
            except Exception as e:
                logger.error(f"Görev #{i} temizleme hatası: {str(e)}")
    
    async def _periodic_cleanup(self):
        """Periyodik temizleme işlemi"""
        while self.is_running:
            try:
                # Kapatılma sinyali kontrol et
                if self._shutdown_event.is_set():
                    break
                    
                # 10 dakika bekleme periyodu
                for _ in range(600):  # 600 saniye = 10 dakika
                    if not self.is_running or self._shutdown_event.is_set():
                        break
                    await asyncio.sleep(1)
                
                if not self.is_running:
                    break
                
                # Süresi dolmuş hataları temizle
                cleared_errors = self.db.clear_expired_error_groups()
                if cleared_errors > 0:
                    logger.info(f"{cleared_errors} adet süresi dolmuş hata kaydı temizlendi")
                    # Hafızadaki hata listesini de güncelle
                    self._load_error_groups()
                
                # Aktivite listesini temizle (bellekte çok yer kaplamasın)
                if len(self.displayed_users) > 500:
                    logger.info(f"Aktivite takip listesi temizleniyor ({len(self.displayed_users)} -> 100)")
                    self.displayed_users = set(list(self.displayed_users)[-100:])
                
                # Hata sayaçlarını ve son hataları temizle
                self.error_counter = {}
                self.last_error_messages = {}
                
            except asyncio.CancelledError:
                logger.info("Periyodik temizleme iptal edildi")
                break
            except Exception as e:
                logger.error(f"Periyodik temizleme hatası: {str(e)}")
    
    def _load_error_groups(self):
        """Veritabanından hata veren grupları yükler"""
        error_groups = self.db.get_error_groups()
        self.error_groups.clear()
        self.error_reasons.clear()
        
        for group_id, group_title, error_reason, _, _ in error_groups:
            self.error_groups.add(group_id)
            self.error_reasons[group_id] = error_reason
            
        if self.error_groups:
            logger.info(f"{len(self.error_groups)} adet hata veren grup yüklendi")
    
    async def _cleanup(self):
        """İşlemler tamamlandığında kaynakları temizler"""
        # Temizleme işleminin bir kere yapılmasını sağla
        with self._cleanup_lock:
            try:
                logger.info("Kaynaklar temizleniyor...")
                
                if hasattr(self, 'client') and self.client and self.client.is_connected():
                    await self.client.disconnect()
                    logger.info("Client bağlantısı kapatıldı")
            except Exception as e:
                logger.error(f"Temizleme hatası: {str(e)}")
    
    async def shutdown(self):
        """Bot'u düzgün şekilde kapatır"""
        if not self.is_running:
            return  # Zaten kapatılıyorsa tekrar işlem yapma
            
        try:
            # Çalışma bayrağını kapat
            self.is_running = False
            
            # Shutdown olayını ayarla
            self._shutdown_event.set()
            
            logger.info("Bot kapatma işlemi başlatıldı")
            
            # Önce aktif görevleri iptal et
            await self._cancel_all_tasks(self.active_tasks)
            
            # İstatistikleri göster
            await self._show_final_stats()
            
        except Exception as e:
            logger.error(f"Kapatma işlemi hatası: {str(e)}")
        finally:
            # Son olarak temizliği gerçekleştir
            await self._cleanup()
    
    async def _show_final_stats(self):
        """Çalışma istatistiklerini gösterir"""
        try:
            # Çalışma süresi hesapla
            uptime = datetime.now() - self.start_time
            hours, remainder = divmod(uptime.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{int(hours)}:{int(minutes):02}:{int(seconds):02}"
            
            # Veritabanı istatistiklerini al
            stats = self.db.get_database_stats()
            
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
    
    def _print_help(self):
        """Yardım mesajı gösterir"""
        help_text = f"""
{Fore.CYAN}=== KOMUTLAR ==={Style.RESET_ALL}
{Fore.GREEN}q{Style.RESET_ALL}: Botu kapat
{Fore.GREEN}p{Style.RESET_ALL}: Duraklat/Devam Et
{Fore.GREEN}s{Style.RESET_ALL}: Durum bilgisi göster
{Fore.GREEN}c{Style.RESET_ALL}: Konsolu temizle
{Fore.GREEN}h{Style.RESET_ALL}: Bu yardım mesajını göster
"""
        print(help_text)