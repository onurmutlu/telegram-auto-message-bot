"""
Genel bot ayarları modülü.
API kimlik bilgileri, debug modu ve log ayarları yönetimi.
"""

import os
import logging
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich import box
from rich.table import Table

def api_settings(dashboard):
    """API kimlik ayarlarını düzenler"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]API AYARLARI[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut API bilgilerini göster - güvenlik için maskele
    api_id = os.getenv("API_ID", "")
    api_hash = os.getenv("API_HASH", "")
    phone = os.getenv("PHONE_NUMBER", "")
    
    # API kimliklerini maskele
    if (api_id):
        masked_api_id = api_id[:2] + "*" * (len(api_id) - 2)
    else:
        masked_api_id = "[red]Ayarlanmamış[/red]"
        
    if (api_hash):
        masked_api_hash = api_hash[:4] + "*" * 24 + api_hash[-4:] if len(api_hash) > 8 else "****"
    else:
        masked_api_hash = "[red]Ayarlanmamış[/red]"
        
    if (phone):
        masked_phone = phone[:3] + "*" * (len(phone) - 5) + phone[-2:]
    else:
        masked_phone = "[red]Ayarlanmamış[/red]"
    
    # Mevcut bilgileri tablo olarak göster
    table = Table(show_header=True, box=box.SIMPLE)
    table.add_column("Ayar", style="cyan")
    table.add_column("Değer", style="green")
    table.add_row("API ID", masked_api_id)
    table.add_row("API Hash", masked_api_hash)
    table.add_row("Telefon Numarası", masked_phone)
    
    dashboard.console.print(table)
    
    # İşlemler menüsü
    dashboard.console.print("\n[bold]İşlemler[/bold]")
    dashboard.console.print("1. API ID değiştir")
    dashboard.console.print("2. API Hash değiştir")
    dashboard.console.print("3. Telefon numarası değiştir")
    dashboard.console.print("4. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
    
    if (choice == "1"):
        new_api_id = Prompt.ask("Yeni API ID")
        if (new_api_id.strip() and new_api_id.isdigit()):
            dashboard._update_env_variable("API_ID", new_api_id)
            dashboard.console.print("[green]✅ API ID güncellendi. Değişikliklerin etkinleşmesi için botu yeniden başlatmalısınız.[/green]")
        else:
            dashboard.console.print("[red]❌ Geçersiz API ID. Sayısal bir değer girmelisiniz.[/red]")
            
    elif (choice == "2"):
        new_api_hash = Prompt.ask("Yeni API Hash")
        if (new_api_hash.strip() and len(new_api_hash) > 10):
            dashboard._update_env_variable("API_HASH", new_api_hash)
            dashboard.console.print("[green]✅ API Hash güncellendi. Değişikliklerin etkinleşmesi için botu yeniden başlatmalısınız.[/green]")
        else:
            dashboard.console.print("[red]❌ Geçersiz API Hash.[/red]")
            
    elif (choice == "3"):
        new_phone = Prompt.ask("Yeni telefon numarası (örn: +901234567890)")
        if (new_phone.strip() and new_phone.startswith("+") and len(new_phone) > 8):
            dashboard._update_env_variable("PHONE_NUMBER", new_phone)
            dashboard.console.print("[green]✅ Telefon numarası güncellendi. Değişikliklerin etkinleşmesi için botu yeniden başlatmalısınız.[/green]")
        else:
            dashboard.console.print("[red]❌ Geçersiz telefon numarası. '+' ile başlamalı ve en az 8 karakter olmalıdır.[/red]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Ana menüye dönmek için Enter tuşuna basın[/italic]")

def debug_settings(dashboard):
    """Debug modunu yapılandırır"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]DEBUG AYARLARI[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut debug durumunu göster
    debug_mode = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    status_text = "[green]Aktif[/green]" if debug_mode else "[yellow]Devre dışı[/yellow]"
    dashboard.console.print(f"Debug modu: {status_text}")
    dashboard.console.print(f"Log seviyesi: [cyan]{log_level}[/cyan]")
    
    # Yardımcı bilgi
    if (debug_mode):
        dashboard.console.print("\n[yellow]⚠️ Debug modu aktif olduğunda daha ayrıntılı loglar üretilir ve performans etkilenebilir.[/yellow]")
    
    # İşlemler menüsü
    dashboard.console.print("\n[bold]İşlemler[/bold]")
    dashboard.console.print(f"1. Debug modunu {'devre dışı bırak' if debug_mode else 'etkinleştir'}")
    dashboard.console.print("2. Log seviyesi değiştir")
    dashboard.console.print("3. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3"], default="3")
    
    if (choice == "1"):
        # Debug modunu değiştir
        new_debug_mode = not debug_mode
        dashboard._update_env_variable("DEBUG", str(new_debug_mode).lower())
        
        # Doğrudan servislere de uygula
        for service_name, service in dashboard.services.items():
            if (hasattr(service, 'debug')):
                service.debug = new_debug_mode
        
        status = "etkinleştirildi" if new_debug_mode else "devre dışı bırakıldı"
        dashboard.console.print(f"[green]✅ Debug modu {status}.[/green]")
        
    elif (choice == "2"):
        # Log seviyesi değiştir
        dashboard.console.print("\n[bold]Log Seviyesi Seçimi[/bold]")
        dashboard.console.print("1. DEBUG - En detaylı loglar")
        dashboard.console.print("2. INFO - Temel operasyonel bilgiler (Önerilen)")
        dashboard.console.print("3. WARNING - Sadece uyarılar ve hatalar")
        dashboard.console.print("4. ERROR - Sadece hatalar")
        dashboard.console.print("5. CRITICAL - Sadece kritik hatalar")
        
        log_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="2")
        
        levels = {
            "1": "DEBUG",
            "2": "INFO",
            "3": "WARNING",
            "4": "ERROR",
            "5": "CRITICAL"
        }
        
        new_level = levels[log_choice]
        dashboard._update_env_variable("LOG_LEVEL", new_level)
        
        # Loglama seviyesini hemen değiştir
        try:
            numeric_level = getattr(logging, new_level)
            logging.getLogger().setLevel(numeric_level)
            dashboard.console.print(f"[green]✅ Log seviyesi {new_level} olarak ayarlandı.[/green]")
        except:
            dashboard.console.print("[red]❌ Log seviyesi değiştirilemedi.[/red]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Ana menüye dönmek için Enter tuşuna basın[/italic]")

def log_settings(dashboard):
    """Log ayarlarını yapılandırır"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]LOG AYARLARI[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut log ayarlarını göster
    log_file_path = os.getenv("LOG_FILE_PATH", "logs/bot.log")
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    log_max_size = int(os.getenv("LOG_MAX_SIZE", "5242880"))  # 5MB
    log_format = os.getenv("LOG_FORMAT", "detailed")
    
    # Log dosyası boyutunu daha anlaşılır formatta göster
    log_size_mb = log_max_size / (1024 * 1024)
    
    dashboard.console.print(f"Log dosyası: [cyan]{log_file_path}[/cyan]")
    dashboard.console.print(f"Yedeklenen log sayısı: [cyan]{log_backup_count}[/cyan]")
    dashboard.console.print(f"Maksimum log boyutu: [cyan]{log_size_mb:.1f} MB[/cyan]")
    dashboard.console.print(f"Log formatı: [cyan]{log_format}[/cyan]")
    
    # İşlemler menüsü
    dashboard.console.print("\n[bold]İşlemler[/bold]")
    dashboard.console.print("1. Log dosya yolunu değiştir")
    dashboard.console.print("2. Yedekleme sayısını değiştir")
    dashboard.console.print("3. Maksimum log boyutunu değiştir")
    dashboard.console.print("4. Log formatını değiştir")
    dashboard.console.print("5. Logları görüntüle")
    dashboard.console.print("6. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5", "6"], default="6")
    
    if (choice == "1"):
        # Log dosya yolunu değiştir
        new_path = Prompt.ask("Yeni log dosya yolu", default=log_file_path)
        if (new_path.strip()):
            dashboard._update_env_variable("LOG_FILE_PATH", new_path)
            dashboard.console.print("[green]✅ Log dosya yolu güncellendi. Değişikliklerin etkinleşmesi için botu yeniden başlatmalısınız.[/green]")
    
    elif (choice == "2"):
        # Yedekleme sayısını değiştir
        new_count = IntPrompt.ask("Yedeklenecek log dosyası sayısı", default=log_backup_count, min_value=1, max_value=50)
        dashboard._update_env_variable("LOG_BACKUP_COUNT", str(new_count))
        dashboard.console.print("[green]✅ Yedekleme sayısı güncellendi.[/green]")
    
    elif (choice == "3"):
        # Maksimum log boyutunu değiştir
        dashboard.console.print("\n[bold]Maksimum Log Boyutu Seçimi[/bold]")
        dashboard.console.print("1. 1 MB")
        dashboard.console.print("2. 5 MB (Önerilen)")
        dashboard.console.print("3. 10 MB")
        dashboard.console.print("4. 50 MB")
        dashboard.console.print("5. Özel değer")
        
        size_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="2")
        
        sizes = {
            "1": 1048576,    # 1 MB
            "2": 5242880,    # 5 MB
            "3": 10485760,   # 10 MB
            "4": 52428800,   # 50 MB
            "5": None        # Özel
        }
        
        if (size_choice != "5"):
            new_size = sizes[size_choice]
        else:
            # Özel boyut
            new_size_mb = IntPrompt.ask("Maksimum log boyutu (MB)", default=int(log_size_mb), min_value=1)
            new_size = new_size_mb * 1024 * 1024
        
        dashboard._update_env_variable("LOG_MAX_SIZE", str(new_size))
        dashboard.console.print(f"[green]✅ Maksimum log boyutu {new_size/(1024*1024):.1f} MB olarak ayarlandı.[/green]")
    
    elif (choice == "4"):
        # Log formatını değiştir
        dashboard.console.print("\n[bold]Log Formatı Seçimi[/bold]")
        dashboard.console.print("1. Detaylı (zamanı, seviyesi, modül ve mesaj)")
        dashboard.console.print("2. Standart (zamanı, seviyesi ve mesaj)")
        dashboard.console.print("3. Basit (sadece zaman ve mesaj)")
        
        format_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3"], default="1")
        
        formats = {
            "1": "detailed",
            "2": "standard",
            "3": "simple"
        }
        
        new_format = formats[format_choice]
        dashboard._update_env_variable("LOG_FORMAT", new_format)
        dashboard.console.print(f"[green]✅ Log formatı '{new_format}' olarak ayarlandı.[/green]")
    
    elif (choice == "5"):
        # Logları görüntüle
        try:
            dashboard.clear_screen()
            dashboard.console.print(Panel.fit(
                "[bold cyan]LOG KAYITLARI[/bold cyan]",
                border_style="cyan"
            ))
            
            # Son 20 satırı görüntüle
            import subprocess
            result = subprocess.run(['tail', '-n', '20', log_file_path], 
                                    capture_output=True, text=True)
            
            if (result.returncode == 0):
                dashboard.console.print(result.stdout)
            else:
                dashboard.console.print(f"[red]Log dosyası okunamadı: {log_file_path}[/red]")
                
        except Exception as e:
            dashboard.console.print(f"[red]Hata: {str(e)}[/red]")
            
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Log Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")
        # Recursive olarak bu ekranı tekrar göster
        log_settings(dashboard)
        return
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Ana menüye dönmek için Enter tuşuna basın[/italic]")