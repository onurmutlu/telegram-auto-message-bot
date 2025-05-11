"""
# ============================================================================ #
# Dosya: error_manager.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/error_handling/error_manager.py
# İşlev: Merkezi hata yönetimi ve kurtarma stratejileri.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Awaitable, Type, Union, Tuple
from enum import Enum
from functools import wraps

from app.services.error_handling.exceptions import ServiceError

logger = logging.getLogger(__name__)

class RetryStrategy(Enum):
    """Yeniden deneme stratejileri"""
    FIXED = "fixed"            # Sabit bekleme süresi
    LINEAR = "linear"          # Doğrusal artan bekleme süresi
    EXPONENTIAL = "exponential"  # Üstel artan bekleme süresi
    RANDOM = "random"          # Rastgele bekleme süresi


class CircuitState(Enum):
    """Devre kesici durumları"""
    CLOSED = "closed"      # Normal çalışma durumu
    OPEN = "open"          # Hata durumu (istekler geçirilmez)
    HALF_OPEN = "half_open"  # Deneme durumu


class CircuitBreaker:
    """
    Devre kesici deseni uygulaması.
    
    Belirli hata eşiklerini aşan işlemleri durdurarak,
    sistemin daha fazla zarar görmesini engeller ve
    otomatik olarak kurtarma dener.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_success_threshold: int = 2,
        error_types: Optional[List[Type[Exception]]] = None
    ):
        """
        CircuitBreaker başlatıcısı.
        
        Args:
            failure_threshold: Devreyi açmak için gereken arka arkaya hata sayısı
            recovery_timeout: Devrenin açık kalacağı süre (saniye)
            half_open_success_threshold: Devreyi kapatmak için gereken arka arkaya başarı sayısı
            error_types: İzlenecek özel hata türleri (None ise tüm hatalar sayılır)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_success_threshold = half_open_success_threshold
        self.error_types = error_types or [Exception]
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.next_attempt_time = None
    
    async def execute(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """
        Fonksiyonu devre kesici mantığı ile çalıştırır.
        
        Args:
            func: Çalıştırılacak asenkron fonksiyon
            *args, **kwargs: Fonksiyon parametreleri
            
        Returns:
            Any: Fonksiyonun sonucu
            
        Raises:
            Exception: Fonksiyonun fırlattığı herhangi bir hata
        """
        # Devre durumunu kontrol et
        if self.state == CircuitState.OPEN:
            # Kurtarma zamanı geldiyse yarı açık duruma geç
            if datetime.now() >= self.next_attempt_time:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info("Devre kesici yarı açık duruma geçti, deneme başlatılıyor.")
            else:
                raise ServiceError(
                    message="Devre açık, istek reddedildi",
                    details={
                        "circuit_state": self.state.value,
                        "next_attempt": self.next_attempt_time.isoformat()
                    },
                    retriable=False,
                    severity=2,
                    error_code="CIRCUIT_OPEN"
                )
        
        try:
            # Fonksiyonu çalıştır
            result = await func(*args, **kwargs)
            
            # Başarılı çalışma - sayaçları güncelle
            self.success_count += 1
            self.failure_count = 0
            self.last_success_time = datetime.now()
            
            # Yarı açık durumda başarı eşiği aşıldıysa devreyi kapat
            if self.state == CircuitState.HALF_OPEN and self.success_count >= self.half_open_success_threshold:
                self.state = CircuitState.CLOSED
                logger.info("Devre kesici kapalı duruma geçti, normal çalışmaya dönüldü.")
            
            return result
            
        except Exception as e:
            # Hatayı izleyelim mi?
            is_tracked_error = False
            for error_type in self.error_types:
                if isinstance(e, error_type):
                    is_tracked_error = True
                    break
            
            if not is_tracked_error:
                # İzlenmeyen hata türü, sayaçları değiştirmeden yeniden fırlat
                raise
            
            # Hata sayaçlarını güncelle
            self.failure_count += 1
            self.success_count = 0
            self.last_failure_time = datetime.now()
            
            # Hata eşiğini aşınca devreyi aç
            if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.next_attempt_time = datetime.now() + timedelta(seconds=self.recovery_timeout)
                logger.warning(
                    f"Devre kesici açık duruma geçti, {self.recovery_timeout}s sonra tekrar denenecek"
                )
            
            # Half-open durumunda herhangi bir hata devreyi yeniden açar
            elif self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.next_attempt_time = datetime.now() + timedelta(seconds=self.recovery_timeout)
                logger.warning(
                    f"Yarı açık devre başarısız oldu, devre yeniden açıldı. "
                    f"{self.recovery_timeout}s sonra tekrar denenecek"
                )
            
            # Hatayı yeniden fırlat
            raise
    
    def reset(self) -> None:
        """Devre kesiciyi sıfırlayarak kapalı duruma getirir."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.next_attempt_time = None
        logger.info("Devre kesici sıfırlandı ve kapalı duruma getirildi.")
    
    def get_state(self) -> Dict[str, Any]:
        """Devre kesici durumunu döndürür."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success": self.last_success_time.isoformat() if self.last_success_time else None,
            "next_attempt": self.next_attempt_time.isoformat() if self.next_attempt_time else None
        }


class ErrorManager:
    """
    Merkezi hata yönetimi sınıfı.
    
    Hata yakalama, loglama, yeniden deneme ve devre kesme gibi 
    işlevleri merkezi olarak yönetir.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ErrorManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """ErrorManager başlatıcısı."""
        if self._initialized:
            return
            
        # Hata kaydı
        self.error_log = []
        self.max_log_size = 1000
        
        # Servis başına devre kesici
        self.circuit_breakers = {}
        
        # Varsayılan retry ayarları
        self.default_retry_strategy = RetryStrategy.EXPONENTIAL
        self.default_retry_attempts = 3
        self.default_retry_delay = 1.0  # saniye
        self.default_max_retry_delay = 60.0  # saniye
        
        self._initialized = True
        logger.info("Hata Yöneticisi başlatıldı")
    
    def log_error(self, error: Exception, service_name: Optional[str] = None) -> None:
        """
        Hatayı kaydeder.
        
        Args:
            error: Kaydedilecek hata
            service_name: Hatayı fırlatan servis
        """
        now = datetime.now()
        
        # ServiceError için özel işlem
        if isinstance(error, ServiceError):
            error.occurred_at = now
            if not error.service_name and service_name:
                error.service_name = service_name
                
            error_entry = error.to_dict()
        else:
            # Standart Exception için
            error_entry = {
                "message": str(error),
                "service_name": service_name,
                "error_type": error.__class__.__name__,
                "occurred_at": now.isoformat(),
                "traceback": getattr(error, "__traceback__", None)
            }
        
        # Hata kaydına ekle
        self.error_log.append(error_entry)
        
        # Log boyutunu kontrol et
        if len(self.error_log) > self.max_log_size:
            # En eski kayıtları kaldır
            self.error_log = self.error_log[-self.max_log_size:]
        
        # Hata seviyesine göre loglama
        if isinstance(error, ServiceError) and error.severity >= 2:
            logger.error(f"[{service_name or 'Unknown'}] {str(error)}")
        else:
            logger.warning(f"[{service_name or 'Unknown'}] {str(error)}")
    
    def get_circuit_breaker(
        self, 
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0
    ) -> CircuitBreaker:
        """
        Servis için devre kesici alır veya oluşturur.
        
        Args:
            service_name: Servis adı
            failure_threshold: Devreyi açmak için gereken hata sayısı
            recovery_timeout: Devrenin açık kalacağı süre (saniye)
            
        Returns:
            CircuitBreaker: Devre kesici instance
        """
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )
        
        return self.circuit_breakers[service_name]
    
    async def retry_async(
        self,
        func: Callable[..., Awaitable[Any]],
        *args,
        retry_strategy: RetryStrategy = None,
        max_attempts: int = None,
        initial_delay: float = None,
        max_delay: float = None,
        service_name: Optional[str] = None,
        error_types: Optional[List[Type[Exception]]] = None,
        **kwargs
    ) -> Any:
        """
        Asenkron bir fonksiyonu yeniden deneme stratejisiyle çalıştırır.
        
        Args:
            func: Çalıştırılacak asenkron fonksiyon
            *args: Fonksiyon parametreleri
            retry_strategy: Yeniden deneme stratejisi
            max_attempts: Maksimum deneme sayısı
            initial_delay: İlk bekleme süresi (saniye)
            max_delay: Maksimum bekleme süresi (saniye)
            service_name: Servis adı (loglama için)
            error_types: Yeniden denemeyi tetikleyen hata türleri
            **kwargs: Fonksiyon anahtar kelime parametreleri
            
        Returns:
            Any: Fonksiyonun sonucu
            
        Raises:
            Exception: Tüm denemeler başarısız olduğunda son hata
        """
        # Varsayılan değerleri kullan
        retry_strategy = retry_strategy or self.default_retry_strategy
        max_attempts = max_attempts or self.default_retry_attempts
        initial_delay = initial_delay or self.default_retry_delay
        max_delay = max_delay or self.default_max_retry_delay
        error_types = error_types or [Exception]
        
        attempt = 0
        last_exception = None
        
        while attempt < max_attempts:
            try:
                return await func(*args, **kwargs)
                
            except Exception as e:
                # Bu tür bir hata için yeniden deneme yapılacak mı?
                should_retry = False
                for error_type in error_types:
                    if isinstance(e, error_type):
                        # ServiceError ve retriable=False ise yeniden deneme yapma
                        if isinstance(e, ServiceError) and not e.retriable:
                            should_retry = False
                            break
                        should_retry = True
                        break
                
                if not should_retry:
                    # Yeniden deneme yapılmayacak hata, hemen fırlat
                    raise
                
                # Hata kaydı
                attempt += 1
                last_exception = e
                
                self.log_error(e, service_name=service_name)
                
                # Son deneme miydi?
                if attempt >= max_attempts:
                    logger.warning(
                        f"[{service_name or 'Unknown'}] Maksimum deneme sayısına ulaşıldı "
                        f"({max_attempts}), hata: {str(e)}"
                    )
                    raise
                
                # Bekleme süresini hesapla
                delay = self._calculate_delay(
                    retry_strategy=retry_strategy,
                    attempt=attempt,
                    initial_delay=initial_delay,
                    max_delay=max_delay
                )
                
                logger.info(
                    f"[{service_name or 'Unknown'}] Deneme {attempt}/{max_attempts} "
                    f"başarısız oldu, {delay:.2f}s sonra tekrar denenecek. Hata: {str(e)}"
                )
                
                # Bekleme
                await asyncio.sleep(delay)
        
        # Bu noktaya asla ulaşmamalı, ama yine de hata fırlat
        if last_exception:
            raise last_exception
        raise RuntimeError("Beklenmeyen retry hatası")
    
    def _calculate_delay(
        self, 
        retry_strategy: RetryStrategy,
        attempt: int,
        initial_delay: float,
        max_delay: float
    ) -> float:
        """
        Stratejiye göre bekleme süresini hesaplar.
        
        Args:
            retry_strategy: Yeniden deneme stratejisi
            attempt: Kaçıncı deneme olduğu
            initial_delay: İlk bekleme süresi
            max_delay: Maksimum bekleme süresi
            
        Returns:
            float: Bekleme süresi (saniye)
        """
        if retry_strategy == RetryStrategy.FIXED:
            delay = initial_delay
        
        elif retry_strategy == RetryStrategy.LINEAR:
            delay = initial_delay * attempt
        
        elif retry_strategy == RetryStrategy.EXPONENTIAL:
            delay = initial_delay * (2 ** (attempt - 1))
        
        elif retry_strategy == RetryStrategy.RANDOM:
            max_jitter = initial_delay * attempt
            delay = initial_delay + random.uniform(0, max_jitter)
        
        else:
            delay = initial_delay
        
        # Maksimum süreyi aşmasını önle
        return min(delay, max_delay)
    
    def get_recent_errors(
        self, 
        service_name: Optional[str] = None,
        limit: int = 10,
        error_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Son hataları döndürür.
        
        Args:
            service_name: Sadece belirli bir servis için hatalar
            limit: Döndürülecek maksimum hata sayısı
            error_type: Sadece belirli bir hata türü
            
        Returns:
            List[Dict[str, Any]]: Hata kayıtları
        """
        # Uygun hataları filtrele
        filtered_errors = self.error_log
        
        if service_name:
            filtered_errors = [
                e for e in filtered_errors 
                if e.get("service_name") == service_name
            ]
        
        if error_type:
            filtered_errors = [
                e for e in filtered_errors 
                if e.get("error_type") == error_type
            ]
        
        # En yeni hatalardan başlayarak limit kadar döndür
        return sorted(
            filtered_errors,
            key=lambda e: e.get("occurred_at", ""),
            reverse=True
        )[:limit]
    
    def get_circuit_breaker_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm devre kesicilerin durumunu döndürür.
        
        Returns:
            Dict[str, Dict[str, Any]]: Servis adına göre devre kesici durumları
        """
        return {
            service: cb.get_state()
            for service, cb in self.circuit_breakers.items()
        }
    
    def reset_circuit_breaker(self, service_name: str) -> bool:
        """
        Belirli bir servisin devre kesicisini sıfırlar.
        
        Args:
            service_name: Servis adı
            
        Returns:
            bool: Başarılı ise True
        """
        if service_name in self.circuit_breakers:
            self.circuit_breakers[service_name].reset()
            return True
        return False
    
    def reset_all_circuit_breakers(self) -> None:
        """Tüm devre kesicileri sıfırlar."""
        for cb in self.circuit_breakers.values():
            cb.reset()


# Yardımcı decorator fonksiyonları

def retry(
    max_attempts: int = 3,
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    error_types: Optional[List[Type[Exception]]] = None
):
    """
    Asenkron bir fonksiyonu yeniden deneme mantığıyla çalıştıran decorator.
    
    Örnek:
        @retry(max_attempts=3, retry_strategy=RetryStrategy.EXPONENTIAL)
        async def fetch_data():
            # Bu fonksiyon hata fırlatırsa, belirtilen stratejiye göre
            # yeniden denenecektir
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # ErrorManager singleton instance'ını al
            error_manager = ErrorManager()
            
            # Servis adını tahmin et
            service_name = None
            if args and hasattr(args[0], "service_name"):
                service_name = args[0].service_name
            
            # Retry mantığıyla çalıştır
            return await error_manager.retry_async(
                func, 
                *args, 
                retry_strategy=retry_strategy,
                max_attempts=max_attempts,
                initial_delay=initial_delay,
                max_delay=max_delay,
                service_name=service_name,
                error_types=error_types,
                **kwargs
            )
        return wrapper
    return decorator


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    error_types: Optional[List[Type[Exception]]] = None
):
    """
    Asenkron bir fonksiyonu devre kesici mantığıyla çalıştıran decorator.
    
    Örnek:
        @circuit_breaker(failure_threshold=5, recovery_timeout=30.0)
        async def call_external_api():
            # Bu fonksiyon arka arkaya 5 kez hata fırlatırsa,
            # 30 saniye boyunca devre açık kalacak ve çağrılar reddedilecek
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # ErrorManager singleton instance'ını al
            error_manager = ErrorManager()
            
            # Servis adını tahmin et
            service_name = None
            if args and hasattr(args[0], "service_name"):
                service_name = args[0].service_name
            else:
                # Servis adı yoksa fonksiyon adını kullan
                service_name = func.__name__
            
            # Servis için circuit breaker al
            cb = error_manager.get_circuit_breaker(
                service_name=service_name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )
            
            # Devre kesici mantığıyla çalıştır
            return await cb.execute(func, *args, **kwargs)
        return wrapper
    return decorator 