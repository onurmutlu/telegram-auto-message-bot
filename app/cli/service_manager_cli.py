#!/usr/bin/env python
import asyncio
import logging
import sys
import os
import argparse
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

# Gerekli modülleri içe aktar
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.db.session import get_session, create_pool, close_pool
from app.services.service_manager import get_service_manager
from app.services.service_monitor import get_service_monitor
from app.core.config import settings

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('runtime/logs/service_cli.log')
    ]
)
logger = logging.getLogger(__name__)

class ServiceCLI:
    """
    Servis yönetimi için komut satırı arayüzü
    """
    
    def __init__(self):
        self.service_manager = None
        self.service_monitor = None
        self.db = None
    
    async def initialize(self):
        """Temel bileşenleri başlatır"""
        try:
            # Veritabanı bağlantısı kur
            await create_pool()
            self.db = next(get_session())
            
            # Servis yöneticisine bağlan
            self.service_manager = await get_service_manager(db=self.db)
            
            # Servis monitörüne bağlan
            self.service_monitor = await get_service_monitor(db=self.db)
            
            return True
        except Exception as e:
            logger.error(f"Başlatma hatası: {e}")
            return False
    
    async def list_services(self, args):
        """Tüm servisleri listeler"""
        if not self.service_manager:
            await self.initialize()
        
        print("\n=== SERVİS DURUMU ===")
        status = await self.service_manager.get_all_services_status()
        
        # Servis durumunu tablo olarak göster
        print(f"{'Servis Adı':<20} {'Durum':<10} {'Hata':<5} {'Çalışma Süresi':<15}")
        print("-" * 55)
        
        for name, info in status.items():
            running = "✓ Aktif" if info.get("running", False) else "✗ Pasif"
            error_count = info.get("error_count", 0)
            uptime = info.get("uptime", 0)
            
            # Süreyi formatla
            if uptime:
                hours, remainder = divmod(uptime, 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime_str = f"{int(hours)}s {int(minutes)}d {int(seconds)}s"
            else:
                uptime_str = "Çalışmıyor"
            
            print(f"{name:<20} {running:<10} {error_count:<5} {uptime_str:<15}")
        
        print(f"\nToplam {len(status)} servis, {sum(1 for s in status.values() if s.get('running', False))} aktif")
    
    async def service_details(self, args):
        """Belirli bir servisin detaylarını gösterir"""
        if not self.service_monitor:
            await self.initialize()
        
        service_name = args.service_name
        details = await self.service_monitor.get_service_details(service_name)
        
        if "error" in details:
            print(f"Hata: {details['error']}")
            return
        
        print(f"\n=== {service_name.upper()} SERVİS DETAYI ===")
        
        # Durum bilgisini göster
        status = details.get("status", {})
        print(f"Durum          : {'Aktif' if status.get('running', False) else 'Pasif'}")
        print(f"Başlatılmış    : {'Evet' if status.get('initialized', False) else 'Hayır'}")
        print(f"Hata Sayısı    : {status.get('error_count', 0)}")
        
        # Çalışma süresi
        uptime = status.get("uptime", 0)
        if uptime:
            hours, remainder = divmod(uptime, 3600)
            minutes, seconds = divmod(remainder, 60)
            print(f"Çalışma Süresi : {int(hours)} saat {int(minutes)} dakika {int(seconds)} saniye")
        
        # Veritabanı durum bilgileri
        db_status = details.get("db_status", {})
        if db_status:
            print("\n--- Veritabanı Durum Bilgileri ---")
            print(f"Başlangıç      : {db_status.get('started_at', 'Bilinmiyor')}")
            print(f"Son Aktivite   : {db_status.get('last_active', 'Bilinmiyor')}")
            print(f"Durum          : {db_status.get('status', 'Bilinmiyor')}")
        
        # Yapılandırma bilgileri
        config = details.get("config", {})
        if config:
            print("\n--- Yapılandırma Bilgileri ---")
            print(f"{'Anahtar':<20} {'Değer':<20} {'Tip':<10}")
            print("-" * 50)
            
            for key, info in config.items():
                print(f"{key:<20} {info.get('value', ''):<20} {info.get('type', 'string'):<10}")
    
    async def start_service(self, args):
        """Belirli bir servisi başlatır"""
        if not self.service_manager:
            await self.initialize()
        
        service_name = args.service_name
        print(f"{service_name} servisi başlatılıyor...")
        
        result = await self.service_manager.restart_service(service_name)
        
        if result:
            print(f"{service_name} servisi başarıyla başlatıldı!")
        else:
            print(f"{service_name} servisi başlatılamadı.")
    
    async def stop_service(self, args):
        """Belirli bir servisi durdurur"""
        if not self.service_manager:
            await self.initialize()
        
        service_name = args.service_name
        print(f"{service_name} servisi durduruluyor...")
        
        # Servisi durdur
        try:
            if service_name in self.service_manager.services:
                service = self.service_manager.services[service_name]
                if hasattr(service, 'stop') and callable(service.stop):
                    await service.stop()
                    print(f"{service_name} servisi başarıyla durduruldu!")
                else:
                    print(f"{service_name} servisi durdurulamadı: stop metodu bulunamadı.")
            else:
                print(f"{service_name} servisi bulunamadı.")
        except Exception as e:
            print(f"{service_name} servisi durdurulurken hata oluştu: {e}")
    
    async def restart_service(self, args):
        """Belirli bir servisi yeniden başlatır"""
        if not self.service_manager:
            await self.initialize()
        
        service_name = args.service_name
        print(f"{service_name} servisi yeniden başlatılıyor...")
        
        result = await self.service_manager.restart_service(service_name)
        
        if result:
            print(f"{service_name} servisi başarıyla yeniden başlatıldı!")
        else:
            print(f"{service_name} servisi yeniden başlatılamadı.")
    
    async def start_all(self, args):
        """Tüm servisleri başlatır"""
        if not self.service_manager:
            await self.initialize()
        
        print("Tüm servisler başlatılıyor...")
        
        await self.service_manager.start_services()
        print("Tüm servisler başlatıldı!")
    
    async def stop_all(self, args):
        """Tüm servisleri durdurur"""
        if not self.service_manager:
            await self.initialize()
        
        print("Tüm servisler durduruluyor...")
        
        await self.service_manager.stop_services()
        print("Tüm servisler durduruldu!")
    
    async def monitor(self, args):
        """Servisleri gerçek zamanlı olarak izler"""
        if not self.service_monitor:
            await self.initialize()
        
        print("Servis izleme başlatılıyor (Çıkmak için Ctrl+C)...")
        
        await self.service_monitor.start()
        
        try:
            # Periyodik olarak durum bilgisini göster
            while True:
                # Ekranı temizle
                os.system('cls' if os.name == 'nt' else 'clear')
                
                # Zaman göster
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"=== SERVİS İZLEME ({now}) ===")
                
                # Tüm servislerin durumunu al
                status = await self.service_manager.get_all_services_status()
                
                # Servis durumunu tablo olarak göster
                print(f"{'Servis Adı':<20} {'Durum':<10} {'Hata':<5} {'Çalışma Süresi':<15}")
                print("-" * 55)
                
                for name, info in status.items():
                    running = "✓ Aktif" if info.get("running", False) else "✗ Pasif"
                    error_count = info.get("error_count", 0)
                    uptime = info.get("uptime", 0)
                    
                    # Süreyi formatla
                    if uptime:
                        hours, remainder = divmod(uptime, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        uptime_str = f"{int(hours)}s {int(minutes)}d {int(seconds)}s"
                    else:
                        uptime_str = "Çalışmıyor"
                    
                    print(f"{name:<20} {running:<10} {error_count:<5} {uptime_str:<15}")
                
                print(f"\nToplam {len(status)} servis, {sum(1 for s in status.values() if s.get('running', False))} aktif")
                print("\nİzleme çalışıyor... (Çıkmak için CTRL+C)")
                
                # Bekleme
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            print("\nİzleme durduruluyor...")
        finally:
            await self.service_monitor.stop()
            print("İzleme durduruldu.")
    
    async def set_config(self, args):
        """Servis yapılandırmasını değiştirir"""
        if not self.service_monitor:
            await self.initialize()
        
        service_name = args.service_name
        key = args.key
        value = args.value
        
        print(f"{service_name} servisi için {key} değeri ayarlanıyor...")
        
        result = await self.service_monitor.update_service_config(service_name, key, value)
        
        if result.get("success", False):
            print(f"Başarılı: {result.get('message')}")
        else:
            print(f"Hata: {result.get('error', 'Bilinmeyen hata')}")

async def main():
    """Ana uygulama giriş noktası"""
    parser = argparse.ArgumentParser(description="Telegram Bot Servis Yönetim Aracı")
    subparsers = parser.add_subparsers(dest="command", help="Alt komutlar")
    
    # Liste komutu
    list_parser = subparsers.add_parser("list", help="Tüm servisleri listele")
    
    # Detay komutu
    detail_parser = subparsers.add_parser("detail", help="Servis detaylarını göster")
    detail_parser.add_argument("service_name", help="Servis adı")
    
    # Başlat komutu
    start_parser = subparsers.add_parser("start", help="Servisi başlat")
    start_parser.add_argument("service_name", help="Servis adı")
    
    # Durdur komutu
    stop_parser = subparsers.add_parser("stop", help="Servisi durdur")
    stop_parser.add_argument("service_name", help="Servis adı")
    
    # Yeniden başlat komutu
    restart_parser = subparsers.add_parser("restart", help="Servisi yeniden başlat")
    restart_parser.add_argument("service_name", help="Servis adı")
    
    # Tümünü başlat komutu
    start_all_parser = subparsers.add_parser("start-all", help="Tüm servisleri başlat")
    
    # Tümünü durdur komutu
    stop_all_parser = subparsers.add_parser("stop-all", help="Tüm servisleri durdur")
    
    # İzleme komutu
    monitor_parser = subparsers.add_parser("monitor", help="Servisleri gerçek zamanlı izle")
    
    # Yapılandırma komutu
    config_parser = subparsers.add_parser("config", help="Servis yapılandırmasını değiştir")
    config_parser.add_argument("service_name", help="Servis adı")
    config_parser.add_argument("key", help="Yapılandırma anahtarı")
    config_parser.add_argument("value", help="Yapılandırma değeri")
    
    args = parser.parse_args()
    
    cli = ServiceCLI()
    
    # Komutlara göre fonksiyonları çağır
    if args.command == "list":
        await cli.list_services(args)
    elif args.command == "detail":
        await cli.service_details(args)
    elif args.command == "start":
        await cli.start_service(args)
    elif args.command == "stop":
        await cli.stop_service(args)
    elif args.command == "restart":
        await cli.restart_service(args)
    elif args.command == "start-all":
        await cli.start_all(args)
    elif args.command == "stop-all":
        await cli.stop_all(args)
    elif args.command == "monitor":
        await cli.monitor(args)
    elif args.command == "config":
        await cli.set_config(args)
    else:
        parser.print_help()
    
    # Veritabanı bağlantısını kapat
    await close_pool()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nUygulama kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Uygulama hatası: {e}", exc_info=True)
        sys.exit(1) 