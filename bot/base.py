"""
Temel bot sınıfı
"""
import asyncio
import logging
import os
import sys
import signal
from datetime import datetime
from typing import Optional
from pathlib import Path

from telethon import TelegramClient
from colorama import Fore, Style, init
from tabulate import tabulate

from database.user_db import UserDatabase

init(autoreset=True)
logger = logging.getLogger(__name__)

class BaseBot:
    """
    Temel bot sınıfı - ortak işlevler ve özellikler
    """
    def __init__(self, api_id: int, api_hash: str, phone: str, 
                 user_db: UserDatabase, config=None):
        """
        Bot temel sınıfını başlat
        """
        # API kimlik bilgileri
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        
        # Veritabanı
        self.db = user_db
        
        # Yapılandırma
        self.config = config
        
        # Session dosya yolu
        self.session_file = "session/member_session"
        
        # Durum değişkenleri
        self.is_running = True
        self.is_paused = False
        
        # Terminal format ayarları
        self.terminal_format = {
            'info': f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {{}}",
            'warning': f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {{}}",
            'error': f"{Fore.RED}[ERROR]{Style.RESET_ALL} {{}}"
        }
        
        # Path nesnelerinin oluştur
        session_path = Path(self.session_file).parent
        if not session_path.exists():
            session_path.mkdir(parents=True, exist_ok=True)
        
        # Telethon istemci oluştur
        self.client = TelegramClient(
            self.session_file, 
            self.api_id, 
            self.api_hash,
            device_model="Telegram Auto Bot",
            system_version="Python 3.9",
            app_version="v3.1"
        )
        
        # Sinyal işleyicileri
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, sig, frame):
        """Sinyal işleyicisi"""
        print(f"\n{Fore.YELLOW}⚠️ İşlem kesintisi algılandı, güvenli bir şekilde kapatılıyor...{Style.RESET_ALL}")
        self.is_running = False
        
    async def stop_bot(self):
        """Botu durdur"""
        print(f"{Fore.YELLOW}⚠️ Bot durduruluyor...{Style.RESET_ALL}")
        self.is_running = False
        
    def toggle_pause(self):
        """Botu duraklat/devam ettir"""
        self.is_paused = not self.is_paused
        status = "duraklatıldı ⏸️" if self.is_paused else "devam ediyor ▶️"
        print(f"{Fore.CYAN}ℹ️ Bot {status}{Style.RESET_ALL}")
        logger.info(f"Bot {status}")
        
    def show_status(self):
        """Bot durumunu gösterir"""
        status = "Çalışıyor ▶️" if not self.is_paused else "Duraklatıldı ⏸️"
        
        print(f"\n{Fore.CYAN}=== BOT DURUM BİLGİSİ ==={Style.RESET_ALL}")
        print(f"{Fore.GREEN}▶ Durum:{Style.RESET_ALL} {status}")
        print(f"{Fore.GREEN}▶ Telefon:{Style.RESET_ALL} {self.phone}")
        
    def clear_console(self):
        """Konsol ekranını temizler"""
        import os
        # İşletim sistemine göre uygun komut
        if os.name == 'posix':  # Unix/Linux/MacOS
            os.system('clear')
        elif os.name == 'nt':   # Windows
            os.system('cls')
        
        # Temizleme sonrası başlık göster
        print(f"{Fore.CYAN}{'='*30}")
        print(f"{Fore.GREEN}TELEGRAM AUTO MESSAGE BOT v3.1")
        print(f"{Fore.CYAN}{'='*30}{Style.RESET_ALL}")
        
        # Yardımı tekrar göster
        self.show_help()

    def toggle_debug(self):
        """Debug modunu aç/kapa"""
        if hasattr(self, 'debug_mode'):
            self.debug_mode = not self.debug_mode
            status = "açıldı 🔍" if self.debug_mode else "kapatıldı 🔒"
            print(f"{Fore.CYAN}ℹ️ Debug modu {status}{Style.RESET_ALL}")
            logger.info(f"Debug modu {status}")
        else:
            print(f"{Fore.YELLOW}⚠️ Bu bot türü debug modunu desteklemiyor{Style.RESET_ALL}")
        
    def show_help(self):
        """Komut yardımını gösterir"""
        commands = [
            ["p", "Duraklat/Devam et"],
            ["s", "Durum bilgisi göster"],
            ["c", "Konsolu temizle"],
            ["d", "Debug modu aç/kapat"],
            ["u", "Kullanıcı istatistiklerini göster"],
            ["q", "Çıkış"],
            ["h", "Bu yardım mesajı"]
        ]
        
        print(f"\n{Fore.CYAN}=== BOT KOMUTLARI ==={Style.RESET_ALL}")
        print(tabulate(commands, headers=["Komut", "Açıklama"], tablefmt="simple"))
        print()
        
    def show_user_stats(self):
        """Kullanıcı istatistiklerini gösterir"""
        try:
            stats = self.db.get_database_stats()
            
            print(f"\n{Fore.CYAN}👥 KULLANICI İSTATİSTİKLERİ{Style.RESET_ALL}")
            
            user_stats = [
                ["Toplam Kullanıcı", stats["total_users"]],
                ["Davet Edilen", stats["invited_users"]],
                ["Engellenen", stats["blocked_users"]],
                ["Hata Veren Grup", stats["error_groups"]]
            ]
            
            print(tabulate(user_stats, headers=["Kategori", "Sayı"], tablefmt="grid"))
            
        except Exception as e:
            logger.error(f"İstatistik gösterme hatası: {str(e)}")
        
    async def wait_with_countdown(self, seconds: int, step: int = 60) -> None:
        """
        Belirtilen süre boyunca sayaç göstererek bekler
        Args:
            seconds: Bekleme süresi (saniye)
            step: Konsola yazdırma adımı (saniye)
        """
        end_time = datetime.now().timestamp() + seconds
        while datetime.now().timestamp() < end_time and self.is_running and not self.is_paused:
            remaining = int(end_time - datetime.now().timestamp())
            if remaining % step == 0 or remaining <= 10:
                mins, secs = divmod(remaining, 60)
                print(f"{Fore.CYAN}⏳ Kalan süre: {mins}:{secs:02d}{Style.RESET_ALL}", end="\r")
            await asyncio.sleep(1)
            
        if not self.is_running or self.is_paused:
            print(f"{Fore.YELLOW}⚠️ Bekleme iptal edildi!{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}✅ Bekleme tamamlandı!{' ' * 20}{Style.RESET_ALL}")
        
    async def command_listener(self):
        """Gelişmiş komut satırı arayüzü"""
        commands = {
            'p': {'desc': 'Duraklat/Devam', 'func': self.toggle_pause},
            'q': {'desc': 'Çıkış', 'func': self.stop_bot},
            's': {'desc': 'Durum Göster', 'func': self.show_status},
            'h': {'desc': 'Yardım', 'func': self.show_help},
            'c': {'desc': 'Konsolu Temizle', 'func': self.clear_console},
            'd': {'desc': 'Debug Modu Aç/Kapat', 'func': self.toggle_debug},
            'u': {'desc': 'Kullanıcı İstatistikleri', 'func': self.show_user_stats},
        }
        
        # Başlangıçta komutları göster
        self.show_help()
        
        while self.is_running:
            try:
                # Komut bekleme ve işleme
                cmd = await self._async_input("\nKomut > ")
                
                if cmd.lower() in commands:
                    command = commands[cmd.lower()]
                    logger.info(f"Komut çalıştırılıyor: {cmd} - {command['desc']}")
                    
                    # Asenkron fonksiyon mu kontrolü
                    if asyncio.iscoroutinefunction(command['func']):
                        await command['func']()
                    else:
                        command['func']()
                elif cmd and cmd.strip():
                    print(f"{Fore.RED}❌ Bilinmeyen komut: {cmd}{Style.RESET_ALL}")
                    
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Komut işleme hatası: {str(e)}")
                
            # Ufak bir gecikme
            await asyncio.sleep(0.1)
    
    async def _async_input(self, prompt: str = "") -> str:
        """
        Asenkron olarak konsol girdisi alır
        Args:
            prompt: Kullanıcıya gösterilecek istem metni
        Returns:
            Kullanıcının girdiği metin
        """
        # Asenkron olmayan bir fonksiyonu asenkron bir bağlamda çalıştır
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input(prompt).strip())
    
    async def _cleanup(self):
        """Kaynakları temizler"""
        try:
            if self.client:
                await self.client.disconnect()
            if self.db:
                self.db.close()
                
            logger.info("Resources cleaned up")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")