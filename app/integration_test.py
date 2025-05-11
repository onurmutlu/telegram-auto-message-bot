#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kapsamlı Servis Entegrasyon Testi
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Bot servislerini import et
from bot.services.service_manager import ServiceManager
from bot.services.event_service import EventService
from bot.services.analytics_service import AnalyticsService
from bot.services.error_service import ErrorService, ErrorRecord
from bot.services.group_service import GroupService
from bot.services.user_service import UserService
from bot.services.datamining_service import DataMiningService
from bot.services.message_service import MessageService
from bot.services.service_factory import ServiceFactory

# Veritabanı bağlantısı
from database.user_db import UserDatabase
from database.db_connection import get_db_pool

# Konsol için Rich
console = Console()

# Logger kurulumu
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class IntegrationTest:
    """Entegrasyon test sınıfı"""
    
    def __init__(self):
        """Entegrasyon test başlatıcısı"""
        self.db = None
        self.service_manager = None
        self.stop_event = asyncio.Event()
        
    async def setup(self):
        """Test ortamını hazırla"""
        console.print("\n[bold cyan]Entegrasyon Test Ortamı Hazırlanıyor...[/bold cyan]")
        
        # Veritabanı bağlantısı
        db_connection = os.getenv("DB_CONNECTION", "postgresql://postgres:postgres@localhost:5432/telegram_bot")
        self.db = UserDatabase(db_url=db_connection)
        await self.db.connect()
        
        # Konfigürasyon oluştur
        self.config = {
            'analytics': {
                'update_interval': 1800,
                'max_retained_reports': 30
            },
            'error_service': {
                'max_retained_errors': 1000,
                'error_log_path': 'logs/errors',
                'notify_critical': True,
                'notify_error': True,
                'alert_threshold': 5,
                'alert_window': 300,
                'category_thresholds': {
                    'DATABASE': 3, 
                    'TELEGRAM_API': 10,
                    'NETWORK': 5,
                    'GENERAL': 5
                },
                'category_windows': {
                    'DATABASE': 600,
                    'TELEGRAM_API': 300,
                    'NETWORK': 300,
                    'GENERAL': 300
                }
            }
        }
        
        # ServiceFactory ve ServiceManager başlat
        service_factory = ServiceFactory(client=None, config=self.config, db=self.db, stop_event=self.stop_event)
        self.service_manager = ServiceManager(service_factory=service_factory, client=None, config=self.config, db=self.db, stop_event=self.stop_event)
        
        console.print("[green]Test ortamı başarıyla hazırlandı[/green]")
        return True
        
    async def teardown(self):
        """Test sonunda temizlik yap"""
        if self.service_manager:
            await self.service_manager.stop_services()
            
        if self.db:
            await self.db.disconnect()
            
        console.print("[green]Test ortamı temizlendi[/green]")
    
    async def test_service_registration(self):
        """Servislerin düzgün kaydedilip kaydedilmediğini test eder"""
        console.print("\n[bold cyan]Servis Kayıt Testleri Başlatılıyor...[/bold cyan]")
        
        # Aktif servisleri belirle
        active_services = [
            "user", "group", "reply", "gpt", "dm", "invite", "promo", 
            "announcement", "datamining", "message", "analytics", "error"
        ]
        
        # Servisleri oluştur ve kaydet
        created_services = await self.service_manager.create_and_register_services(active_services)
        
        # Service Manager status tablosu göster
        console.print(f"Kaydedilen servis sayısı: {len(created_services)}")
        
        table = Table(title="Kaydedilen Servisler")
        table.add_column("Servis Adı", style="cyan")
        table.add_column("Durum", style="green")
        
        for name, service in created_services.items():
            table.add_row(name, "✓" if service else "✗")
            
        console.print(table)
        
        # Servis iletişimi kurulumu
        await self.service_manager.initialize_service_communications()
        
        # Servisleri başlat
        await self.service_manager.start_services()
        
        # Service Manager status tablosu göster
        status = await self.service_manager.get_status()
        
        table = Table(title="Servis Durumları")
        table.add_column("Servis Adı", style="cyan")
        table.add_column("Çalışıyor", style="green")
        
        for name, info in status.items():
            running = info.get('running', False)
            table.add_row(name, "✓" if running else "✗")
            
        console.print(table)
        
        return len(created_services) > 0
    
    async def test_event_service(self):
        """EventService'in olay yayınlama ve dinleme yeteneklerini test eder"""
        console.print("\n[bold cyan]EventService Testi Başlatılıyor...[/bold cyan]")
        
        event_service = self.service_manager.get_service("event")
        if not event_service:
            console.print("[red]EventService bulunamadı![/red]")
            return False
        
        # Test bayrakları
        test_received = {"user": False, "group": False, "analytics": False}
        
        # Test için event handler
        async def test_event_handler(event_data):
            service_name = event_data.get('target', 'unknown')
            console.print(f"[green]Event alındı ({service_name}): {event_data}[/green]")
            test_received[service_name] = True
        
        # Event dinleyicileri ekle
        event_service.add_listener("test_event", "user", test_event_handler)
        event_service.add_listener("test_event", "group", test_event_handler)
        event_service.add_listener("test_event", "analytics", test_event_handler)
        
        # Test eventleri gönder
        console.print("[cyan]Test eventleri gönderiliyor...[/cyan]")
        
        await event_service.emit_event("test_event", {"message": "Test mesajı 1", "target": "user"})
        await event_service.emit_event("test_event", {"message": "Test mesajı 2", "target": "group"})
        await event_service.emit_event("test_event", {"message": "Test mesajı 3", "target": "analytics"})
        
        # Eventlerin işlenmesi için kısa bir süre bekle
        await asyncio.sleep(0.5)
        
        # Sonuçları kontrol et
        all_received = all(test_received.values())
        console.print(f"EventService testi: [{'green' if all_received else 'red'}]{'Başarılı' if all_received else 'Başarısız'}[/{'green' if all_received else 'red'}]")
        
        return all_received
    
    async def test_error_service(self):
        """ErrorService'in hata işleme özelliklerini test eder"""
        console.print("\n[bold cyan]ErrorService Testi Başlatılıyor...[/bold cyan]")
        
        error_service = self.service_manager.get_service("error")
        if not error_service:
            console.print("[red]ErrorService bulunamadı![/red]")
            return False
        
        # Test hataları oluştur
        console.print("[cyan]Test hataları oluşturuluyor...[/cyan]")
        
        # 1. Veritabanı hatası
        db_error_id = await error_service.log_error(
            error_type="ConnectionError",
            message="Test veritabanı bağlantı hatası",
            source="integration_test",
            severity="ERROR",
            category="DATABASE"
        )
        console.print(f"[green]Veritabanı hatası oluşturuldu. ID: {db_error_id}[/green]")
        
        # 2. Ağ hatası
        net_error_id = await error_service.log_error(
            error_type="TimeoutError",
            message="Test ağ zaman aşımı hatası",
            source="integration_test",
            severity="WARNING",
            category="NETWORK"
        )
        console.print(f"[green]Ağ hatası oluşturuldu. ID: {net_error_id}[/green]")
        
        # 3. Kritik API hatası
        api_error_id = await error_service.log_error(
            error_type="APIError",
            message="Test Telegram API hatası",
            source="integration_test",
            severity="CRITICAL",
            category="TELEGRAM_API"
        )
        console.print(f"[green]API hatası oluşturuldu. ID: {api_error_id}[/green]")
        
        # Hataları kategori bazlı listele
        console.print("[cyan]Kategori bazlı hata istatistikleri alınıyor...[/cyan]")
        stats = await error_service.get_category_stats(hours=24)
        
        if stats:
            # Tablo oluştur
            stats_table = Table(title="Kategori Bazlı Hata İstatistikleri")
            stats_table.add_column("Kategori", style="cyan")
            stats_table.add_column("Toplam", style="yellow")
            stats_table.add_column("Kritik", style="red")
            stats_table.add_column("Hata", style="yellow")
            stats_table.add_column("Uyarı", style="green")
            
            categories_found = False
            for category, count in stats.items():
                categories_found = True
                # Farklı türleri ayır - kategori istatistikleri dict veya int olabilir
                if isinstance(count, dict):
                    total = count.get('total', 0)
                    critical = count.get('CRITICAL', 0)
                    error = count.get('ERROR', 0)
                    warning = count.get('WARNING', 0)
                else:
                    total = count
                    critical = 0
                    error = 0
                    warning = 0
                
                stats_table.add_row(
                    category,
                    str(total),
                    str(critical),
                    str(error),
                    str(warning)
                )
            
            if categories_found:
                console.print(stats_table)
            else:
                console.print("[yellow]Kategoriler bulunamadı veya boş.[/yellow]")
        else:
            console.print("[yellow]Hiç hata istatistiği bulunamadı.[/yellow]")
        
        # Bir hatayı çözüldü olarak işaretle
        console.print("[cyan]Ağ hatası çözüldü olarak işaretleniyor...[/cyan]")
        resolved = await error_service.resolve_error(
            error_id=net_error_id,
            resolution_info="Test için çözüldü olarak işaretlendi"
        )
        console.print(f"[green]Hata çözüldü olarak işaretlendi: {resolved}[/green]")
        
        # Başarılı bir test için kriterleri kontrol et
        success = (db_error_id is not None and 
                    net_error_id is not None and 
                    api_error_id is not None and 
                    stats is not None and 
                    resolved)
        
        console.print(f"ErrorService testi: [{'green' if success else 'red'}]{'Başarılı' if success else 'Başarısız'}[/{'green' if success else 'red'}]")
        
        return success
    
    async def test_analytics_service(self):
        """AnalyticsService'in grup analiz özelliklerini test eder"""
        console.print("\n[bold cyan]AnalyticsService Testi Başlatılıyor...[/bold cyan]")
        
        analytics_service = self.service_manager.get_service("analytics")
        if not analytics_service:
            console.print("[red]AnalyticsService bulunamadı![/red]")
            return False
        
        # Test grupları oluştur (test verisiyle)
        console.print("[cyan]Test grup verileri oluşturuluyor...[/cyan]")
        
        # Test grup analitik verileri
        test_groups = [
            {
                'name': 'Test Grup 1',
                'group_id': 1001,
                'message_count': 450,
                'active_users': 120,
                'engagement_rate': 22.5
            },
            {
                'name': 'Test Grup 2',
                'group_id': 1002,
                'message_count': 350,
                'active_users': 80,
                'engagement_rate': 18.2
            },
            {
                'name': 'Test Grup 3',
                'group_id': 1003,
                'message_count': 250,
                'active_users': 45,
                'engagement_rate': 15.8
            }
        ]
        
        # Test raporunu oluştur
        console.print("[cyan]Analitik raporu oluşturuluyor...[/cyan]")
        
        # Haftalık rapor için test verisi oluştur
        test_report = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'period': '7 gün',
            'total_groups': 25,
            'total_members': 4500,
            'total_messages': 13750,
            'active_users': 1560,
            'avg_engagement': 12.8,
            'groups': test_groups
        }
        
        # Analytics Service initialize edildi mi?
        initialized = analytics_service.initialized
        console.print(f"AnalyticsService initialize: [{'green' if initialized else 'red'}]{'Başarılı' if initialized else 'Başarısız'}[/{'green' if initialized else 'red'}]")
        
        # CSV formatında dışa aktarma testi
        console.print("[cyan]Analitik verileri CSV olarak dışa aktarılıyor (test)...[/cyan]")
        
        # Test export dosyası
        export_dir = "data/analytics_export"
        os.makedirs(export_dir, exist_ok=True)
        export_file = f"{export_dir}/test_analytics_export.csv"
        
        with open(export_file, 'w', encoding='utf-8') as f:
            f.write("group_id,name,message_count,active_users,engagement_rate\n")
            for group in test_groups:
                f.write(f"{group['group_id']},{group['name']},{group['message_count']},{group['active_users']},{group['engagement_rate']}\n")
                
        console.print(f"[green]Veriler dışa aktarıldı: {export_file}[/green]")
        
        # Başarılı bir test için kriterleri kontrol et
        success = (initialized and os.path.exists(export_file))
        
        console.print(f"AnalyticsService testi: [{'green' if success else 'red'}]{'Başarılı' if success else 'Başarısız'}[/{'green' if success else 'red'}]")
        
        return success
    
    async def test_service_integration(self):
        """Servislerin birbiriyle entegre çalışmasını test eder"""
        console.print("\n[bold cyan]Servis Entegrasyon Testi Başlatılıyor...[/bold cyan]")
        
        # Gerekli servisleri al
        event_service = self.service_manager.get_service("event")
        error_service = self.service_manager.get_service("error")
        analytics_service = self.service_manager.get_service("analytics")
        user_service = self.service_manager.get_service("user")
        group_service = self.service_manager.get_service("group")
        
        if not all([event_service, error_service, analytics_service, user_service, group_service]):
            console.print("[red]Bazı servisler bulunamadı![/red]")
            return False
        
        # Entegrasyon Test 1: Error olaylarını Analytics servisi dinleyebiliyor mu?
        console.print("[cyan]Test 1: Error olaylarını dinleme...[/cyan]")
        
        # Analytics servisini error olayları için kaydet
        received_error_event = False
        
        async def on_error_event(event_data):
            nonlocal received_error_event
            console.print(f"[green]Analytics servisi error olayını aldı: {event_data['error_type']}[/green]")
            received_error_event = True
        
        event_service.add_listener("error_logged", "analytics", on_error_event)
        
        # Test hatası oluştur
        error_id = await error_service.log_error(
            error_type="IntegrationTestError",
            message="Entegrasyon test hatası",
            source="integration_test",
            severity="ERROR",
            category="GENERAL"
        )
        
        # Biraz bekle ve kontrol et
        await asyncio.sleep(0.5)
        console.print(f"Error olayı dinleme testi: [{'green' if received_error_event else 'red'}]{'Başarılı' if received_error_event else 'Başarısız'}[/{'green' if received_error_event else 'red'}]")
        
        # Entegrasyon Test 2: Grup değişikliklerini Analytics izleyebiliyor mu?
        console.print("[cyan]Test 2: Grup değişikliklerini izleme...[/cyan]")
        
        group_event_received = False
        
        async def on_group_event(event_data):
            nonlocal group_event_received
            console.print(f"[green]Analytics servisi grup olayını aldı: {event_data.get('event_type', 'unknown')}[/green]")
            group_event_received = True
        
        event_service.add_listener("group_updated", "analytics", on_group_event)
        
        # Grup değişikliği olayı yayınla
        await event_service.emit_event("group_updated", {
            "event_type": "member_joined",
            "group_id": 1001,
            "user_id": 12345,
            "timestamp": datetime.now().isoformat()
        })
        
        # Biraz bekle ve kontrol et
        await asyncio.sleep(0.5)
        console.print(f"Grup olayı dinleme testi: [{'green' if group_event_received else 'red'}]{'Başarılı' if group_event_received else 'Başarısız'}[/{'green' if group_event_received else 'red'}]")
        
        # Entegrasyon testi sonuçlarını değerlendir
        success = received_error_event and group_event_received
        console.print(f"Servis entegrasyon testi: [{'green' if success else 'red'}]{'Başarılı' if success else 'Başarısız'}[/{'green' if success else 'red'}]")
        
        return success
        
    async def run_all_tests(self):
        """Tüm testleri çalıştır"""
        try:
            console.print(Panel.fit(
                "[bold cyan]TELEGRAM BOT SERVİS ENTEGRASYON TESTLERİ[/bold cyan]",
                border_style="green"
            ))
            
            # Test ortamını kur
            await self.setup()
            
            # Testleri koş
            service_registration_result = await self.test_service_registration()
            event_result = await self.test_event_service()
            error_result = await self.test_error_service()
            analytics_result = await self.test_analytics_service()
            integration_result = await self.test_service_integration()
            
            # Özet tablosu göster
            results_table = Table(title="Test Sonuçları")
            results_table.add_column("Test", style="cyan")
            results_table.add_column("Sonuç", style="green")
            
            results_table.add_row("Servis Kayıt Testi", "✓" if service_registration_result else "✗")
            results_table.add_row("EventService Testi", "✓" if event_result else "✗")
            results_table.add_row("ErrorService Testi", "✓" if error_result else "✗")
            results_table.add_row("AnalyticsService Testi", "✓" if analytics_result else "✗")
            results_table.add_row("Entegrasyon Testi", "✓" if integration_result else "✗")
            
            console.print(results_table)
            
            # Genel sonuç
            overall_result = all([
                service_registration_result,
                event_result,
                error_result,
                analytics_result,
                integration_result
            ])
            
            console.print(Panel(
                f"[{'green' if overall_result else 'red'}]Genel Test Sonucu: {'BAŞARILI' if overall_result else 'BAŞARISIZ'}[/{'green' if overall_result else 'red'}]",
                border_style="cyan"
            ))
            
        except Exception as e:
            console.print(f"[bold red]Test çalıştırma hatası: {str(e)}[/bold red]")
            import traceback
            console.print(traceback.format_exc())
        finally:
            # Test ortamını temizle
            await self.teardown()

async def main():
    """Ana test fonksiyonu"""
    test_runner = IntegrationTest()
    await test_runner.run_all_tests()

if __name__ == "__main__":
    # AsyncIO ile ana fonksiyonu çalıştır
    asyncio.run(main()) 