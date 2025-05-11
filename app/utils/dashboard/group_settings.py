"""
Grup ayarları modülü.
Bot'un grup yönetimi ve üye toplama işlemlerini yapılandırır.
"""

import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import box

def manage_groups(dashboard):
    """Genel grup ayarlarını yönetir"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]GRUP AYARLARI[/bold cyan]",
        border_style="cyan"
    ))
    
    # Alt menü
    dashboard.console.print("\n[bold]Grup Yönetimi[/bold]")
    dashboard.console.print("1. Hedef grupları yönet")
    dashboard.console.print("2. Admin gruplarını yönet")
    dashboard.console.print("3. Hata veren grupları sıfırla")
    dashboard.console.print("4. Üye toplama ayarları")
    dashboard.console.print("5. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="5")
    
    if choice == "1":
        target_groups(dashboard)
    elif choice == "2":
        admin_groups(dashboard)
    elif choice == "3":
        reset_error_groups(dashboard)
    elif choice == "4":
        member_collection_settings(dashboard)
    
    # Ana menüye dönüş için seçenek 5'in işlenmesine gerek yok
    if choice != "5":
        # İşlem tamamlandıktan sonra bu ekranı tekrar göster
        manage_groups(dashboard)

def target_groups(dashboard):
    """Hedef grupları yönetir"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]HEDEF GRUPLAR YÖNETİMİ[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut hedef grupları al
    group_links = os.getenv("GROUP_LINKS", "").split(",")
    group_links = [link.strip() for link in group_links if link.strip()]
    
    dashboard.console.print(f"[yellow]Mevcut Hedef Grup Sayısı:[/yellow] {len(group_links)}")
    
    if group_links:
        # Tabloyu göster
        table = Table(show_header=True, box=box.SIMPLE)
        table.add_column("No", style="cyan", width=4)
        table.add_column("Grup Linki/ID", style="green")
        
        for i, link in enumerate(group_links):
            table.add_row(str(i+1), link)
        
        dashboard.console.print(table)
    else:
        dashboard.console.print("[yellow]Herhangi bir hedef grup tanımlanmamış.[/yellow]")
    
    # İşlemler menüsü
    dashboard.console.print("\n[bold]İşlemler[/bold]")
    dashboard.console.print("1. Grup ekle")
    dashboard.console.print("2. Grup çıkar")
    dashboard.console.print("3. Grup listesini temizle")
    dashboard.console.print("4. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
    
    if choice == "1":
        # Grup ekle
        new_group = Prompt.ask("Eklenecek grup linki/ID (örn: t.me/grubum veya -1001234567890)")
        
        if new_group.strip():
            if new_group not in group_links:
                group_links.append(new_group)
                
                # .env'yi güncelle
                new_value = ",".join(group_links)
                dashboard._update_env_variable("GROUP_LINKS", new_value)
                dashboard.console.print(f"[green]✅ Grup eklendi: {new_group}[/green]")
            else:
                dashboard.console.print("[yellow]Bu grup zaten ekli.[/yellow]")
    
    elif choice == "2" and group_links:
        # Grup çıkar
        group_idx = IntPrompt.ask(
            "Çıkarılacak grubun numarası", 
            min_value=1,
            max_value=len(group_links)
        )
        
        removed = group_links.pop(group_idx - 1)
        
        # .env'yi güncelle
        new_value = ",".join(group_links)
        dashboard._update_env_variable("GROUP_LINKS", new_value)
        dashboard.console.print(f"[green]✅ Grup çıkarıldı: {removed}[/green]")
    
    elif choice == "3" and group_links:
        # Grup listesini temizle
        if Confirm.ask("Tüm grup listesini temizlemek istediğinize emin misiniz?"):
            dashboard._update_env_variable("GROUP_LINKS", "")
            dashboard.console.print(f"[green]✅ Grup listesi temizlendi.[/green]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Grup Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

def admin_groups(dashboard):
    """Admin gruplarını yönetir"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]ADMİN GRUPLARI YÖNETİMİ[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut admin grupları al
    admin_group_links = os.getenv("ADMIN_GROUP_LINKS", "").split(",")
    admin_group_links = [link.strip() for link in admin_group_links if link.strip()]
    
    dashboard.console.print(f"[yellow]Mevcut Admin Grup Sayısı:[/yellow] {len(admin_group_links)}")
    
    if admin_group_links:
        # Tabloyu göster
        table = Table(show_header=True, box=box.SIMPLE)
        table.add_column("No", style="cyan", width=4)
        table.add_column("Grup Linki/ID", style="green")
        
        for i, link in enumerate(admin_group_links):
            table.add_row(str(i+1), link)
        
        dashboard.console.print(table)
    else:
        dashboard.console.print("[yellow]Herhangi bir admin grubu tanımlanmamış.[/yellow]")
    
    # İşlemler menüsü
    dashboard.console.print("\n[bold]İşlemler[/bold]")
    dashboard.console.print("1. Admin grubu ekle")
    dashboard.console.print("2. Admin grubu çıkar")
    dashboard.console.print("3. Admin grup listesini temizle")
    dashboard.console.print("4. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
    
    if choice == "1":
        # Grup ekle
        new_group = Prompt.ask("Eklenecek admin grup linki/ID (örn: t.me/admingrubum veya -1001234567890)")
        
        if new_group.strip():
            if new_group not in admin_group_links:
                admin_group_links.append(new_group)
                
                # .env'yi güncelle
                new_value = ",".join(admin_group_links)
                dashboard._update_env_variable("ADMIN_GROUP_LINKS", new_value)
                dashboard.console.print(f"[green]✅ Admin grubu eklendi: {new_group}[/green]")
            else:
                dashboard.console.print("[yellow]Bu admin grubu zaten ekli.[/yellow]")
    
    elif choice == "2" and admin_group_links:
        # Grup çıkar
        group_idx = IntPrompt.ask(
            "Çıkarılacak admin grubunun numarası", 
            min_value=1,
            max_value=len(admin_group_links)
        )
        
        removed = admin_group_links.pop(group_idx - 1)
        
        # .env'yi güncelle
        new_value = ",".join(admin_group_links)
        dashboard._update_env_variable("ADMIN_GROUP_LINKS", new_value)
        dashboard.console.print(f"[green]✅ Admin grubu çıkarıldı: {removed}[/green]")
    
    elif choice == "3" and admin_group_links:
        # Grup listesini temizle
        if Confirm.ask("Tüm admin grup listesini temizlemek istediğinize emin misiniz?"):
            dashboard._update_env_variable("ADMIN_GROUP_LINKS", "")
            dashboard.console.print(f"[green]✅ Admin grup listesi temizlendi.[/green]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Grup Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

def reset_error_groups(dashboard):
    """Hata veren grupları sıfırlar"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]HATA VEREN GRUPLARI SIFIRLA[/bold cyan]",
        border_style="cyan"
    ))
    
    # Hata veren grupları al
    error_groups = []
    try:
        if 'group' in dashboard.services and hasattr(dashboard.services['group'], 'error_groups'):
            error_groups = dashboard.services['group'].error_groups
    except:
        pass
    
    if error_groups:
        dashboard.console.print(f"[yellow]Hata veren grup sayısı:[/yellow] {len(error_groups)}")
        
        # Tabloyu göster
        table = Table(show_header=True, box=box.SIMPLE)
        table.add_column("No", style="cyan", width=4)
        table.add_column("Grup ID", style="red")
        
        for i, group_id in enumerate(error_groups):
            table.add_row(str(i+1), str(group_id))
        
        dashboard.console.print(table)
        
        # Sıfırlama seçeneği
        if Confirm.ask("Hata veren gruplar listesini sıfırlamak istiyor musunuz?"):
            try:
                if 'group' in dashboard.services and hasattr(dashboard.services['group'], 'error_groups'):
                    dashboard.services['group'].error_groups = []
                    dashboard.console.print("[green]✅ Hata veren gruplar listesi sıfırlandı.[/green]")
            except Exception as e:
                dashboard.console.print(f"[red]❌ Hata: {str(e)}[/red]")
    else:
        dashboard.console.print("[green]✅ Herhangi bir hata veren grup bulunmuyor.[/green]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Grup Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

def member_collection_settings(dashboard):
    """Üye toplama ayarlarını yapılandırır"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]ÜYE TOPLAMA AYARLARI[/bold cyan]",
        border_style="cyan"
    ))
    
    # Mevcut ayarları göster
    collection_enabled = True
    collection_interval = 3600  # 1 saat
    max_members_per_group = 500
    
    try:
        if 'dm' in dashboard.services:
            if hasattr(dashboard.services['dm'], 'collect_members_enabled'):
                collection_enabled = dashboard.services['dm'].collect_members_enabled
                
            if hasattr(dashboard.services['dm'], 'collection_interval'):
                collection_interval = dashboard.services['dm'].collection_interval
                
            if hasattr(dashboard.services['dm'], 'max_members_per_group'):
                max_members_per_group = dashboard.services['dm'].max_members_per_group
    except:
        pass
    
    # Durum bilgisini göster
    status_text = "[green]Aktif[/green]" if collection_enabled else "[yellow]Devre dışı[/yellow]"
    dashboard.console.print(f"Üye toplama durumu: {status_text}")
    dashboard.console.print(f"Toplama aralığı: {collection_interval//60} dakika")
    dashboard.console.print(f"Grup başına maksimum üye: {max_members_per_group}")
    
    # İşlemler menüsü
    dashboard.console.print("\n[bold]İşlemler[/bold]")
    dashboard.console.print(f"1. Üye toplamayı {'devre dışı bırak' if collection_enabled else 'etkinleştir'}")
    dashboard.console.print("2. Toplama aralığını değiştir")
    dashboard.console.print("3. Grup başına maksimum üye sayısını değiştir")
    dashboard.console.print("4. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
    
    if choice == "1":
        # Üye toplamayı aç/kapat
        new_status = not collection_enabled
        if 'dm' in dashboard.services and hasattr(dashboard.services['dm'], 'collect_members_enabled'):
            dashboard.services['dm'].collect_members_enabled = new_status
            status_text = "etkinleştirildi" if new_status else "devre dışı bırakıldı"
            dashboard.console.print(f"[green]✅ Üye toplama {status_text}.[/green]")
    
    elif choice == "2":
        # Toplama aralığını değiştir
        dashboard.console.print("\n[bold cyan]Toplama Aralığı Seçimi[/bold cyan]")
        dashboard.console.print("1. 30 dakika")
        dashboard.console.print("2. 1 saat")
        dashboard.console.print("3. 3 saat")
        dashboard.console.print("4. 6 saat")
        dashboard.console.print("5. 12 saat")
        dashboard.console.print("6. Özel değer")
        
        interval_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5", "6"], default="2")
        
        intervals = {
            "1": 1800,    # 30 dakika
            "2": 3600,    # 1 saat
            "3": 10800,   # 3 saat
            "4": 21600,   # 6 saat
            "5": 43200,   # 12 saat
            "6": None     # Özel
        }
        
        if interval_choice != "6":
            new_interval = intervals[interval_choice]
        else:
            # Özel aralık
            new_minutes = IntPrompt.ask("Dakika olarak aralık", default=collection_interval//60, min_value=5)
            new_interval = new_minutes * 60
        
        # Değeri güncelle
        if 'dm' in dashboard.services and hasattr(dashboard.services['dm'], 'collection_interval'):
            dashboard.services['dm'].collection_interval = new_interval
            dashboard.console.print(f"[green]✅ Toplama aralığı {new_interval//60} dakika olarak ayarlandı.[/green]")
    
    elif choice == "3":
        # Grup başına maksimum üye sayısını değiştir
        dashboard.console.print("\n[bold cyan]Grup Başına Maksimum Üye Sayısı[/bold cyan]")
        dashboard.console.print("1. 100 üye")
        dashboard.console.print("2. 250 üye")
        dashboard.console.print("3. 500 üye")
        dashboard.console.print("4. 1000 üye")
        dashboard.console.print("5. Limitsiz")
        dashboard.console.print("6. Özel değer")
        
        limit_choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5", "6"], default="3")
        
        limits = {
            "1": 100,
            "2": 250,
            "3": 500,
            "4": 1000,
            "5": 0,       # Limitsiz
            "6": None     # Özel
        }
        
        if limit_choice != "6":
            new_limit = limits[limit_choice]
        else:
            # Özel limit
            new_limit = IntPrompt.ask("Grup başına maksimum üye sayısı", default=max_members_per_group, min_value=0)
        
        # Değeri güncelle
        if 'dm' in dashboard.services and hasattr(dashboard.services['dm'], 'max_members_per_group'):
            dashboard.services['dm'].max_members_per_group = new_limit
            limit_text = "Limitsiz" if new_limit == 0 else str(new_limit)
            dashboard.console.print(f"[green]✅ Grup başına maksimum üye sayısı {limit_text} olarak ayarlandı.[/green]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Grup Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")