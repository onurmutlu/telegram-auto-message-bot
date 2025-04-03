"""
Rate limiter ayarları modülü.
Bot'un API kullanım hızlarını ve bekleme sürelerini yapılandırır.
"""

import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import box

def api_rate_limits(dashboard):
    """API hız limitlerini yönetir"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]API HIZ LİMİTLERİ[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut değerleri göster
    message_limit = int(os.getenv("MESSAGE_RATE_LIMIT", "20"))
    dm_limit = int(os.getenv("DM_RATE_LIMIT", "5"))
    join_limit = int(os.getenv("JOIN_RATE_LIMIT", "10"))
    api_limit = int(os.getenv("API_RATE_LIMIT", "30"))
    
    # Tablo oluştur
    table = Table(show_header=True, box=box.SIMPLE)
    table.add_column("İşlem Türü", style="cyan")
    table.add_column("Mevcut Limit (dk başına)", style="yellow", justify="right")
    
    table.add_row("Mesaj Gönderimi", str(message_limit))
    table.add_row("DM Gönderimi", str(dm_limit))
    table.add_row("Grup Katılma", str(join_limit))
    table.add_row("API Çağrıları", str(api_limit))
    
    dashboard.console.print(table)
    
    # Kullanıcının belirttiği bir hız limitini değiştirmesi için menü
    dashboard.console.print("\n[bold]Limit Değiştirme[/bold]")
    dashboard.console.print("1. Mesaj gönderme limiti")
    dashboard.console.print("2. DM gönderme limiti")
    dashboard.console.print("3. Grup katılma limiti")
    dashboard.console.print("4. API çağrı limiti")
    dashboard.console.print("5. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="5")
    
    if choice == "1":
        # Mesaj gönderme limiti
        new_limit = IntPrompt.ask(
            "Dakika başına mesaj gönderme limiti", 
            default=message_limit,
            min_value=1,
            max_value=100
        )
        dashboard._update_env_variable("MESSAGE_RATE_LIMIT", str(new_limit))
        
        # Servislere de uygula
        if 'group' in dashboard.services and hasattr(dashboard.services['group'], 'rate_limiter'):
            dashboard.services['group'].rate_limiter.message_limit = new_limit
            
        dashboard.console.print(f"[green]✅ Mesaj gönderme limiti {new_limit} olarak ayarlandı.[/green]")
        
    elif choice == "2":
        # DM gönderme limiti
        new_limit = IntPrompt.ask(
            "Dakika başına DM gönderme limiti", 
            default=dm_limit,
            min_value=1,
            max_value=50
        )
        dashboard._update_env_variable("DM_RATE_LIMIT", str(new_limit))
        
        # Servislere de uygula
        if 'dm' in dashboard.services and hasattr(dashboard.services['dm'], 'rate_limiter'):
            dashboard.services['dm'].rate_limiter.dm_limit = new_limit
            
        dashboard.console.print(f"[green]✅ DM gönderme limiti {new_limit} olarak ayarlandı.[/green]")
        
    elif choice == "3":
        # Grup katılma limiti
        new_limit = IntPrompt.ask(
            "Dakika başına grup katılma limiti", 
            default=join_limit,
            min_value=1,
            max_value=40
        )
        dashboard._update_env_variable("JOIN_RATE_LIMIT", str(new_limit))
        
        # Servislere de uygula
        if 'group' in dashboard.services and hasattr(dashboard.services['group'], 'rate_limiter'):
            dashboard.services['group'].rate_limiter.join_limit = new_limit
            
        dashboard.console.print(f"[green]✅ Grup katılma limiti {new_limit} olarak ayarlandı.[/green]")
        
    elif choice == "4":
        # API çağrı limiti
        new_limit = IntPrompt.ask(
            "Dakika başına API çağrı limiti", 
            default=api_limit,
            min_value=10,
            max_value=100
        )
        dashboard._update_env_variable("API_RATE_LIMIT", str(new_limit))
        
        # Tüm servislere uygula
        for service_name, service in dashboard.services.items():
            if hasattr(service, 'rate_limiter'):
                service.rate_limiter.api_limit = new_limit
                
        dashboard.console.print(f"[green]✅ API çağrı limiti {new_limit} olarak ayarlandı.[/green]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Rate Limiter Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

def wait_times(dashboard):
    """Bekleme sürelerini yapılandırır"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]BEKLEME SÜRELERİ[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut değerleri göster
    error_wait = int(os.getenv("ERROR_WAIT_TIME", "300"))  # 5 dakika
    flood_wait = int(os.getenv("FLOOD_WAIT_MULTIPLIER", "2"))  # çarpan
    relogin_wait = int(os.getenv("RELOGIN_WAIT", "1800"))  # 30 dakika
    
    # Tablo oluştur
    table = Table(show_header=True, box=box.SIMPLE)
    table.add_column("Bekleme Türü", style="cyan")
    table.add_column("Mevcut Değer", style="yellow")
    table.add_column("Açıklama", style="green")
    
    table.add_row(
        "Hata Beklemesi", 
        f"{error_wait} saniye", 
        "Hata sonrası bekleme süresi"
    )
    table.add_row(
        "Flood Çarpanı", 
        f"{flood_wait}x", 
        "Flood bekleme süresinin çarpanı"
    )
    table.add_row(
        "Yeniden Giriş", 
        f"{relogin_wait} saniye", 
        "Oturum hatası sonrası bekleme"
    )
    
    dashboard.console.print(table)
    
    # Kullanıcı seçimi
    dashboard.console.print("\n[bold]Bekleme Süresi Değiştirme[/bold]")
    dashboard.console.print("1. Hata beklemesi")
    dashboard.console.print("2. Flood çarpanı")
    dashboard.console.print("3. Yeniden giriş beklemesi")
    dashboard.console.print("4. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
    
    if choice == "1":
        # Hata beklemesi
        new_wait = IntPrompt.ask(
            "Hata sonrası bekleme süresi (saniye)", 
            default=error_wait,
            min_value=10,
            max_value=3600
        )
        dashboard._update_env_variable("ERROR_WAIT_TIME", str(new_wait))
        
        # Servislere de uygula
        for service_name, service in dashboard.services.items():
            if hasattr(service, 'error_wait_time'):
                service.error_wait_time = new_wait
                
        dashboard.console.print(f"[green]✅ Hata beklemesi {new_wait} saniye olarak ayarlandı.[/green]")
        
    elif choice == "2":
        # Flood çarpanı
        new_multiplier = IntPrompt.ask(
            "Flood bekleme çarpanı", 
            default=flood_wait,
            min_value=1,
            max_value=10
        )
        dashboard._update_env_variable("FLOOD_WAIT_MULTIPLIER", str(new_multiplier))
        
        # Servislere de uygula
        for service_name, service in dashboard.services.items():
            if hasattr(service, 'flood_wait_multiplier'):
                service.flood_wait_multiplier = new_multiplier
                
        dashboard.console.print(f"[green]✅ Flood çarpanı {new_multiplier}x olarak ayarlandı.[/green]")
        
    elif choice == "3":
        # Yeniden giriş beklemesi
        new_wait = IntPrompt.ask(
            "Yeniden giriş beklemesi (saniye)", 
            default=relogin_wait,
            min_value=60,
            max_value=7200
        )
        dashboard._update_env_variable("RELOGIN_WAIT", str(new_wait))
        
        # Servislere de uygula
        for service_name, service in dashboard.services.items():
            if hasattr(service, 'relogin_wait'):
                service.relogin_wait = new_wait
                
        dashboard.console.print(f"[green]✅ Yeniden giriş beklemesi {new_wait} saniye olarak ayarlandı.[/green]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Rate Limiter Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

def error_behaviors(dashboard):
    """Hata davranışlarını yapılandırır"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]HATA DAVRANIŞLARI[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut ayarları göster
    max_retries = int(os.getenv("MAX_RETRIES", "3"))
    auto_relogin = os.getenv("AUTO_RELOGIN", "true").lower() in ("true", "1", "yes")
    notify_errors = os.getenv("NOTIFY_ERRORS", "true").lower() in ("true", "1", "yes")
    
    # Tablo oluştur
    table = Table(show_header=True, box=box.SIMPLE)
    table.add_column("Ayar", style="cyan")
    table.add_column("Değer", style="yellow")
    table.add_column("Açıklama", style="green")
    
    table.add_row(
        "Maksimum Deneme", 
        str(max_retries), 
        "Hata sonrası tekrar deneme sayısı"
    )
    table.add_row(
        "Otomatik Giriş", 
        "Açık" if auto_relogin else "Kapalı", 
        "Oturum hatalarında otomatik giriş"
    )
    table.add_row(
        "Hata Bildirimi", 
        "Açık" if notify_errors else "Kapalı", 
        "Admin gruba hata bildirimi"
    )
    
    dashboard.console.print(table)
    
    # Kullanıcı seçimi
    dashboard.console.print("\n[bold]Hata Davranışı Değiştirme[/bold]")
    dashboard.console.print("1. Maksimum deneme sayısı")
    dashboard.console.print("2. Otomatik giriş")
    dashboard.console.print("3. Hata bildirimi")
    dashboard.console.print("4. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
    
    if choice == "1":
        # Maksimum deneme sayısı
        new_retries = IntPrompt.ask(
            "Maksimum deneme sayısı", 
            default=max_retries,
            min_value=1,
            max_value=10
        )
        dashboard._update_env_variable("MAX_RETRIES", str(new_retries))
        
        # Servislere de uygula
        for service_name, service in dashboard.services.items():
            if hasattr(service, 'max_retries'):
                service.max_retries = new_retries
                
        dashboard.console.print(f"[green]✅ Maksimum deneme sayısı {new_retries} olarak ayarlandı.[/green]")
        
    elif choice == "2":
        # Otomatik giriş
        new_auto_relogin = not auto_relogin
        dashboard._update_env_variable("AUTO_RELOGIN", str(new_auto_relogin).lower())
        
        # Servislere de uygula
        for service_name, service in dashboard.services.items():
            if hasattr(service, 'auto_relogin'):
                service.auto_relogin = new_auto_relogin
                
        status = "açıldı" if new_auto_relogin else "kapatıldı"
        dashboard.console.print(f"[green]✅ Otomatik giriş {status}.[/green]")
        
    elif choice == "3":
        # Hata bildirimi
        new_notify = not notify_errors
        dashboard._update_env_variable("NOTIFY_ERRORS", str(new_notify).lower())
        
        # Servislere de uygula
        for service_name, service in dashboard.services.items():
            if hasattr(service, 'notify_errors'):
                service.notify_errors = new_notify
                
        status = "açıldı" if new_notify else "kapatıldı"
        dashboard.console.print(f"[green]✅ Hata bildirimi {status}.[/green]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Rate Limiter Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")