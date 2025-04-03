"""
Davet ayarları modülü.
Bot'un davet gönderme davranışlarını yönetir.
"""

import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import box

def manage_invite_templates(dashboard):
    """Davet şablonlarını yönetir"""
    # Aynı zamanda template_editor'u çağırabilir
    dashboard.template_editor("invites")

def manage_super_users(dashboard):
    """Süper kullanıcıları yönetir"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]SÜPER KULLANICI YÖNETİMİ[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut süper kullanıcıları al
    super_users = os.getenv("SUPER_USERS", "").split(",")
    super_users = [user.strip() for user in super_users if user.strip()]
    
    dashboard.console.print(f"[yellow]Mevcut Süper Kullanıcı Sayısı:[/yellow] {len(super_users)}")
    
    if super_users:
        # Tabloyu göster
        table = Table(show_header=True, box=box.SIMPLE)
        table.add_column("No", style="cyan", width=4)
        table.add_column("Kullanıcı ID/Kullanıcı Adı", style="green")
        
        for i, user in enumerate(super_users):
            table.add_row(str(i+1), user)
        
        dashboard.console.print(table)
    
    # İşlemler menüsü
    dashboard.console.print("\n[bold]İşlemler[/bold]")
    dashboard.console.print("1. Süper kullanıcı ekle")
    dashboard.console.print("2. Süper kullanıcı çıkar")
    dashboard.console.print("3. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3"], default="3")
    
    if choice == "1":
        # Süper kullanıcı ekle
        new_user = Prompt.ask("Eklenecek kullanıcı ID/kullanıcı adı")
        
        if new_user.strip():
            if new_user not in super_users:
                super_users.append(new_user)
                
                # .env'yi güncelle
                new_value = ",".join(super_users)
                dashboard._update_env_variable("SUPER_USERS", new_value)
                dashboard.console.print(f"[green]✅ Süper kullanıcı eklendi: {new_user}[/green]")
            else:
                dashboard.console.print("[yellow]Bu kullanıcı zaten ekli.[/yellow]")
    
    elif choice == "2" and super_users:
        # Süper kullanıcı çıkar
        user_idx = IntPrompt.ask(
            "Çıkarılacak kullanıcının numarası", 
            min_value=1,
            max_value=len(super_users)
        )
        
        removed = super_users.pop(user_idx - 1)
        
        # .env'yi güncelle
        new_value = ",".join(super_users)
        dashboard._update_env_variable("SUPER_USERS", new_value)
        dashboard.console.print(f"[green]✅ Süper kullanıcı çıkarıldı: {removed}[/green]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Davet Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

def invite_frequency(dashboard):
    """Davet gönderim sıklığını ayarlar"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]DAVET GÖNDERİM SIKLIĞI[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut ayarları göster
    default_interval = 60  # 60 sn
    default_max_per_day = 50  # Günlük maksimum
    
    current_interval = default_interval
    current_max = default_max_per_day
    
    try:
        if hasattr(dashboard.services['dm'], 'invite_interval'):
            current_interval = dashboard.services['dm'].invite_interval
            
        if hasattr(dashboard.services['dm'], 'max_invites_per_day'):
            current_max = dashboard.services['dm'].max_invites_per_day
    except:
        pass
    
    dashboard.console.print(f"[yellow]Davet aralığı:[/yellow] {current_interval} saniye")
    dashboard.console.print(f"[yellow]Günlük maksimum davet:[/yellow] {current_max}")
    
    # Ayarları değiştirme menüsü
    dashboard.console.print("\n[bold]Ayarları Değiştir[/bold]")
    dashboard.console.print("1. Davet aralığını değiştir")
    dashboard.console.print("2. Günlük maksimum daveti değiştir")
    dashboard.console.print("3. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3"], default="3")
    
    if choice == "1":
        # Davet aralığını değiştir
        dashboard.console.print("\n[bold cyan]Davet Aralığı Seçimi[/bold cyan]")
        dashboard.console.print("[yellow]Not: Çok kısa aralıklar Telegram tarafından kısıtlanabilir![/yellow]")
        dashboard.console.print("1. Hızlı (30 saniye)")
        dashboard.console.print("2. Normal (60 saniye)")
        dashboard.console.print("3. Yavaş (120 saniye)")
        dashboard.console.print("4. Çok Yavaş (300 saniye)")
        dashboard.console.print("5. Özel değer")
        
        interval_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="2")
        
        if interval_choice == "1":
            new_interval = 30
        elif interval_choice == "2":  
            new_interval = 60
        elif interval_choice == "3":
            new_interval = 120
        elif interval_choice == "4":
            new_interval = 300
        else:  # 5 - Özel değer
            new_interval = IntPrompt.ask("Saniye olarak aralık", default=current_interval, min_value=10)
        
        # Değeri güncelle
        if 'dm' in dashboard.services and hasattr(dashboard.services['dm'], 'invite_interval'):
            dashboard.services['dm'].invite_interval = new_interval
            dashboard.console.print(f"[green]✅ Davet aralığı {new_interval} saniye olarak ayarlandı.[/green]")
    
    elif choice == "2":
        # Günlük maksimum daveti değiştir
        dashboard.console.print("\n[bold cyan]Günlük Maksimum Davet Seçimi[/bold cyan]")
        dashboard.console.print("[yellow]Not: Yüksek değerler hesabınızın kısıtlanmasına neden olabilir![/yellow]")
        dashboard.console.print("1. Güvenli (20)")
        dashboard.console.print("2. Normal (50)")
        dashboard.console.print("3. Yüksek (100)")
        dashboard.console.print("4. Çok Yüksek (200)")
        dashboard.console.print("5. Özel değer")
        
        max_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="2")
        
        if max_choice == "1":
            new_max = 20
        elif max_choice == "2":  
            new_max = 50
        elif max_choice == "3":
            new_max = 100
        elif max_choice == "4":
            new_max = 200
        else:  # 5 - Özel değer
            new_max = IntPrompt.ask("Günlük maksimum davet sayısı", default=current_max, min_value=1)
        
        # Değeri güncelle
        if 'dm' in dashboard.services and hasattr(dashboard.services['dm'], 'max_invites_per_day'):
            dashboard.services['dm'].max_invites_per_day = new_max
            dashboard.console.print(f"[green]✅ Günlük maksimum davet sayısı {new_max} olarak ayarlandı.[/green]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Davet Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")