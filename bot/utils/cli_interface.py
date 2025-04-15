# -*- coding: utf-8 -*-
"""
# ============================================================================ #
# Dosya: cli_interface.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/utils/cli_interface.py
# İşlev: Komut satırı arayüzü ve klavye girişi yönetimi.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""
import os
import sys
import asyncio
import logging
import threading
import time
import platform
from datetime import datetime, timedelta
from colorama import Fore, Style, init
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
import aioconsole
import termios
import tty
import select
import json
import matplotlib.pyplot as plt

# Initialize colorama
init(autoreset=True)
logger = logging.getLogger(__name__) # Use local logger
console = Console()

# --- Helper Functions ---

def _calculate_uptime(start_time):
    """
    Bot'un çalışma süresini saniye cinsinden hesaplar.

    Args:
        start_time (datetime): Botun başlangıç zamanı.

    Returns:
        float: Çalışma süresi (saniye)
    """
    if not start_time:
        return 0
    return (datetime.now() - start_time).total_seconds()

def _format_uptime(start_time):
    """
    Bot'un çalışma süresini insan tarafından okunabilir formata dönüştürür.

    Args:
        start_time (datetime): Botun başlangıç zamanı.

    Returns:
        str: "Xg Ys Zd Ws" formatında çalışma süresi (gün, saat, dakika, saniye)
    """
    uptime_seconds = _calculate_uptime(start_time)
    if uptime_seconds <= 0:
        return "0s 0d 0sn"

    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{int(days)}g {int(hours)}s {int(minutes)}d {int(seconds)}sn"


# --- CLI Interface Functions ---

def is_terminal_support_color():
    """
    Terminalin renk desteği olup olmadığını tespit eder.

    Farklı terminal türleri ve işletim sistemlerinde renk desteği kontrolü yapar.
    Windows terminallerinde renk desteği CMD ve PowerShell'e göre değişir.

    Returns:
        bool: Terminal renk destekliyorsa True, değilse False
    """
    # Eğer stdout bir terminal değilse (örn. pipe edilmişse)
    if not sys.stdout.isatty():
        return False

    # Windows için ek kontroller
    if os.name == 'nt':
        # Windows 10'da ansi desteği varsayılan olarak aktif
        try:
            # Check if platform.release() returns a valid number for comparison
            release_num = int(platform.release())
            if release_num >= 10:
                return True
        except ValueError:
             # Handle cases where platform.release() might not be a simple number
             pass # Continue with other checks
        # Önceki Windows sürümleri için özel kontroller gerekir
        return 'ANSICON' in os.environ

    # Linux/Mac ve diğer sistemlerde varsayılan olarak renk desteği var
    return True

def print_banner():
    """
    Uygulama başlangıç banner'ını gösterir.

    Renkli ve biçimlendirilmiş bir banner görüntüler, uygulama sürümü ve telif hakkı
    bilgilerini de içerir.
    """
    print(f"\n{Fore.CYAN}╔{'═' * 60}╗{Style.RESET_ALL}")
    print(f"{Fore.CYAN}║{' ' * 10}TELEGRAM AUTO MESSAGE BOT v3.5.0{' ' * 10}║{Style.RESET_ALL}")
    print(f"{Fore.CYAN}║{' ' * 15}Author: @siyahkare{' ' * 15}║{Style.RESET_ALL}")
    print(f"{Fore.CYAN}║{' ' * 5}Ticari Ürün - Tüm Hakları Saklıdır © 2025{' ' * 5}║{Style.RESET_ALL}")
    print(f"{Fore.CYAN}╚{'═' * 60}╝{Style.RESET_ALL}")
    print(f"\n{Fore.WHITE}Bu yazılım, SiyahKare Yazılım tarafından geliştirilmiş ticari bir ürünüdür.{Style.RESET_ALL}")

def print_status(console, services):
    """Daha güzel durum raporu yazdır"""
    console.print("\n[bold blue]===== BOT DURUM RAPORU =====[/bold blue]")
    for name, service in services.items():
        status = service.is_running()
        status_text = "[green]✓ Çalışıyor[/green]" if status else "[red]✗ Durdu[/red]"
        console.print(f"[bold]{name.upper()}:[/bold] {status_text}")

async def check_services(services):
    """
    Tüm servislerin durumunu kontrol eder ve sorunları giderir
    
    Args:
        services: Servisler sözlüğü
    """
    print(f"\n{Fore.CYAN}📊 SERVİS KONTROL RAPORU{Style.RESET_ALL}")
    print("="*50)
    
    for name, service in services.items():
        if service:
            if hasattr(service, "running"):
                status = f"{Fore.GREEN}✓ ÇALIŞIYOR{Style.RESET_ALL}" if service.running else f"{Fore.RED}✗ DURAKLATILDI{Style.RESET_ALL}"
            else:
                status = f"{Fore.YELLOW}? DURUM BİLİNMİYOR{Style.RESET_ALL}"
                
            # Servis türüne göre özellikleri göster
            details = []
            
            if name == "group" or name == "message":
                details.append(f"Mesaj sayısı: {getattr(service, 'sent_count', 'N/A')}")
                details.append(f"Hedef grup sayısı: {len(getattr(service, 'target_groups', []))}")
            elif name == "dm":
                details.append(f"İşlenen DM: {getattr(service, 'processed_dms', 'N/A')}")
                details.append(f"Gönderilen davet: {getattr(service, 'invites_sent', 'N/A')}")
            elif name == "invite":
                details.append(f"Davet sayısı: {getattr(service, 'sent_count', 'N/A')}")
            elif name == "reply":
                if hasattr(service, "my_id"):
                    details.append(f"Bot ID: {service.my_id}")
            
            # Servis durumunu göster
            print(f"📌 {Fore.CYAN}{name.upper()} SERVİSİ{Style.RESET_ALL}: {status}")
            for detail in details:
                print(f"   • {detail}")
        else:
            print(f"❌ {Fore.RED}{name.upper()} SERVİSİ MEVCUT DEĞİL{Style.RESET_ALL}")
    
    print("="*50)

def show_help():
    """Mevcut komutlar için yardım gösterir."""
    help_panel = Panel(
        "[bold cyan]Klavye Komutları:[/bold cyan]\n"
        "[yellow]h[/yellow] - Bu yardım menüsünü göster\n"
        "[yellow]s[/yellow] - Durum raporu göster\n"
        "[yellow]i[/yellow] - İstatistikleri göster\n"
        "[yellow]c[/yellow] - Konsolu temizle\n"
        "[yellow]r[/yellow] - Servisleri yeniden başlat\n"
        "[yellow]l[/yellow] - Loglama seviyesini değiştir\n"
        "[yellow]d[/yellow] - Demografik analiz göster\n"
        "[yellow]m[/yellow] - Veri madenciliği ve analiz yönetimi\n"
        "[yellow]t[/yellow] - Hedefli kampanya oluştur ve yönet\n"
        "[yellow]a[/yellow] - Agresif veri toplama başlat\n"
        "[yellow]q[/yellow] - Botu kapat",
        title="Yardım",
        border_style="cyan"
    )
    console.print(help_panel)

async def show_status(service_manager):
    """Servis durumlarını gösterir."""
    try:
        status = await service_manager.get_status()
        
        table = Table(title="Servis Durumu", show_header=True, header_style="bold cyan")
        table.add_column("Servis", style="cyan")
        table.add_column("Durum", style="green")
        table.add_column("Detaylar", style="yellow")
        
        for name, data in status.items():
            running = data.get('running', False)
            status_text = "[green]Çalışıyor" if running else "[red]Durdu"
            details = ", ".join([f"{k}: {v}" for k, v in data.items() if k != "running"])
            table.add_row(name, status_text, details)
            
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]Durum raporu hazırlanırken hata: {str(e)}[/bold red]")

async def show_statistics(service_manager):
    """Servis istatistiklerini gösterir."""
    try:
        stats = await service_manager.get_statistics()
        
        for name, data in stats.items():
            if data:
                table = Table(title=f"{name.capitalize()} İstatistikleri", show_header=True, header_style="bold cyan")
                table.add_column("Metrik", style="cyan")
                table.add_column("Değer", style="yellow")
                
                for key, value in data.items():
                    table.add_row(str(key), str(value))
                    
                console.print(table)
                console.print("")
            else:
                console.print(f"[yellow]{name} için istatistik bulunamadı[/yellow]")
                
    except Exception as e:
        console.print(f"[bold red]İstatistikler hazırlanırken hata: {str(e)}[/bold red]")

def toggle_logging_level():
    """Log seviyesini değiştirir (INFO <-> DEBUG)"""
    root_logger = logging.getLogger()
    current_level = root_logger.level
    
    if current_level == logging.DEBUG:
        root_logger.setLevel(logging.INFO)
        console.print("[green]Log seviyesi INFO olarak ayarlandı[/green]")
    else:
        root_logger.setLevel(logging.DEBUG)
        console.print("[green]Log seviyesi DEBUG olarak ayarlandı[/green]")

async def restart_services(service_manager):
    """Tüm servisleri yeniden başlatır."""
    try:
        for name in service_manager.services.keys():
            console.print(f"[yellow]Servis yeniden başlatılıyor: {name}[/yellow]")
            await service_manager.restart_service(name)
            
        console.print("[bold green]Tüm servisler yeniden başlatıldı[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Servis yeniden başlatma hatası: {str(e)}[/bold red]")

async def handle_keyboard_input(console, service_manager, stop_event):
    """
    Klavye girişlerini işler ve komutları process_command fonksiyonuyla değerlendirir.
    
    Args:
        console: Rich Console nesnesi
        service_manager: Servis yönetici nesnesi
        stop_event: Uygulamayı durdurmak için event nesnesi
    """
    # Banner ve yardımı başlangıçta göster - zaten main.py'de çağrılacak
    # print_banner()
    # show_help()
    
    console.print("[cyan]Klavye komutları aktif. Komutlar için 'h' tuşuna basın.[/cyan]")
    
    while not stop_event.is_set():
        try:
            # Kullanıcıdan girişi al
            command = await asyncio.to_thread(input, "\nKomut (h/s/i/c/r/l/d/m/t/a/q): ")
            command = command.strip().lower()
            
            # Komutu işle
            should_exit = await process_command(command, service_manager)
            
            # Çıkış sinyali geldiyse döngüden çık
            if should_exit:
                stop_event.set()
                break
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Komut işleme hatası: {str(e)}")
            await asyncio.sleep(1)
    
    return True  # İşlem tamamlandı

async def process_command(cmd, service_manager):
    """
    Girilen komutu işler. Ana thread'den çağrılır.
    """
    try:
        cmd = cmd.lower()
        
        if cmd == 'q':
            print("\n\nBot kapatılıyor...")
            return True  # Çıkış sinyali
            
        elif cmd == 'h':
            show_help()
            
        elif cmd == 's':
            await show_status(service_manager)
            
        elif cmd == 'i':
            await show_statistics(service_manager)
            
        elif cmd == 'c':
            os.system('cls' if os.name == 'nt' else 'clear')
            print("Konsol temizlendi. Komutlar için 'h' tuşuna basın.")
            
        elif cmd == 'r':
            await restart_services(service_manager)
            
        elif cmd == 'l':
            toggle_logging_level()
            
        # YENİ: Demografik analiz komutu
        elif cmd == 'd':
            await display_demographics(service_manager)
            
        # YENİ: Veri madenciliği menüsü
        elif cmd == 'm':
            await show_mining_menu(service_manager)
            
        # YENİ: Hedefli kampanya menüsü  
        elif cmd == 't':
            await show_campaign_menu(service_manager)
        
        # Agresif veri toplama komutu
        elif cmd == 'a' or cmd == 'agresif':
            console.print("[bold yellow]Agresif veri toplama başlatılıyor...[/bold yellow]")
            group_service = service_manager.get_service("group")
            if group_service:
                discovered = await group_service.discover_groups_aggressive()
                console.print(f"[bold green]Agresif veri toplama tamamlandı! {len(discovered)} grup işlendi[/bold green]")
            else:
                console.print("[bold red]Grup servisi bulunamadı![/bold red]")
            
        return False  # Normal işlem sinyali
        
    except Exception as e:
        logger.error(f"Komut işleme hatası: {str(e)}")
        return False

# Demografik analiz gösterme fonksiyonu
async def display_demographics(service_manager):
    """Toplanan demografik verileri gösteren bir özet rapor oluşturur"""
    try:
        data_mining = service_manager.get_service("datamining")
        
        if not data_mining:
            console.print("[bold red]DataMining servisi bulunamadı![/bold red]")
            return
        
        # Demografik raporu al
        console.print("[cyan]Demografik rapor alınıyor, lütfen bekleyin...[/cyan]")
        report = await data_mining.generate_demographic_report(format='json')
        report_data = json.loads(report)
        
        # Ana panel ve başlık
        console.print(Panel(
            f"[bold white]Demografik Analiz Raporu[/bold white]\n"
            f"[cyan]Oluşturulma: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"Toplam Kullanıcı: {report_data.get('total_users', 0)}[/cyan]",
            border_style="blue"
        ))
        
        # Dil Dağılımı Tablosu
        language_table = Table(title="Dil Dağılımı", show_header=True)
        language_table.add_column("Dil", style="cyan")
        language_table.add_column("Kullanıcı Sayısı", style="green", justify="right")
        
        lang_dist = report_data.get('language_distribution', {})
        for lang, count in lang_dist.items():
            language_table.add_row(lang or "Bilinmiyor", str(count))
            
        console.print(language_table)
        
        # Aktivite Dağılımı Tablosu
        activity_table = Table(title="Aktivite Dağılımı", show_header=True)
        activity_table.add_column("Aktivite", style="cyan")
        activity_table.add_column("Kullanıcı Sayısı", style="green", justify="right")
        
        activity_dist = report_data.get('activity_distribution', {})
        for activity, count in activity_dist.items():
            activity_table.add_row(activity, str(count))
            
        console.print(activity_table)
        
        # Grup Dağılımı Tablosu (en fazla 10 grup göster)
        group_table = Table(title="Grup Dağılımı (İlk 10)", show_header=True)
        group_table.add_column("Grup", style="cyan")
        group_table.add_column("Üye Sayısı", style="green", justify="right")
        
        group_dist = report_data.get('group_distribution', {})
        for i, (group, count) in enumerate(group_dist.items()):
            if i >= 10: break
            group_table.add_row(group, str(count))
            
        console.print(group_table)
        
        # Grafik görselleştirme opsiyonunu sor
        if input("\nGrafik olarak görmek ister misiniz? (e/h): ").lower() == 'e':
            await visualize_demographics(report_data)
        
    except Exception as e:
        console.print(f"[bold red]Demografik rapor oluşturma hatası: {str(e)}[/bold red]")

# Grafik görselleştirme fonksiyonu
async def visualize_demographics(data):
    """Demografik verileri matplotlib ile grafikler"""
    try:
        # Üç farklı grafik oluştur
        plt.figure(figsize=(15, 15))
        
        # 1. Dil Dağılımı Pasta Grafiği
        plt.subplot(2, 2, 1)
        lang_dist = data.get('language_distribution', {})
        labels = list(lang_dist.keys())
        sizes = list(lang_dist.values())
        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
        plt.title('Dil Dağılımı')
        
        # 2. Aktivite Dağılımı Çubuk Grafiği
        plt.subplot(2, 2, 2)
        activity_dist = data.get('activity_distribution', {})
        act_labels = list(activity_dist.keys())
        act_values = list(activity_dist.values())
        plt.bar(act_labels, act_values, color='skyblue')
        plt.title('Aktivite Dağılımı')
        plt.xticks(rotation=45)
        
        # 3. Grup Dağılımı Çubuk Grafiği (en fazla 10 grup)
        plt.subplot(2, 1, 2)
        group_dist = data.get('group_distribution', {})
        top_groups = dict(list(group_dist.items())[:10])
        plt.bar(list(top_groups.keys()), list(top_groups.values()), color='lightgreen')
        plt.title('En Popüler 10 Grup')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Grafiği göster
        plt.savefig('demographic_report.png')  # Dosyaya kaydet
        plt.show()  # Ekranda göster
        
        console.print("[green]Grafik 'demographic_report.png' dosyasına kaydedildi.[/green]")
        
    except Exception as e:
        console.print(f"[bold red]Grafik oluşturma hatası: {str(e)}[/bold red]")

# Veri madenciliği yönetim menüsü 
async def show_mining_menu(service_manager):
    """Veri madenciliği için alt menü gösterir"""
    menu_panel = Panel(
        "[bold cyan]Veri Madenciliği Menüsü:[/bold cyan]\n"
        "[yellow]1[/yellow] - Tam veri toplama başlat\n"
        "[yellow]2[/yellow] - Artırımlı veri toplama başlat\n" 
        "[yellow]3[/yellow] - Kullanıcı segmentlerini göster\n"
        "[yellow]4[/yellow] - İstatistikleri göster\n"
        "[yellow]0[/yellow] - Ana menüye dön",
        title="Veri Madenciliği",
        border_style="green"
    )
    
    console.print(menu_panel)
    choice = input("Seçiminiz: ")
    
    data_mining = service_manager.get_service("datamining")
    if not data_mining:
        console.print("[bold red]DataMining servisi bulunamadı![/bold red]")
        return
    
    if choice == "1":
        console.print("[cyan]Tam veri toplama başlatılıyor...[/cyan]")
        await data_mining._full_data_mining()
        console.print("[green]Tam veri toplama tamamlandı![/green]")
    
    elif choice == "2":
        console.print("[cyan]Artırımlı veri toplama başlatılıyor...[/cyan]")
        await data_mining._incremental_data_mining()
        console.print("[green]Artırımlı veri toplama tamamlandı![/green]")
    
    elif choice == "3":
        console.print("[cyan]Kullanıcı segmentleri getiriliyor...[/cyan]")
        segments = {}
        for seg_name in data_mining.segments:
            users = await data_mining.get_user_segment(seg_name)
            segments[seg_name] = len(users)
        
        # Segment tablosu
        segment_table = Table(title="Kullanıcı Segmentleri", show_header=True)
        segment_table.add_column("Segment", style="cyan")
        segment_table.add_column("Kullanıcı Sayısı", style="green", justify="right")
        
        for segment, count in segments.items():
            segment_table.add_row(segment, str(count))
            
        console.print(segment_table)
    
    elif choice == "4":
        console.print("[cyan]İstatistikler getiriliyor...[/cyan]")
        stats = await data_mining.get_statistics()
        
        # İstatistik tablosu
        stats_table = Table(title="Veri Madenciliği İstatistikleri", show_header=True)
        stats_table.add_column("Metrik", style="cyan")
        stats_table.add_column("Değer", style="green")
        
        for key, value in stats.items():
            if isinstance(value, dict):
                stats_table.add_row(key, json.dumps(value, indent=2))
            else:
                stats_table.add_row(key, str(value))
                
        console.print(stats_table)

# Hedefli kampanya menüsü
async def show_campaign_menu(service_manager):
    """Hedefli kampanyalar için alt menü gösterir"""
    menu_panel = Panel(
        "[bold cyan]Hedefli Kampanya Menüsü:[/bold cyan]\n"
        "[yellow]1[/yellow] - Yeni kampanya oluştur\n"
        "[yellow]2[/yellow] - Mevcut kampanyaları listele\n" 
        "[yellow]3[/yellow] - Kampanya gönder\n"
        "[yellow]0[/yellow] - Ana menüye dön",
        title="Hedefli Kampanyalar",
        border_style="magenta"
    )
    
    console.print(menu_panel)
    choice = input("Seçiminiz: ")
    
    # Servisleri al
    data_mining = service_manager.get_service("datamining")
    invite_service = service_manager.get_service("invite")
    
    if not data_mining or not invite_service:
        console.print("[bold red]Gerekli servisler bulunamadı![/bold red]")
        return
    
    # TargetedCampaign sınıfını import et ve örneğini oluştur
    from bot.utils.targeted_campaign import TargetedCampaign
    campaign_manager = TargetedCampaign(data_mining, invite_service)
    
    if choice == "1":
        # Kullanıcıdan kampanya bilgilerini al
        console.print("[cyan]Yeni kampanya oluşturuluyor...[/cyan]")
        
        # Segment seçimi için segmentleri listele
        console.print("[yellow]Kullanılabilir segmentler:[/yellow]")
        for i, segment in enumerate(campaign_manager.campaign_templates.keys()):
            console.print(f"  {i+1}. {segment}")
        
        segment_choice = input("Hedef segment seçin (isim olarak yazın): ")
        campaign_name = input("Kampanya adı girin: ")
        product = input("Ürün/Hizmet adı girin: ")
        
        # Kampanyayı oluştur
        campaign = campaign_manager.create_campaign(
            segment_choice,
            campaign_name,
            product
        )
        
        # Kampanyayı kaydet
        saved = campaign_manager.save_campaign(campaign)
        
        if saved:
            console.print("[green]Kampanya başarıyla kaydedildi![/green]")
            
            # Kampanya detaylarını göster
            campaign_table = Table(title="Kampanya Detayları", show_header=True)
            campaign_table.add_column("Alan", style="cyan")
            campaign_table.add_column("Değer", style="green")
            
            for key, value in campaign.items():
                campaign_table.add_row(key, str(value))
                
            console.print(campaign_table)
        else:
            console.print("[bold red]Kampanya kaydedilemedi![/bold red]")
    
    elif choice == "2":
        # Mevcut kampanyaları listele
        console.print("[cyan]Mevcut kampanyalar getiriliyor...[/cyan]")
        
        try:
            # campaigns.json dosyasını oku
            with open('data/campaigns.json', 'r', encoding='utf-8') as f:
                campaigns = json.load(f)
                
            if not campaigns:
                console.print("[yellow]Henüz kaydedilmiş kampanya bulunmuyor.[/yellow]")
                return
                
            # Kampanya tablosu
            campaign_table = Table(title="Mevcut Kampanyalar", show_header=True)
            campaign_table.add_column("ID", style="cyan", justify="right")
            campaign_table.add_column("Ad", style="green")
            campaign_table.add_column("Segment", style="yellow")
            campaign_table.add_column("Ürün/Hizmet", style="magenta")
            campaign_table.add_column("Oluşturulma", style="blue")
            
            for campaign in campaigns:
                campaign_table.add_row(
                    str(campaign.get('id', '-')),
                    campaign.get('name', '-'),
                    campaign.get('segment', '-'),
                    campaign.get('product', '-'),
                    campaign.get('created_at', '-')
                )
                
            console.print(campaign_table)
            
        except FileNotFoundError:
            console.print("[yellow]Henüz kaydedilmiş kampanya bulunmuyor.[/yellow]")
        except Exception as e:
            console.print(f"[bold red]Kampanyaları getirme hatası: {str(e)}[/bold red]")
    
    elif choice == "3":
        # Kampanya gönderme
        console.print("[cyan]Kampanya gönderimi için hazırlanıyor...[/cyan]")
        
        try:
            # Kampanyaları listele
            with open('data/campaigns.json', 'r', encoding='utf-8') as f:
                campaigns = json.load(f)
                
            if not campaigns:
                console.print("[yellow]Gönderilecek kampanya bulunmuyor.[/yellow]")
                return
                
            # Kampanyaları listele
            console.print("[yellow]Kampanyalar:[/yellow]")
            for i, campaign in enumerate(campaigns):
                console.print(f"  {i+1}. {campaign.get('name')} - {campaign.get('segment')}")
            
            # Kampanya seçimi
            campaign_idx = int(input("Göndermek istediğiniz kampanya numarasını girin: ")) - 1
            if campaign_idx < 0 or campaign_idx >= len(campaigns):
                console.print("[bold red]Geçersiz kampanya numarası![/bold red]")
                return
                
            selected_campaign = campaigns[campaign_idx]
            
            # Kaç kullanıcıya gönderilecek?
            batch_size = int(input("Kaç kullanıcıya göndermek istiyorsunuz? "))
            
            # Kampanyayı gönder
            console.print(f"[cyan]Kampanya gönderiliyor: {selected_campaign.get('name')}...[/cyan]")
            
            results = await campaign_manager.send_campaign(selected_campaign, batch_size)
            
            # Sonuçları göster
            result_table = Table(title="Gönderim Sonuçları", show_header=True)
            result_table.add_column("Metrik", style="cyan")
            result_table.add_column("Değer", style="green", justify="right")
            
            for key, value in results.items():
                result_table.add_row(key, str(value))
                
            console.print(result_table)
            
        except FileNotFoundError:
            console.print("[yellow]Henüz kaydedilmiş kampanya bulunmuyor.[/yellow]")
        except Exception as e:
            console.print(f"[bold red]Kampanya gönderimi hatası: {str(e)}[/bold red]")
