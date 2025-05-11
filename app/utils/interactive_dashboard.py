"""
# ============================================================================ #
# Dosya: interactive_dashboard.py
# Yol: /Users/siyahkare/code/telegram-bot/app/utils/interactive_dashboard.py
# İşlev: Telegram bot için interaktif kumanda paneli.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import sys
import time
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union, Set
from datetime import datetime, timedelta
import shutil
import threading
import traceback

import rich
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, TaskID

class InteractiveDashboard:
    """
    Rich kütüphanesi kullanarak bot ayarları için interaktif terminal arayüzü.
    """
    
    def __init__(self, services: Dict[str, Any], config: Any, user_db: Any):
        """
        Dashboard bileşenini başlatır.
        
        Args:
            services: Servis nesnelerini içeren sözlük
            config: Yapılandırma nesnesi
            user_db: Veritabanı nesnesi
        """
        self.services = services or {}  # Boş servislere izin ver
        self.config = config
        self.db = user_db
        self.console = Console()
        self.running = True
        self.current_menu = "main"
        self.menu_history = []
        
        # Servis durumunu kontrol et
        if not self.services:
            self.console.print("[yellow]⚠️ Uyarı: Hiçbir servis bulunamadı. Bazı özellikler çalışmayabilir.[/yellow]")
        
        # Menu tanımlamaları - (başlık, işlev) çiftleri
        self.menus = {
            "main": [
                ("Genel Ayarlar", self.general_settings),
                ("Mesaj Ayarları", self.message_settings),
                ("Grup Ayarları", self.group_settings),
                ("Davet Ayarları", self.invite_settings),
                ("Rate Limiter Ayarları", self.rate_limiter_settings),
                ("Veritabanı Ayarları", self.database_settings),
                ("Şablon Yöneticisi", self.template_manager),
                ("Servis Durumu", self.service_status),  # Bu satır güncellendi
                ("Ana Menüye Dön", self.main_menu),
                ("Çıkış", self.exit_dashboard),
            ],
            "general": [
                ("API Kimlik Ayarları", self.api_settings),
                ("Debug Modu", self.debug_settings),
                ("Log Ayarları", self.log_settings),
                ("Geri", self.go_back),
            ],
            "message": [
                ("Mesaj Aralığı Ayarla", self.set_message_interval),
                ("Mesaj Şablonlarını Yönet", self.manage_message_templates),
                ("Otomatik Yanıt Ayarları", self.response_settings),
                ("Geri", self.go_back),
            ],
            "group": [
                ("Grup Listesi Yönetimi", self.manage_groups),
                ("Hedef Gruplar", self.target_groups),
                ("Admin Grupları", self.admin_groups),
                ("Hatalı Grupları Sıfırla", self.reset_error_groups),
                ("Üye Toplama Ayarları", self.member_collection_settings),
                ("Geri", self.go_back),
            ],
            "invite": [
                ("Davet Şablonlarını Yönet", self.manage_invite_templates),
                ("Süper Kullanıcı Listesi", self.manage_super_users),
                ("Davet Gönderim Sıklığı", self.invite_frequency),
                ("Geri", self.go_back),
            ],
            "rate_limiter": [
                ("API Hız Limitleri", self.api_rate_limits),
                ("Bekleme Süreleri", self.wait_times),
                ("Hata Davranışları", self.error_behaviors),
                ("Geri", self.go_back),
            ],
            "database": [
                ("Veritabanı İstatistikleri", self.db_stats),
                ("Veritabanı Optimizasyonu", self.optimize_db),
                ("Veriyi Dışa Aktar", self.export_data),
                ("Yedekleme ve Geri Yükleme", self.backup_restore),
                ("Geri", self.go_back),
            ],
            "templates": [
                ("Mesaj Şablonları", lambda: self.template_editor("messages")),
                ("Davet Şablonları", lambda: self.template_editor("invites")),
                ("Yanıt Şablonları", lambda: self.template_editor("responses")),
                ("Geri", self.go_back),
            ],
        }

    # Ana çalışma döngüsü
    async def run(self):
        """Dashboard ana döngüsü"""
        try:
            while self.running:
                self.clear_screen()
                if self.current_menu == "main":
                    self.display_main_menu()
                else:
                    self.display_submenu(self.current_menu)
                
                choice = await asyncio.to_thread(
                    Prompt.ask, 
                    "[bold cyan]Seçiminiz[/bold cyan]", 
                    choices=[str(i+1) for i in range(len(self.menus[self.current_menu]))],
                    show_choices=False
                )
                
                # Seçimi işle
                choice_idx = int(choice) - 1
                if choice_idx >= 0 and choice_idx < len(self.menus[self.current_menu]):
                    # Seçilen menü öğesinin fonksiyonunu çağır
                    menu_func = self.menus[self.current_menu][choice_idx][1]
                    await asyncio.to_thread(menu_func)
                
                # Kısa bekleme
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            self.console.print("[yellow]Dashboard kapatılıyor...[/yellow]")
            return
        except Exception as e:
            self.console.print(f"[red]Dashboard hatası: {str(e)}[/red]")
            import traceback
            traceback.print_exc()
    
    # Yardımcı işlevler
    def clear_screen(self):
        """Terminal ekranını temizler"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_main_menu(self):
        """Ana menüyü gösterir"""
        self.console.print(Panel.fit(
            "[bold cyan]TELEGRAM BOT YÖNETİM PANELİ[/bold cyan]",
            border_style="cyan"
        ))
        
        self.console.print("\n[bold]Ana Menü[/bold]\n")
        
        for i, (title, _) in enumerate(self.menus["main"]):
            self.console.print(f"[green]{i+1}.[/green] {title}")
    
    def display_submenu(self, menu_key):
        """Alt menüleri gösterir"""
        title_map = {
            "general": "GENEL AYARLAR",
            "message": "MESAJ AYARLARI",
            "group": "GRUP AYARLARI",
            "invite": "DAVET AYARLARI",
            "rate_limiter": "RATE LIMITER AYARLARI",
            "database": "VERİTABANI AYARLARI",
            "templates": "ŞABLON YÖNETİCİSİ"
        }
        
        title = title_map.get(menu_key, "ALT MENÜ")
        
        self.console.print(Panel.fit(
            f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan"
        ))
        
        for i, (item_title, _) in enumerate(self.menus[menu_key]):
            self.console.print(f"[green]{i+1}.[/green] {item_title}")

    # Yönetim işlevleri
    def main_menu(self):
        """Ana menüye döner"""
        self.current_menu = "main"
        self.menu_history = []
    
    def go_back(self):
        """Önceki menüye döner"""
        if self.menu_history:
            self.current_menu = self.menu_history.pop()
        else:
            self.current_menu = "main"
    
    def exit_dashboard(self):
        """Dashboard'dan çıkar"""
        self.running = False

    # Yardımcı metotlar
    def _update_env_variable(self, key, value):
        """
        .env dosyasındaki bir değişkeni günceller
        """
        try:
            with open(".env", "r") as f:
                env_lines = f.readlines()
            
            key_exists = False
            updated_lines = []
            
            for line in env_lines:
                if line.startswith(f"{key}="):
                    updated_lines.append(f"{key}={value}\n")
                    key_exists = True
                else:
                    updated_lines.append(line)
            
            if not key_exists:
                updated_lines.append(f"{key}={value}\n")
            
            with open(".env", "w") as f:
                f.writelines(updated_lines)
            
            # Ayrıca mevcut ortam değişkenini de güncelle
            os.environ[key] = value
            
            return True
        except Exception as e:
            self.console.print(f"[red]Çevre değişkeni güncellenemedi: {str(e)}[/red]")
            return False

    # Alt menü yönlendirmeleri
    def general_settings(self):
        """Genel ayarlar menüsünü göster"""
        self.menu_history.append(self.current_menu)
        self.current_menu = "general"
    
    def message_settings(self):
        """Mesaj ayarları menüsünü göster"""
        self.menu_history.append(self.current_menu)
        self.current_menu = "message"
    
    def group_settings(self):
        """Grup ayarları menüsünü göster"""
        self.menu_history.append(self.current_menu)
        self.current_menu = "group"
    
    def invite_settings(self):
        """Davet ayarları menüsünü göster"""
        self.menu_history.append(self.current_menu)
        self.current_menu = "invite"
    
    def rate_limiter_settings(self):
        """Rate limiter ayarları menüsünü göster"""
        self.menu_history.append(self.current_menu)
        self.current_menu = "rate_limiter"
    
    def database_settings(self):
        """Veritabanı ayarları menüsünü göster"""
        self.menu_history.append(self.current_menu)
        self.current_menu = "database"
    
    def template_manager(self):
        """Şablon yöneticisi menüsünü göster"""
        self.menu_history.append(self.current_menu)
        self.current_menu = "templates"
    
    # Servis durumu ekranı
    async def service_status(self):
        """Servis durumlarını göster"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]SERVİS DURUM BİLGİLERİ[/bold cyan]",
            border_style="cyan"
        ))
        
        # Herhangi bir servis var mı kontrol et
        if not self.services:
            self.console.print("[yellow]⚠️ Hiçbir aktif servis bulunamadı.[/yellow]")
            self.console.print("[yellow]Servislerin başlatılması için botu yeniden başlatmanız gerekebilir.[/yellow]")
            Prompt.ask("\n[italic]Ana menüye dönmek için Enter tuşuna basın[/italic]")
            return
        
        table = Table(show_header=True, box=box.ROUNDED)
        table.add_column("Servis", style="cyan")
        table.add_column("Durum", style="green")
        table.add_column("İstatistikler", style="yellow")
        
        # DM servisi
        dm_service = self.services.get('dm')
        if dm_service:
            dm_status = "✅ ÇALIŞIYOR" if getattr(dm_service, "running", False) else "❌ DURDURULDU"
            dm_stats = f"Davet: {getattr(dm_service, 'invites_sent', 0)}"
            table.add_row("DM Servisi", dm_status, dm_stats)
        
        # Grup servisi
        group_service = self.services.get('group')
        if group_service:
            group_status = "✅ ÇALIŞIYOR" if getattr(group_service, "is_running", False) else "❌ DURDURULDU"
            group_stats = f"Mesajlar: {getattr(group_service, 'sent_count', 0)}"
            table.add_row("Grup Servisi", group_status, group_stats)
            
        # Yanıt servisi
        reply_service = self.services.get('reply')
        if reply_service:
            reply_status = "✅ ÇALIŞIYOR" if getattr(reply_service, "running", False) else "❌ DURDURULDU"
            reply_stats = f"Yanıtlar: {getattr(reply_service, 'reply_count', 0)}"
            table.add_row("Yanıt Servisi", reply_status, reply_stats)
            
        # Kullanıcı servisi
        user_service = self.services.get('user')
        if user_service:
            user_status = "✅ AKTİF" 
            user_stats = "VT yönetimi"
            table.add_row("Kullanıcı Servisi", user_status, user_stats)
        
        self.console.print(table)
        
        # Servis kontrolü
        self.console.print("\n[bold yellow]Servis Kontrolü[/bold yellow]")
        self.console.print("1. Tüm servisleri duraklat/devam ettir")
        self.console.print("2. DM servisini duraklat/devam ettir")
        self.console.print("3. Grup servisini duraklat/devam ettir")
        self.console.print("4. Yanıt servisini duraklat/devam ettir")
        self.console.print("5. Geri")
        
        choice = Prompt.ask("[bold cyan]Seçiminiz[/bold cyan]", choices=["1", "2", "3", "4", "5"])
        
        if choice == "1":
            all_paused = any(not getattr(s, "running", False) for s in self.services.values() if hasattr(s, "running"))
            for service_name, service in self.services.items():
                if hasattr(service, "running"):
                    service.running = all_paused
            status = "devam ettirildi" if all_paused else "duraklatıldı"
            self.console.print(f"[green]✅ Tüm servisler {status}[/green]")
        
        elif choice == "2" and 'dm' in self.services:
            self.services['dm'].running = not self.services['dm'].running
            status = "devam ettirildi" if self.services['dm'].running else "duraklatıldı"
            self.console.print(f"[green]✅ DM servisi {status}[/green]")
        
        elif choice == "3" and 'group' in self.services:
            self.services['group'].is_running = not self.services['group'].is_running
            status = "devam ettirildi" if self.services['group'].is_running else "duraklatıldı"
            self.console.print(f"[green]✅ Grup servisi {status}[/green]")
        
        elif choice == "4" and 'reply' in self.services:
            self.services['reply'].running = not self.services['reply'].running
            status = "devam ettirildi" if self.services['reply'].running else "duraklatıldı"
            self.console.print(f"[green]✅ Yanıt servisi {status}[/green]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")

        # service_status metoduna ek seçenek:

        self.console.print("[bold]İşlemler:[/bold]")
        self.console.print("1. Grupları keşfet")
        self.console.print("2. Servisleri yeniden başlat")
        self.console.print("3. Ana menüye dön")

        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3"])

        if choice == "1":
            self.console.print("[yellow]Gruplar keşfediliyor...[/yellow]")
            if hasattr(self.services.get('group', {}), 'discover_groups'):
                await self.services.get('group').discover_groups()
            elif hasattr(self.bot, 'discover_groups') and self.bot:
                await self.bot.discover_groups()
            else:
                self.console.print("[red]Grup keşif özelliği bulunamadı[/red]")

    #############################################
    # GENEL AYARLAR MODÜLÜ İMPLEMENTASYONLARI
    #############################################
    
    def api_settings(self):
        """API kimlik ayarlarını düzenler"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]API KİMLİK AYARLARI[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut değerleri göster
        api_id = os.getenv("API_ID", "Tanımsız")
        api_hash = os.getenv("API_HASH", "Tanımsız")
        phone = os.getenv("PHONE_NUMBER", "Tanımsız")
        
        self.console.print(f"[yellow]Mevcut API ID:[/yellow] {api_id}")
        self.console.print(f"[yellow]Mevcut API Hash:[/yellow] {'*' * len(api_hash) if api_hash != 'Tanımsız' else 'Tanımsız'}")
        self.console.print(f"[yellow]Mevcut Telefon:[/yellow] {phone}")
        
        # Değerleri değiştirme
        self.console.print("\n[bold]API Kimliklerini Değiştir[/bold]")
        self.console.print("[red]UYARI: Bu değerleri değiştirmek yeniden giriş yapılmasını gerektirebilir![/red]")
        
        change = Confirm.ask("API kimliklerini değiştirmek istiyor musunuz?")
        if change:
            # Değerleri iste
            new_api_id = Prompt.ask("Yeni API ID", default=api_id)
            new_api_hash = Prompt.ask("Yeni API Hash", default=api_hash)
            new_phone = Prompt.ask("Yeni Telefon Numarası", default=phone)
            
            # .env dosyasını güncelle
            self._update_env_variable("API_ID", new_api_id)
            self._update_env_variable("API_HASH", new_api_hash)
            self._update_env_variable("PHONE_NUMBER", new_phone)
            
            self.console.print("[green]✅ API kimlikleri güncellendi![/green]")
            self.console.print("[yellow]⚠️ Değişikliklerin etkili olması için uygulamayı yeniden başlatmanız gerekiyor.[/yellow]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Genel Ayarlar menüsüne dönmek için Enter tuşuna basın[/italic]")

    def debug_settings(self):
        """Debug modunu yapılandırır"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]DEBUG MODU AYARLARI[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut değeri göster
        debug_mode = os.getenv("DEBUG", "false").lower() == "true"
        status = "[green]AÇIK[/green]" if debug_mode else "[red]KAPALI[/red]"
        self.console.print(f"Debug modu şu anda: {status}")
        
        # Değiştirme seçeneği
        change = Confirm.ask("Debug modunu değiştirmek istiyor musunuz?")
        if change:
            new_debug = not debug_mode
            self._update_env_variable("DEBUG", str(new_debug).lower())
            new_status = "[green]AÇIK[/green]" if new_debug else "[red]KAPALI[/red]"
            self.console.print(f"Debug modu şimdi: {new_status}")
            self.console.print("[yellow]⚠️ Değişikliğin tamamen etkili olması için uygulamayı yeniden başlatmanız önerilir.[/yellow]")
        
        # Ek debug seçenekleri
        self.console.print("\n[bold]Ek Debug Seçenekleri[/bold]")
        self.console.print("1. Log seviyesini değiştir")
        self.console.print("2. Konsol çıktı ayrıntı seviyesini değiştir")
        self.console.print("3. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3"], default="3")
        
        if choice == "1":
            levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            current_level = os.getenv("LOG_LEVEL", "INFO")
            level_table = Table(show_header=True, box=box.SIMPLE)
            level_table.add_column("Seviye", style="cyan")
            level_table.add_column("Açıklama", style="green")
            
            level_table.add_row("DEBUG", "En ayrıntılı loglama - geliştirme için")
            level_table.add_row("INFO", "Standart bilgi mesajları")
            level_table.add_row("WARNING", "Sadece uyarılar ve hatalar")
            level_table.add_row("ERROR", "Sadece hatalar")
            level_table.add_row("CRITICAL", "Sadece kritik hatalar")
            
            self.console.print(level_table)
            self.console.print(f"Mevcut log seviyesi: [yellow]{current_level}[/yellow]")
            
            new_level = Prompt.ask(
                "Yeni log seviyesi", 
                choices=levels,
                default=current_level
            )
            
            self._update_env_variable("LOG_LEVEL", new_level)
            self.console.print(f"[green]✅ Log seviyesi {new_level} olarak ayarlandı[/green]")
        
        elif choice == "2":
            verbose = os.getenv("VERBOSE", "false").lower() == "true"
            status = "[green]AÇIK[/green]" if verbose else "[red]KAPALI[/red]"
            self.console.print(f"Ayrıntılı konsol çıktısı şu anda: {status}")
            
            new_verbose = not verbose
            self._update_env_variable("VERBOSE", str(new_verbose).lower())
            new_status = "[green]AÇIK[/green]" if new_verbose else "[red]KAPALI[/red]"
            self.console.print(f"Ayrıntılı konsol çıktısı şimdi: {new_status}")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Genel Ayarlar menüsüne dönmek için Enter tuşuna basın[/italic]")

    def log_settings(self):
        """Log ayarlarını yapılandırır"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]LOG AYARLARI[/bold cyan]",
            border_style="cyan"
        ))
        
        # Log dosyası konumları
        log_dir = os.getenv("LOG_DIR", "logs")
        log_file = os.getenv("LOG_FILE", "app.log")
        log_path = os.path.join(log_dir, log_file)
        
        self.console.print(f"Log dosyası: [cyan]{log_path}[/cyan]")
        
        # Log dosyası var mı kontrol et
        if os.path.exists(log_path):
            size_mb = round(os.path.getsize(log_path) / (1024 * 1024), 2)
            mod_time = time.ctime(os.path.getmtime(log_path))
            self.console.print(f"Dosya boyutu: [yellow]{size_mb} MB[/yellow]")
            self.console.print(f"Son değişiklik: [yellow]{mod_time}[/yellow]")
            
            # Son 5 log satırını göster
            self.console.print("\n[bold]Son Log Mesajları:[/bold]")
            try:
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                    last_lines = lines[-5:] if len(lines) > 5 else lines
                    for line in last_lines:
                        if "ERROR" in line or "CRITICAL" in line:
                            self.console.print(f"[red]{line.strip()}[/red]")
                        elif "WARNING" in line:
                            self.console.print(f"[yellow]{line.strip()}[/yellow]")
                        else:
                            self.console.print(line.strip())
            except Exception as e:
                self.console.print(f"[red]Log dosyası okunamadı: {e}[/red]")
        else:
            self.console.print("[yellow]Log dosyası henüz oluşturulmamış.[/yellow]")
        
        # Log ayarları
        self.console.print("\n[bold]Log Ayarları:[/bold]")
        self.console.print("1. Log dosyasını temizle")
        self.console.print("2. Log dosyası konumunu değiştir")
        self.console.print("3. Log döndürme ayarları")
        self.console.print("4. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1":
            confirm = Confirm.ask("[red]DİKKAT:[/red] Log dosyasını temizlemek istediğinize emin misiniz?")
            if confirm:
                try:
                    open(log_path, 'w').close()
                    self.console.print("[green]✅ Log dosyası temizlendi[/green]")
                except Exception as e:
                    self.console.print(f"[red]Log dosyası temizlenemedi: {e}[/red]")
        
        elif choice == "2":
            new_dir = Prompt.ask("Yeni log dizini", default=log_dir)
            new_file = Prompt.ask("Yeni log dosya adı", default=log_file)
            
            os.makedirs(new_dir, exist_ok=True)
            self._update_env_variable("LOG_DIR", new_dir)
            self._update_env_variable("LOG_FILE", new_file)
            self.console.print(f"[green]✅ Log konumu güncellendi: {os.path.join(new_dir, new_file)}[/green]")
        
        elif choice == "3":
            max_size = os.getenv("LOG_MAX_SIZE", "10")
            backup_count = os.getenv("LOG_BACKUP_COUNT", "3")
            
            self.console.print(f"Mevcut maksimum log dosya boyutu: [yellow]{max_size} MB[/yellow]")
            self.console.print(f"Mevcut yedek log sayısı: [yellow]{backup_count}[/yellow]")
            
            new_size = Prompt.ask("Yeni maksimum log boyutu (MB)", default=max_size)
            new_count = Prompt.ask("Yeni yedek log sayısı", default=backup_count)
            
            self._update_env_variable("LOG_MAX_SIZE", new_size)
            self._update_env_variable("LOG_BACKUP_COUNT", new_count)
            self.console.print("[green]✅ Log döndürme ayarları güncellendi[/green]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Genel Ayarlar menüsüne dönmek için Enter tuşuna basın[/italic]")

    def set_message_interval(self):
        """Mesaj gönderme aralıklarını ayarlar"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]MESAJ GÖNDERME ARALIĞI AYARLARI[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut değerleri göster
        min_interval = int(os.getenv("MIN_MESSAGE_INTERVAL", "300"))  # 5 dakika
        max_interval = int(os.getenv("MAX_MESSAGE_INTERVAL", "600"))  # 10 dakika
        
        self.console.print(f"Minimum mesaj aralığı: [yellow]{min_interval} saniye[/yellow] ({min_interval//60} dakika)")
        self.console.print(f"Maksimum mesaj aralığı: [yellow]{max_interval} saniye[/yellow] ({max_interval//60} dakika)")
        
        # Random aralık açıklaması
        self.console.print("\n[italic]Bot her mesaj gönderiminden sonra minimum ve maksimum değer arasında rastgele bir süre bekler.[/italic]")
        self.console.print("[italic]Bu, botun daha doğal görünmesini ve hız sınırı hatalarından kaçınmasını sağlar.[/italic]")
        
        # Değişiklik yapmak ister misiniz?
        change = Confirm.ask("\nMesaj aralıklarını değiştirmek istiyor musunuz?")
        if change:
            # Değerleri dakika cinsinden al, saniyeye çevir
            new_min = IntPrompt.ask("Yeni minimum mesaj aralığı (dakika)", default=min_interval//60)
            new_max = IntPrompt.ask("Yeni maksimum mesaj aralığı (dakika)", default=max_interval//60)
            
            # Saniyeye çevir
            new_min_sec = new_min * 60
            new_max_sec = new_max * 60
            
            # Kontrol et: min < max
            if new_min_sec >= new_max_sec:
                self.console.print("[red]Hata: Minimum aralık maksimumdan küçük olmalıdır![/red]")
            else:
                self._update_env_variable("MIN_MESSAGE_INTERVAL", str(new_min_sec))
                self._update_env_variable("MAX_MESSAGE_INTERVAL", str(new_max_sec))
                self.console.print(f"[green]✅ Mesaj aralıkları güncellendi: {new_min} - {new_max} dakika[/green]")
                
                # Servisi yeniden başlatma önerisi
                if 'group' in self.services:
                    restart = Confirm.ask("Değişiklikleri hemen uygulamak için grup servisini yeniden başlatmak ister misiniz?")
                    if restart:
                        # Servisin reset metodunu çağır (varsa)
                        if hasattr(self.services['group'], 'reset_intervals'):
                            self.services['group'].reset_intervals(new_min_sec, new_max_sec)
                            self.console.print("[green]✅ Grup servisi yeni aralıklarla güncellendi[/green]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Mesaj Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    def manage_message_templates(self):
        """Mesaj şablonlarını yönetir"""
        # Bu metot template_editor metoduna yönlendirsin
        self.template_editor("messages")

    def response_settings(self):
        """Otomatik yanıt ayarlarını yapılandırır"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]OTOMATİK YANIT AYARLARI[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut ayarları göster
        active = os.getenv("AUTO_REPLY_ENABLED", "true").lower() == "true"
        chance = int(os.getenv("REPLY_CHANCE", "30"))
        cooldown = int(os.getenv("REPLY_COOLDOWN", "60"))
        
        status = "[green]AÇIK[/green]" if active else "[red]KAPALI[/red]"
        self.console.print(f"Otomatik yanıtlar: {status}")
        self.console.print(f"Yanıt verme olasılığı: [yellow]%{chance}[/yellow]")
        self.console.print(f"Yanıt bekleme süresi: [yellow]{cooldown}[/yellow] saniye")
        
        # Ayar seçenekleri
        self.console.print("\n[bold]Yanıt Ayarları:[/bold]")
        self.console.print(f"1. Otomatik yanıtları {'kapat' if active else 'aç'}")
        self.console.print("2. Yanıt olasılığını değiştir")
        self.console.print("3. Bekleme süresini değiştir")
        self.console.print("4. Yanıt şablonlarını düzenle")
        self.console.print("5. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="5")
        
        if choice == "1":
            new_status = not active
            self._update_env_variable("AUTO_REPLY_ENABLED", str(new_status).lower())
            
            if 'reply' in self.services and hasattr(self.services['reply'], 'enabled'):
                self.services['reply'].enabled = new_status
                
            new_text = "açıldı" if new_status else "kapatıldı"
            self.console.print(f"[green]✅ Otomatik yanıtlar {new_text}[/green]")
            
        elif choice == "2":
            # Yanıt olasılığını değiştir
            new_chance = IntPrompt.ask(
                "Yanıt verme olasılığı (%)", 
                default=chance,
                min_value=0,
                max_value=100
            )
            
            self._update_env_variable("REPLY_CHANCE", str(new_chance))
            
            if 'reply' in self.services and hasattr(self.services['reply'], 'reply_chance'):
                self.services['reply'].reply_chance = new_chance
                
            self.console.print(f"[green]✅ Yanıt olasılığı %{new_chance} olarak ayarlandı[/green]")
            
        elif choice == "3":
            # Bekleme süresini değiştir
            new_cooldown = IntPrompt.ask(
                "Yanıt bekleme süresi (saniye)", 
                default=cooldown,
                min_value=5
            )
            
            self._update_env_variable("REPLY_COOLDOWN", str(new_cooldown))
            
            if 'reply' in self.services and hasattr(self.services['reply'], 'cooldown'):
                self.services['reply'].cooldown = new_cooldown
                
            self.console.print(f"[green]✅ Bekleme süresi {new_cooldown} saniye olarak ayarlandı[/green]")
            
        elif choice == "4":
            # Şablon düzenleyici
            self.template_editor("responses")
            return  # Tekrar bu menüye dönmesin
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Mesaj Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    #############################################
    # GRUP AYARLARI MODÜLÜ İMPLEMENTASYONLARI
    #############################################
    
    def manage_groups(self):
        """Genel grup ayarlarını yönetir"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]GRUP YÖNETİMİ[/bold cyan]",
            border_style="cyan"
        ))
        
        # Alt seçenekler
        self.console.print("\n[bold]Grup Yönetimi Seçenekleri:[/bold]")
        self.console.print("1. Hedef grupları yönet")
        self.console.print("2. Admin gruplarını yönet")
        self.console.print("3. Hata veren grupları sıfırla")
        self.console.print("4. Üye toplama ayarları")
        self.console.print("5. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="5")
        
        if choice == "1":
            self.target_groups()
        elif choice == "2":
            self.admin_groups()
        elif choice == "3":
            self.reset_error_groups()
        elif choice == "4":
            self.member_collection_settings()
            
        # Kullanıcının devam etmesi için bekle
        if choice != "5":
            Prompt.ask("\n[italic]Grup Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    def target_groups(self):
        """Hedef grupları yönetir"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]HEDEF GRUPLAR[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut grupları göster
        groups = os.getenv("GROUP_LINKS", "").split(",")
        groups = [g.strip() for g in groups if g.strip()]
        
        if groups:
            self.console.print(f"[bold]Toplam {len(groups)} hedef grup:[/bold]\n")
            
            # Tablo olarak göster
            table = Table(show_header=True, box=box.SIMPLE)
            table.add_column("No", style="cyan", width=4)
            table.add_column("Grup Linki/ID", style="green")
            
            for i, group in enumerate(groups):
                table.add_row(str(i+1), group)
                
            self.console.print(table)
        else:
            self.console.print("[yellow]Henüz hedef grup tanımlanmamış.[/yellow]")
        
        # İşlem menüsü
        self.console.print("\n[bold]İşlemler:[/bold]")
        self.console.print("1. Grup ekle")
        self.console.print("2. Grup sil")
        self.console.print("3. Gruptaki üyeleri kontrol et")
        self.console.print("4. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1":
            # Grup ekle
            new_group = Prompt.ask("Eklenecek grup linki veya ID (ör: https://t.me/grupadi veya -100123456789)")
            if new_group:
                # Grup URL'ini temizle ve standartlaştır
                if "t.me/" in new_group:
                    parts = new_group.split("t.me/")
                    new_group = "https://t.me/" + parts[-1]
                
                if new_group not in groups:
                    groups.append(new_group)
                    self._update_env_variable("GROUP_LINKS", ",".join(groups))
                    self.console.print(f"[green]✅ Grup eklendi: {new_group}[/green]")
                else:
                    self.console.print("[yellow]Bu grup zaten listede var![/yellow]")
                    
        elif choice == "2" and groups:
            # Grup sil
            idx = IntPrompt.ask(
                "Silmek istediğiniz grubun numarası", 
                min_value=1, 
                max_value=len(groups)
            )
            
            removed = groups.pop(idx-1)
            self._update_env_variable("GROUP_LINKS", ",".join(groups))
            self.console.print(f"[green]✅ Grup silindi: {removed}[/green]")
            
        elif choice == "3" and groups:
            # Gruptaki üye sayısını kontrol et
            if 'group' not in self.services or not hasattr(self.services['group'], 'client'):
                self.console.print("[red]❌ Bu işlem şu anda yapılamıyor. Bot bağlantısı yok.[/red]")
            else:
                idx = IntPrompt.ask(
                    "Kontrol etmek istediğiniz grubun numarası", 
                    min_value=1, 
                    max_value=len(groups)
                )
                
                target = groups[idx-1]
                self.console.print(f"[yellow]Grup kontrol ediliyor: {target}...[/yellow]")
                
                # Bu kısımda gerçek üye sayısını kontrol etmek için asenkron bir işlem gerekiyor
                # Bu örnek kodda sadece bir bilgi mesajı gösteriyoruz
                self.console.print("[green]Bu grup için API üzerinden üye bilgisi alınabilir.[/green]")
                self.console.print("[yellow]Bu özellik production kodunda implementasyonu gerektirir.[/yellow]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Grup Yönetimi menüsüne dönmek için Enter tuşuna basın[/italic]")

    def admin_groups(self):
        """Admin gruplarını yönetir"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]ADMİN GRUPLARI[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut admin gruplarını göster
        admin_groups = os.getenv("ADMIN_GROUP_LINKS", "").split(",")
        admin_groups = [g.strip() for g in admin_groups if g.strip()]
        
        if admin_groups:
            self.console.print(f"[bold]Toplam {len(admin_groups)} admin grubu:[/bold]\n")
            
            # Tablo olarak göster
            table = Table(show_header=True, box=box.SIMPLE)
            table.add_column("No", style="cyan", width=4)
            table.add_column("Grup Linki/ID", style="green")
            
            for i, group in enumerate(admin_groups):
                table.add_row(str(i+1), group)
                
            self.console.print(table)
        else:
            self.console.print("[yellow]Henüz admin grubu tanımlanmamış.[/yellow]")
        
        # İşlem menüsü
        self.console.print("\n[bold]İşlemler:[/bold]")
        self.console.print("1. Admin grubu ekle")
        self.console.print("2. Admin grubu sil")
        self.console.print("3. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3"], default="3")
        
        if choice == "1":
            # Grup ekle
            new_group = Prompt.ask("Eklenecek admin grubu linki veya ID")
            if new_group:
                # Grup URL'ini temizle ve standartlaştır
                if "t.me/" in new_group:
                    parts = new_group.split("t.me/")
                    new_group = "https://t.me/" + parts[-1]
                
                if new_group not in admin_groups:
                    admin_groups.append(new_group)
                    self._update_env_variable("ADMIN_GROUP_LINKS", ",".join(admin_groups))
                    self.console.print(f"[green]✅ Admin grubu eklendi: {new_group}[/green]")
                else:
                    self.console.print("[yellow]Bu grup zaten admin listesinde var![/yellow]")
                    
        elif choice == "2" and admin_groups:
            # Grup sil
            idx = IntPrompt.ask(
                "Silmek istediğiniz admin grubunun numarası", 
                min_value=1, 
                max_value=len(admin_groups)
            )
            
            removed = admin_groups.pop(idx-1)
            self._update_env_variable("ADMIN_GROUP_LINKS", ",".join(admin_groups))
            self.console.print(f"[green]✅ Admin grubu silindi: {removed}[/green]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Grup Yönetimi menüsüne dönmek için Enter tuşuna basın[/italic]")

    def reset_error_groups(self):
        """Hata veren grupları sıfırlar"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]HATA VEREN GRUPLARI SIFIRLAMA[/bold cyan]",
            border_style="cyan"
        ))
        
        # Hata veren grupları kontrol et
        error_groups = []
        
        # Grup servisini kontrol et ve hata veren grupları al
        if 'group' in self.services and hasattr(self.services['group'], 'error_groups'):
            error_groups = self.services['group'].error_groups
        
        if error_groups:
            self.console.print(f"[bold red]Toplam {len(error_groups)} hata veren grup bulundu:[/bold red]\n")
            
            # Tablo olarak göster
            table = Table(show_header=True, box=box.SIMPLE)
            table.add_column("No", style="cyan", width=4)
            table.add_column("Grup ID/Link", style="red")
            table.add_column("Hata Sayısı", style="yellow")
            
            for i, group_data in enumerate(error_groups):
                # Basit bir liste ise
                if isinstance(group_data, str):
                    table.add_row(str(i+1), group_data, "Bilinmiyor")
                # Dict ise
                elif isinstance(group_data, dict):
                    group_id = group_data.get('id', 'Bilinmiyor')
                    error_count = str(group_data.get('error_count', 'Bilinmiyor'))
                    table.add_row(str(i+1), str(group_id), error_count)
                
            self.console.print(table)
            
            # Reset seçeneği
            reset = Confirm.ask("[red]Hata veren gruplar listesini sıfırlamak istediğinize emin misiniz?[/red]")
            if reset:
                # Grup servisindeki hata gruplarını sıfırla
                if 'group' in self.services and hasattr(self.services['group'], 'error_groups'):
                    self.services['group'].error_groups = []
                    self.console.print("[green]✅ Hata veren gruplar listesi sıfırlandı![/green]")
                else:
                    self.console.print("[red]❌ Hata listesi sıfırlanamadı.[/red]")
        else:
            self.console.print("[green]✓ Şu anda hata veren grup bulunmuyor.[/green]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Grup Yönetimi menüsüne dönmek için Enter tuşuna basın[/italic]")

    def member_collection_settings(self):
        """Üye toplama ayarlarını yapılandırır"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]ÜYE TOPLAMA AYARLARI[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut ayarları göster
        collect_enabled = os.getenv("COLLECT_MEMBERS", "false").lower() == "true"
        collect_interval = int(os.getenv("COLLECT_INTERVAL", "3600"))  # 1 saat
        max_members = int(os.getenv("MAX_MEMBERS_PER_GROUP", "500"))
        
        status = "[green]AÇIK[/green]" if collect_enabled else "[red]KAPALI[/red]"
        self.console.print(f"Üye toplama: {status}")
        self.console.print(f"Toplama aralığı: [yellow]{collect_interval}[/yellow] saniye ({collect_interval//60} dakika)")
        self.console.print(f"Grup başına maksimum üye: [yellow]{max_members}[/yellow]")
        
        if 'user' in self.services and hasattr(self.services['user'], 'get_user_count'):
            try:
                user_count = self.services['user'].get_user_count()
                self.console.print(f"Toplam kayıtlı kullanıcı sayısı: [cyan]{user_count}[/cyan]")
            except:
                pass
        
        # Ayar seçenekleri
        self.console.print("\n[bold]Üye Toplama Ayarları:[/bold]")
        self.console.print(f"1. Üye toplamayı {'kapat' if collect_enabled else 'aç'}")
        self.console.print("2. Toplama aralığını değiştir")
        self.console.print("3. Maksimum üye sayısını değiştir")
        self.console.print("4. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1":
            new_status = not collect_enabled
            self._update_env_variable("COLLECT_MEMBERS", str(new_status).lower())
            
            if 'member_collector' in self.services and hasattr(self.services['member_collector'], 'enabled'):
                self.services['member_collector'].enabled = new_status
                
            new_text = "açıldı" if new_status else "kapatıldı"
            self.console.print(f"[green]✅ Üye toplama {new_text}[/green]")
            
        elif choice == "2":
            # Toplama aralığı
            min_val = 10 if collect_enabled else 30
            new_interval_min = IntPrompt.ask(
                "Yeni toplama aralığı (dakika)", 
                default=collect_interval//60,
                min_value=min_val
            )
            
            new_interval_sec = new_interval_min * 60
            self._update_env_variable("COLLECT_INTERVAL", str(new_interval_sec))
            
            if 'member_collector' in self.services and hasattr(self.services['member_collector'], 'interval'):
                self.services['member_collector'].interval = new_interval_sec
                
            self.console.print(f"[green]✅ Toplama aralığı {new_interval_min} dakika olarak ayarlandı[/green]")
            
        elif choice == "3":
            # Maksimum üye
            new_max = IntPrompt.ask(
                "Grup başına maksimum üye", 
                default=max_members,
                min_value=10,
                max_value=5000
            )
            
            self._update_env_variable("MAX_MEMBERS_PER_GROUP", str(new_max))
            
            if 'member_collector' in self.services and hasattr(self.services['member_collector'], 'max_members'):
                self.services['member_collector'].max_members = new_max
                
            self.console.print(f"[green]✅ Maksimum üye sayısı {new_max} olarak ayarlandı[/green]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Grup Yönetimi menüsüne dönmek için Enter tuşuna basın[/italic]")

    #############################################
    # DAVET AYARLARI MODÜLÜ İMPLEMENTASYONLARI
    #############################################

    def manage_invite_templates(self):
        """Davet şablonlarını yönetir"""
        # Şablon düzenleyicisini çağır
        self.template_editor("invites")

    def manage_super_users(self):
        """Süper kullanıcıları yönetir"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]SÜPER KULLANICI YÖNETİMİ[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut süper kullanıcıları al
        super_users = os.getenv("SUPER_USERS", "").split(",")
        super_users = [user.strip() for user in super_users if user.strip()]
        
        if super_users:
            self.console.print(f"[bold]Toplam {len(super_users)} süper kullanıcı:[/bold]\n")
            
            # Tablo olarak göster
            table = Table(show_header=True, box=box.SIMPLE)
            table.add_column("No", style="cyan", width=4)
            table.add_column("Kullanıcı ID", style="green")
            
            for i, user in enumerate(super_users):
                table.add_row(str(i+1), user)
                
            self.console.print(table)
        else:
            self.console.print("[yellow]Henüz süper kullanıcı tanımlanmamış.[/yellow]")
        
        # İşlem menüsü
        self.console.print("\n[bold]İşlemler:[/bold]")
        self.console.print("1. Kullanıcı ekle")
        self.console.print("2. Kullanıcı sil")
        self.console.print("3. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3"], default="3")
        
        if choice == "1":
            # Kullanıcı ekle
            new_user = Prompt.ask("Eklenecek kullanıcı ID (sayı olmalı)")
            if new_user.isdigit():
                if new_user not in super_users:
                    super_users.append(new_user)
                    self._update_env_variable("SUPER_USERS", ",".join(super_users))
                    self.console.print(f"[green]✅ Süper kullanıcı eklendi: {new_user}[/green]")
                else:
                    self.console.print("[yellow]Bu kullanıcı zaten süper kullanıcı listesinde![/yellow]")
            else:
                self.console.print("[red]❌ Geçersiz kullanıcı ID. Sadece sayı girebilirsiniz.[/red]")
                
        elif choice == "2" and super_users:
            # Kullanıcı sil
            idx = IntPrompt.ask(
                "Silmek istediğiniz kullanıcının numarası", 
                min_value=1, 
                max_value=len(super_users)
            )
            
            removed = super_users.pop(idx-1)
            self._update_env_variable("SUPER_USERS", ",".join(super_users))
            self.console.print(f"[green]✅ Süper kullanıcı silindi: {removed}[/green]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Davet Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    def invite_frequency(self):
        """Davet gönderim sıklığını ayarlar"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]DAVET GÖNDERİM SIKLIĞI[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut değerleri göster
        min_interval = int(os.getenv("MIN_INVITE_INTERVAL", "300"))  # 5 dakika
        max_interval = int(os.getenv("MAX_INVITE_INTERVAL", "900"))  # 15 dakika
        daily_limit = int(os.getenv("DAILY_INVITE_LIMIT", "50"))     # Günlük limit
        
        self.console.print(f"Minimum davet aralığı: [yellow]{min_interval} saniye[/yellow] ({min_interval//60} dakika)")
        self.console.print(f"Maksimum davet aralığı: [yellow]{max_interval} saniye[/yellow] ({max_interval//60} dakika)")
        self.console.print(f"Günlük davet limiti: [yellow]{daily_limit}[/yellow]")
        
        # Random aralık açıklaması
        self.console.print("\n[italic]Bot her davet gönderiminden sonra minimum ve maksimum değer arasında rastgele bir süre bekler.[/italic]")
        
        # Değişiklik yapmak ister misiniz?
        self.console.print("\n[bold]Davet Ayarları:[/bold]")
        self.console.print("1. Aralık ayarlarını değiştir")
        self.console.print("2. Günlük limiti değiştir")
        self.console.print("3. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3"], default="3")
        
        if choice == "1":
            # Aralığı değiştir
            new_min = IntPrompt.ask("Yeni minimum davet aralığı (dakika)", default=min_interval//60)
            new_max = IntPrompt.ask("Yeni maksimum davet aralığı (dakika)", default=max_interval//60)
            
            # Saniyeye çevir
            new_min_sec = new_min * 60
            new_max_sec = new_max * 60
            
            # Kontrol et: min < max
            if new_min_sec >= new_max_sec:
                self.console.print("[red]Hata: Minimum aralık maksimumdan küçük olmalıdır![/red]")
            else:
                self._update_env_variable("MIN_INVITE_INTERVAL", str(new_min_sec))
                self._update_env_variable("MAX_INVITE_INTERVAL", str(new_max_sec))
                self.console.print(f"[green]✅ Davet aralıkları güncellendi: {new_min} - {new_max} dakika[/green]")
                
                # DM servisini güncelle
                if 'dm' in self.services:
                    if hasattr(self.services['dm'], 'min_interval'):
                        self.services['dm'].min_interval = new_min_sec
                    if hasattr(self.services['dm'], 'max_interval'):
                        self.services['dm'].max_interval = new_max_sec
                    self.console.print("[green]✅ DM servisi güncellendi[/green]")
                
        elif choice == "2":
            # Günlük limiti değiştir
            new_limit = IntPrompt.ask(
                "Yeni günlük davet limiti", 
                default=daily_limit,
                min_value=5,
                max_value=200
            )
            
            self._update_env_variable("DAILY_INVITE_LIMIT", str(new_limit))
            
            if 'dm' in self.services and hasattr(self.services['dm'], 'daily_limit'):
                self.services['dm'].daily_limit = new_limit
                
            self.console.print(f"[green]✅ Günlük davet limiti {new_limit} olarak ayarlandı[/green]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Davet Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    #############################################
    # RATE LIMITER AYARLARI MODÜLÜ İMPLEMENTASYONLARI
    #############################################

    def api_rate_limits(self):
        """API hız limitlerini yönetir"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]API HIZ LİMİTLERİ[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut değerleri göster
        message_limit = int(os.getenv("MESSAGE_RATE_LIMIT", "20"))
        dm_limit = int(os.getenv("DM_RATE_LIMIT", "5"))
        join_limit = int(os.getenv("JOIN_RATE_LIMIT", "10"))
        
        # Tablo oluştur
        table = Table(show_header=True, box=box.SIMPLE)
        table.add_column("İşlem", style="cyan")
        table.add_column("Limit (dk başına)", style="yellow", justify="right")
        
        table.add_row("Mesaj gönderme", str(message_limit))
        table.add_row("DM gönderme", str(dm_limit))
        table.add_row("Gruba katılma", str(join_limit))
        
        self.console.print(table)
        
        # Açıklama
        self.console.print("\n[italic]Bu limitler, Telegram API kısıtlamalarını aşmamak için belirlenen maksimum işlem sayısıdır.[/italic]")
        self.console.print("[italic]Bot bu limitleri aşarsa, flood wait hataları alabilir ve geçici olarak engellenebilir.[/italic]")
        
        # Değişiklik seçenekleri
        self.console.print("\n[bold]API Hız Limitleri:[/bold]")
        self.console.print("1. Mesaj gönderme limitini değiştir")
        self.console.print("2. DM gönderme limitini değiştir")
        self.console.print("3. Gruba katılma limitini değiştir")
        self.console.print("4. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1":
            # Mesaj limitini değiştir
            new_limit = IntPrompt.ask(
                "Yeni mesaj gönderme limiti (dakika başına)", 
                default=message_limit,
                min_value=5,
                max_value=100
            )
            
            self._update_env_variable("MESSAGE_RATE_LIMIT", str(new_limit))
            
            # Servisleri güncelle
            if 'rate_limiter' in self.services and hasattr(self.services['rate_limiter'], 'message_limit'):
                self.services['rate_limiter'].message_limit = new_limit
                
            self.console.print(f"[green]✅ Mesaj gönderme limiti dakika başına {new_limit} olarak ayarlandı[/green]")
            
        elif choice == "2":
            # DM limitini değiştir
            new_limit = IntPrompt.ask(
                "Yeni DM gönderme limiti (dakika başına)", 
                default=dm_limit,
                min_value=1,
                max_value=30
            )
            
            self._update_env_variable("DM_RATE_LIMIT", str(new_limit))
            
            # Servisleri güncelle
            if 'rate_limiter' in self.services and hasattr(self.services['rate_limiter'], 'dm_limit'):
                self.services['rate_limiter'].dm_limit = new_limit
                
            self.console.print(f"[green]✅ DM gönderme limiti dakika başına {new_limit} olarak ayarlandı[/green]")
            
        elif choice == "3":
            # Katılma limitini değiştir
            new_limit = IntPrompt.ask(
                "Yeni gruba katılma limiti (dakika başına)", 
                default=join_limit,
                min_value=1,
                max_value=20
            )
            
            self._update_env_variable("JOIN_RATE_LIMIT", str(new_limit))
            
            # Servisleri güncelle
            if 'rate_limiter' in self.services and hasattr(self.services['rate_limiter'], 'join_limit'):
                self.services['rate_limiter'].join_limit = new_limit
                
            self.console.print(f"[green]✅ Gruba katılma limiti dakika başına {new_limit} olarak ayarlandı[/green]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Rate Limiter Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    def wait_times(self):
        """Bekleme sürelerini yapılandırır"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]BEKLEME SÜRELERİ[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut değerleri göster
        error_wait = int(os.getenv("ERROR_WAIT_TIME", "300"))  # Hata sonrası 5 dk bekle
        flood_wait = float(os.getenv("FLOOD_WAIT_MULTIPLIER", "1.5"))  # Flood beklemesi çarpanı
        
        self.console.print(f"Hata sonrası bekleme: [yellow]{error_wait}[/yellow] saniye ({error_wait//60} dakika)")
        self.console.print(f"Flood wait çarpanı: [yellow]{flood_wait}x[/yellow]")
        
        # Açıklama
        self.console.print("\n[italic]Hata sonrası bekleme süresi, API hatası alındığında tekrar denemeden önce beklenecek süredir.[/italic]")
        self.console.print("[italic]Flood wait çarpanı, Telegram'ın belirttiği bekleme süresini bu değerle çarparak uzatır.[/italic]")
        
        # Değişiklik seçenekleri
        self.console.print("\n[bold]Bekleme Süreleri:[/bold]")
        self.console.print("1. Hata sonrası bekleme süresini değiştir")
        self.console.print("2. Flood wait çarpanını değiştir")
        self.console.print("3. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3"], default="3")
        
        if choice == "1":
            # Hata beklemesi
            new_wait = IntPrompt.ask(
                "Yeni hata bekleme süresi (saniye)", 
                default=error_wait,
                min_value=10,
                max_value=3600
            )
            
            self._update_env_variable("ERROR_WAIT_TIME", str(new_wait))
            
            # Servisleri güncelle
            for service_name, service in self.services.items():
                if hasattr(service, 'error_wait_time'):
                    service.error_wait_time = new_wait
                    
                    service.error_wait_time = new_wait
                    
            self.console.print(f"[green]✅ Hata bekleme süresi {new_wait} saniye olarak ayarlandı[/green]")
            
        elif choice == "2":
            # Flood çarpanı
            new_multiplier = float(Prompt.ask(
                "Yeni flood wait çarpanı (örn: 1.5)", 
                default=str(flood_wait)
            ))
            
            if new_multiplier < 1.0:
                self.console.print("[yellow]⚠️ 1.0'dan küçük değerler önerilmez ve Telegram tarafından engellemeye yol açabilir![/yellow]")
                if not Confirm.ask("Yine de devam etmek istiyor musunuz?"):
                    return
                    
            self._update_env_variable("FLOOD_WAIT_MULTIPLIER", str(new_multiplier))
            
            # Servisleri güncelle
            if 'rate_limiter' in self.services and hasattr(self.services['rate_limiter'], 'flood_wait_multiplier'):
                self.services['rate_limiter'].flood_wait_multiplier = new_multiplier
                
            self.console.print(f"[green]✅ Flood wait çarpanı {new_multiplier}x olarak ayarlandı[/green]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Rate Limiter Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    def error_behaviors(self):
        """Hata davranışlarını yapılandırır"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]HATA DAVRANIŞLARI[/bold cyan]",
            border_style="cyan"
        ))
        
        # Mevcut değerleri göster
        retry_count = int(os.getenv("MAX_RETRIES", "3"))
        notify_errors = os.getenv("NOTIFY_ERRORS", "true").lower() == "true"
        auto_restart = os.getenv("AUTO_RESTART_ON_ERROR", "false").lower() == "true"
        
        self.console.print(f"Maksimum deneme sayısı: [yellow]{retry_count}[/yellow]")
        self.console.print(f"Hata bildirimi: {'[green]AÇIK[/green]' if notify_errors else '[red]KAPALI[/red]'}")
        self.console.print(f"Otomatik yeniden başlatma: {'[green]AÇIK[/green]' if auto_restart else '[red]KAPALI[/red]'}")
        
        # Açıklama
        self.console.print("\n[italic]Maksimum deneme sayısı, bir işlem başarısız olduğunda kaç kez tekrar deneneceğini belirler.[/italic]")
        self.console.print("[italic]Hata bildirimi açıksa, kritik hatalar admin gruplarına bildirilir.[/italic]")
        
        # Değişiklik seçenekleri
        self.console.print("\n[bold]Hata Davranışları:[/bold]")
        self.console.print("1. Maksimum deneme sayısını değiştir")
        self.console.print("2. Hata bildirimini aç/kapat")
        self.console.print("3. Otomatik yeniden başlatmayı aç/kapat")
        self.console.print("4. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1":
            # Deneme sayısı
            new_retries = IntPrompt.ask(
                "Yeni maksimum deneme sayısı", 
                default=retry_count,
                min_value=1,
                max_value=10
            )
            
            self._update_env_variable("MAX_RETRIES", str(new_retries))
            
            # Servisleri güncelle
            for service_name, service in self.services.items():
                if hasattr(service, 'max_retries'):
                    service.max_retries = new_retries
                    
            self.console.print(f"[green]✅ Maksimum deneme sayısı {new_retries} olarak ayarlandı[/green]")
            
        elif choice == "2":
            # Hata bildirimi
            new_notify = not notify_errors
            self._update_env_variable("NOTIFY_ERRORS", str(new_notify).lower())
            
            # Servisleri güncelle
            for service_name, service in self.services.items():
                if hasattr(service, 'notify_errors'):
                    service.notify_errors = new_notify
                    
            status = "açıldı" if new_notify else "kapatıldı"
            self.console.print(f"[green]✅ Hata bildirimi {status}[/green]")
            
        elif choice == "3":
            # Otomatik yeniden başlatma
            new_restart = not auto_restart
            self._update_env_variable("AUTO_RESTART_ON_ERROR", str(new_restart).lower())
            
            status = "açıldı" if new_restart else "kapatıldı"
            self.console.print(f"[green]✅ Otomatik yeniden başlatma {status}[/green]")
            
            if new_restart:
                self.console.print("[yellow]⚠️ Otomatik yeniden başlatma, botun çökme sonrası kendini yeniden başlatmasına izin verecektir.[/yellow]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Rate Limiter Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    #############################################
    # VERİTABANI AYARLARI MODÜLÜ İMPLEMENTASYONLARI
    #############################################

    def db_stats(self):
        """Veritabanı istatistiklerini gösterir"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]VERİTABANI İSTATİSTİKLERİ[/bold cyan]",
            border_style="cyan"
        ))
        
        try:
            # Veritabanına erişimi kontrol et
            if not hasattr(self.db, 'connection'):
                self.console.print("[red]❌ Veritabanı bağlantısı bulunamadı.[/red]")
                Prompt.ask("\n[italic]Veritabanı Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")
                return
                
            # Temel veritabanı bilgileri
            db_path = getattr(self.db, 'db_path', 'Bilinmiyor')
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
                
            self.console.print(f"[yellow]Veritabanı Dosyası:[/yellow] {db_path}")
            self.console.print(f"[yellow]Veritabanı Boyutu:[/yellow] {size_str}")
            
            # Tablo istatistiklerini göster
            self.console.print("\n[bold]Tablo İstatistikleri:[/bold]")
            
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
                    cursor = self.db.connection.cursor()
                    cursor.execute(query)
                    count = cursor.fetchone()[0]
                    
                    # Son güncelleme zamanı (bu SQL uyumlu olmayabilir)
                    try:
                        cursor.execute(f"SELECT MAX(updated_at) FROM {table_name}")
                        last_update = cursor.fetchone()[0] or "Veri yok"
                    except:
                        last_update = "Belirsiz"
                    
                    table.add_row(table_name, str(count), str(last_update))
                except Exception as e:
                    table.add_row(table_name, "Hata", f"({str(e)})")
                    
            self.console.print(table)
            
            # Ekstra istatistikler
            self.console.print("\n[bold]Özet İstatistikler:[/bold]")
            
            # Aktif kullanıcı sayısı
            try:
                cursor = self.db.connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
                active_users = cursor.fetchone()[0]
                self.console.print(f"Aktif Kullanıcı Sayısı: [green]{active_users}[/green]")
            except:
                pass
                
            # Toplam mesaj sayısı
            try:
                cursor = self.db.connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM messages")
                total_messages = cursor.fetchone()[0]
                self.console.print(f"Toplam Mesaj Sayısı: [green]{total_messages}[/green]")
            except:
                pass
                
            # Üye toplanmış gruplar
            try:
                cursor = self.db.connection.cursor()
                cursor.execute("SELECT COUNT(DISTINCT group_id) FROM users")
                member_groups = cursor.fetchone()[0]
                self.console.print(f"Üye Toplanan Grup Sayısı: [green]{member_groups}[/green]")
            except:
                pass
            
        except Exception as e:
            self.console.print(f"[red]❌ İstatistikler alınırken hata oluştu: {str(e)}[/red]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Veritabanı Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    def optimize_db(self):
        """Veritabanını optimize eder"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]VERİTABANI OPTİMİZASYONU[/bold cyan]",
            border_style="cyan"
        ))
        
        # Veritabanı bağlantısını kontrol et
        if not hasattr(self.db, 'connection'):
            self.console.print("[red]❌ Veritabanı bağlantısı bulunamadı.[/red]")
            Prompt.ask("\n[italic]Veritabanı Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")
            return
        
        # Optimizasyon seçenekleri
        self.console.print("[bold]Optimizasyon İşlemleri:[/bold]")
        self.console.print("1. VACUUM - Veritabanını sıkıştır")
        self.console.print("2. REINDEX - İndeksleri yeniden oluştur")
        self.console.print("3. Eski kayıtları temizle")
        self.console.print("4. Tüm optimizasyonları çalıştır")
        self.console.print("5. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4", "5"], default="5")
        
        if choice in ["1", "2", "3", "4"]:
            # Yedekleme uyarısı
            self.console.print("[yellow]⚠️ Optimizasyon öncesi veritabanını yedeklemek önerilir![/yellow]")
            backup = Confirm.ask("Optimizasyon öncesi veritabanını yedeklemek istiyor musunuz?")
            
            if backup:
                try:
                    # Yedekleme
                    db_path = getattr(self.db, 'db_path', None)
                    if db_path and os.path.exists(db_path):
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_dir = "backups"
                        os.makedirs(backup_dir, exist_ok=True)
                        
                        backup_path = os.path.join(backup_dir, f"db_backup_{timestamp}.sqlite")
                        shutil.copy2(db_path, backup_path)
                        self.console.print(f"[green]✅ Veritabanı yedeklendi: {backup_path}[/green]")
                except Exception as e:
                    self.console.print(f"[red]❌ Yedekleme hatası: {str(e)}[/red]")
                    return
        
        try:
            cursor = self.db.connection.cursor()
            
            if choice == "1" or choice == "4":
                # VACUUM
                self.console.print("[yellow]VACUUM işlemi çalıştırılıyor...[/yellow]")
                cursor.execute("VACUUM")
                self.console.print("[green]✅ VACUUM tamamlandı[/green]")
            
            if choice == "2" or choice == "4":
                # REINDEX
                self.console.print("[yellow]REINDEX işlemi çalıştırılıyor...[/yellow]")
                cursor.execute("REINDEX")
                self.console.print("[yellow]Eski mesaj kayıtları temizleniyor...[/yellow]")
                try:
                    cursor.execute(f"DELETE FROM messages WHERE date(created_at) < date('now', '-{days} days')")
                    count = cursor.rowcount
                    self.console.print(f"[green]✅ {count} eski mesaj silindi[/green]")
                except Exception as e:
                    self.console.print(f"[red]❌ Mesaj temizleme hatası: {str(e)}[/red]")
                
                # Davet geçmişi
                self.console.print("[yellow]Eski davet kayıtları temizleniyor...[/yellow]")
                try:
                    cursor.execute(f"DELETE FROM invites WHERE date(created_at) < date('now', '-{days} days')")
                    count = cursor.rowcount
                    self.console.print(f"[green]✅ {count} eski davet silindi[/green]")
                except Exception as e:
                    self.console.print(f"[red]❌ Davet temizleme hatası: {str(e)}[/red]")
                
                # Log kayıtları varsa
                self.console.print("[yellow]Eski log kayıtları temizleniyor...[/yellow]")
                try:
                    days = 30  # Define the number of days as needed
                    cursor.execute(f"DELETE FROM logs WHERE date(timestamp) < date('now', '-{days} days')")
                    count = cursor.rowcount
                    self.console.print(f"[green]✅ {count} eski log silindi[/green]")
                except Exception as e:
                    self.console.print("[yellow]Log tablosu bulunamadı veya erişilemedi[/yellow]")
                
        except Exception as e:
            self.console.print(f"[red]❌ Optimizasyon hatası: {str(e)}[/red]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Veritabanı Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    def export_data(self):
        """Veriyi dışa aktarır"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]VERİYİ DIŞA AKTAR[/bold cyan]",
            border_style="cyan"
        ))
        
        # Export format seçimi
        self.console.print("[bold]Dışa Aktarma Formatı:[/bold]")
        self.console.print("1. JSON (Tüm veriler)")
        self.console.print("2. CSV (Tablo bazlı)")
        self.console.print("3. SQL Dump (SQLite)")
        self.console.print("4. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "4":
            return
            
        # Hangi tabloları dışa aktaracağını sor
        if choice in ["1", "2"]:
            table_choice = Prompt.ask(
                "Hangi veriyi dışa aktarmak istiyorsunuz?",
                choices=["users", "groups", "messages", "invites", "all"],
                default="all"
            )
        else:
            table_choice = "all"  # SQL dump her zaman tüm veritabanını alır
        
        # Export işlemi
        try:
            # Export dizinini oluştur
            export_dir = "exports"
            os.makedirs(export_dir, exist_okay=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if choice == "1":
                # JSON export
                export_path = os.path.join(export_dir, f"export_{table_choice}_{timestamp}.json")
                self.console.print(f"[yellow]JSON verisi dışa aktarılıyor: {export_path}[/yellow]")
                
                # Basit bir örnek, gerçek implementasyon veritabanı yapınıza bağlı olacaktır
                if hasattr(self.db, 'export_to_json'):
                    self.db.export_to_json(export_path, table_choice)
                    self.console.print(f"[green]✅ Veri başarıyla JSON formatında dışa aktarıldı: {export_path}[/green]")
                else:
                    self.console.print("[red]❌ Veritabanı servisi JSON export desteği sağlamıyor.[/red]")
                
            elif choice == "2":
                # CSV export
                export_path = os.path.join(export_dir, f"export_{table_choice}_{timestamp}.csv")
                self.console.print(f"[yellow]CSV verisi dışa aktarılıyor: {export_path}[/yellow]")
                
                # Basit bir örnek
                if hasattr(self.db, 'export_to_csv'):
                    self.db.export_to_csv(export_path, table_choice)
                    self.console.print(f"[green]✅ Veri başarıyla CSV formatında dışa aktarıldı: {export_path}[/green]")
                else:
                    self.console.print("[red]❌ Veritabanı servisi CSV export desteği sağlamıyor.[/red]")
                
            elif choice == "3":
                # SQL dump
                export_path = os.path.join(export_dir, f"db_dump_{timestamp}.sql")
                self.console.print(f"[yellow]SQL dump oluşturuluyor: {export_path}[/yellow]")
                
                # SQLite için basit örnek
                db_path = getattr(self.db, 'db_path', None)
                if db_path and os.path.exists(db_path):
                    # SQLite .dump komutu kullanılabilir (bu örnek bir betik olarak oluşturulmalı gerçek uygulamada)
                    import subprocess
                    with open(export_path, 'w') as f:
                        subprocess.run(['sqlite3', db_path, '.dump'], stdout=f)
                    self.console.print(f"[green]✅ Veritabanı dump başarıyla oluşturuldu: {export_path}[/green]")
                else:
                    self.console.print("[red]❌ Veritabanı dosyası bulunamadı.[/red]")
                
        except Exception as e:
            self.console.print(f"[red]❌ Dışa aktarma hatası: {str(e)}[/red]")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Veritabanı Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    def backup_restore(self):
        """Yedekleme ve geri yükleme işlemleri"""
        self.clear_screen()
        
        self.console.print(Panel.fit(
            "[bold cyan]YEDEKLEME VE GERİ YÜKLEME[/bold cyan]",
            border_style="cyan"
        ))
        
        # İşlem seçimi
        self.console.print("[bold]İşlem Seçimi:[/bold]")
        self.console.print("1. Veritabanını yedekle")
        self.console.print("2. Yedeği geri yükle")
        self.console.print("3. Yedekleri listele")
        self.console.print("4. Geri")
        
        choice = Prompt.ask("Seçiminiz", choices=["1", "2", "3", "4"], default="4")
        
        if choice == "1":
            # Yedekleme
            self.clear_screen()
            self.console.print("[bold cyan]VERİTABANI YEDEKLEME[/bold cyan]")
            
            # Veritabanı dosyasını kontrol et
            db_path = getattr(self.db, 'db_path', None)
            if not db_path or not os.path.exists(db_path):
                self.console.print("[red]❌ Veritabanı dosyası bulunamadı.[/red]")
                Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")
                return
                
            # Yedekleme dizinini oluştur
            backup_dir = "backups"
            os.makedirs(backup_dir, exist_okay=True)
            
            # Yedek adı
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"db_backup_{timestamp}.sqlite"
            backup_name = Prompt.ask("Yedek dosyası adı", default=default_name)
            
            backup_path = os.path.join(backup_dir, backup_name)
            try:
                shutil.copy2(db_path, backup_path)
                self.console.print(f"[green]✅ Veritabanı yedeklendi: {backup_path}[/green]")
            except Exception as e:
                self.console.print(f"[red]❌ Yedekleme hatası: {str(e)}[/red]")
        
        elif choice == "2":
            # Geri yükleme
            self.clear_screen()
            self.console.print("[bold cyan]YEDEK GERİ YÜKLEME[/bold cyan]")
            
            # Yedekleme dizinini kontrol et
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                self.console.print("[red]❌ Yedekleme dizini bulunamadı.[/red]")
                Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")
                return
            
            # Yedek dosyalarını listele
            backups = sorted(os.listdir(backup_dir))
            if not backups:
                self.console.print("[yellow]Henüz yedek dosyası bulunmuyor.[/yellow]")
                Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")
                return
            
            self.console.print("\n[bold]Mevcut Yedekler:[/bold]")
            for i, backup in enumerate(backups):
                self.console.print(f"[green]{i+1}.[/green] {backup}")
            
            # Geri yüklenecek yedeği seç
            idx = IntPrompt.ask(
                "Geri yüklemek istediğiniz yedeğin numarası", 
                min_value=1, 
                max_value=len(backups)
            )
            
            backup_path = os.path.join(backup_dir, backups[idx-1])
            confirm = Confirm.ask(f"[red]DİKKAT:[/red] {backup_path} dosyasını geri yüklemek istediğinize emin misiniz?")
            if confirm:
                try:
                    shutil.copy2(backup_path, db_path)
                    self.console.print(f"[green]✅ Yedek geri yüklendi: {backup_path}[/green]")
                except Exception as e:
                    self.console.print(f"[red]❌ Geri yükleme hatası: {str(e)}[/red]")
        
        elif choice == "3":
            # Yedekleri listele
            self.clear_screen()
            self.console.print("[bold cyan]MEVCUT YEDEKLER[/bold cyan]")
            
            # Yedekleme dizinini kontrol et
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                self.console.print("[red]❌ Yedekleme dizini bulunamadı.[/red]")
                Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")
                return
            
            # Yedek dosyalarını listele
            backups = sorted(os.listdir(backup_dir))
            if not backups:
                self.console.print("[yellow]Henüz yedek dosyası bulunmuyor.[/yellow]")
            else:
                self.console.print("\n[bold]Mevcut Yedekler:[/bold]")
                for i, backup in enumerate(backups):
                    self.console.print(f"[green]{i+1}.[/green] {backup}")
        
        # Kullanıcının devam etmesi için bekle
        Prompt.ask("\n[italic]Veritabanı Ayarları menüsüne dönmek için Enter tuşuna basın[/italic]")

    #############################################
    # ŞABLON YÖNETİCİSİ MODÜLÜ İMPLEMENTASYONLARI
    #############################################

    def template_editor(self, template_type):
        """Şablon düzenleme ekranı"""
        self.clear_screen()
        
        # Şablon türüne göre başlık belirle
        title_map = {
            "messages": "MESAJ ŞABLONLARI",
            "invites": "DAVET ŞABLONLARI", 
            "responses": "YANIT ŞABLONLARI"
        }
        
        title = title_map.get(template_type, "ŞABLON DÜZENLE")
        
        self.console.print(Panel.fit(
            f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan"
        ))
        
        # Şablon dosya yolları
        file_paths = {
            "messages": os.getenv("MESSAGES_FILE", "data/messages.json"),
            "invites": os.getenv("INVITES_FILE", "data/invites.json"),
            "responses": os.getenv("RESPONSES_FILE", "data/responses.json")
        }
        
        file_path = file_paths.get(template_type)
        if not file_path:
            self.console.print("[red]❌ Şablon türü için dosya yolu tanımlı değil.[/red]")
            Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")
            return
        
        # Dosya var mı kontrol et
        if not os.path.exists(file_path):
            self.console.print(f"[yellow]⚠️ Şablon dosyası bulunamadı: {file_path}[/yellow]")
            
            # Yeni dosya oluştur mu?
            create_file = Confirm.ask("Yeni bir şablon dosyası oluşturmak istiyor musunuz?")
            if create_file:
                # Dizini oluştur
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Şablon türüne göre temel yapı oluştur
                if template_type == "messages":
                    templates = ["Örnek mesaj 1", "Örnek mesaj 2"]
                elif template_type == "invites":
                    templates = {
                        "default": ["Merhaba, grubumuz hakkında bilgi almak ister misiniz?", 
                                   "Size özel davet linki göndermek istiyorum."],
                        "vip": ["VIP üyelerimiz için özel davet."]
                    }
                else:  # responses
                    templates = {
                        "greeting": ["Merhaba!", "Selam!"],
                        "thanks": ["Teşekkürler!", "Sağ olun!"]
                    }
                
                # Dosyaya kaydet
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(templates, f, ensure_ascii=False, indent=2)
                    self.console.print(f"[green]✅ Şablon dosyası oluşturuldu: {file_path}[/green]")
                except Exception as e:
                    self.console.print(f"[red]❌ Dosya oluşturma hatası: {str(e)}[/red]")
                    Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")
                    return
            else:
                return
        
        # Şablonları yükle
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                templates = json.load(f)
        except Exception as e:
            self.console.print(f"[red]❌ Şablon dosyası okunamadı: {str(e)}[/red]")
            Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")
            return
        
        # Şablon formatına göre düzenleme ekranını çağır
        if isinstance(templates, list):
            # Basit liste formatı (mesaj şablonları)
            self._edit_simple_templates(template_type, file_path, templates)
        elif isinstance(templates, dict):
            # Kategorili format (davet ve yanıt şablonları)
            self._edit_categorized_templates(template_type, file_path, templates)
        else:
            self.console.print("[red]❌ Desteklenmeyen şablon formatı.[/red]")
            Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")
    
    def _edit_simple_templates(self, template_type, file_path, templates):
        """Basit liste formatındaki şablonları düzenler"""
        while True:
            self.clear_screen()
            
            title_map = {
                "messages": "MESAJ ŞABLONLARI",
                "invites": "DAVET ŞABLONLARI",
                "responses": "YANIT ŞABLONLARI"
            }
            
            title = title_map.get(template_type, "ŞABLON DÜZENLE")
            
            self.console.print(Panel.fit(
                f"[bold cyan]{title} DÜZENLE[/bold cyan]",
                border_style="cyan"
            ))
            
            if templates:
                # Şablonları listele
                table = Table(show_header=True, box=box.SIMPLE)
                table.add_column("No", style="cyan", width=4)
                table.add_column("Şablon", style="green")
                
                for i, template in enumerate(templates):
                    # Uzun şablonları kısalt
                    display_text = template[:50] + "..." if len(template) > 50 else template
                    table.add_row(str(i+1), display_text)
                
                self.console.print(table)
                self.console.print(f"\nToplam {len(templates)} şablon.")
            else:
                self.console.print("[yellow]Henüz hiç şablon eklenmemiş.[/yellow]")
            
            # İşlemler menüsü
            self.console.print("\n[bold]İşlemler:[/bold]")
            self.console.print("1. Yeni şablon ekle")
            if templates:
                self.console.print("2. Şablon düzenle")
                self.console.print("3. Şablon sil")
            self.console.print(f"{'4' if templates else '2'}. Geri")
            
            # Kullanıcı seçimi
            choices = ["1", "2", "3", "4"] if templates else ["1", "2"]
            choice = Prompt.ask("Seçiminiz", choices=choices, default="1")
            
            if choice == "1":
                # Yeni şablon ekle
                self.clear_screen()
                self.console.print("[bold cyan]YENİ ŞABLON EKLE[/bold cyan]")
                self.console.print("[yellow]Not: Çoklu satır için Enter tuşuna basın, bitirmek için boş bir satır girin.[/yellow]\n")
                
                # Çoklu satır girişi
                lines = []
                while True:
                    line = input("> ")
                    if not line.strip():  # Boş satır - bitir
                        break
                    lines.append(line)
                
                if lines:
                    new_template = "\n".join(lines)
                    templates.append(new_template)
                    
                    # Dosyaya kaydet
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(templates, f, ensure_ascii=False, indent=2)
                        self.console.print(f"[green]✅ Yeni şablon eklendi.[/green]")
                    except Exception as e:
                        self.console.print(f"[red]❌ Kaydetme hatası: {str(e)}[/red]")
                
            elif choice == "2" and templates:
                # Şablon düzenle
                idx = IntPrompt.ask(
                    "Düzenlemek istediğiniz şablonun numarası",
                    min_value=1,
                    max_value=len(templates)
                )
                
                self.clear_screen()
                self.console.print("[bold cyan]ŞABLON DÜZENLE[/bold cyan]")
                self.console.print(f"[yellow]Mevcut şablon:[/yellow]\n")
                self.console.print(templates[idx-1])
                self.console.print("\n[yellow]Yeni şablonu girin (çoklu satır için Enter, bitirmek için boş satır):[/yellow]\n")
                
                # Çoklu satır girişi
                lines = []
                while True:
                    line = input("> ")
                    if not line.strip():  # Boş satır - bitir
                        break
                    lines.append(line)
                
                if lines:
                    new_template = "\n".join(lines)
                    templates[idx-1] = new_template
                    
                    # Dosyaya kaydet
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(templates, f, ensure_ascii=False, indent=2)
                        self.console.print(f"[green]✅ Şablon güncellendi.[/green]")
                    except Exception as e:
                        self.console.print(f"[red]❌ Kaydetme hatası: {str(e)}[/red]")
                        
            elif choice == "3" and templates:
                # Şablon sil
                idx = IntPrompt.ask(
                    "Silmek istediğiniz şablonun numarası",
                    min_value=1,
                    max_value=len(templates)
                )
                
                # Onay
                confirm = Confirm.ask(f"[yellow]{idx}. şablonu silmek istediğinize emin misiniz?[/yellow]")
                if confirm:
                    deleted = templates.pop(idx-1)
                    
                    # Dosyaya kaydet
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(templates, f, ensure_ascii=False, indent=2)
                        self.console.print(f"[green]✅ Şablon silindi.[/green]")
                    except Exception as e:
                        self.console.print(f"[red]❌ Kaydetme hatası: {str(e)}[/red]")
                        
            elif (choice == "4" and templates) or (choice == "2" and not templates):
                # Geri dön
                break
            
            # Her işlemden sonra kısa bekle
            Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")
    
    def _edit_categorized_templates(self, template_type, file_path, templates):
        """Kategorili şablonları düzenler (davet ve yanıt şablonları)"""
        while True:
            self.clear_screen()
            
            title_map = {
                "invites": "DAVET ŞABLONLARI",
                "responses": "YANIT ŞABLONLARI"
            }
            
            title = title_map.get(template_type, "KATEGORİLİ ŞABLONLAR")
            
            self.console.print(Panel.fit(
                f"[bold cyan]{title} DÜZENLE[/bold cyan]",
                border_style="cyan"
            ))
            
            if templates:
                # Kategorileri listele
                table = Table(show_header=True, box=box.SIMPLE)
                table.add_column("No", style="cyan", width=4)
                table.add_column("Kategori", style="green")
                table.add_column("Şablon Sayısı", style="yellow", justify="right")
                
                for i, (category, items) in enumerate(templates.items()):
                    table.add_row(str(i+1), category, str(len(items)))
                
                self.console.print(table)
                self.console.print(f"\nToplam {len(templates)} kategori.")
            else:
                self.console.print("[yellow]Henüz hiç kategori eklenmemiş.[/yellow]")
            
            # İşlemler menüsü
            self.console.print("\n[bold]İşlemler:[/bold]")
            self.console.print("1. Kategori seç ve düzenle")
            self.console.print("2. Yeni kategori ekle")
            if templates:
                self.console.print("3. Kategori sil")
                self.console.print("4. Kategori adını değiştir")
            self.console.print(f"{'5' if templates else '3'}. Geri")
            
            # Kullanıcı seçimi
            choices = ["1", "2", "3", "4", "5"] if templates else ["1", "2", "3"]
            choice = Prompt.ask("Seçiminiz", choices=choices, default="1")
            
            if choice == "1" and templates:
                # Kategori seç
                categories = list(templates.keys())
                for i, category in enumerate(categories):
                    self.console.print(f"[green]{i+1}.[/green] {category}")
                
                idx = IntPrompt.ask(
                    "Düzenlemek istediğiniz kategorinin numarası",
                    min_value=1,
                    max_value=len(categories)
                )
                
                selected_category = categories[idx-1]
                self._edit_category_items(template_type, file_path, templates, selected_category)
                
            elif choice == "2":
                # Yeni kategori ekle
                new_category = Prompt.ask("Yeni kategori adı")
                if new_category and new_category not in templates:
                    templates[new_category] = []
                    
                    # Dosyaya kaydet
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(templates, f, ensure_ascii=False, indent=2)
                        self.console.print(f"[green]✅ Yeni kategori eklendi: {new_category}[/green]")
                    except Exception as e:
                        self.console.print(f"[red]❌ Kaydetme hatası: {str(e)}[/red]")
                else:
                    self.console.print("[yellow]Kategori adı boş olamaz veya mevcut bir kategoriyle aynı olamaz.[/yellow]")
                    
            elif choice == "3" and templates:
                # Kategori sil
                categories = list(templates.keys())
                for i, category in enumerate(categories):
                    self.console.print(f"[green]{i+1}.[/green] {category}")
                
                idx = IntPrompt.ask(
                    "Silmek istediğiniz kategorinin numarası",
                    min_value=1,
                    max_value=len(categories)
                )
                
                selected_category = categories[idx-1]
                
                # Onay
                confirm = Confirm.ask(f"[yellow]'{selected_category}' kategorisini ve içindeki tüm şablonları silmek istediğinize emin misiniz?[/yellow]")
                if confirm:
                    del templates[selected_category]
                    
                    # Dosyaya kaydet
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(templates, f, ensure_ascii=False, indent=2)
                        self.console.print(f"[green]✅ Kategori silindi: {selected_category}[/green]")
                    except Exception as e:
                        self.console.print(f"[red]❌ Kaydetme hatası: {str(e)}[/red]")
                        
            elif choice == "4" and templates:
                # Kategori adını değiştir
                categories = list(templates.keys())
                for i, category in enumerate(categories):
                    self.console.print(f"[green]{i+1}.[/green] {category}")
                
                idx = IntPrompt.ask(
                    "Adını değiştirmek istediğiniz kategorinin numarası",
                    min_value=1,
                    max_value=len(categories)
                )
                
                old_category = categories[idx-1]
                new_category = Prompt.ask("Yeni kategori adı", default=old_category)
                
                if new_category and new_category != old_category and new_category not in templates:
                    # Kategorinin içeriğini kopyala ve eskisini sil
                    templates[new_category] = templates[old_category]
                    del templates[old_category]
                    
                    # Dosyaya kaydet
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(templates, f, ensure_ascii=False, indent=2)
                        self.console.print(f"[green]✅ Kategori adı değiştirildi: {old_category} → {new_category}[/green]")
                    except Exception as e:
                        self.console.print(f"[red]❌ Kaydetme hatası: {str(e)}[/red]")
                else:
                    self.console.print("[yellow]Geçersiz kategori adı veya bu isimde kategori zaten var.[/yellow]")
                    
            elif (choice == "5" and templates) or (choice == "3" and not templates):
                # Geri dön
                break
            
            # Her işlemden sonra kısa bekle
            Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")

    def _edit_category_items(self, template_type, file_path, templates, category):
        """Bir kategorideki şablonları düzenler"""
        while True:
            self.clear_screen()
            
            self.console.print(Panel.fit(
                f"[bold cyan]{category.upper()} KATEGORİSİ[/bold cyan]",
                border_style="cyan"
            ))
            
            items = templates[category]
            
            if items:
                # Şablonları listele
                table = Table(show_header=True, box=box.SIMPLE)
                table.add_column("No", style="cyan", width=4)
                table.add_column("Şablon", style="green")
                
                for i, item in enumerate(items):
                    # Uzun şablonları kısalt
                    display_text = item[:50] + "..." if len(item) > 50 else item
                    table.add_row(str(i+1), display_text)
                
                self.console.print(table)
                self.console.print(f"\nToplam {len(items)} şablon.")
            else:
                self.console.print("[yellow]Bu kategoride henüz hiç şablon yok.[/yellow]")
            
            # İşlemler menüsü
            self.console.print("\n[bold]İşlemler:[/bold]")
            self.console.print("1. Yeni şablon ekle")
            if items:
                self.console.print("2. Şablon düzenle")
                self.console.print("3. Şablon sil")
            self.console.print(f"{'4' if items else '2'}. Geri")
            
            # Kullanıcı seçimi
            choices = ["1", "2", "3", "4"] if items else ["1", "2"]
            choice = Prompt.ask("Seçiminiz", choices=choices, default="1")
            
            if choice == "1":
                # Yeni şablon ekle
                self.clear_screen()
                self.console.print(f"[bold cyan]{category.upper()} - YENİ ŞABLON EKLE[/bold cyan]")
                self.console.print("[yellow]Not: Çoklu satır için Enter tuşuna basın, bitirmek için boş bir satır girin.[/yellow]\n")
                
                # Çoklu satır girişi
                lines = []
                while True:
                    line = input("> ")
                    if not line.strip():  # Boş satır - bitir
                        break
                    lines.append(line)
                
                if lines:
                    new_template = "\n".join(lines)
                    templates[category].append(new_template)
                    
                    # Dosyaya kaydet
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(templates, f, ensure_ascii=False, indent=2)
                        self.console.print(f"[green]✅ Yeni şablon eklendi.[/green]")
                    except Exception as e:
                        self.console.print(f"[red]❌ Kaydetme hatası: {str(e)}[/red]")
                
            elif choice == "2" and items:
                # Şablon düzenle
                idx = IntPrompt.ask(
                    "Düzenlemek istediğiniz şablonun numarası",
                    min_value=1,
                    max_value=len(items)
                )
                
                self.clear_screen()
                self.console.print(f"[bold cyan]{category.upper()} - ŞABLON DÜZENLE[/bold cyan]")
                self.console.print(f"[yellow]Mevcut şablon:[/yellow]\n")
                self.console.print(items[idx-1])
                self.console.print("\n[yellow]Yeni şablonu girin (çoklu satır için Enter, bitirmek için boş satır):[/yellow]\n")
                
                # Çoklu satır girişi
                lines = []
                while True:
                    line = input("> ")
                    if not line.strip():  # Boş satır - bitir
                        break
                    lines.append(line)
                
                if lines:
                    new_template = "\n".join(lines)
                    templates[category][idx-1] = new_template
                    
                    # Dosyaya kaydet
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(templates, f, ensure_ascii=False, indent=2)
                        self.console.print(f"[green]✅ Şablon güncellendi.[/green]")
                    except Exception as e:
                        self.console.print(f"[red]❌ Kaydetme hatası: {str(e)}[/red]")
                        
            elif choice == "3" and items:
                # Şablon sil
                idx = IntPrompt.ask(
                    "Silmek istediğiniz şablonun numarası",
                    min_value=1,
                    max_value=len(items)
                )
                
                # Onay
                confirm = Confirm.ask(f"[yellow]Bu şablonu silmek istediğinize emin misiniz?[/yellow]")
                if confirm:
                    deleted = templates[category].pop(idx-1)
                    
                    # Dosyaya kaydet
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(templates, f, ensure_ascii=False, indent=2)
                        self.console.print(f"[green]✅ Şablon silindi.[/green]")
                    except Exception as e:
                        self.console.print(f"[red]❌ Kaydetme hatası: {str(e)}[/red]")
                        
            elif (choice == "4" and items) or (choice == "2" and not items):
                # Geri dön
                break
            
            # Her işlemden sonra kısa bekle
            Prompt.ask("\n[italic]Devam etmek için Enter tuşuna basın[/italic]")

    # Interactive Dashboard'a servis kontrolü için özel metot ekleyin

    async def check_services(self):
        """Tüm servislerin durumunu kontrol eder"""
        print("\n--- Servis Durumları ---\n")
        
        if not self.services:
            print("❌ Hiç servis bulunamadı!")
            return
            
        for name, service in self.services.items():
            status = "✅ Çalışıyor" if getattr(service, "running", False) else "❌ Durdu"
            print(f"{name}: {status}")
            
            # Servis detayları
            if hasattr(service, "get_status"):
                try:
                    # Async fonksiyon olup olmadığını kontrol et
                    if asyncio.iscoroutinefunction(service.get_status):
                        status_dict = await service.get_status()
                    else:
                        status_dict = service.get_status()
                        
                    for key, value in status_dict.items():
                        if key != "running":  # running zaten yukarıda gösteriliyor
                            print(f"  - {key}: {value}")
                except Exception as e:
                    print(f"  ⚠️ Detay alınamadı: {e}")
                    
        print("\nDaha fazla detay için console log'ları kontrol edin.\n")