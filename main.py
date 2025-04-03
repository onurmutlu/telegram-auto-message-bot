"""
# ============================================================================ #
# Dosya: main.py
# Yol: /Users/siyahkare/code/telegram-bot/main.py
# İşlev: Telegram Otomatik Mesajlaşma Sistemi Ana Modülü
#
# Build: 2025-04-01-03:00:00
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, Telegram üzerinde otomatik mesajlaşma sisteminin 
# ana kontrol bileşenidir:
#
# - Üç servisin entegrasyonu ve kontrolü:
#   * Mesaj servisi: Gruplara düzenli mesaj gönderimi
#   * Yanıt servisi: Gelen mesajlara otomatik yanıt üretimi
#   * DM servisi: Kullanıcılara özel mesaj/davet gönderimi
#
# - Özellikleri:
#   * Etkileşimli konsol arayüzü
#   * Gelişmiş hata yönetimi ve loglama
#   * Asenkron işlem desteği
#   * Kullanıcı veritabanı entegrasyonu
#   * Şablon tabanlı mesajlaşma sistemi
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""
import os
import sys
import asyncio
import logging
import argparse
import traceback
import threading
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from colorama import Fore, Style, init
from telethon import TelegramClient, errors as errors

# Proje modülleri
from config.settings import Config
from database.user_db import UserDatabase
from bot.services.dm_service import DirectMessageService
from bot.services.reply_service import ReplyService
from bot.handlers.group_handler import GroupHandler
from bot.services.service_factory import ServiceFactory  # Import ServiceFactory

# main.py dosyasının başlarında bir logging filtresi ekleyelim

import logging

# Çevre değişkenlerini yükle
load_dotenv()

# Renkli çıktı desteğini ayarla
init(autoreset=True)
logger = logging.getLogger(__name__)

# Global durdurma eventi
stop_event = threading.Event()

def is_terminal_support_color():
    """
    Terminalin renk desteği olup olmadığını tespit eder.
    
    Returns:
        bool: Terminal renk destekliyorsa True, değilse False
    """
    if not sys.stdout.isatty():
        return False
    return True

def print_banner():
    """Uygulama başlangıç banner'ını gösterir."""
    print(f"\n{Fore.CYAN}╔{'═' * 60}╗{Style.RESET_ALL}")
    print(f"{Fore.CYAN}║{' ' * 10}TELEGRAM AUTO MESSAGE BOT v3.4.6{' ' * 10}║{Style.RESET_ALL}")
    print(f"{Fore.CYAN}║{' ' * 15}Author: @siyahkare{' ' * 15}║{Style.RESET_ALL}")
    print(f"{Fore.CYAN}║{' ' * 5}Ticari Ürün - Tüm Hakları Saklıdır © 2025{' ' * 5}║{Style.RESET_ALL}")
    print(f"{Fore.CYAN}╚{'═' * 60}╝{Style.RESET_ALL}")
    print(f"\n{Fore.WHITE}Bu yazılım, SiyahKare Yazılım tarafından geliştirilmiş ticari bir ürünüdür.{Style.RESET_ALL}")

def print_status(services):
    """
    Servislerin durum bilgilerini tablolaştırarak gösterir.
    
    Üç farklı servisin (mesaj, yanıt, özel mesaj) güncel durumunu,
    istatistiklerini ve performans metriklerini formatlı olarak ekrana yazdırır.
    
    Args:
        services (dict): 'message', 'reply', 'dm' anahtarlarıyla servis nesnelerini 
                         içeren sözlük
    """
    print(f"\n{Fore.CYAN}=== SERVİS DURUMU ==={Style.RESET_ALL}")
    
    # Mesaj servisi durumu
    msg_service = services['message']
    status = msg_service.get_status()
    print(f"{Fore.GREEN}📩 Mesaj Servisi:{Style.RESET_ALL}")
    print(f"  Durum: {'Çalışıyor' if status['running'] else 'Duraklatıldı'}")
    print(f"  Son çalışma: {status['last_run']}")
    print(f"  Gönderilen mesajlar: {status['messages_sent']}")
    print(f"  Başarısız mesajlar: {status['messages_failed']}")
    print(f"  Aktif gruplar: {status['active_groups']}")
    print(f"  Geçerli aralık: {status['current_interval']}")
    
    # Yanıt servisi durumu
    reply_service = services['reply']
    status = reply_service.get_status()
    print(f"\n{Fore.YELLOW}💬 Yanıt Servisi:{Style.RESET_ALL}")
    print(f"  Durum: {'Çalışıyor' if status['running'] else 'Duraklatıldı'}")
    print(f"  İşlenen mesajlar: {status['processed_messages']}")
    print(f"  Gönderilen yanıtlar: {status['replies_sent']}")
    
    # Özel mesaj servisi durumu
    dm_service = services['dm']
    status = dm_service.get_status()
    print(f"\n{Fore.MAGENTA}📨 Özel Mesaj Servisi:{Style.RESET_ALL}")
    print(f"  Durum: {'Çalışıyor' if status['running'] else 'Duraklatıldı'}")
    print(f"  İşlenen özel mesajlar: {status['processed_dms']}")
    print(f"  Gönderilen davetler: {status['invites_sent']}")

def print_help():
    """Yardım mesajını gösterir"""
    print(f"\n{Fore.CYAN}=== KOMUTLAR ==={Style.RESET_ALL}")
    print(f"{Fore.GREEN}s{Style.RESET_ALL} - Durum bilgisini göster")
    print(f"{Fore.GREEN}p{Style.RESET_ALL} - Tüm servisleri duraklat/devam ettir")
    print(f"{Fore.GREEN}pm{Style.RESET_ALL} - Mesaj servisini duraklat/devam ettir")
    print(f"{Fore.GREEN}pr{Style.RESET_ALL} - Yanıt servisini duraklat/devam ettir")
    print(f"{Fore.GREEN}pd{Style.RESET_ALL} - Özel mesaj servisini duraklat/devam ettir")
    print(f"{Fore.GREEN}c{Style.RESET_ALL} - Konsolu temizle")
    print(f"{Fore.GREEN}d{Style.RESET_ALL} - Debug modu aç/kapat")
    print(f"{Fore.GREEN}u{Style.RESET_ALL} - Kullanıcı istatistiklerini göster")
    print(f"{Fore.GREEN}q{Style.RESET_ALL} - Güvenli çıkış")
    print(f"{Fore.GREEN}h{Style.RESET_ALL} - Bu yardım mesajını göster")

def print_tips():
    """Kullanım ipuçlarını gösterir"""
    print(f"\n{Fore.CYAN}=== HIZLI İPUÇLARI ==={Style.RESET_ALL}")
    headers = ["Konu", "Açıklama"]
    rows = [
        ["h", "Mevcut komutları gösterme"],
        ["s", "Servis durumunu görüntüleme"],
        ["runtime/logs/", "Hata kayıtlarına erişim"],
        ["Ctrl+C / q", "Güvenli kapatma"],
        ["İnternet", "Stabil bağlantı gerekli"],
        ["Limitler", "Mesaj gönderim ayarlarını düşük tutun"]
    ]
    
    col_width = max(len(word) for row in rows for word in row) + 2
    print("".join(word.ljust(col_width) for word in headers))
    print("".join("-" * (col_width-1) for _ in headers))
    for row in rows:
        print("".join(word.ljust(col_width) for word in row))

def print_dashboard(services):
    """Renkli ve detaylı durum panosu gösterir."""
    os.system('cls' if os.name == 'nt' else 'clear')  # Konsol ekranını temizle
    
    # Banner
    print(f"\n{Fore.CYAN}╔{'═' * 60}╗{Style.RESET_ALL}")
    print(f"{Fore.CYAN}║{' ' * 13}TELEGRAM BOT DURUM PANOSU{' ' * 13}║{Style.RESET_ALL}")
    print(f"{Fore.CYAN}╚{'═' * 60}╝{Style.RESET_ALL}")
    
    # Genel durum
    now = datetime.now()
    run_time = now - start_time
    hours, remainder = divmod(run_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    print(f"\n{Fore.YELLOW}▶ GÖSTERİM ZAMANI: {now.strftime('%H:%M:%S')}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}▶ ÇALIŞMA SÜRESİ: {hours:02}:{minutes:02}:{seconds:02}{Style.RESET_ALL}")
    
    # DM servisi
    dm_service = services.get('dm')
    if (dm_service):
        total_invites = dm_service.invites_sent
        status = "✅ ÇALIŞIYOR" if dm_service.running else "❌ DURDURULDU"
        
        print(f"\n{Fore.GREEN}┌─{'─' * 58}┐{Style.RESET_ALL}")
        print(f"{Fore.GREEN}│ DM SERVİSİ - {status:<48}│{Style.RESET_ALL}")
        print(f"{Fore.GREEN}├─{'─' * 58}┤{Style.RESET_ALL}")
        
        # Davet gönderimleri
        print(f"{Fore.GREEN}│ Gönderilen Davetler: {total_invites:<42}│{Style.RESET_ALL}")
        
        # Son aktivite
        last_activity = getattr(dm_service, 'last_activity', now)
        last_activity_str = last_activity.strftime('%H:%M:%S') if isinstance(last_activity, datetime) else "Bilinmiyor"
        print(f"{Fore.GREEN}│ Son Aktivite: {last_activity_str:<47}│{Style.RESET_ALL}")
        
        # Rate limiter durumu
        if hasattr(dm_service, 'rate_limiter'):
            rate_info = dm_service.rate_limiter.get_status()
            print(f"{Fore.GREEN}│ Hız Limit: {rate_info['rate']}/{rate_info['period']:.1f}s (Kullanılan: {rate_info['used_slots']}/{rate_info['rate']})│{Style.RESET_ALL}")
            if rate_info['time_since_error'] is not None:
                print(f"{Fore.GREEN}│ Son Hatadan Beri: {rate_info['time_since_error']//60:.0f} dk  {' ' * 33}│{Style.RESET_ALL}")
        
        # Grafik gösterim - Davet gönderim grafiği
        if total_invites > 0:
            scale = min(50, total_invites)  # Maksimum 50 karakter
            bar = '█' * scale
            print(f"{Fore.GREEN}│ Davet Grafiği: {bar}{' ' * (46-scale)}│{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}│ Davet Grafiği: [Aktivite yok]{' ' * 33}│{Style.RESET_ALL}")
        
        print(f"{Fore.GREEN}└─{'─' * 58}┘{Style.RESET_ALL}")
    
    # Grup servisi
    group_service = services.get('group')
    if group_service:
        sent_count = getattr(group_service, 'sent_count', 0)
        status = "✅ ÇALIŞIYOR" if getattr(group_service, 'is_running', False) else "❌ DURDURULDU"
        
        print(f"\n{Fore.BLUE}┌─{'─' * 58}┐{Style.RESET_ALL}")
        print(f"{Fore.BLUE}│ GRUP SERVİSİ - {status:<46}│{Style.RESET_ALL}")
        print(f"{Fore.BLUE}├─{'─' * 58}┤{Style.RESET_ALL}")
        
        # Gönderim sayıları
        print(f"{Fore.BLUE}│ Toplam Mesajlar: {sent_count:<43}│{Style.RESET_ALL}")
        
        # Aktivite grafiği
        if sent_count > 0:
            scale = min(50, sent_count)
            bar = '█' * scale
            print(f"{Fore.BLUE}│ Mesaj Grafiği: {bar}{' ' * (46-scale)}│{Style.RESET_ALL}")
        else:
            print(f"{Fore.BLUE}│ Mesaj Grafiği: [Aktivite yok]{' ' * 33}│{Style.RESET_ALL}")
        
        # Hatalı gruplar
        error_groups = getattr(group_service, 'error_groups', set())
        error_count = len(error_groups)
        print(f"{Fore.BLUE}│ Hatalı Gruplar: {error_count:<44}│{Style.RESET_ALL}")
        
        print(f"{Fore.BLUE}└─{'─' * 58}┘{Style.RESET_ALL}")
    
    # Veritabanı istatistikleri
    user_db = services.get('user_db')
    if user_db:
        try:
            total_users = user_db.get_user_count()
            invited_users = user_db.get_invited_user_count()
            
            print(f"\n{Fore.MAGENTA}┌─{'─' * 58}┐{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}│ VERİTABANI İSTATİSTİKLERİ{' ' * 36}│{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}├─{'─' * 58}┤{Style.RESET_ALL}")
            
            print(f"{Fore.MAGENTA}│ Toplam Kullanıcılar: {total_users:<39}│{Style.RESET_ALL}")
            print(f"{Fore.MAGENTA}│ Davet Gönderilen Kullanıcılar: {invited_users:<28}│{Style.RESET_ALL}")
            
            # İlerleme çubuğu
            if total_users > 0:
                percentage = invited_users / total_users * 100
                bar_length = 40
                completed = int(percentage / 100 * bar_length)
                print(f"{Fore.MAGENTA}│ Davet Oranı: {percentage:.1f}% [{'#' * completed}{' ' * (bar_length-completed)}] │{Style.RESET_ALL}")
            else:
                print(f"{Fore.MAGENTA}│ Davet Oranı: 0.0% [{' ' * 40}] │{Style.RESET_ALL}")
            
            print(f"{Fore.MAGENTA}└─{'─' * 58}┘{Style.RESET_ALL}")
        except:
            pass
    
    # Komutlar
    print(f"\n{Fore.WHITE}── KOMUTLAR ──────────────────────────────────────────{Style.RESET_ALL}")
    print(f"{Fore.WHITE}s: Durum Raporu | p: Servisleri Duraklat | h: Yardım | q: Çıkış{Style.RESET_ALL}")

async def keyboard_input_handler(services, config, user_db):
    """
    Kullanıcı klavye girdilerini asenkron olarak işler.
    
    Kullanıcıdan komut alır ve bu komutlara göre servisleri kontrol eder,
    durum raporları sunar veya debug modu gibi ayarları değiştirir.
    
    Args:
        services (dict): Kontrol edilecek servis nesnelerini içeren sözlük
        
    Komutlar:
        q: Programdan güvenli çıkış
        s: Servis durum bilgilerini görüntüle
        p: Tüm servisleri duraklat/devam ettir
        pm: Mesaj servisini duraklat/devam ettir
        pr: Yanıt servisini duraklat/devam ettir
        pd: Özel mesaj servisini duraklat/devam ettir
        c: Konsolu temizle
        d: Debug modunu aç/kapat
        h: Yardım bilgilerini göster
        u: Kullanıcı istatistiklerini göster
        i: İnteraktif dashboard'ı aç
    """
    paused = False
    debug_mode = False
    
    while not stop_event.is_set():
        try:
            # Non-blocking input
            if sys.stdin.isatty():
                cmd = await asyncio.to_thread(input)
                
                if cmd == 'q':
                    logger.info("Kullanıcı tarafından çıkış istendi")
                    stop_event.set()
                    break
                    
                elif cmd == 's':
                    print_dashboard(services)
                    
                elif cmd == 'p':
                    paused = not paused
                    for service_name, service in services.items():
                        service.running = not paused
                    status = "duraklatıldı" if paused else "devam ettirildi"
                    logger.info(f"Tüm servisler {status}")
                    print(f"{Fore.YELLOW}Tüm servisler {status}{Style.RESET_ALL}")
                
                elif cmd == 'pm':
                    services['message'].running = not services['message'].running
                    status = "duraklatıldı" if not services['message'].running else "devam ettirildi"
                    logger.info(f"Mesaj servisi {status}")
                    print(f"{Fore.YELLOW}Mesaj servisi {status}{Style.RESET_ALL}")
                
                elif cmd == 'pr':
                    services['reply'].running = not services['reply'].running
                    status = "duraklatıldı" if not services['reply'].running else "devam ettirildi"
                    logger.info(f"Yanıt servisi {status}")
                    print(f"{Fore.YELLOW}Yanıt servisi {status}{Style.RESET_ALL}")
                
                elif cmd == 'pd':
                    services['dm'].running = not services['dm'].running
                    status = "duraklatıldı" if not services['dm'].running else "devam ettirildi"
                    logger.info(f"Özel mesaj servisi {status}")
                    print(f"{Fore.YELLOW}Özel mesaj servisi {status}{Style.RESET_ALL}")
                
                elif cmd == 'c':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print_banner()
                
                elif cmd == 'd':
                    debug_mode = not debug_mode
                    log_level = logging.DEBUG if debug_mode else logging.INFO
                    logging.getLogger().setLevel(log_level)
                    print(f"{Fore.YELLOW}Debug modu {'açıldı' if debug_mode else 'kapatıldı'}{Style.RESET_ALL}")
                
                elif cmd == 'h':
                    print_help()
                
                elif cmd == 'u':
                    user_count = services['message'].bot.db.get_user_count()
                    active_users = services['message'].bot.db.get_active_user_count()
                    print(f"\n{Fore.CYAN}=== KULLANICI İSTATİSTİKLERİ ==={Style.RESET_ALL}")
                    print(f"Toplam kullanıcı sayısı: {user_count}")
                    print(f"Aktif kullanıcı sayısı: {active_users}")
                
                elif cmd == 'i':
                    print(f"{Fore.GREEN}İnteraktif dashboard başlatılıyor...{Style.RESET_ALL}")
                    try:
                        from bot.utils.interactive_dashboard import InteractiveDashboard
                        dashboard = InteractiveDashboard(services, config, user_db)
                        await dashboard.run()
                        print(f"{Fore.GREEN}Dashboard kapatıldı.{Style.RESET_ALL}")
                    except Exception as e:
                        print(f"{Fore.RED}Dashboard hatası: {str(e)}{Style.RESET_ALL}")
                
                else:
                    if cmd:  # Boş komut değilse
                        print(f"{Fore.RED}Geçersiz komut. Yardım için 'h' yazın.{Style.RESET_ALL}")
        
        except Exception as e:
            logger.error(f"Klavye girdi işleme hatası: {e}")
        
        await asyncio.sleep(0.1)  # CPU yükünü azaltmak için kısa bekleme

def setup_logger(debug_mode=False):
    """
    Logger yapılandırmasını yapar.
    
    Args:
        debug_mode (bool): Debug modunda çalıştırılacaksa True
    
    Returns:
        logging.Logger: Yapılandırılmış logger nesnesi
    """
    log_level = logging.DEBUG if debug_mode else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Önceki handler'ları temizle
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Konsol handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # Grup mesajlarını filtrele
    class GroupMessageFilter(logging.Filter):
        def filter(self, record):
            message = str(record.getMessage())
            return not "Received group message in chat" in message
    
    console_handler.addFilter(GroupMessageFilter())
    
    # Formatlayıcı
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # Handler'ı ekle
    root_logger.addHandler(console_handler)
    
    # Dosya handler
    try:
        os.makedirs("runtime/logs", exist_ok=True)
        log_file = "runtime/logs/bot.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Log dosyası oluşturma hatası: {e}")
    
    return logging.getLogger(__name__)

# Global başlangıç zamanı
start_time = datetime.now()

async def main():
    """
    Ana uygulama başlatma ve kontrol fonksiyonu.
    
    Yapılan işlemler:
    1. Komut satırı argümanlarını işleme
    2. Logging yapılandırması
    3. Veritabanı başlatma ve bakım işlemleri
    4. Bot istemcisinin yapılandırılması ve Telegram'a bağlantı
    5. Servislerin oluşturulması ve başlatılması
    6. Kullanıcı girdilerini işleyen asenkron görevin başlatılması
    7. Hata işleme ve temiz kapatma mekanizmaları
    
    Returns:
        int: İşlem başarılıysa 0, hata durumunda 1
        
    Raises:
        KeyboardInterrupt: Kullanıcı tarafından Ctrl+C ile durdurulduğunda
        Exception: Diğer tüm hatalar yakalanıp loglanır
    """
    global start_time
    
    # Komut satırı argümanlarını çözümle
    parser = argparse.ArgumentParser(description='Telegram Otomatik Mesaj Botu')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug modu aktif')
    parser.add_argument('-r', '--reset-errors', action='store_true', help='Hata veren grupları sıfırla')
    parser.add_argument('-o', '--optimize-db', action='store_true', help='Veritabanı optimizasyonu yap')
    parser.add_argument('-e', '--env', type=str, default='production', help='Çalışma ortamı')
    parser.add_argument('-b', '--backup', action='store_true', help='Veritabanı yedeği al')
    args = parser.parse_args()
    
    try:
        # Log seviyesini ayarla
        log_level = logging.DEBUG if args.debug else logging.INFO
        
        # Logger yapılandırması 
        logger = setup_logger(args.debug)
        
        logger.info("🚀 Uygulama başlatılıyor...")
        
        # Çalışma zamanı 
        now = datetime.now()
        logger.info(f"⏱️ Başlangıç zamanı: {now.strftime('%H:%M:%S')}")
        
        # Önce Config sınıfından bir örnek oluştur
        config = Config(config_path="data/config.json",
                        messages_path="data/messages.json",
                        invites_path="data/invites.json",
                        responses_path="data/responses.json")
        
        # Klasörlerin oluşturulduğundan emin ol
        config.create_directories()  # Şimdi config nesnesi tanımlanmış durumda
        
        # Veritabanını başlat
        db_path = os.getenv("DB_PATH", "data/users.db")
        user_db = UserDatabase(db_path)
        if args.optimize_db:
            logger.info("Veritabanı optimizasyonu yapılıyor...")
            user_db.optimize_database()
        if args.backup:
            logger.info("Veritabanı yedeği alınıyor...")
            user_db.backup_database()
        
        # Yapılandırma dosyalarını yükle
        config.load_message_templates()
        config.load_invite_templates()
        config.load_response_templates()
        
        # Bot client'ını başlat
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        phone_number = os.getenv("PHONE_NUMBER")
        
        # Durdurma eventini oluştur
        stop_event.clear()
        
        # Debug: Çevre değişkenlerini kontrol et
        if args.debug:
            print(f"{Fore.CYAN}===== ÇEVRE DEĞİŞKENLERİ KONTROLÜ ====={Style.RESET_ALL}")
            print(f"{Fore.YELLOW}GROUP_LINKS: {os.environ.get('GROUP_LINKS', 'Tanımlanmamış')}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}ADMIN_GROUPS: {os.environ.get('ADMIN_GROUPS', 'Tanımlanmamış')}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}TARGET_GROUPS: {os.environ.get('TARGET_GROUPS', 'Tanımlanmamış')}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}SUPER_USERS: {os.environ.get('SUPER_USERS', 'Tanımlanmamış')}{Style.RESET_ALL}")
        
        # Telegram client bağlantısı
        client = TelegramClient('mysession', api_id, api_hash)
        await client.connect()
        
        # Giriş kontrolü
        if not await client.is_user_authorized():
            await client.send_code_request(phone_number)
            print(f"{Fore.YELLOW}Telegram doğrulama kodu gerekli!{Style.RESET_ALL}")
            code = input("Telefonunuza gelen kodu girin: ")
            try:
                await client.sign_in(phone_number, code)
            except errors.SessionPasswordNeededError:
                # İki faktörlü doğrulamayı yönet
                print(f"{Fore.YELLOW}📱 İki faktörlü doğrulama etkin!{Style.RESET_ALL}")
                password = input("Lütfen Telegram hesabınızın şifresini girin: ")
                await client.sign_in(password=password)
                print(f"{Fore.GREEN}✅ İki faktörlü doğrulama başarılı!{Style.RESET_ALL}")

        print(f"{Fore.GREEN}✅ Telegram bağlantısı başarılı!{Style.RESET_ALL}")
        
        # Servisleri oluştur ve başlat
        service_factory = ServiceFactory(client, config, user_db)
        services = {}
        service_tasks = []

        # Temel servisleri oluştur
        services['dm'] = service_factory.create_service("dm")
        services['reply'] = service_factory.create_service("reply")
        services['group'] = service_factory.create_service("group")
        services['user'] = service_factory.create_service("user")

        # Debug modunda test et
        if args.debug:
            print(f"\n{Fore.CYAN}===== DM SERVİSİ TESTİ ====={Style.RESET_ALL}")
            services['dm'].debug_links()

        # Servisleri başlat
        print(f"{Fore.GREEN}Servisler başlatılıyor...{Style.RESET_ALL}")

        # Servis görevlerini oluştur
        service_tasks = [
            asyncio.create_task(services['reply'].run()),
            asyncio.create_task(services['dm'].run())
            # Grup servisi ayrı ve daha yüksek öncelikle başlatılıyor
        ]

        # Grup servisini öncelikli olarak başlat
        group_task = asyncio.create_task(services['group'].run())

        # Diğer periyodik görevler için ayrı bir task grubu
        periodic_tasks = [
            asyncio.create_task(services['dm'].process_dm_users()),  # Her 5 dakikada bir DM gönder
            # Grup üye toplama işlemini servis sınıfına taşıyalım
            asyncio.create_task(services['dm'].collect_group_members()) 
        ]

        # Önce öncelikli görevleri bekle
        await asyncio.gather(group_task)
        print("✅ Grup servisi başlatıldı!")

        # Sonra diğer görevleri başlat
        await asyncio.gather(*service_tasks, *periodic_tasks)
        
        print_tips()
        
        # Klavye girdilerini işleyen görevi başlat
        input_task = asyncio.create_task(keyboard_input_handler(services, config, user_db))
        
        # Tüm görevleri bekle
        await asyncio.gather(*service_tasks, input_task)
        
        return 0  # Başarılı sonlanma kodu
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Kullanıcı tarafından sonlandırılıyor...{Style.RESET_ALL}")
        # Temiz kapatma için stop eventi ayarla
        stop_event.set()
        # Kısa bir süre bekle
        await asyncio.sleep(2)
        return 0
        
    except Exception as e:
        logger.error(f"Kritik hata: {e}", exc_info=True)
        
        # Kapanış temizliği
        try:
            logger.info("Servisler durduruluyor...")
            stop_event.set()  # Tüm servisleri durdur
            
            # Servislerin temiz kapatılmasını bekle
            await asyncio.sleep(2)
            
            # Bot bağlantısını kapat
            if 'client' in locals() and client:
                logger.info("Telegram bağlantısı kapatılıyor...")
                await client.disconnect()
            
            # Veritabanı bağlantısını kapat
            if 'user_db' in locals() and user_db:
                logger.info("Veritabanı bağlantısı kapatılıyor...")
                user_db.close()
                
        except Exception as close_error:
            logger.error(f"Kapatma sırasında hata: {close_error}")
            
        # Detaylı hata bilgisi
        print(f"\n{Fore.RED}Hata ayrıntıları:{Style.RESET_ALL}")
        traceback.print_exc()
        
        print(f"\n{Fore.YELLOW}Hatalar runtime/logs/bot.log dosyasında kaydedildi{Style.RESET_ALL}")
        return 1  # Hata kodu dön

if __name__ == "__main__":
    print_banner()
    
    # Async olarak ana fonksiyonu çalıştır
    exit_code = asyncio.run(main())
    sys.exit(exit_code)