"""
Veritabanı ayarları modülü.
Bot veritabanını yönetmek, istatistikleri görmek ve yedeklemek için arayüz sağlar.
"""

import os
import json
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich import box

def db_stats(dashboard):
    """Veritabanı istatistiklerini gösterir"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]VERİTABANI İSTATİSTİKLERİ[/bold cyan]",
        border_style="cyan"
    ))
    
    try:
        # Veritabanına erişimi kontrol et
        if not hasattr(dashboard.db, 'connection'):
            dashboard.console.print("[red]❌ Veritabanı bağlantısı bulunamadı.[/red]")
            Prompt.ask("\n[italic]Ana menüye dönmek için Enter tuşuna basın[/italic]")
            return
            
        # Temel veritabanı bilgileri
        db_path = getattr(dashboard.db, 'db_path', 'Bilinmiyor')
        db_size = 0
        
        if os.path.exists(db_path):
            db_size = os.path.getsize(db_path)
            # Boyutu uygun formata dönüştür (KB, MB)
            if db_size < 1024:
                size_str = f"{db_size} B"
            elif db_size < 1024 * 1024:
                size_str = f"{db_size/1024:.2f} KB"
            else:
                size_str = f"{db_size/(1024*1024):.2f} MB"
        else:
            size_str = "Belirsiz"
            
        dashboard.console.print(f"[yellow]Veritabanı Dosyası:[/yellow] {db_path}")
        dashboard.console.print(f"[yellow]Veritabanı Boyutu:[/yellow] {size_str}")
        
        # Tablo istatistiklerini göster
        dashboard.console.print("\n[bold]Tablo İstatistikleri:[/bold]")
        
        table = Table(show_header=True, box=box.SIMPLE)
        table.add_column("Tablo", style="cyan")
        table.add_column("Satır Sayısı", style="yellow", justify="right")
        table.add_column("Son Güncelleme", style="green")
        
        # Bilinen tablolar için istatistikleri al
        tables = ["users", "groups", "messages", "invites", "sessions"]
        
        for table_name in tables:
            try:
                # Satır sayısı
                query = f"SELECT COUNT(*) FROM {table_name}"
                cursor = dashboard.db.connection.cursor()
                cursor.execute(query)
                count = cursor.fetchone()[0]
                
                # Son güncelleme zamanı (bu SQL uyumlu olmayabilir, uyarlanması gerekiyor)
                # SQLite için:
                try:
                    cursor.execute(f"SELECT MAX(updated_at) FROM {table_name}")
                    last_update = cursor.fetchone()[0] or "Veri yok"
                except:
                    last_update = "Belirsiz"
                
                table.add_row(table_name, str(count), str(last_update))
            except Exception as e:
                table.add_row(table_name, "Hata", f"({str(e)})")
                
        dashboard.console.print(table)
        
        # Ekstra istatistikler
        dashboard.console.print("\n[bold]Özet İstatistikler:[/bold]")
        
        # Aktif kullanıcı sayısı
        try:
            cursor = dashboard.db.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
            active_users = cursor.fetchone()[0]
            dashboard.console.print(f"Aktif Kullanıcı Sayısı: [green]{active_users}[/green]")
        except:
            pass
            
        # Toplam mesaj sayısı
        try:
            cursor = dashboard.db.connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]
            dashboard.console.print(f"Toplam Mesaj Sayısı: [green]{total_messages}[/green]")
        except:
            pass
            
        # Üye toplanmış gruplar
        try:
            cursor = dashboard.db.connection.cursor()
            cursor.execute("SELECT COUNT(DISTINCT group_id) FROM users")
            member_groups = cursor.fetchone()[0]
            dashboard.console.print(f"Üye Toplanan Grup Sayısı: [green]{member_groups}[/green]")
        except:
            pass
        
    except Exception as e:
        dashboard.console.print(f"[red]❌ İstatistikler alınırken hata oluştu: {str(e)}[/red]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Veritabanı Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

def optimize_db(dashboard):
    """Veritabanını optimize eder"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]VERİTABANI OPTİMİZASYONU[/bold cyan]",
        border_style="cyan"
    ))
    
    # Optimizasyon işlemleri
    dashboard.console.print("\n[bold]Optimizasyon İşlemleri:[/bold]")
    dashboard.console.print("1. VACUUM - Boş alanları temizle")
    dashboard.console.print("2. REINDEX - İndeksleri yeniden oluştur")
    dashboard.console.print("3. Eski kayıtları temizle")
    dashboard.console.print("4. Analiz çalıştır")
    dashboard.console.print("5. Tüm optimizasyonları çalıştır")
    dashboard.console.print("6. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5", "6"], default="6")
    
    if choice == "6":
        return
        
    try:
        # Veritabanına erişimi kontrol et
        if not hasattr(dashboard.db, 'connection'):
            dashboard.console.print("[red]❌ Veritabanı bağlantısı bulunamadı.[/red]")
            Prompt.ask("\n[italic]Ana menüye dönmek için Enter tuşuna basın[/italic]")
            return
            
        # Yedekleme uyarısı
        dashboard.console.print("\n[yellow]⚠️ Optimizasyon öncesi veritabanını yedeklemek iyi bir fikirdir.[/yellow]")
        
        if Confirm.ask("Devam etmeden önce veritabanını yedeklemek ister misiniz?"):
            # Basit bir yedekleme işlemi
            db_path = getattr(dashboard.db, 'db_path', None)
            
            if db_path and os.path.exists(db_path):
                backup_dir = "backups"
                os.makedirs(backup_dir, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"db_backup_before_optimize_{timestamp}.bak"
                backup_path = os.path.join(backup_dir, backup_file)
                
                shutil.copy2(db_path, backup_path)
                dashboard.console.print(f"[green]✅ Veritabanı yedeklendi: {backup_path}[/green]")
        
        # İşlemleri gerçekleştir
        cursor = dashboard.db.connection.cursor()
        
        if choice in ["1", "5"]:
            # VACUUM
            dashboard.console.print("[yellow]VACUUM işlemi başlatılıyor...[/yellow]")
            cursor.execute("VACUUM")
            dashboard.console.print("[green]✅ VACUUM tamamlandı.[/green]")
            
        if choice in ["2", "5"]:
            # REINDEX
            dashboard.console.print("[yellow]REINDEX işlemi başlatılıyor...[/yellow]")
            cursor.execute("REINDEX")
            dashboard.console.print("[green]✅ REINDEX tamamlandı.[/green]")
            
        if choice in ["3", "5"]:
            # Eski kayıtları temizle
            days = IntPrompt.ask(
                "Kaç günden eski kayıtlar temizlensin?", 
                default=30, 
                min_value=7,
                show_default=True
            )
            
            dashboard.console.print(f"[yellow]{days} günden eski kayıtlar temizleniyor...[/yellow]")
            
            # Eski mesajları temizle
            try:
                cursor.execute(f"DELETE FROM messages WHERE created_at < datetime('now', '-{days} days')")
                deleted = cursor.rowcount
                dashboard.console.print(f"[green]✅ {deleted} eski mesaj silindi.[/green]")
            except Exception as e:
                dashboard.console.print(f"[red]Mesajlar temizlenirken hata: {str(e)}[/red]")
                
            # Eski oturum kayıtlarını temizle
            try:
                cursor.execute(f"DELETE FROM sessions WHERE last_activity < datetime('now', '-{days} days')")
                deleted = cursor.rowcount
                dashboard.console.print(f"[green]✅ {deleted} eski oturum kaydı silindi.[/green]")
            except Exception as e:
                dashboard.console.print(f"[red]Oturumlar temizlenirken hata: {str(e)}[/red]")
                
            # Diğer tablolardaki eski kayıtları temizle...
                
        if choice in ["4", "5"]:
            # Analiz çalıştır
            dashboard.console.print("[yellow]Analiz işlemi başlatılıyor...[/yellow]")
            cursor.execute("ANALYZE")
            dashboard.console.print("[green]✅ Analiz tamamlandı.[/green]")
        
        dashboard.console.print("\n[green]✅ Seçilen optimizasyon işlemleri tamamlandı.[/green]")
        
    except Exception as e:
        dashboard.console.print(f"[red]❌ Optimizasyon sırasında hata oluştu: {str(e)}[/red]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Veritabanı Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

def export_data(dashboard):
    """Veritabanı verilerini dışa aktarır"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]VERİYİ DIŞA AKTAR[/bold cyan]",
        border_style="cyan"
    ))
    
    # Veritabanı tipi kontrolü
    db_type = "SQLite"
    if hasattr(dashboard.db, 'connection') and hasattr(dashboard.db.connection, 'driver_name'):
        db_type = dashboard.db.connection.driver_name
    
    # Dışa aktarma formatları
    dashboard.console.print("[bold]Dışa Aktarma Formatları:[/bold]")
    dashboard.console.print("1. JSON")
    dashboard.console.print("2. CSV")
    dashboard.console.print("3. SQL Dump (sadece SQLite)")
    dashboard.console.print("4. Geri")
    
    choice = Prompt.ask("Format seçin", choices=["1", "2", "3", "4"], default="1")
    
    if choice == "4":
        return
    
    # Dışa aktarılacak veri türleri
    dashboard.console.print("\n[bold]Dışa Aktarılacak Veriler:[/bold]")
    dashboard.console.print("1. Tüm veriler")
    dashboard.console.print("2. Sadece kullanıcılar")
    dashboard.console.print("3. Sadece gruplar")
    dashboard.console.print("4. Mesaj istatistikleri")
    
    data_choice = Prompt.ask("Veri türü seçin", choices=["1", "2", "3", "4"], default="1")
    
    # Dosya adı
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    formats = {
        "1": "json",
        "2": "csv",
        "3": "sql"
    }
    
    data_types = {
        "1": "all",
        "2": "users",
        "3": "groups",
        "4": "messages"
    }
    
    filename = f"export_{data_types[data_choice]}_{timestamp}.{formats[choice]}"
    filepath = os.path.join("exports", filename)
    
    # Dizini kontrol et
    os.makedirs("exports", exist_ok=True)
    
    try:
        dashboard.console.print(f"\n[yellow]Veriler dışa aktarılıyor: {filepath}[/yellow]")
        
        if hasattr(dashboard.db, 'export_data'):
            success = dashboard.db.export_data(
                format=formats[choice], 
                data_type=data_types[data_choice],
                filepath=filepath
            )
            
            if success:
                dashboard.console.print(f"[green]✅ Veriler başarıyla dışa aktarıldı: {filepath}[/green]")
            else:
                dashboard.console.print(f"[red]❌ Dışa aktarım başarısız oldu[/red]")
        else:
            dashboard.console.print("[yellow]Bu işlem için destek bulunmuyor.[/yellow]")
            
    except Exception as e:
        dashboard.console.print(f"[red]Hata: {str(e)}[/red]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Veritabanı Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

def backup_restore(dashboard):
    """Veritabanı yedekleme ve geri yükleme"""
    dashboard.clear_screen()
    
    dashboard.console.print(Panel.fit(
        "[bold cyan]YEDEKLEME VE GERİ YÜKLEME[/bold cyan]",
        border_style="cyan"
    ))
    
    # Seçenekler
    dashboard.console.print("[bold]İşlemler:[/bold]")
    dashboard.console.print("1. Veritabanını yedekle")
    dashboard.console.print("2. Yedeği geri yükle")
    dashboard.console.print("3. Yedekleri listele")
    dashboard.console.print("4. Geri")
    
    choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="1")
    
    if choice == "1":
        # Yedekleme işlemi
        dashboard.console.print("\n[bold]Veritabanı Yedekleme[/bold]")
        
        # Yedek dizini kontrol et
        backup_dir = os.path.join("backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        # Yedek adı
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        custom_name = Prompt.ask("Yedek adı (varsayılan için Enter)", default=backup_name)
        
        if not custom_name.endswith(".bak"):
            custom_name += ".bak"
            
        backup_path = os.path.join(backup_dir, custom_name)
        
        try:
            dashboard.console.print(f"[yellow]Yedekleme işlemi başlatılıyor: {backup_path}[/yellow]")
            
            if hasattr(dashboard.db, 'backup_database'):
                success = dashboard.db.backup_database(backup_path)
                
                if success:
                    dashboard.console.print(f"[green]✅ Veritabanı başarıyla yedeklendi: {backup_path}[/green]")
                else:
                    dashboard.console.print(f"[red]❌ Yedekleme başarısız oldu[/red]")
            else:
                dashboard.console.print("[yellow]Bu işlem için destek bulunmuyor.[/yellow]")
                
        except Exception as e:
            dashboard.console.print(f"[red]Hata: {str(e)}[/red]")
    
    elif choice == "2":
        # Geri yükleme işlemi
        dashboard.console.print("\n[bold]Veritabanı Geri Yükleme[/bold]")
        dashboard.console.print("[red]⚠️ UYARI: Bu işlem mevcut veritabanının üzerine yazacaktır![/red]")
        
        # Yedek dizini kontrol et
        backup_dir = os.path.join("backups")
        
        if not os.path.exists(backup_dir) or not os.listdir(backup_dir):
            dashboard.console.print("[yellow]Hiç yedek bulunmuyor![/yellow]")
        else:
            # Yedekleri listele
            backups = sorted(os.listdir(backup_dir), reverse=True)
            backup_table = Table(show_header=True, box=box.SIMPLE)
            backup_table.add_column("No", style="cyan", width=4)
            backup_table.add_column("Yedek Adı", style="green")
            backup_table.add_column("Tarih", style="yellow")
            backup_table.add_column("Boyut", style="magenta", justify="right")
            
            for i, backup in enumerate(backups):
                if backup.endswith('.bak'):
                    try:
                        backup_path = os.path.join(backup_dir, backup)
                        mod_time = datetime.fromtimestamp(os.path.getmtime(backup_path)).strftime("%Y-%m-%d %H:%M")
                        size_kb = round(os.path.getsize(backup_path) / 1024, 2)
                        backup_table.add_row(str(i+1), backup, mod_time, f"{size_kb} KB")
                    except:
                        backup_table.add_row(str(i+1), backup, "?", "?")
            
            dashboard.console.print(backup_table)
            
            # Yedek seçimi
            backup_idx = IntPrompt.ask(
                "Geri yüklenecek yedeğin numarası (İptal için 0)", 
                min_value=0,
                max_value=len(backups)
            )
            
            if backup_idx > 0:
                selected_backup = backups[backup_idx-1]
                backup_path = os.path.join(backup_dir, selected_backup)
                
                # Son onay
                confirm = Confirm.ask(f"[red]{selected_backup} yedeğini geri yüklemek istediğinize emin misiniz?[/red]")
                
                if confirm:
                    try:
                        dashboard.console.print(f"[yellow]Geri yükleme işlemi başlatılıyor: {backup_path}[/yellow]")
                        
                        if hasattr(dashboard.db, 'restore_database'):
                            success = dashboard.db.restore_database(backup_path)
                            
                            if success:
                                dashboard.console.print(f"[green]✅ Veritabanı başarıyla geri yüklendi![/green]")
                                dashboard.console.print("[yellow]⚠️ Bot'u yeniden başlatmanız gerekebilir.[/yellow]")
                            else:
                                dashboard.console.print(f"[red]❌ Geri yükleme başarısız oldu[/red]")
                        else:
                            dashboard.console.print("[yellow]Bu işlem için destek bulunmuyor.[/yellow]")
                            
                    except Exception as e:
                        dashboard.console.print(f"[red]Hata: {str(e)}[/red]")
    
    elif choice == "3":
        # Yedekleri listeleme
        dashboard.console.print("\n[bold]Yedek Listesi[/bold]")
        
        # Yedek dizini kontrol et
        backup_dir = os.path.join("backups")
        
        if not os.path.exists(backup_dir) or not os.listdir(backup_dir):
            dashboard.console.print("[yellow]Hiç yedek bulunmuyor![/yellow]")
        else:
            # Yedekleri listele
            backups = sorted(os.listdir(backup_dir), reverse=True)
            backup_table = Table(show_header=True, box=box.SIMPLE)
            backup_table.add_column("No", style="cyan", width=4)
            backup_table.add_column("Yedek Adı", style="green")
            backup_table.add_column("Tarih", style="yellow")
            backup_table.add_column("Boyut", style="magenta", justify="right")
            
            for i, backup in enumerate(backups):
                if backup.endswith('.bak'):
                    try:
                        backup_path = os.path.join(backup_dir, backup)
                        mod_time = datetime.fromtimestamp(os.path.getmtime(backup_path)).strftime("%Y-%m-%d %H:%M")
                        size_kb = round(os.path.getsize(backup_path) / 1024, 2)
                        backup_table.add_row(str(i+1), backup, mod_time, f"{size_kb} KB")
                    except:
                        backup_table.add_row(str(i+1), backup, "?", "?")
            
            dashboard.console.print(backup_table)
            
            # Silme seçeneği
            delete_option = Confirm.ask("Bir yedeği silmek ister misiniz?")
            if delete_option:
                delete_idx = IntPrompt.ask(
                    "Silinecek yedeğin numarası (İptal için 0)", 
                    min_value=0,
                    max_value=len(backups)
                )
                
                if delete_idx > 0:
                    selected_backup = backups[delete_idx-1]
                    backup_path = os.path.join(backup_dir, selected_backup)
                    
                    # Onay
                    confirm = Confirm.ask(f"[red]{selected_backup} yedeğini silmek istediğinize emin misiniz?[/red]")
                    
                    if confirm:
                        try:
                            os.remove(backup_path)
                            dashboard.console.print(f"[green]✅ Yedek başarıyla silindi: {selected_backup}[/green]")
                        except Exception as e:
                            dashboard.console.print(f"[red]Hata: {str(e)}[/red]")
    
    # Kullanıcının devam etmesi için bekle
    Prompt.ask("\n[italic]Veritabanı Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")