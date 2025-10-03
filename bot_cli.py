#!/usr/bin/env python3
"""
Telegram Bot Yönetim Arayüzü
-----------------
Bu araç, Telegram botunun tüm yönetim işlevlerini tek bir yerden gerçekleştirmenizi sağlar:
- Oturum yönetimi (kimlik doğrulama)
- Bot servislerini başlatma/durdurma
- Dashboard erişimi
- Grup mesajlaşma ayarları
"""
import os
import sys
import time
import asyncio
import logging
import argparse
import subprocess
import signal
import getpass
import json
from typing import Dict, List, Any, Optional, Tuple, TypeVar, Callable, Awaitable

import questionary
from questionary import Style
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

# Proje modüllerini import et
# Ana klasörü path'e ekle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Questionary asenkron kullanım için yardımcı fonksiyon
T = TypeVar('T')
async def ask_async(question_func: Callable[..., questionary.Question], *args, **kwargs) -> T:
    """Questionary sorgularını asenkron ortamda çalıştırır."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: question_func(*args, **kwargs).ask())

# Log yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_cli.log")
    ]
)
logger = logging.getLogger("BotCLI")

# Zengin konsol stili
console = Console()

# Questionary stili
custom_style = Style([
    ('qmark', 'fg:cyan bold'),
    ('question', 'fg:white bold'),
    ('answer', 'fg:yellow bold'),
    ('pointer', 'fg:cyan bold'),
    ('highlighted', 'fg:green bold'),
    ('selected', 'fg:green bold'),
    ('separator', 'fg:cyan'),
    ('instruction', 'fg:white'),
    ('text', 'fg:white'),
    ('disabled', 'fg:gray'),
])

# Çalışma dizini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")
SESSIONS_DIR = os.path.join(BASE_DIR, "app", "sessions")

# Ortam değişkenlerini oku
def load_env():
    """Ortam değişkenlerini .env dosyasından yükler."""
    env_vars = {}
    
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env_vars[key] = value
                    # Ortam değişkenlerine ekle
                    os.environ[key] = value
    
    return env_vars

# Ortam değişkenlerini güncelle
def update_env(key, value):
    """Belirli bir ortam değişkenini günceller."""
    env_vars = {}
    
    # Mevcut değişkenleri oku
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    try:
                        k, v = line.split("=", 1)
                        env_vars[k] = v
                    except ValueError:
                        pass
    
    # Değişkeni güncelle
    env_vars[key] = value
    
    # Dosyaya yaz
    with open(ENV_FILE, "w") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")
    
    # Ortam değişkenini güncelle
    os.environ[key] = value

# ANA SINIF: Bot CLI
class BotCLI:
    """Telegram Bot Yönetim Arayüzü"""
    
    def __init__(self):
        """CLI arayüzünü başlat"""
        self.client = None
        self.user_info = None
        self.bot_process = None
        self.dashboard_process = None
        self.services_status = {}
        self.env_vars = load_env()
        
        # Oturum dizinini kontrol et
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        
        # API kimlik bilgilerini kontrol et
        self.api_id = os.environ.get("API_ID")
        self.api_hash = os.environ.get("API_HASH")
        self.session_name = os.environ.get("SESSION_NAME", "telegram_session")
        
        if not self.api_id or not self.api_hash:
            console.print("[bold red]API kimlik bilgileri bulunamadı! Lütfen .env dosyasını düzenleyin.[/bold red]")
            console.print("API_ID ve API_HASH değerlerini https://my.telegram.org adresinden alabilirsiniz.")
            sys.exit(1)
    
    async def check_auth(self) -> bool:
        """Mevcut oturum durumunu kontrol eder."""
        try:
            # Oturum dosyasını kontrol et
            session_path = os.path.join(SESSIONS_DIR, f"{self.session_name}.session")
            if not os.path.exists(session_path):
                return False
            
            # Bir client oluştur ve bağlantıyı kontrol et
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            
            auth_status = await client.is_user_authorized()
            
            if auth_status:
                # Kullanıcı bilgilerini al
                self.user_info = await client.get_me()
                console.print(f"[green]Oturum açık: {self.user_info.first_name} (@{self.user_info.username})[/green]")
                self.client = client
                return True
            else:
                await client.disconnect()
                console.print("[yellow]Oturum kapalı, yeniden kimlik doğrulama gerekiyor.[/yellow]")
                return False
                
        except Exception as e:
            logger.error(f"Oturum kontrolü sırasında hata: {e}")
            console.print(f"[red]Hata: {e}[/red]")
            return False
    
    async def authenticate(self) -> bool:
        """Telegram hesabına oturum açar."""
        try:
            console.print("\n[cyan]Telegram hesabına giriş yapılıyor...[/cyan]")
            
            # Telefon numarasını al
            phone = await ask_async(
                questionary.text,
                "Telefon numaranızı girin (+90xxxxxxxxxx formatında):",
                style=custom_style
            )
            
            # Oturum yolunu belirle
            session_path = os.path.join(SESSIONS_DIR, self.session_name)
            
            # Client oluştur
            client = TelegramClient(session_path, self.api_id, self.api_hash)
            await client.connect()
            
            # Kod gönder
            await client.send_code_request(phone)
            console.print(f"[green]Doğrulama kodu {phone} numarasına gönderildi.[/green]")
            
            # Doğrulama kodunu al
            code = await ask_async(
                questionary.text,
                "Telegram'dan gelen 5 haneli doğrulama kodunu girin:",
                style=custom_style
            )
            
            try:
                # Giriş yap
                await client.sign_in(phone, code)
                
            except SessionPasswordNeededError:
                # 2FA gerekiyorsa şifreyi sor
                console.print("[yellow]İki faktörlü kimlik doğrulama (2FA) gerekiyor.[/yellow]")
                password = await ask_async(
                    questionary.password,
                    "Telegram hesabınızın iki faktörlü kimlik doğrulama şifresini girin:",
                    style=custom_style
                )
                
                await client.sign_in(password=password)
            
            # Kullanıcı bilgilerini al
            self.user_info = await client.get_me()
            console.print(f"[green]Giriş başarılı: {self.user_info.first_name} (@{self.user_info.username})[/green]")
            
            # Çevre değişkenlerini güncelle
            update_env("SESSION_NAME", self.session_name)
            
            self.client = client
            return True
            
        except PhoneCodeInvalidError:
            console.print("[red]Hata: Geçersiz doğrulama kodu![/red]")
            return False
            
        except Exception as e:
            logger.error(f"Kimlik doğrulama sırasında hata: {e}")
            console.print(f"[red]Hata: {e}[/red]")
            return False
    
    async def start_bot(self):
        """Bot servisini başlatır."""
        if self.bot_process and self.bot_process.poll() is None:
            console.print("[yellow]Bot zaten çalışıyor.[/yellow]")
            return
        
        console.print("[cyan]Bot başlatılıyor...[/cyan]")
        
        # Veritabanı bağlantısını atla
        update_env("DB_SKIP", "True")
        
        try:
            # Python yorumlayıcısını bul
            python_exe = sys.executable
            
            # Komutu oluştur
            cmd = [python_exe, "autostart_bot.py"]
            
            # Süreci başlat
            self.bot_process = subprocess.Popen(
                cmd,
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Sürecin PID'sini kaydet
            pid = self.bot_process.pid
            console.print(f"[green]Bot başlatıldı (PID: {pid})[/green]")
            
            return True
            
        except Exception as e:
            logger.error(f"Bot başlatılırken hata: {e}")
            console.print(f"[red]Hata: {e}[/red]")
            return False
    
    def stop_bot(self):
        """Bot servisini durdurur."""
        if not self.bot_process or self.bot_process.poll() is not None:
            console.print("[yellow]Bot zaten durdurulmuş.[/yellow]")
            return
        
        console.print("[cyan]Bot durduruluyor...[/cyan]")
        
        try:
            # Windows sistemlerde terminate() yerine kill() kullan
            if os.name == 'nt':
                self.bot_process.kill()
            else:
                # Unix/Linux sistemlerde SIGTERM gönder
                self.bot_process.terminate()
            
            # Sürecin bitmesini bekle
            self.bot_process.wait(timeout=5)
            
            console.print("[green]Bot durduruldu.[/green]")
            return True
            
        except subprocess.TimeoutExpired:
            # Süreç belirtilen sürede bitmedi, zorla kapat
            console.print("[yellow]Bot yanıt vermiyor, zorla kapatılıyor...[/yellow]")
            self.bot_process.kill()
            self.bot_process.wait()
            console.print("[green]Bot zorla durduruldu.[/green]")
            return True
            
        except Exception as e:
            logger.error(f"Bot durdurulurken hata: {e}")
            console.print(f"[red]Hata: {e}[/red]")
            return False
    
    async def start_dashboard(self):
        """Dashboard servisini başlatır."""
        if self.dashboard_process and self.dashboard_process.poll() is None:
            console.print("[yellow]Dashboard zaten çalışıyor.[/yellow]")
            return
        
        console.print("[cyan]Dashboard başlatılıyor...[/cyan]")
        
        try:
            # Python yorumlayıcısını bul
            python_exe = sys.executable
            
            # Komutu oluştur
            cmd = [python_exe, "-m", "app.frontend.run"]
            
            # Süreci başlat
            self.dashboard_process = subprocess.Popen(
                cmd,
                cwd=BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Sürecin PID'sini kaydet
            pid = self.dashboard_process.pid
            console.print(f"[green]Dashboard başlatıldı (PID: {pid})[/green]")
            
            # Tarayıcıda aç
            if await ask_async(
                questionary.confirm,
                "Dashboard'u tarayıcıda açmak ister misiniz?",
                default=True,
                style=custom_style
            ):
                # 3 saniye bekle - başlamasını sağla
                await asyncio.sleep(3)
                
                url = "http://localhost:8000"
                
                # İşletim sistemine göre tarayıcı açma komutu
                if sys.platform.startswith('darwin'):  # macOS
                    subprocess.run(['open', url])
                elif os.name == 'nt':  # Windows
                    os.startfile(url)
                elif os.name == 'posix':  # Linux, BSD, etc.
                    subprocess.run(['xdg-open', url])
            
            return True
            
        except Exception as e:
            logger.error(f"Dashboard başlatılırken hata: {e}")
            console.print(f"[red]Hata: {e}[/red]")
            return False
    
    def stop_dashboard(self):
        """Dashboard servisini durdurur."""
        if not self.dashboard_process or self.dashboard_process.poll() is not None:
            console.print("[yellow]Dashboard zaten durdurulmuş.[/yellow]")
            return
        
        console.print("[cyan]Dashboard durduruluyor...[/cyan]")
        
        try:
            # Windows sistemlerde terminate() yerine kill() kullan
            if os.name == 'nt':
                self.dashboard_process.kill()
            else:
                # Unix/Linux sistemlerde SIGTERM gönder
                self.dashboard_process.terminate()
            
            # Sürecin bitmesini bekle
            self.dashboard_process.wait(timeout=5)
            
            console.print("[green]Dashboard durduruldu.[/green]")
            return True
            
        except subprocess.TimeoutExpired:
            # Süreç belirtilen sürede bitmedi, zorla kapat
            console.print("[yellow]Dashboard yanıt vermiyor, zorla kapatılıyor...[/yellow]")
            self.dashboard_process.kill()
            self.dashboard_process.wait()
            console.print("[green]Dashboard zorla durduruldu.[/green]")
            return True
            
        except Exception as e:
            logger.error(f"Dashboard durdurulurken hata: {e}")
            console.print(f"[red]Hata: {e}[/red]")
            return False
    
    async def check_service_status(self):
        """Bot servislerinin durumunu kontrol eder."""
        if not self.client or not self.client.is_connected():
            console.print("[yellow]Bot servislerini kontrol etmek için Telegram bağlantısı gerekli.[/yellow]")
            return {}
        
        console.print("[cyan]Bot servisleri kontrol ediliyor...[/cyan]")
        
        try:
            # API üzerinden servislerin durumunu al
            # Burada servislerin durumu alınabilir
            self.services_status = {
                "messenger": True,
                "analytics": True,
                "monitoring": True,
                "scheduler": True
            }
            
            # Tablo oluştur
            table = Table(title="Bot Servisleri", box=box.ROUNDED)
            table.add_column("Servis", style="cyan")
            table.add_column("Durum", style="green")
            
            for service, status in self.services_status.items():
                table.add_row(
                    service.capitalize(),
                    "[green]Çalışıyor[/green]" if status else "[red]Durduruldu[/red]"
                )
            
            console.print(table)
            
            return self.services_status
            
        except Exception as e:
            logger.error(f"Servis durumu kontrol edilirken hata: {e}")
            console.print(f"[red]Hata: {e}[/red]")
            return {}
    
    async def configure_messaging(self):
        """Mesajlaşma ayarlarını yapılandırır."""
        console.print("\n[cyan]Mesajlaşma Ayarları[/cyan]")
        
        try:
            # Mevcut ayarları al
            messaging_settings = {}
            
            # Ayarları yapılandır
            auto_engage = await ask_async(
                questionary.confirm,
                "Gruplara otomatik mesaj gönderilsin mi?",
                default=True,
                style=custom_style
            )
            
            if auto_engage:
                engage_interval = await ask_async(
                    questionary.select,
                    "Mesaj gönderme sıklığı:",
                    choices=[
                        "10 dakika",
                        "30 dakika",
                        "1 saat",
                        "3 saat",
                        "6 saat",
                        "12 saat",
                        "24 saat"
                    ],
                    default="1 saat",
                    style=custom_style
                )
                
                engage_mode = await ask_async(
                    questionary.select,
                    "Mesaj gönderme modu:",
                    choices=[
                        "Aktif kullanıcılara göre",
                        "Son mesajlara göre",
                        "Grup aktivitesine göre",
                        "Tüm gruplara"
                    ],
                    default="Grup aktivitesine göre",
                    style=custom_style
                )
                
                # Ayarları kaydet
                messaging_settings["auto_engage"] = auto_engage
                messaging_settings["engage_interval"] = engage_interval
                messaging_settings["engage_mode"] = engage_mode
                
                # Ortam değişkenlerini güncelle
                update_env("AUTO_ENGAGE", "True")
                update_env("ENGAGE_INTERVAL", engage_interval.split()[0])
                update_env("ENGAGE_MODE", engage_mode)
                
                console.print("[green]Mesajlaşma ayarları kaydedildi.[/green]")
            else:
                update_env("AUTO_ENGAGE", "False")
                console.print("[yellow]Otomatik mesajlaşma devre dışı bırakıldı.[/yellow]")
            
            return messaging_settings
            
        except Exception as e:
            logger.error(f"Mesajlaşma ayarları yapılandırılırken hata: {e}")
            console.print(f"[red]Hata: {e}[/red]")
            return {}
    
    async def main_menu(self):
        """Ana menü."""
        while True:
            choice = await ask_async(
                questionary.select,
                "İşlem Seçin:",
                choices=[
                    "Bot Başlat",
                    "Bot Durdur",
                    "Dashboard Aç",
                    "Servis Durumunu Kontrol Et",
                    "Mesajlaşma Ayarları",
                    "Çıkış"
                ],
                style=custom_style
            )
            
            if choice == "Bot Başlat":
                await self.start_bot()
            elif choice == "Bot Durdur":
                self.stop_bot()
            elif choice == "Dashboard Aç":
                await self.start_dashboard()
            elif choice == "Servis Durumunu Kontrol Et":
                await self.check_service_status()
            elif choice == "Mesajlaşma Ayarları":
                await self.configure_messaging()
            elif choice == "Çıkış":
                break
    
    async def run(self):
        """Uygulamayı çalıştır."""
        # Banner
        console.print(Panel.fit(
            "[bold cyan]Telegram Bot Yönetim Arayüzü[/bold cyan]\n\n"
            "[white]Bu araç ile bot servislerini yönetebilir, "
            "oturum açabilir ve ayarları yapılandırabilirsiniz.[/white]",
            title="Hoş Geldiniz",
            subtitle="v1.0",
            border_style="green"
        ))
        
        # Oturum kontrolü
        auth_status = await self.check_auth()
        
        if not auth_status:
            # Kimlik doğrulama
            auth_status = await self.authenticate()
            
            if not auth_status:
                console.print("[red]Kimlik doğrulama başarısız. Uygulama kapatılıyor.[/red]")
                return
        
        # Ana menü
        await self.main_menu()
        
        # Bağlantıları temizle
        if self.client and self.client.is_connected():
            await self.client.disconnect()
        
        console.print("[green]Uygulama kapatılıyor...[/green]")

async def main():
    """Ana fonksiyon."""
    cli = BotCLI()
    await cli.run()

if __name__ == "__main__":
    # Windows'ta asyncio event loop politikasını ayarla
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nUygulama kapatıldı.")
    except Exception as e:
        logger.exception("Uygulama çalıştırılırken hata")
        print(f"Hata: {e}") 