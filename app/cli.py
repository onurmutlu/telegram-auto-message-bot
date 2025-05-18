#!/usr/bin/env python3
"""
# ============================================================================ #
# Dosya: cli.py
# Yol: /Users/siyahkare/code/telegram-bot/app/cli.py
# İşlev: Bot için komut satırı arayüzü. Bot yönetimi için kullanılır.
#
# Versiyon: v1.0.0
# ============================================================================ #
"""

import asyncio
import os
import sys
import argparse
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy import text

# Proje kök dizinini Python yoluna ekle
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_dir)

from app.core.config import settings
from app.db.session import get_session
from app.services.service_manager import ServiceManager

# Renklendirme için ANSI kodları
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Log yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("bot-cli")

class BotCLI:
    """
    Bot için komut satırı arayüzü.
    Bu arayüz, botu başlatmak, durdurmak, servisleri yönetmek ve 
    sistem durumunu kontrol etmek için kullanılır.
    """
    
    def __init__(self):
        self.service_manager = None
        self.client = None
        self.db = None
    
    async def initialize(self):
        """CLI'ı başlat, veritabanı bağlantısını kur."""
        try:
            # Veritabanı bağlantısı
            self.db = next(get_session())
            return True
        except Exception as e:
            logger.error(f"CLI başlatma hatası: {str(e)}")
            return False
    
    async def start_bot(self):
        """Botu ve tüm servisleri başlat."""
        print(f"{Colors.BOLD}{Colors.BLUE}Bot başlatılıyor...{Colors.ENDC}")
        
        try:
            # Main modülünü dinamik olarak import et
            from app.main import TelegramBot
            
            # Bot nesnesini oluştur
            bot = TelegramBot()
            
            # Botu başlat
            await bot.initialize()
            await bot.start()
            
            print(f"{Colors.GREEN}Bot başarıyla başlatıldı{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.RED}Bot başlatma hatası: {str(e)}{Colors.ENDC}")
    
    async def stop_bot(self):
        """Botu ve tüm servisleri durdur."""
        print(f"{Colors.BOLD}{Colors.BLUE}Bot durduruluyor...{Colors.ENDC}")
        
        try:
            # Çalışan PID dosyalarını kontrol et
            bot_pids_file = os.path.join(project_dir, ".bot_pids")
            if os.path.exists(bot_pids_file):
                with open(bot_pids_file, "r") as f:
                    pids = f.read().strip().split("\n")
                
                for pid in pids:
                    if pid:
                        try:
                            pid = int(pid)
                            print(f"PID {pid} durduruluyor...")
                            os.kill(pid, 15)  # SIGTERM gönder
                        except ProcessLookupError:
                            print(f"PID {pid} bulunamadı, atlanıyor")
                        except Exception as e:
                            print(f"PID {pid} durdurulurken hata: {str(e)}")
                
                # PID dosyasını temizle
                os.remove(bot_pids_file)
            else:
                print("Bot PID dosyası bulunamadı. Bot çalışmıyor olabilir.")
            
            print(f"{Colors.GREEN}Bot durdurma işlemi tamamlandı{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.RED}Bot durdurma hatası: {str(e)}{Colors.ENDC}")
    
    async def status(self):
        """Bot ve servis durumlarını göster."""
        print(f"{Colors.BOLD}{Colors.BLUE}Bot Durumu{Colors.ENDC}")
        
        # Bot PID durumu
        bot_pids_file = os.path.join(project_dir, ".bot_pids")
        if os.path.exists(bot_pids_file):
            with open(bot_pids_file, "r") as f:
                pids = f.read().strip().split("\n")
            
            active_pids = []
            for pid in pids:
                if pid:
                    try:
                        pid = int(pid)
                        # PID hala çalışıyor mu kontrol et
                        os.kill(pid, 0)  # Sinyal göndermeden sadece PID kontrolü
                        active_pids.append(pid)
                    except ProcessLookupError:
                        pass
                    except Exception:
                        pass
            
            if active_pids:
                print(f"{Colors.GREEN}Bot çalışıyor - PID: {', '.join(map(str, active_pids))}{Colors.ENDC}")
            else:
                print(f"{Colors.RED}Bot çalışmıyor (PID dosyası var ama süreçler aktif değil){Colors.ENDC}")
        else:
            print(f"{Colors.RED}Bot çalışmıyor{Colors.ENDC}")
        
        # Veritabanı bağlantısı
        try:
            db = next(get_session())
            result = db.execute(text("SELECT 1"))
            if result.scalar() == 1:
                print(f"{Colors.GREEN}Veritabanı bağlantısı: OK{Colors.ENDC}")
            else:
                print(f"{Colors.RED}Veritabanı bağlantısı: HATA{Colors.ENDC}")
            db.close()
        except Exception as e:
            print(f"{Colors.RED}Veritabanı bağlantısı: HATA - {str(e)}{Colors.ENDC}")
        
        # Servis durumları
        try:
            # HealthService üzerinden durumu al
            print("Bot nesnesini oluşturuyor...")
            from app.main import TelegramBot
            
            # Bot nesnesini oluştur
            bot = TelegramBot()
            
            print("Bot başlatılıyor...")
            # Botu başlat
            await bot.initialize()
            
            print("Health servisini kontrol ediyor...")
            # Health servisini al
            health_service = bot.services.get("health")
            if health_service:
                print("Health servisinden durum alınıyor...")
                health_status = await health_service.get_detailed_status()
                
                print(f"\n{Colors.BOLD}{Colors.BLUE}Sistem Durumu:{Colors.ENDC}")
                print(f"  CPU Kullanımı: {health_status['current']['system'].get('cpu_usage', 'N/A')}%")
                print(f"  RAM Kullanımı: {health_status['current']['system'].get('ram_usage', 'N/A')}%")
                print(f"  Disk Kullanımı: {health_status['current']['system'].get('disk_usage', 'N/A')}%")
                
                print(f"\n{Colors.BOLD}{Colors.BLUE}Servis Durumları:{Colors.ENDC}")
                for service_name, service_data in health_status['current']['services'].get('services', {}).items():
                    status = service_data.get('running', False)
                    status_color = Colors.GREEN if status else Colors.RED
                    print(f"  {service_name}: {status_color}{'ÇALIŞIYOR' if status else 'DURUM'}{Colors.ENDC}")
                
                print(f"\n{Colors.BOLD}{Colors.BLUE}Telegram Durumu:{Colors.ENDC}")
                tg_status = health_status['current']['telegram']
                tg_connected = tg_status.get('connected', False)
                tg_color = Colors.GREEN if tg_connected else Colors.RED
                print(f"  Bağlantı: {tg_color}{'BAĞLI' if tg_connected else 'BAĞLANTI YOK'}{Colors.ENDC}")
                print(f"  Oturum Açık: {tg_color}{'EVET' if tg_status.get('authorized', False) else 'HAYIR'}{Colors.ENDC}")
                
            else:
                print(f"{Colors.RED}Health service bulunamadı, servis durumları alınamıyor{Colors.ENDC}")
            
            # Botu temizle
            print("Bot temizleniyor...")
            await bot.cleanup()
            
        except Exception as e:
            import traceback
            print(f"{Colors.RED}Servis durumlarını kontrol ederken hata: {str(e)}{Colors.ENDC}")
            print(f"{Colors.RED}Hata detayı: {traceback.format_exc()}{Colors.ENDC}")
    
    async def update_templates(self):
        """Mesaj şablonlarını yeniden yükle."""
        print(f"{Colors.BOLD}{Colors.BLUE}Mesaj şablonları yenileniyor...{Colors.ENDC}")
        
        try:
            # load_templates.py skriptini çalıştır
            from app.scripts.load_templates import load_templates
            
            result = await load_templates()
            
            if result:
                print(f"{Colors.GREEN}Mesaj şablonları başarıyla güncellendi{Colors.ENDC}")
            else:
                print(f"{Colors.RED}Mesaj şablonları güncellenirken hata oluştu{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.RED}Şablonları güncelleme hatası: {str(e)}{Colors.ENDC}")
    
    async def repair_database(self):
        """Veritabanı onarım ve bakım işlemlerini gerçekleştir."""
        print(f"{Colors.BOLD}{Colors.BLUE}Veritabanı bakımı başlatılıyor...{Colors.ENDC}")
        
        try:
            # fix_database.py skriptini çalıştır
            from app.scripts.fix_database import repair_database
            
            result = await repair_database()
            
            if result:
                print(f"{Colors.GREEN}Veritabanı bakımı başarıyla tamamlandı{Colors.ENDC}")
            else:
                print(f"{Colors.RED}Veritabanı bakımı sırasında sorunlar oluştu{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.RED}Veritabanı bakım hatası: {str(e)}{Colors.ENDC}")
    
    async def create_session(self):
        """Yeni Telegram oturumu oluştur."""
        print(f"{Colors.BOLD}{Colors.BLUE}Yeni Telegram oturumu oluşturuluyor...{Colors.ENDC}")
        
        try:
            from app.scripts.create_fresh_session import create_session
            
            result = await create_session()
            
            if result:
                print(f"{Colors.GREEN}Yeni oturum başarıyla oluşturuldu{Colors.ENDC}")
            else:
                print(f"{Colors.RED}Oturum oluşturulurken hata oluştu{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.RED}Oturum oluşturma hatası: {str(e)}{Colors.ENDC}")
    
    async def fix_connection(self):
        """Telegram bağlantısını onarır ve yeniden başlatır."""
        print(f"{Colors.BOLD}{Colors.BLUE}Telegram bağlantısı onarılıyor...{Colors.ENDC}")
        
        try:
            # Telegram reconnect aracını çalıştır
            import subprocess
            
            print(f"{Colors.BLUE}Telegram oturumunu kontrol ediliyor...{Colors.ENDC}")
            # Oturum dosyasını kontrol et
            session_file = f"{settings.SESSION_NAME}.session"
            if os.path.exists(session_file):
                print(f"{Colors.GREEN}Oturum dosyası bulundu: {session_file}{Colors.ENDC}")
            else:
                print(f"{Colors.RED}Oturum dosyası bulunamadı: {session_file}{Colors.ENDC}")
                print(f"{Colors.BLUE}Yeni oturum oluşturmak için 'python -m app.cli session' komutunu kullanın{Colors.ENDC}")
                return
            
            print(f"{Colors.BLUE}Telegram bağlantısı test ediliyor...{Colors.ENDC}")
            # Python scripti çalıştır
            reconnect_script = os.path.join(project_dir, "utilities", "telegram_reconnect.py")
            result = subprocess.run([sys.executable, reconnect_script], 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE,
                                    text=True)
            
            # Sonucu göster
            if result.returncode == 0:
                print(f"{Colors.GREEN}Telegram bağlantı testi başarılı{Colors.ENDC}")
                print(result.stdout)
            else:
                print(f"{Colors.RED}Telegram bağlantı testi başarısız oldu{Colors.ENDC}")
                print(f"Hata: {result.stderr}")
                print(f"Çıktı: {result.stdout}")
            
            # Bot çalışıyor mu kontrol et
            print(f"{Colors.BLUE}Bot durumu kontrol ediliyor...{Colors.ENDC}")
            # restart_bot.sh scriptini çalıştır
            restart_script = os.path.join(project_dir, "restart_bot.sh")
            if os.path.exists(restart_script):
                print(f"{Colors.GREEN}Bot yeniden başlatılıyor...{Colors.ENDC}")
                subprocess.run(["bash", restart_script], 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE)
                print(f"{Colors.GREEN}Bot yeniden başlatılma işlemi tamamlandı{Colors.ENDC}")
            else:
                print(f"{Colors.YELLOW}restart_bot.sh bulunamadı, botu manuel olarak yeniden başlatın{Colors.ENDC}")
            
        except Exception as e:
            print(f"{Colors.RED}Bağlantı onarım hatası: {str(e)}{Colors.ENDC}")
    
    async def connection_info(self):
        """Telegram bağlantı bilgilerini detaylı göster."""
        print(f"{Colors.BOLD}{Colors.BLUE}Telegram Bağlantı Bilgileri{Colors.ENDC}")
        print("="*50)
        
        try:
            # API bilgileri
            print(f"{Colors.BLUE}API Bilgileri:{Colors.ENDC}")
            print(f"  API ID: {settings.API_ID}")
            api_hash = settings.API_HASH
            if hasattr(api_hash, 'get_secret_value'):
                api_hash = api_hash.get_secret_value()
            print(f"  API HASH: {api_hash[:5]}...{api_hash[-5:]}")
            
            # Oturum bilgileri
            print(f"\n{Colors.BLUE}Oturum Bilgileri:{Colors.ENDC}")
            session_path = f"{settings.SESSION_NAME}.session"
            if os.path.exists(session_path):
                session_size = os.path.getsize(session_path)
                print(f"  Oturum dosyası: {Colors.GREEN}Mevcut{Colors.ENDC} ({session_size} bytes)")
                # Son değiştirilme zamanı
                mod_time = os.path.getmtime(session_path)
                mod_time_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
                print(f"  Son değiştirilme: {mod_time_str}")
            else:
                print(f"  Oturum dosyası: {Colors.RED}Bulunamadı{Colors.ENDC}")
            
            # PID bilgileri
            print(f"\n{Colors.BLUE}Process Bilgileri:{Colors.ENDC}")
            pid_file = os.path.join(project_dir, "bot.pid")
            if os.path.exists(pid_file):
                with open(pid_file, "r") as f:
                    pid = f.read().strip()
                    if pid:
                        try:
                            os.kill(int(pid), 0)  # Sinyal göndermeden sadece PID kontrolü
                            print(f"  Bot PID: {Colors.GREEN}{pid} (Çalışıyor){Colors.ENDC}")
                        except:
                            print(f"  Bot PID: {Colors.RED}{pid} (Çalışmıyor){Colors.ENDC}")
                    else:
                        print(f"  Bot PID: {Colors.RED}Geçersiz{Colors.ENDC}")
            else:
                print(f"  Bot PID: {Colors.RED}Bulunamadı{Colors.ENDC}")
            
            # Health servisi üzerinden detaylı bilgi al
            print(f"\n{Colors.BLUE}Health Servisi Bilgileri:{Colors.ENDC}")
            try:
                # Bot nesnesini oluştur
                from app.main import TelegramBot
                bot = TelegramBot()
                await bot.initialize()
                
                # Health servisini al
                health_service = bot.services.get("health")
                if health_service:
                    health_status = await health_service.get_detailed_status()
                    tg_status = health_status['current']['telegram']
                    
                    print(f"  Bağlantı durumu: {Colors.GREEN if tg_status.get('connected', False) else Colors.RED}{tg_status.get('connection_status', 'unknown')}{Colors.ENDC}")
                    print(f"  Yetkilendirme: {Colors.GREEN if tg_status.get('authorized', False) else Colors.RED}{tg_status.get('auth_status', 'unknown')}{Colors.ENDC}")
                    
                    if 'ping_ms' in tg_status:
                        print(f"  Ping: {tg_status['ping_ms']} ms")
                    
                    if 'user_id' in tg_status:
                        print(f"  Kullanıcı ID: {tg_status['user_id']}")
                    
                    if 'username' in tg_status:
                        print(f"  Kullanıcı adı: @{tg_status['username'] or 'Yok'}")
                    
                    print(f"  Genel durum: {Colors.GREEN if tg_status.get('status') == 'healthy' else Colors.RED}{tg_status.get('status', 'unknown')}{Colors.ENDC}")
                
                # Botu temizle
                await bot.cleanup()
                
            except Exception as e:
                print(f"  {Colors.RED}Health servisi bilgileri alınamadı: {str(e)}{Colors.ENDC}")
            
            print("="*50)
            
        except Exception as e:
            print(f"{Colors.RED}Bağlantı bilgileri alınırken hata: {str(e)}{Colors.ENDC}")

def parse_args():
    """Komut satırı argümanlarını ayrıştır."""
    parser = argparse.ArgumentParser(description="Telegram Bot CLI")
    
    # Alt-komutlar
    subparsers = parser.add_subparsers(dest="command", help="Komut")
    
    # start komutu
    start_parser = subparsers.add_parser("start", help="Botu başlat")
    
    # stop komutu
    stop_parser = subparsers.add_parser("stop", help="Botu durdur")
    
    # status komutu
    status_parser = subparsers.add_parser("status", help="Bot durumunu kontrol et")
    
    # templates komutu
    templates_parser = subparsers.add_parser("templates", help="Mesaj şablonlarını güncelle")
    
    # repair komutu
    repair_parser = subparsers.add_parser("repair", help="Veritabanı onarım ve bakım işlemleri")
    
    # session komutu
    session_parser = subparsers.add_parser("session", help="Yeni Telegram oturumu oluştur")
    
    # fix komutu
    fix_parser = subparsers.add_parser("fix", help="Telegram bağlantısını onar")
    
    # info komutu
    info_parser = subparsers.add_parser("info", help="Telegram bağlantı bilgilerini göster")
    
    return parser.parse_args()

async def main():
    """Ana fonksiyon."""
    args = parse_args()
    
    cli = BotCLI()
    await cli.initialize()
    
    if args.command == "start":
        await cli.start_bot()
    elif args.command == "stop":
        await cli.stop_bot()
    elif args.command == "status":
        await cli.status()
    elif args.command == "templates":
        await cli.update_templates()
    elif args.command == "repair":
        await cli.repair_database()
    elif args.command == "session":
        await cli.create_session()
    elif args.command == "fix":
        await cli.fix_connection()
    elif args.command == "info":
        await cli.connection_info()
    else:
        print("Geçerli bir komut belirtmelisiniz. Yardım için --help kullanın.")

if __name__ == "__main__":
    asyncio.run(main())