"""
# ============================================================================ #
# Dosya: demo_service.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/demo_service.py
# İşlev: v3.9.0 özelliklerini test etmek için demo servisi.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
import random
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.services.base_service import BaseService
from app.db.async_connection_pool import get_db_pool, AsyncDbConnectionPool, transactional
from app.services.error_handling import ErrorManager, RetryStrategy, ServiceError, ResourceError
from app.services.error_handling.error_manager import retry, circuit_breaker

logger = logging.getLogger(__name__)

class DemoService(BaseService):
    """
    v3.9.0 özelliklerini test etmek için demo servisi.
    
    Bu servis:
    1. Asenkron veritabanı bağlantı havuzunu test eder
    2. Hata yönetimi ve kurtarma stratejilerini test eder
    3. Sağlık izleme ve metrik toplama sistemini test eder
    """
    
    service_name = "demo_service"
    default_interval = 60  # 60 saniyede bir çalıştır
    
    def __init__(self, **kwargs):
        """
        DemoService başlatıcısı.
        
        Args:
            **kwargs: BaseService parametreleri
        """
        super().__init__(**kwargs)
        
        # Durum izleme
        self.running = False
        self.error_rate = 0.2  # Hata oranı (%20)
        self.last_run = None
        self.total_runs = 0
        self.total_errors = 0
        self.last_error = None
        
        # Performans metrikleri
        self.operation_times = []
        self.avg_operation_time = 0
        self.max_operation_time = 0
        
        # Veritabanı havuzu
        self.db_pool = None
        
        # Hata yöneticisi
        self.error_manager = ErrorManager()
    
    async def _start(self) -> bool:
        """
        Demo servisini başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("Demo Servisi başlatılıyor...")
            
            # Asenkron DB havuzunu başlat
            self.db_pool = await get_db_pool(min_size=3, max_size=10)
            await self.db_pool.ping()
            
            # Test tablosunu oluştur (yoksa)
            await self._create_test_table()
            
            # Servis durumunu güncelle
            self.running = True
            logger.info("Demo Servisi başarıyla başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"Demo Servisi başlatma hatası: {str(e)}")
            self.last_error = str(e)
            self.total_errors += 1
            return False
    
    async def _stop(self) -> bool:
        """
        Demo servisini durdurur.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            logger.info("Demo Servisi durduruluyor...")
            
            # Veritabanı havuzunu kapat
            if self.db_pool:
                await self.db_pool.close()
            
            # Servis durumunu güncelle
            self.running = False
            logger.info("Demo Servisi durduruldu")
            return True
            
        except Exception as e:
            logger.error(f"Demo Servisi durdurma hatası: {str(e)}")
            self.last_error = str(e)
            self.total_errors += 1
            return False
    
    async def _update(self) -> None:
        """
        Periyodik güncelleme işlemi.
        Her çalıştığında bir dizi demo işlemi gerçekleştirir.
        """
        start_time = time.time()
        
        try:
            # Çalışma sayacını güncelle
            self.total_runs += 1
            self.last_run = datetime.now()
            
            # Demo işlemleri gerçekleştir
            await self._run_demo_tasks()
            
            # Performans metriklerini güncelle
            operation_time = time.time() - start_time
            self.operation_times.append(operation_time)
            
            # Son 10 çalışmanın ortalamasını al
            if len(self.operation_times) > 10:
                self.operation_times = self.operation_times[-10:]
            
            self.avg_operation_time = sum(self.operation_times) / len(self.operation_times)
            self.max_operation_time = max(self.operation_times)
            
        except Exception as e:
            # Hata durumunu güncelle
            self.total_errors += 1
            self.last_error = str(e)
            
            # Hatayı kaydet
            self.error_manager.log_error(e, service_name=self.service_name)
            logger.error(f"Demo Servisi güncelleme hatası: {str(e)}")
    
    async def _create_test_table(self) -> None:
        """Demo için test tablosu oluşturur."""
        query = """
        CREATE TABLE IF NOT EXISTS demo_metrics (
            id SERIAL PRIMARY KEY,
            metric_name VARCHAR(50) NOT NULL,
            metric_value FLOAT NOT NULL,
            recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        try:
            await self.db_pool.execute(query)
            logger.info("Demo test tablosu oluşturuldu veya zaten mevcut")
        except Exception as e:
            logger.error(f"Test tablosu oluşturma hatası: {str(e)}")
            raise
    
    async def _run_demo_tasks(self) -> None:
        """Çeşitli demo işlemleri çalıştırır."""
        logger.info("Demo işlemleri başlatılıyor...")
        
        # 1. Veritabanı işlemleri
        await self._test_database_operations()
        
        # 2. Retry mekanizması
        await self._test_retry_mechanism()
        
        # 3. Circuit breaker
        await self._test_circuit_breaker()
        
        logger.info("Demo işlemleri tamamlandı")
    
    async def _test_database_operations(self) -> None:
        """Veritabanı havuzunu ve işlemleri test eder."""
        try:
            # Paralel veritabanı işlemleri
            tasks = []
            for i in range(5):
                tasks.append(self._save_metric(f"test_metric_{i}", random.uniform(0, 100)))
            
            # Paralel işlemleri bekle
            await asyncio.gather(*tasks)
            
            # Transaction testi
            await self._transaction_demo()
            
            logger.info("Veritabanı işlemleri başarıyla tamamlandı")
            
        except Exception as e:
            logger.error(f"Veritabanı işlemleri sırasında hata: {str(e)}")
            raise
    
    @transactional
    async def _transaction_demo(self) -> None:
        """Transaction desteğini test eder."""
        # İlk kayıt ekle
        await self.db_pool.execute(
            "INSERT INTO demo_metrics (metric_name, metric_value, recorded_at) VALUES ($1, $2, $3)",
            "transaction_test_1", 42.0, datetime.now()
        )
        
        # Rastgele hata (test için)
        if random.random() < 0.1:  # %10 şansla hata
            raise ResourceError(
                message="Transaction test hatası (beklenen)",
                resource_type="database",
                service_name=self.service_name
            )
        
        # İkinci kayıt ekle
        await self.db_pool.execute(
            "INSERT INTO demo_metrics (metric_name, metric_value, recorded_at) VALUES ($1, $2, $3)",
            "transaction_test_2", 43.0, datetime.now()
        )
    
    async def _save_metric(self, name: str, value: float) -> None:
        """Metrik değerini veritabanına kaydeder."""
        query = """
        INSERT INTO demo_metrics (metric_name, metric_value, recorded_at)
        VALUES ($1, $2, $3)
        """
        
        await self.db_pool.execute(query, name, value, datetime.now())
    
    @retry(max_attempts=3, retry_strategy=RetryStrategy.EXPONENTIAL)
    async def _test_retry_mechanism(self) -> None:
        """Retry mekanizmasını test eder."""
        # Rastgele hata (test için)
        if random.random() < self.error_rate:
            logger.warning("Retry testi için rastgele hata oluşturuluyor...")
            raise ServiceError(
                message="Retry test hatası (beklenen)",
                details={"test": True, "retry": True},
                service_name=self.service_name,
                retriable=True
            )
        
        # Başarılı işlem
        logger.info("Retry mekanizması testi başarılı")
    
    @circuit_breaker(failure_threshold=3, recovery_timeout=10.0)
    async def _test_circuit_breaker(self) -> None:
        """Circuit breaker mekanizmasını test eder."""
        # Rastgele hata (test için) - yüksek hata oranı
        if random.random() < self.error_rate * 2:  # Daha yüksek hata oranı
            logger.warning("Circuit breaker testi için rastgele hata oluşturuluyor...")
            raise ServiceError(
                message="Circuit breaker test hatası (beklenen)",
                details={"test": True, "circuit_breaker": True},
                service_name=self.service_name
            )
        
        # Başarılı işlem
        logger.info("Circuit breaker mekanizması testi başarılı")
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servis durum bilgilerini döndürür.
        
        Returns:
            Dict[str, Any]: Durum bilgileri
        """
        # Circuit breaker durumunu al
        cb_state = None
        if self.service_name in self.error_manager.circuit_breakers:
            cb = self.error_manager.circuit_breakers[self.service_name]
            cb_state = cb.get_state()
        
        # Durum bilgilerini döndür
        return {
            'service': self.service_name,
            'running': self.running,
            'total_runs': self.total_runs,
            'total_errors': self.total_errors,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'last_error': self.last_error,
            'error_rate': self.error_rate,
            'avg_operation_time': self.avg_operation_time,
            'max_operation_time': self.max_operation_time,
            'circuit_breaker': cb_state
        }
    
    async def get_db_stats(self) -> Dict[str, Any]:
        """
        Veritabanı istatistiklerini döndürür.
        
        Returns:
            Dict[str, Any]: Veritabanı istatistikleri
        """
        if not self.db_pool:
            return {"error": "Veritabanı havuzu başlatılmadı"}
        
        try:
            # DB havuzu istatistiklerini al
            db_stats = await self.db_pool.get_stats()
            
            # Son kaydedilen metrikleri al
            metrics = await self.db_pool.fetch(
                "SELECT * FROM demo_metrics ORDER BY recorded_at DESC LIMIT 5"
            )
            
            return {
                "pool_stats": db_stats,
                "recent_metrics": [
                    {
                        "id": m["id"],
                        "name": m["metric_name"],
                        "value": m["metric_value"],
                        "recorded_at": m["recorded_at"].isoformat()
                    }
                    for m in metrics
                ]
            }
            
        except Exception as e:
            logger.error(f"Veritabanı istatistikleri alınırken hata: {str(e)}")
            return {"error": str(e)}
    
    async def set_error_rate(self, rate: float) -> None:
        """
        Test amaçlı hata oranını ayarlar.
        
        Args:
            rate: 0.0 ile 1.0 arasında hata oranı
        """
        self.error_rate = max(0.0, min(1.0, rate))
        logger.info(f"Hata oranı ayarlandı: {self.error_rate:.2f}")
    
    async def force_error(self, error_type: str = "service") -> None:
        """
        Test amaçlı hata oluşturur.
        
        Args:
            error_type: Hata türü
        """
        if error_type == "service":
            raise ServiceError(
                message="Manuel oluşturulan servis hatası",
                service_name=self.service_name,
                details={"manual": True}
            )
        elif error_type == "resource":
            raise ResourceError(
                message="Manuel oluşturulan kaynak hatası",
                resource_type="database",
                service_name=self.service_name,
                details={"manual": True}
            )
        else:
            raise Exception(f"Manuel oluşturulan genel hata: {error_type}")

async def run_demo():
    """Demo servisi test çalıştırması"""
    # Log ayarları
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Demo servisi test ediliyor...")
    
    try:
        # DB Havuzunu başlat
        from app.db.async_connection_pool import AsyncDbConnectionPool
        db_pool = AsyncDbConnectionPool()
        await db_pool.initialize(min_size=2, max_size=5)
        
        # Demo servisi oluştur
        demo = DemoService()
        demo.db_pool = db_pool
        
        # Servisi başlat
        await demo._start()
    
        # Demo işlemlerini çalıştır
        print("Demo işlemleri başlatılıyor...")
        await demo._update()
        
        # Durum bilgisi al
        status = await demo.get_status()
        print("\nDemo servisi durumu:")
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        # DB istatistikleri al
        db_stats = await demo.get_db_stats()
        print("\nVeritabanı istatistikleri:")
        if "error" in db_stats:
            print(f"  Hata: {db_stats['error']}")
        else:
            print("  Havuz istatistikleri:")
            for key, value in db_stats["pool_stats"].items():
                print(f"    {key}: {value}")
            
            print("\n  Son metrikler:")
            for metric in db_stats.get("recent_metrics", []):
                print(f"    {metric['name']}: {metric['value']} ({metric['recorded_at']})")
    
    except Exception as e:
        print(f"Demo çalıştırma hatası: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Servisi durdur
        if 'demo' in locals():
            print("\nDemo servisi durduruluyor...")
            await demo._stop()
            print("Demo servisi durduruldu.")

# Doğrudan çalıştırma durumunda
if __name__ == "__main__":
    asyncio.run(run_demo()) 