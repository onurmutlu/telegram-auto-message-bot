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
import aioconsole

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

async def handle_keyboard_input(services, start_time):
    """
    Klavye girişlerini işler ve CLI arayüzünü yönetir.
    
    Args:
        services (dict): Servis adı -> Servis nesnesi eşleşmesi
        start_time (datetime): Başlangıç zamanı
        
    Returns:
        bool: İşlem başarılı ise True
    """
    # None değere sahip servisleri temizle
    services = {k: v for k, v in services.items() if v is not None}
    
    # Komut bilgilerini göster
    console.print("\n[bold cyan]Klavye Komutları:[/bold cyan]")
    console.print("  [green]s[/green] - Servis durumlarını göster")
    console.print("  [green]i[/green] - Servis istatistiklerini göster")
    console.print("  [green]g[/green] - Grup servisi özeti")
    console.print("  [green]u[/green] - Kullanıcı servisi özeti")
    console.print("  [green]r[/green] - Yanıt servisi özeti")
    console.print("  [green]p[/green] - Durakla/Devam et")
    console.print("  [green]q[/green] - Çıkış\n")
    
    # Durum bilgisi gösterme fonksiyonu
    async def show_service_status():
        console.print("\n[bold green]Servis Durumları:[/bold green]")
        
        table = Table(title="Servis Durumları", expand=True)
        table.add_column("Servis", style="cyan")
        table.add_column("Durum", style="green")
        table.add_column("Çalışma Süresi", style="yellow")
        table.add_column("İstatistik", style="magenta")
        
        for name, service in services.items():
            if name != 'user_db' and name != 'service_manager' and hasattr(service, 'get_status'):
                try:
                    status = await service.get_status()
                    stats = await service.get_statistics() if hasattr(service, 'get_statistics') else {}
                    
                    # Durum özeti oluştur
                    status_str = "✅ Aktif" if status.get('running', False) else "⏸️ Durakladı"
                    
                    # Çalışma süresi
                    uptime = status.get('uptime_seconds', 0)
                    uptime_str = f"{uptime//3600}s {(uptime%3600)//60}d {uptime%60}sn"
                    
                    # Özet istatistik 
                    main_stat = ""
                    if name == 'group' and 'total_sent' in stats:
                        main_stat = f"{stats['total_sent']} mesaj"
                    elif name == 'user' and 'total_users' in stats:
                        main_stat = f"{stats['total_users']} kullanıcı"
                    elif name == 'reply' and 'reply_count' in stats:
                        main_stat = f"{stats['reply_count']} yanıt"
                    
                    table.add_row(name, status_str, uptime_str, main_stat)
                except Exception as e:
                    table.add_row(name, f"[red]Hata: {str(e)[:20]}[/red]", "", "")
        
        console.print(table)
        console.print()
    
    # Periyodik durum raporu için task
    async def periodic_status_report():
        while True:
            await asyncio.sleep(60)  # Her 60 saniyede bir güncelle
            await show_service_status()
    
    # Periyodik durum raporu taskı başlat
    periodic_task = asyncio.create_task(periodic_status_report())
    
    try:
        while True:
            cmd = await aioconsole.ainput()
            
            if cmd.lower() == 'q':
                console.print("[yellow]Çıkış yapılıyor...[/yellow]")
                break
                
            elif cmd.lower() == 's':
                await show_service_status()
                
            elif cmd.lower() == 'i':
                # Servis istatistiklerini göster
                console.print("\n[bold green]Servis İstatistikleri:[/bold green]")
                
                for name, service in services.items():
                    if name != 'user_db' and name != 'service_manager' and hasattr(service, 'get_statistics'):
                        try:
                            stats = await service.get_statistics()
                            console.print(f"[bold cyan]{name.capitalize()} İstatistikleri:[/bold cyan]")
                            for key, value in stats.items():
                                console.print(f"  [yellow]{key}:[/yellow] {value}")
                            console.print("")
                        except Exception as e:
                            console.print(f"[red]{name} istatistikleri alınamadı: {str(e)}[/red]")
                
            elif cmd.lower() == 'g' and 'group' in services:
                # Grup servisi detaylı raporu
                group_service = services['group']
                console.print("\n[bold cyan]Grup Servisi Detayları:[/bold cyan]")
                
                try:
                    status = await group_service.get_status()
                    stats = await group_service.get_statistics()
                    
                    console.print(f"[green]Durum:[/green] {'Aktif' if status.get('running', False) else 'Durakladı'}")
                    console.print(f"[green]Aktif Gruplar:[/green] {status.get('active_groups_count', 0)}")
                    console.print(f"[green]Hatalı Gruplar:[/green] {status.get('error_groups_count', 0)}")
                    console.print(f"[green]Toplam Gönderilen Mesaj:[/green] {stats.get('total_sent', 0)}")
                    console.print(f"[green]Son Tur Mesaj Sayısı:[/green] {status.get('sent_count', 0)}")
                    console.print("")
                except Exception as e:
                    console.print(f"[red]Grup servisi bilgileri alınamadı: {str(e)}[/red]")
                
            elif cmd.lower() == 'u' and 'user' in services:
                # Kullanıcı servisi detaylı raporu
                user_service = services['user']
                console.print("\n[bold cyan]Kullanıcı Servisi Detayları:[/bold cyan]")
                
                try:
                    status = await user_service.get_status()
                    stats = await user_service.get_statistics()
                    
                    console.print(f"[green]Durum:[/green] {'Aktif' if status.get('running', False) else 'Durakladı'}")
                    console.print(f"[green]Toplam Kullanıcı:[/green] {stats.get('total_users', 0)}")
                    console.print(f"[green]Önbellek Boyutu:[/green] {status.get('cache_size', 0)}")
                    console.print(f"[green]Toplam Katılım:[/green] {stats.get('total_joins', 0)}")
                    console.print(f"[green]Toplam Ayrılma:[/green] {stats.get('total_leaves', 0)}")
                    console.print("")
                except Exception as e:
                    console.print(f"[red]Kullanıcı servisi bilgileri alınamadı: {str(e)}[/red]")
                
            elif cmd.lower() == 'r' and 'reply' in services:
                # Yanıt servisi detaylı raporu
                reply_service = services['reply']
                console.print("\n[bold cyan]Yanıt Servisi Detayları:[/bold cyan]")
                
                try:
                    status = await reply_service.get_status()
                    stats = await reply_service.get_statistics()
                    
                    console.print(f"[green]Durum:[/green] {'Aktif' if status.get('running', False) else 'Durakladı'}")
                    console.print(f"[green]Yanıt Sayısı:[/green] {stats.get('reply_count', 0)}")
                    console.print("")
                except Exception as e:
                    console.print(f"[red]Yanıt servisi bilgileri alınamadı: {str(e)}[/red]")
                
            elif cmd.lower() == 'p':
                # Tüm servisleri duraklat/devam ettir
                for name, service in services.items():
                    if name != 'user_db' and name != 'service_manager' and hasattr(service, 'pause') and hasattr(service, 'resume'):
                        try:
                            status = await service.get_status()
                            if status.get('running', False):
                                await service.pause()
                                console.print(f"[yellow]{name} servisi duraklatıldı[/yellow]")
                            else:
                                await service.resume()
                                console.print(f"[green]{name} servisi devam ettirildi[/green]")
                        except Exception as e:
                            console.print(f"[red]{name} servisi kontrolünde hata: {str(e)}[/red]")
                
            elif cmd.lower() == 'd':
                # Grup keşfi detayları
                if 'discovery' in services:
                    console.print("\n[bold cyan]Grup Keşif Detayları:[/bold cyan]")
                    
                    try:
                        stats = services['discovery'].get_statistics()
                        console.print(f"[green]Keşfedilen Gruplar:[/green] {stats['discovered_groups']}")
                        console.print(f"[green]Katılınan Gruplar:[/green] {stats['joined_groups']}")
                        console.print(f"[green]Karalistedeki Gruplar:[/green] {stats['blacklisted_groups']}")
                        console.print(f"[green]Bilinen Gruplar:[/green] {stats['known_groups']}")
                        console.print(f"[green]Analiz Edilen Gruplar:[/green] {stats['analyzed_groups']}")
                        console.print("")
                    except Exception as e:
                        console.print(f"[red]Keşif istatistikleri alınamadı: {str(e)}[/red]")
                else:
                    console.print("[yellow]Grup keşif servisi aktif değil.[/yellow]")
                    
            elif cmd.lower() == 'start-discovery':
                # Grup keşfini başlat
                if 'discovery' not in services or services['discovery'] is None:
                    console.print("[yellow]Grup keşif servisi oluşturuluyor...[/yellow]")
                    
                    try:
                        from bot.tdlib_integration import TelegramDiscoveryService
                        discovery = TelegramDiscoveryService(
                            db=services['user_db'],
                            config=getattr(services['service_manager'], 'config', None),
                            stop_event=asyncio.Event()
                        )
                        
                        await discovery.initialize()
                        await discovery.start()
                        
                        services['discovery'] = discovery
                        console.print("[green]Grup keşif servisi başlatıldı![/green]")
                    except Exception as e:
                        console.print(f"[red]Keşif servisi başlatılamadı: {str(e)}[/red]")
                else:
                    await services['discovery'].start()
                    console.print("[green]Grup keşif servisi yeniden başlatıldı![/green]")
                
            # Komut bulunamadı
            elif cmd.strip():
                console.print(f"[yellow]Bilinmeyen komut: '{cmd}'. Yardım için 'h' yazabilirsiniz.[/yellow]")
                
    except asyncio.CancelledError:
        console.print("[yellow]CLI arayüzü sonlandırılıyor...[/yellow]")
    finally:
        if not periodic_task.done():
            periodic_task.cancel()
            
    return True
