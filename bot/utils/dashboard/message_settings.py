"""
Mesaj ayarları modülü.
Bot'un mesaj gönderme davranışlarını ve şablonlarını yönetir.
"""

import os
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import box

def set_message_interval(dashboard):
    """Mesaj gönderme aralıklarını ayarlar"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]MESAJ GÖNDERME ARALIKLARI[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut ayarları göster
    base_interval = 300  # 5 dk varsayılan
    active_interval = 150  # Aktif gruplarda 2.5 dk
    interval_variance = 20  # % olarak varyans
    
    # Servis varsa oradan değerleri al
    try:
        if 'group' in dashboard.services:
            if hasattr(dashboard.services['group'], 'base_interval'):
                base_interval = dashboard.services['group'].base_interval
                
            if hasattr(dashboard.services['group'], 'active_interval'):
                active_interval = dashboard.services['group'].active_interval
                
            if hasattr(dashboard.services['group'], 'interval_variance'):
                interval_variance = dashboard.services['group'].interval_variance
    except:
        pass
    
    # Tabloyu göster
    table = Table(show_header=True, box=box.SIMPLE)
    table.add_column("Ayar", style="cyan")
    table.add_column("Değer", style="green")
    table.add_column("Açıklama", style="yellow")
    
    table.add_row(
        "Temel Aralık", 
        f"{base_interval} saniye ({base_interval//60} dakika)",
        "Normal gruplar için mesaj aralığı"
    )
    table.add_row(
        "Aktif Grup Aralığı", 
        f"{active_interval} saniye ({active_interval//60} dakika)",
        "Aktif gruplarda mesaj aralığı"
    )
    table.add_row(
        "Aralık Varyansı", 
        f"%{interval_variance}",
        "Aralıklara eklenen rastgele değişim"
    )
    
    dashboard.console.print(table)
    
    # İşlemler menüsü
    dashboard.console.print("\n[bold]İşlemler[/bold]")
    dashboard.console.print("1. Temel aralığı değiştir")
    dashboard.console.print("2. Aktif grup aralığını değiştir")
    dashboard.console.print("3. Aralık varyansını değiştir")
    dashboard.console.print("4. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
    
    if choice == "1":
        # Temel aralığı değiştir
        dashboard.console.print("\n[bold cyan]Temel Aralık Seçimi[/bold cyan]")
        dashboard.console.print("1. 5 dakika (300 saniye)")
        dashboard.console.print("2. 10 dakika (600 saniye)")
        dashboard.console.print("3. 15 dakika (900 saniye)")
        dashboard.console.print("4. 30 dakika (1800 saniye)")
        dashboard.console.print("5. Özel değer")
        
        interval_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="1")
        
        intervals = {
            "1": 300,   # 5 dakika
            "2": 600,   # 10 dakika
            "3": 900,   # 15 dakika
            "4": 1800,  # 30 dakika
            "5": None   # Özel
        }
        
        if interval_choice != "5":
            new_interval = intervals[interval_choice]
        else:
            # Özel aralık
            new_minutes = IntPrompt.ask("Dakika olarak aralık", default=base_interval//60, min_value=1)
            new_interval = new_minutes * 60
        
        # Değeri güncelle
        if 'group' in dashboard.services and hasattr(dashboard.services['group'], 'base_interval'):
            dashboard.services['group'].base_interval = new_interval
            dashboard.console.print(f"[green]✅ Temel aralık {new_interval//60} dakika olarak ayarlandı.[/green]")
    
    elif choice == "2":
        # Aktif grup aralığını değiştir
        dashboard.console.print("\n[bold cyan]Aktif Grup Aralığı Seçimi[/bold cyan]")
        dashboard.console.print("1. 2.5 dakika (150 saniye)")
        dashboard.console.print("2. 5 dakika (300 saniye)")
        dashboard.console.print("3. 7.5 dakika (450 saniye)")
        dashboard.console.print("4. 10 dakika (600 saniye)")
        dashboard.console.print("5. Özel değer")
        
        interval_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="1")
        
        intervals = {
            "1": 150,   # 2.5 dakika
            "2": 300,   # 5 dakika
            "3": 450,   # 7.5 dakika
            "4": 600,   # 10 dakika
            "5": None   # Özel
        }
        
        if interval_choice != "5":
            new_interval = intervals[interval_choice]
        else:
            # Özel aralık
            new_minutes = IntPrompt.ask("Dakika olarak aralık", default=active_interval//60, min_value=1)
            new_interval = new_minutes * 60
        
        # Değeri güncelle
        if 'group' in dashboard.services and hasattr(dashboard.services['group'], 'active_interval'):
            dashboard.services['group'].active_interval = new_interval
            dashboard.console.print(f"[green]✅ Aktif grup aralığı {new_interval//60} dakika olarak ayarlandı.[/green]")
    
    elif choice == "3":
        # Aralık varyansını değiştir
        dashboard.console.print("\n[bold cyan]Aralık Varyansı Seçimi[/bold cyan]")
        dashboard.console.print("1. %10 - Düşük varyans")
        dashboard.console.print("2. %20 - Normal varyans")
        dashboard.console.print("3. %30 - Yüksek varyans")
        dashboard.console.print("4. %50 - Çok yüksek varyans")
        dashboard.console.print("5. Özel değer")
        
        variance_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="2")
        
        variances = {
            "1": 10,
            "2": 20,
            "3": 30,
            "4": 50,
            "5": None  # Özel
        }
        
        if variance_choice != "5":
            new_variance = variances[variance_choice]
        else:
            # Özel varyans
            new_variance = IntPrompt.ask("Varyans yüzdesi", default=interval_variance, min_value=0, max_value=100)
        
        # Değeri güncelle
        if 'group' in dashboard.services and hasattr(dashboard.services['group'], 'interval_variance'):
            dashboard.services['group'].interval_variance = new_variance
            dashboard.console.print(f"[green]✅ Aralık varyansı %{new_variance} olarak ayarlandı.[/green]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Ana menüye dönmek için Enter tuşuna basın[/italic]")

def manage_message_templates(dashboard):
    """Mesaj şablonlarını yönetir"""
    # Template editor'u çağırır
    dashboard.template_editor("messages")

def response_settings(dashboard):
    """Otomatik yanıt ayarlarını yapılandırır"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]OTOMATİK YANIT AYARLARI[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut ayarları göster
    reply_enabled = True
    reply_chance = 80  # %80
    reply_cooldown = 60  # 60 saniye
    
    try:
        if 'reply' in dashboard.services:
            if hasattr(dashboard.services['reply'], 'enabled'):
                reply_enabled = dashboard.services['reply'].enabled
                
            if hasattr(dashboard.services['reply'], 'reply_chance'):
                reply_chance = dashboard.services['reply'].reply_chance
                
            if hasattr(dashboard.services['reply'], 'cooldown'):
                reply_cooldown = dashboard.services['reply'].cooldown
    except:
        pass
    
    # Durum bilgisi
    status_text = "[green]Aktif[/green]" if reply_enabled else "[yellow]Devre dışı[/yellow]"
    dashboard.console.print(f"Otomatik yanıt durumu: {status_text}")
    dashboard.console.print(f"Yanıt verme olasılığı: %{reply_chance}")
    dashboard.console.print(f"Yanıt bekleme süresi: {reply_cooldown} saniye")
    
    # Yanıt şablonları hakkında bilgi
    reply_templates = []
    try:
        reply_templates_path = os.getenv("RESPONSE_TEMPLATES_PATH", "data/responses.json")
        if os.path.exists(reply_templates_path):
            with open(reply_templates_path, 'r', encoding='utf-8') as f:
                reply_templates = json.load(f)
                
        template_count = sum(len(templates) for templates in reply_templates.values()) if isinstance(reply_templates, dict) else len(reply_templates)
        dashboard.console.print(f"Yanıt şablonu sayısı: {template_count}")
    except:
        dashboard.console.print("[red]Yanıt şablonları yüklenemedi.[/red]")
    
    # İşlemler menüsü
    dashboard.console.print("\n[bold]İşlemler[/bold]")
    dashboard.console.print(f"1. Otomatik yanıtları {'devre dışı bırak' if reply_enabled else 'etkinleştir'}")
    dashboard.console.print("2. Yanıt olasılığını değiştir")
    dashboard.console.print("3. Bekleme süresini değiştir")
    dashboard.console.print("4. Yanıt şablonlarını düzenle")
    dashboard.console.print("5. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="5")
    
    if choice == "1":
        # Otomatik yanıtları aç/kapat
        new_status = not reply_enabled
        if 'reply' in dashboard.services and hasattr(dashboard.services['reply'], 'enabled'):
            dashboard.services['reply'].enabled = new_status
            status_text = "etkinleştirildi" if new_status else "devre dışı bırakıldı"
            dashboard.console.print(f"[green]✅ Otomatik yanıtlar {status_text}.[/green]")
    
    elif choice == "2":
        # Yanıt olasılığını değiştir
        dashboard.console.print("\n[bold cyan]Yanıt Olasılığı Seçimi[/bold cyan]")
        dashboard.console.print("1. %25 - Düşük")
        dashboard.console.print("2. %50 - Orta")
        dashboard.console.print("3. %75 - Yüksek")
        dashboard.console.print("4. %100 - Her zaman")
        dashboard.console.print("5. Özel değer")
        
        chance_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="3")
        
        chances = {
            "1": 25,
            "2": 50,
            "3": 75,
            "4": 100,
            "5": None  # Özel
        }
        
        if chance_choice != "5":
            new_chance = chances[chance_choice]
        else:
            # Özel olasılık
            new_chance = IntPrompt.ask("Yüzde olarak olasılık", default=reply_chance, min_value=1, max_value=100)
        
        # Değeri güncelle
        if 'reply' in dashboard.services and hasattr(dashboard.services['reply'], 'reply_chance'):
            dashboard.services['reply'].reply_chance = new_chance
            dashboard.console.print(f"[green]✅ Yanıt olasılığı %{new_chance} olarak ayarlandı.[/green]")
    
    elif choice == "3":
        # Bekleme süresini değiştir
        dashboard.console.print("\n[bold cyan]Bekleme Süresi Seçimi[/bold cyan]")
        dashboard.console.print("1. 30 saniye")
        dashboard.console.print("2. 60 saniye")
        dashboard.console.print("3. 120 saniye")
        dashboard.console.print("4. 300 saniye")
        dashboard.console.print("5. Özel değer")
        
        cooldown_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="2")
        
        cooldowns = {
            "1": 30,
            "2": 60,
            "3": 120,
            "4": 300,
            "5": None  # Özel
        }
        
        if cooldown_choice != "5":
            new_cooldown = cooldowns[cooldown_choice]
        else:
            # Özel bekleme süresi
            new_cooldown = IntPrompt.ask("Saniye olarak bekleme süresi", default=reply_cooldown, min_value=1)
        
        # Değeri güncelle
        if 'reply' in dashboard.services and hasattr(dashboard.services['reply'], 'cooldown'):
            dashboard.services['reply'].cooldown = new_cooldown
            dashboard.console.print(f"[green]✅ Bekleme süresi {new_cooldown} saniye olarak ayarlandı.[/green]")
    
    elif choice == "4":
        # Yanıt şablonlarını düzenle
        dashboard.template_editor("responses")
        # İşlem tamamlandıktan sonra bu ekranı tekrar göster
        response_settings(dashboard)
        return
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Ana menüye dönmek için Enter tuşuna basın[/italic]")