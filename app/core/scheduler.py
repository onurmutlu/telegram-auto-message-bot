"""
# ============================================================================ #
# Dosya: scheduler.py
# Yol: /Users/siyahkare/code/telegram-bot/app/core/scheduler.py
# İşlev: Merkezi zamanlayıcı yönetimi.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import logging
from typing import Dict, Any, Optional, Callable, Union, List
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AsyncScheduler:
    """
    APScheduler tabanlı asenkron zamanlayıcı sınıfı.
    Görevleri düzenli aralıklarla, belirli bir tarifede veya belirli bir tarihte çalıştırır.
    """
    
    def __init__(self):
        """Zamanlayıcıyı başlatır."""
        
        # Zamanlayıcı yapılandırması
        jobstores = {
            'default': MemoryJobStore()  # Varsayılan olarak bellek tabanlı görev deposu
        }
        
        executors = {
            'default': AsyncIOExecutor()  # Asenkron executor
        }
        
        job_defaults = {
            'coalesce': True,  # Kaçırılan görevleri birleştir
            'max_instances': 3,  # Aynı görevin maksimum eşzamanlı çalışma sayısı
            'misfire_grace_time': 60  # Kaçırılan görevleri çalıştırmak için izin verilen maksimum gecikme (saniye)
        }
        
        # Zamanlayıcıyı oluştur
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults
        )
        
        # Zamanlayıcı durumu
        self.started = False
        self.job_ids = []
        
        logger.info("Asenkron zamanlayıcı oluşturuldu")
        
    async def start(self) -> None:
        """Zamanlayıcıyı başlatır."""
        if not self.started:
            self.scheduler.start()
            self.started = True
            logger.info("Asenkron zamanlayıcı başlatıldı")
        else:
            logger.warning("Zamanlayıcı zaten çalışıyor")
            
    async def shutdown(self, wait: bool = True) -> None:
        """
        Zamanlayıcıyı kapatır.
        
        Args:
            wait: True ise, çalışan görevlerin tamamlanmasını bekler
        """
        if self.started:
            self.scheduler.shutdown(wait=wait)
            self.started = False
            logger.info("Asenkron zamanlayıcı kapatıldı")
        else:
            logger.warning("Zamanlayıcı zaten durmuş")
            
    def _check_started(self) -> None:
        """Zamanlayıcının başlatılıp başlatılmadığını kontrol eder."""
        if not self.started:
            logger.warning("Zamanlayıcı henüz başlatılmadı, otomatik başlatılıyor")
            loop = asyncio.get_event_loop()
            loop.create_task(self.start())
            
    async def add_interval_job(
        self, 
        func: Callable, 
        seconds: int = 0, 
        minutes: int = 0, 
        hours: int = 0, 
        job_id: Optional[str] = None
    ) -> str:
        """
        Belirli aralıklarla çalışacak bir görev ekler.
        
        Args:
            func: Çalıştırılacak fonksiyon
            seconds: Saniye cinsinden aralık
            minutes: Dakika cinsinden aralık
            hours: Saat cinsinden aralık
            job_id: Görev benzersiz kimliği
            
        Returns:
            str: Görev ID'si
        """
        self._check_started()
        
        # Varsayılan bir job_id oluştur
        if job_id is None:
            job_id = f"interval_{func.__name__}_{len(self.job_ids)}"
            
        # Görevi zamanlayıcıya ekle
        job = self.scheduler.add_job(
            func,
            'interval',
            seconds=seconds,
            minutes=minutes,
            hours=hours,
            id=job_id
        )
        
        self.job_ids.append(job_id)
        logger.info(f"Aralık görevi eklendi: {job_id} (her {seconds}s, {minutes}m, {hours}h)")
        return job_id
    
    async def add_cron_job(
        self, 
        func: Callable, 
        minute: Optional[Union[int, str]] = None,
        hour: Optional[Union[int, str]] = None, 
        day: Optional[Union[int, str]] = None, 
        month: Optional[Union[int, str]] = None, 
        day_of_week: Optional[Union[int, str]] = None,
        job_id: Optional[str] = None
    ) -> str:
        """
        Cron formatında belirtilen bir tarifede çalışacak görev ekler.
        
        Args:
            func: Çalıştırılacak fonksiyon
            minute: Dakika (0-59)
            hour: Saat (0-23)
            day: Gün (1-31)
            month: Ay (1-12)
            day_of_week: Haftanın günü (0-6 veya mon,tue,wed,thu,fri,sat,sun)
            job_id: Görev benzersiz kimliği
            
        Returns:
            str: Görev ID'si
        """
        self._check_started()
        
        # Varsayılan bir job_id oluştur
        if job_id is None:
            job_id = f"cron_{func.__name__}_{len(self.job_ids)}"
            
        # Görevi zamanlayıcıya ekle
        job = self.scheduler.add_job(
            func,
            'cron',
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            id=job_id
        )
        
        self.job_ids.append(job_id)
        cron_exp = f"{minute} {hour} {day} {month} {day_of_week}"
        logger.info(f"Cron görevi eklendi: {job_id} ({cron_exp})")
        return job_id
        
    async def add_date_job(
        self, 
        func: Callable, 
        run_date: datetime,
        job_id: Optional[str] = None
    ) -> str:
        """
        Belirtilen bir tarihte bir kez çalışacak görev ekler.
        
        Args:
            func: Çalıştırılacak fonksiyon
            run_date: Çalıştırılacak tarih
            job_id: Görev benzersiz kimliği
            
        Returns:
            str: Görev ID'si
        """
        self._check_started()
        
        # Varsayılan bir job_id oluştur
        if job_id is None:
            job_id = f"date_{func.__name__}_{len(self.job_ids)}"
            
        # Görevi zamanlayıcıya ekle
        job = self.scheduler.add_job(
            func,
            'date',
            run_date=run_date,
            id=job_id
        )
        
        self.job_ids.append(job_id)
        logger.info(f"Tarih görevi eklendi: {job_id} ({run_date.isoformat()})")
        return job_id
        
    def remove_job(self, job_id: str) -> bool:
        """
        Belirtilen ID'ye sahip görevi kaldırır.
        
        Args:
            job_id: Kaldırılacak görevin ID'si
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self.job_ids:
                self.job_ids.remove(job_id)
            logger.info(f"Görev kaldırıldı: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Görev kaldırılırken hata: {str(e)}")
            return False
            
    def get_jobs(self) -> List[Dict[str, Any]]:
        """
        Tüm görevleri döndürür.
        
        Returns:
            List[Dict[str, Any]]: Görev listesi
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            job_info = {
                'id': job.id,
                'name': job.name,
                'trigger': str(job.trigger),
                'next_run_time': job.next_run_time
            }
            jobs.append(job_info)
        return jobs
        
    def pause_job(self, job_id: str) -> bool:
        """
        Belirtilen ID'ye sahip görevi duraklatır.
        
        Args:
            job_id: Duraklatılacak görevin ID'si
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"Görev duraklatıldı: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Görev duraklatılırken hata: {str(e)}")
            return False
            
    def resume_job(self, job_id: str) -> bool:
        """
        Belirtilen ID'ye sahip duraklatılmış görevi devam ettirir.
        
        Args:
            job_id: Devam ettirilecek görevin ID'si
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"Görev devam ettiriliyor: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Görev devam ettirilirken hata: {str(e)}")
            return False

# Tekil zamanlayıcı örneği oluştur
scheduler = AsyncScheduler()