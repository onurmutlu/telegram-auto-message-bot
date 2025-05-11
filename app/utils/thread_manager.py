"""
# ============================================================================ #
# Dosya: thread_manager.py
# Yol: /Users/siyahkare/code/telegram-bot/utils/thread_manager.py
# İşlev: Telegram bot bileşeni
#
# Build: 2025-04-01-00:07:55
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, Telegram bot uygulamasının bileşenlerinden biridir.
# - İlgili servislere entegrasyon
# - Hata yönetimi ve loglama
# - Asenkron işlem desteği
#
# ============================================================================ #
"""
import threading
import logging
import time
import queue
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class ThreadManager:
    """Bot servislerini yöneten thread manager sınıfı"""
    
    def __init__(self, max_workers=3):
        """
        Thread Manager'ı başlatır
        
        Args:
            max_workers: Maksimum worker thread sayısı
        """
        self.services = {}
        self.threads = {}
        self.stop_event = threading.Event()
        self.queue = queue.Queue()
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.event_loop = None
        logger.info(f"Thread Manager başlatıldı. Maksimum worker: {max_workers}")
    
    def register_service(self, name, service_class, priority=0, *args, **kwargs):
        """
        Yeni bir servisi kaydeder
        
        Args:
            name: Servis adı
            service_class: Servis sınıfı
            priority: Servis önceliği (düşük sayı = yüksek öncelik)
            *args, **kwargs: Servis sınıfına geçirilecek argümanlar
        """
        self.services[name] = {
            'class': service_class,
            'priority': priority,
            'args': args,
            'kwargs': kwargs,
            'instance': None
        }
        logger.debug(f"Servis kaydedildi: {name} (Öncelik: {priority})")
    
    def _create_event_loop(self):
        """Her thread için yeni bir event loop oluşturur"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop
    
    def _run_service(self, name, service_info):
        """Belirli bir servisi çalıştırır"""
        logger.info(f"🚀 '{name}' servisi başlatılıyor...")
        
        # Her thread için yeni bir event loop
        loop = self._create_event_loop()
        self.event_loop = loop
        
        # Servis örneğini oluştur
        service_class = service_info['class']
        args = service_info['args']
        kwargs = service_info['kwargs']
        
        # stop_event'i service'e geçir
        kwargs['stop_event'] = self.stop_event
        
        # Servisi başlat
        service = service_class(*args, **kwargs)
        service_info['instance'] = service
        
        try:
            # Servisin ana döngüsünü çalıştır
            loop.run_until_complete(service.run())
        except asyncio.CancelledError:
            logger.info(f"'{name}' servisi iptal edildi")
        except Exception as e:
            logger.error(f"'{name}' servisinde hata: {e}")
        finally:
            # Temizlik işlemleri
            pending = asyncio.all_tasks(loop=loop)
            for task in pending:
                task.cancel()
            
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
            logger.info(f"'{name}' servisi durduruldu")
    
    def start_all(self):
        """Tüm servisleri öncelik sırasına göre başlatır"""
        # Servisleri öncelik sırasına göre sırala
        sorted_services = sorted(
            self.services.items(), 
            key=lambda x: x[1]['priority']
        )
        
        # Tüm servisleri başlat
        for name, service_info in sorted_services:
            thread = threading.Thread(
                target=self._run_service,
                args=(name, service_info),
                name=f"Service-{name}"
            )
            thread.daemon = True
            self.threads[name] = thread
            thread.start()
            logger.info(f"'{name}' servis thread'i başlatıldı")
            # Her servis arasında kısa bir bekleme
            time.sleep(0.5)
    
    def stop_all(self):
        """Tüm servisleri durdurur"""
        logger.info("Tüm servisler durduruluyor...")
        self.stop_event.set()
        
        # Tüm threadleri bekle
        for name, thread in self.threads.items():
            logger.debug(f"'{name}' thread'i bekleniyor...")
            thread.join(timeout=3.0)  # 3 saniye bekle
            
        logger.info("✅ Tüm servisler durduruldu")
        
    def get_service(self, name):
        """Servis örneğini adına göre döndürür"""
        if name in self.services and self.services[name]['instance']:
            return self.services[name]['instance']
        return None

    def get_status(self):
        """Tüm servislerin durumunu döndürür"""
        status = {}
        for name, service_info in self.services.items():
            instance = service_info['instance']
            if instance:
                status[name] = instance.get_status()
            else:
                status[name] = {"status": "not_started"}
        return status