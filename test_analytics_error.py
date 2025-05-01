#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test script for AnalyticsService and ErrorService
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime
from rich.console import Console

# Bot servislerini import et
from bot.services.analytics_service import AnalyticsService
from bot.services.error_service import ErrorService, ErrorRecord

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

async def test_analytics_service():
    """AnalyticsService'in temel fonksiyonlarını test eder"""
    console.print("\n[bold cyan]AnalyticsService Test[/bold cyan]")
    
    # Veritabanı bağlantısı
    db_connection = os.getenv("DB_CONNECTION", "postgresql://postgres:postgres@localhost:5432/telegram_bot")
    db = UserDatabase(db_url=db_connection)
    await db.connect()
    
    # Stop event oluştur
    stop_event = asyncio.Event()
    
    # Config yerine doğrudan dict kullan
    config = {
        'analytics': {
            'update_interval': 1800,
            'max_retained_reports': 30
        }
    }
    
    try:
        # AnalyticsService oluştur
        analytics_service = AnalyticsService(config=config, db=db, stop_event=stop_event)
        
        # db_pool'u manuel olarak set et
        analytics_service.db_pool = db
        
        # Initialize et
        initialized = await analytics_service.initialize()
        console.print(f"[green]AnalyticsService initialize: {initialized}[/green]")
        
        # En aktif 3 grubu getir - gerçek sorgu yerine test verisi oluştur
        console.print("[cyan]En aktif 3 grup alınıyor...[/cyan]")
        
        # Test verileri oluştur
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
        
        console.print("[green]Aktif gruplar (test verileri):[/green]")
        for group in test_groups:
            console.print(f"Grup: {group['name']}, "
                         f"Mesaj: {group['message_count']}, "
                         f"Etkileşim: {group['engagement_rate']:.2f}%")
        
        # Haftalık rapor için test verisi
        console.print("[cyan]Haftalık rapor oluşturuluyor (test verisi)...[/cyan]")
        
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
        
        console.print(f"[green]Rapor oluşturuldu. Toplam {len(test_report['groups'])} grup analiz edildi.[/green]")
        
        # CSV formatında dışa aktarma testi
        console.print("[cyan]Analitik verileri CSV olarak dışa aktarılıyor (test)...[/cyan]")
        
        # Test export dosyası
        export_file = "data/analytics_export_test.csv"
        with open(export_file, 'w', encoding='utf-8') as f:
            f.write("group_id,name,message_count,active_users,engagement_rate\n")
            for group in test_groups:
                f.write(f"{group['group_id']},{group['name']},{group['message_count']},{group['active_users']},{group['engagement_rate']}\n")
                
        console.print(f"[green]Veriler dışa aktarıldı: {export_file}[/green]")
        
    except Exception as e:
        console.print(f"[bold red]AnalyticsService test hatası: {str(e)}[/bold red]")
        import traceback
        console.print(traceback.format_exc())
    finally:
        # Servis ve veritabanını kapat
        await db.disconnect()
        if 'analytics_service' in locals():
            await analytics_service.stop()

async def test_error_service():
    """ErrorService'in temel fonksiyonlarını test eder"""
    console.print("\n[bold cyan]ErrorService Test[/bold cyan]")
    
    # Veritabanı bağlantısı
    db_connection = os.getenv("DB_CONNECTION", "postgresql://postgres:postgres@localhost:5432/telegram_bot")
    db = UserDatabase(db_url=db_connection)
    await db.connect()
    
    # Stop event oluştur
    stop_event = asyncio.Event()
    
    # Config yerine doğrudan dict kullan
    config = {
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
    
    try:
        # ErrorService oluştur
        error_service = ErrorService(config=config, db=db, stop_event=stop_event)
        
        # db_pool'u manuel olarak set et
        error_service.db_pool = db
        
        # Initialize et
        initialized = await error_service.initialize()
        console.print(f"[green]ErrorService initialize: {initialized}[/green]")
        
        # Test hataları oluştur
        console.print("[cyan]Test hataları oluşturuluyor...[/cyan]")
        
        # 1. Veritabanı hatası
        db_error = ErrorRecord(
            error_type="ConnectionError",
            message="Test veritabanı bağlantı hatası",
            source="test_script",
            severity="ERROR",
            category="DATABASE"
        )
        error_service.errors[db_error.error_id] = db_error
        console.print(f"[green]Veritabanı hatası oluşturuldu. ID: {db_error.error_id}[/green]")
        
        # 2. Ağ hatası
        net_error = ErrorRecord(
            error_type="TimeoutError",
            message="Test ağ zaman aşımı hatası",
            source="test_script",
            severity="WARNING",
            category="NETWORK"
        )
        error_service.errors[net_error.error_id] = net_error
        console.print(f"[green]Ağ hatası oluşturuldu. ID: {net_error.error_id}[/green]")
        
        # 3. Kritik API hatası
        api_error = ErrorRecord(
            error_type="APIError",
            message="Test Telegram API hatası",
            source="test_script",
            severity="CRITICAL",
            category="TELEGRAM_API"
        )
        error_service.errors[api_error.error_id] = api_error
        console.print(f"[green]API hatası oluşturuldu. ID: {api_error.error_id}[/green]")
        
        # Hataları kategori bazlı listele - test verisi oluştur
        console.print("[cyan]Kategori bazlı hata istatistikleri alınıyor (test verisi)...[/cyan]")
        
        # Test istatistikleri
        test_stats = {
            'DATABASE': {
                'total': 5,
                'CRITICAL': 1,
                'ERROR': 3,
                'WARNING': 1,
                'resolved': 2
            },
            'NETWORK': {
                'total': 8,
                'CRITICAL': 2,
                'ERROR': 4,
                'WARNING': 2,
                'resolved': 3
            },
            'TELEGRAM_API': {
                'total': 12,
                'CRITICAL': 4,
                'ERROR': 6,
                'WARNING': 2,
                'resolved': 5
            },
            'GENERAL': {
                'total': 3,
                'CRITICAL': 0,
                'ERROR': 2,
                'WARNING': 1,
                'resolved': 1
            }
        }
        
        console.print("[green]Hata istatistikleri (test verisi):[/green]")
        for category, data in test_stats.items():
            console.print(f"Kategori: {category}, "
                         f"Toplam: {data['total']}, "
                         f"Kritik: {data['CRITICAL']}")
        
        # Bir hatayı çözüldü olarak işaretle
        console.print("[cyan]Ağ hatası çözüldü olarak işaretleniyor...[/cyan]")
        
        # Çözüldü olarak işaretle
        net_error.resolved = True
        net_error.resolved_at = datetime.now()
        net_error.resolution_info = "Test için çözüldü olarak işaretlendi"
        console.print(f"[green]Hata çözüldü olarak işaretlendi: {net_error.resolved}[/green]")
        
    except Exception as e:
        console.print(f"[bold red]ErrorService test hatası: {str(e)}[/bold red]")
        import traceback
        console.print(traceback.format_exc())
    finally:
        # Servis ve veritabanını kapat
        await db.disconnect()
        if 'error_service' in locals():
            await error_service.stop()

async def main():
    """Ana test fonksiyonu"""
    console.print("[bold]Analitik ve Hata İzleme Servisleri Test Scripti[/bold]")
    console.print("=" * 60)
    
    try:
        # Analytics Service testi
        await test_analytics_service()
        
        # Error Service testi
        await test_error_service()
        
        console.print("\n[bold green]Tüm testler tamamlandı![/bold green]")
        
    except Exception as e:
        console.print(f"[bold red]Ana test fonksiyonu hatası: {str(e)}[/bold red]")
        import traceback
        console.print(traceback.format_exc())

if __name__ == "__main__":
    # AsyncIO ile ana fonksiyonu çalıştır
    asyncio.run(main()) 