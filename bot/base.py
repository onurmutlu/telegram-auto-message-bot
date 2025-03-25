"""
Temel bot sınıfı
"""
import asyncio
import random
import logging
from datetime import datetime
from typing import List, Set, Dict, Any, Optional
from pathlib import Path
import threading

from telethon import TelegramClient, errors, events
from colorama import Fore, Style, init

# Göreceli import yerine mutlak import kullanımı
from config.settings import TelegramConfig
from database.user_db import UserDatabase
from utils.logger import LoggerSetup

# tabulate kütüphanesini koşullu import et
try:
    from tabulate import tabulate
except ImportError:
    # tabulate yoksa basit bir tablo fonksiyonu tanımla
    def tabulate(data, headers, tablefmt=None):
        result = []
        # Başlıkları ekle
        result.append(" | ".join(headers))
        result.append("-" * (len(" | ".join(headers))))
        
        # Verileri ekle
        for row in data:
            result.append(" | ".join(str(item) for item in row))
        
        return "\n".join(result)

init(autoreset=True)
logger = logging.getLogger(__name__)

class BaseBot:
    """
    Temel bot işlevselliğini sağlayan sınıf
    """
    def __init__(self, api_id: int, api_hash: str, phone: str, user_db: UserDatabase, config=None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.db = user_db
        
        # Session dosyası yolu
        if config and hasattr(config, 'session_path'):
            # Session dizini yoksa oluştur
            session_dir = config.session_path
            session_dir.mkdir(parents=True, exist_ok=True)
            
            # Session dosyası yolu
            session_file = session_dir / 'member_session'
            self.session_name = str(session_file)
            logger.info(f"Session dosyası: {self.session_name}")
        else:
            self.session_name = 'member_session'
            logger.warning("Config nesnesi bulunamadı, varsayılan session konumu kullanılıyor!")
            
        # Telethon istemcisini yapılandır
        self.client = TelegramClient(
            self.session_name, 
            self.api_id, 
            self.api_hash,
            device_model="Telegram Bot",
            system_version="1.0",
            app_version="3.1"
        )
        
        self.is_running = True
        self.is_paused = False
        self.error_groups: Set[int] = set()
        self.error_reasons: Dict[int, str] = {}
        self.start_time = datetime.now()
        self.sent_count = 0
        self.processed_groups: Set[int] = set()
        self.last_message_time = None
        
        # Terminal formatları
        self.terminal_format = LoggerSetup.get_terminal_format()
        
        # Durum raporlama zamanı
        self.last_status_report = datetime.now()
        self.status_report_interval = 300  # 5 dakikada bir durum raporu
        
    async def start(self):
        """Botu başlatır"""
        try:
            logger.info("Bot başlatılıyor...")
            await self.client.start(phone=self.phone)
            logger.info(self.terminal_format['basari'].format("Bot başlatıldı!"))
            
            # Periyodik durum raporlaması için görev
            asyncio.create_task(self._periodic_status_report())
            
            # Bot duruncaya kadar çalıştır
            await self._run_until_disconnected()
            
        except KeyboardInterrupt:
            logger.info("Bot manuel olarak durduruldu")
        except Exception as e:
            logger.error(f"Bot başlatma hatası: {str(e)}", exc_info=True)
        finally:
            await self._cleanup()
    
    async def _periodic_status_report(self):
        """Periyodik olarak durum raporu oluşturur"""
        while self.is_running:
            current_time = datetime.now()
            if (current_time - self.last_status_report).total_seconds() >= self.status_report_interval:
                self.show_status()
                self.last_status_report = current_time
            
            await asyncio.sleep(60)  # Her dakika kontrol et
            
    async def _run_until_disconnected(self):
        """Bot bağlantısı kopana kadar çalıştırır"""
        await self.client.run_until_disconnected()
            
    async def _cleanup(self):
        """Bot kapatılırken çalışacak temizleme işlemleri"""
        try:
            logger.info("Temizleme işlemleri başlatılıyor...")
            
            # Veritabanı bağlantısını kapat
            if hasattr(self, 'db') and self.db:
                self.db.close()
                logger.info("Veritabanı bağlantısı kapatıldı")
                
            # Telethon oturumunu kapat
            if hasattr(self, 'client') and self.client:
                if self.client.is_connected():
                    await self.client.disconnect()
                    logger.info("Telegram bağlantısı kapatıldı")
                    
        except Exception as e:
            logger.error(f"Temizleme işlemi sırasında hata: {str(e)}", exc_info=True)
        finally:
            logger.info("Bot temizleme işlemleri tamamlandı")
            
    def toggle_pause(self):
        """Botu duraklat/devam ettir"""
        self.is_paused = not self.is_paused
        status = "duraklatıldı ⏸️" if self.is_paused else "devam ediyor ▶️"
        logger.info(self.terminal_format['bilgi'].format(f"Bot {status}"))
        
    def stop_bot(self):
        """Botu durdur"""
        self.is_running = False
        logger.info(self.terminal_format['uyari'].format("Bot durduruluyor..."))
        asyncio.create_task(self.client.disconnect())
        
    async def wait_with_countdown(self, seconds: int) -> None:
        """Geri sayımlı bekleme fonksiyonu"""
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < seconds:
            if not self.is_running or self.is_paused:
                break
                
            remaining = seconds - int((datetime.now() - start_time).total_seconds())
            minutes, secs = divmod(remaining, 60)
            
            print(f"\r{self.terminal_format['bekleme'].format(minutes, secs)}", end='')
            await asyncio.sleep(1)
        print()
        
    async def command_listener(self):
        """Gelişmiş komut satırı arayüzü"""
        commands = {
            'p': {'desc': 'Duraklat/Devam', 'func': self.toggle_pause},
            'q': {'desc': 'Çıkış', 'func': self.stop_bot},
            's': {'desc': 'Durum Göster', 'func': self.show_status},
            'h': {'desc': 'Yardım', 'func': self.show_help},
            'c': {'desc': 'Konsolu Temizle', 'func': self.clear_console},
        }
        
        self.show_help()  # Başlangıçta komutları göster
        
        while self.is_running:
            try:
                # Python 3.9+ için asyncio.to_thread, daha eski sürümlerde uyumluluk için
                if hasattr(asyncio, 'to_thread'):
                    cmd_input = await asyncio.to_thread(input, "\nKomut > ")
                else:
                    # Eski Python sürümleri için uyumluluk
                    loop = asyncio.get_event_loop()
                    cmd_input = await loop.run_in_executor(None, lambda: input("\nKomut > "))
                    
                cmd = cmd_input.strip().lower()
                
                if cmd in commands:
                    commands[cmd]['func']()
                elif cmd:
                    print(f"Bilinmeyen komut: '{cmd}'. Yardım için 'h' yazın.")
            except EOFError:
                # Ctrl+D ile çıkış
                logger.info("EOF tespit edildi, bot kapatılıyor...")
                self.stop_bot()
            except KeyboardInterrupt:
                # Ctrl+C ile çıkış 
                logger.info("Klavye kesintisi, bot kapatılıyor...")
                self.stop_bot()
            except Exception as e:
                logger.error(f"Komut işleme hatası: {str(e)}")
                await asyncio.sleep(1)  # Hata durumunda kısa bir bekleme
    
    def show_help(self):
        """Komut yardımını gösterir"""
        print(f"\n{Fore.CYAN}=== BOT KOMUTLARI ==={Style.RESET_ALL}")
        print(f"{Fore.GREEN}p{Style.RESET_ALL} - Duraklat/Devam et")
        print(f"{Fore.GREEN}s{Style.RESET_ALL} - Durum bilgisi göster")
        print(f"{Fore.GREEN}c{Style.RESET_ALL} - Konsolu temizle")
        print(f"{Fore.GREEN}q{Style.RESET_ALL} - Çıkış")
        print(f"{Fore.GREEN}h{Style.RESET_ALL} - Bu yardım mesajı")
        print(f"{Fore.CYAN}=================={Style.RESET_ALL}\n")
        
    def show_status(self):
        """Bot durumunu detaylı gösterir"""
        status = "Duraklatıldı ⏸️" if self.is_paused else "Çalışıyor ▶️"
        runtime = datetime.now() - self.start_time
        hours, remainder = divmod(runtime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        print(f"\n{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}📊 BOT DURUM RAPORU{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}")
        
        # Genel İstatistikler
        stats = [
            ["Çalışma Durumu", status],
            ["Çalışma Süresi", f"{int(hours)}s {int(minutes)}d {int(seconds)}s"],
            ["Toplam Gönderilen Mesaj", self.sent_count],
            ["İşlenmiş Grup Sayısı", len(self.processed_groups)],
            ["Hatalı Grup Sayısı", len(self.error_groups)]
        ]
        
        if self.last_message_time:
            stats.append(["Son Mesaj Zamanı", self.last_message_time.strftime('%H:%M:%S')])
        
        print(tabulate(stats, headers=["Özellik", "Değer"], tablefmt="grid"))
        
        # Hata veren grupları göster
        if self.error_groups:
            print(f"\n{Fore.YELLOW}⚠️ HATA VEREN GRUPLAR:{Style.RESET_ALL}")
            error_list = []
            for group_id, reason in self.error_reasons.items():
                error_list.append([group_id, reason])
            print(tabulate(error_list, headers=["Grup ID", "Neden"], tablefmt="grid"))
        
        print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
        
        # Loga da kaydet
        logger.debug("Durum raporu oluşturuldu")
        
    def _start_keyboard_listener(self):
        """Klavye yerine komut satırı kontrolü"""
        asyncio.create_task(self.command_listener())
        logger.info(self.terminal_format['bilgi'].format("Kontroller: [p]=Duraklat/Devam, [q]=Çıkış, [s]=Durum, [h]=Yardım"))
        
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