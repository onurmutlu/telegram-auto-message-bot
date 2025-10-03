#!/usr/bin/env python
import asyncio
import os
import sys
import signal
import logging
from datetime import datetime

# Proje kök dizinini Python path'e ekleyelim
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.service_monitor import get_service_monitor
from app.db.session import create_pool, close_pool

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('runtime/logs/service_monitor.log')
    ]
)
logger = logging.getLogger(__name__)

async def display_services():
    """Servisleri gerçek zamanlı olarak görüntüle"""
    try:
        # Veritabanını başlat
        await create_pool()
        
        # Monitör servisini al
        monitor = await get_service_monitor()
        await monitor.start()
        
        # Sinyalleri işle
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(monitor, sig)))
        
        logger.info("Servis monitörü başladı. Çıkmak için Ctrl+C'ye basın.")
        
        # Periyodik olarak ekranı güncelle
        try:
            while True:
                # Ekranı temizle
                os.system('cls' if os.name == 'nt' else 'clear')
                
                # Başlık
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"=== TELEGRAM BOT SERVİS İZLEME ({now}) ===")
                print("Çıkmak için CTRL+C'ye basın.")
                print()
                
                # Servis durumlarını al
                service_manager = monitor.service_manager
                if service_manager:
                    statuses = await service_manager.get_all_services_status()
                    
                    # Tablo başlığı
                    print(f"{'Servis Adı':<20} {'Durum':<10} {'Hata Sayısı':<12} {'Çalışma Süresi':<15}")
                    print("-" * 60)
                    
                    # Servis bilgilerini yazdır
                    for name, status in statuses.items():
                        running = "✓ Aktif" if status.get('running', False) else "✗ Pasif"
                        error_count = status.get('error_count', 0)
                        uptime = status.get('uptime', 0)
                        
                        # Süreyi formatla
                        if uptime:
                            hours, remainder = divmod(uptime, 3600)
                            minutes, seconds = divmod(remainder, 60)
                            uptime_str = f"{int(hours)}s {int(minutes)}d {int(seconds)}s"
                        else:
                            uptime_str = "Çalışmıyor"
                            
                        print(f"{name:<20} {running:<10} {error_count:<12} {uptime_str:<15}")
                    
                    # Özet bilgi
                    total = len(statuses)
                    active = sum(1 for s in statuses.values() if s.get('running', False))
                    inactive = total - active
                    print()
                    print(f"Toplam {total} servis: {active} aktif, {inactive} pasif")
                else:
                    print("Servis yöneticisi henüz başlatılmadı.")
                
                # Biraz bekle
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            pass
            
    except Exception as e:
        logger.error(f"Servis monitörü hatası: {e}")
    finally:
        # Temizlik işlemleri
        if 'monitor' in locals():
            await monitor.stop()
        await close_pool()
        logger.info("Servis monitörü kapatıldı.")

async def shutdown(monitor, sig=None):
    """Uygulamayı düzgünce kapat"""
    if sig:
        logger.info(f"Sinyal alındı: {sig.name}, kapatılıyor...")
    
    # Tüm görevleri iptal et
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    logger.info(f"{len(tasks)} görev iptal edildi.")
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Monitörü durdur
    await monitor.stop()
    
    # Döngüyü durdur
    loop = asyncio.get_running_loop()
    loop.stop()

if __name__ == "__main__":
    try:
        asyncio.run(display_services())
    except KeyboardInterrupt:
        print("\nUygulama kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.error(f"Uygulama hatası: {e}", exc_info=True)
        sys.exit(1) 