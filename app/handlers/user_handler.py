"""
# ============================================================================ #
# Dosya: user_handler.py
# Yol: /Users/siyahkare/code/telegram-bot/app/handlers/user_handler.py
# İşlev: Telegram bot için kullanıcı etkileşim yönetimi.
#
# Amaç: Bu modül, kullanıcı komutlarını işleme, özel mesajları yönetme ve 
# davet mesajları gönderme gibi kullanıcı odaklı etkileşimleri kontrol eder.
# Rate limiting, hata yönetimi ve ServiceManager entegrasyonu ile güvenilir
# bir şekilde çalışır.
#
# Temel Özellikler:
# - Kullanıcı komutlarını işleme ve cevaplama
# - Adaptif rate limiting ile özel davet mesajları gönderme
# - Akıllı hata yönetimi ve otomatik hatalardan kurtulma
# - ServiceManager ile uyumlu yaşam döngüsü
# - İstatistik toplama ve durum izleme
# - Asenkron işlem desteği
# - Flood koruması ve otomatik gecikme yönetimi
# - Otomatik yeniden deneme mekanizması
# - Kullanıcı segmentasyonu ve özelleştirilmiş mesajlar
# - Harici metrik sistemi entegrasyonu
# - Circuit breaker modeli ile servis koruması
#
# Build: 2025-04-08-23:45:00
# Versiyon: v3.5.0
# ============================================================================ #
#
# Değişiklik Geçmişi:
# v3.5.0 (2025-04-08) - ServiceManager ile uyumlu hale getirildi
#                      - Yaşam döngüsü metotları eklendi (initialize, start, stop, run)
#                      - İstatistik toplama sistemi eklendi
#                      - Konfigürasyon yükleme mekanizması iyileştirildi
#                      - Daha detaylı hata yönetimi ve izleme
#                      - Yardımcı metotlar eklendi ve geliştirildi
#                      - Otomatik yeniden deneme mekanizması eklendi
#                      - Kullanıcı segmentasyonu eklendi
#                      - Circuit breaker modeli eklendi
# v3.4.0 (2025-04-01) - İlk kapsamlı versiyon
# v3.3.0 (2025-03-15) - İlk sürüm
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import random
import logging
import os
import functools
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Union, Callable, TypeVar, cast
from colorama import Fore, Style
from telethon import errors
from telethon.tl.types import User, Message, Channel
from telethon.errors import (
    RPCError, FloodWaitError, UserPrivacyRestrictedError,
    ChatAdminRequiredError, UserAlreadyParticipantError,
    PhoneNumberBannedError, UserBannedInChannelError
)

# Opsiyonel harici metrik sistemi bağımlılıkları
try:
    import prometheus_client
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Tip tanımları
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

class UserSegment(Enum):
    """
    Kullanıcı segmentlerini tanımlar.
    
    Her segment farklı mesaj sıklığı ve içeriğine sahiptir.
    """
    HIGH_VALUE = "high_value"     # Yüksek etkileşim gösteren değerli kullanıcılar
    ACTIVE = "active"             # Normal aktif kullanıcılar
    INACTIVE = "inactive"         # Düşük etkileşimli kullanıcılar
    NEW = "new"                   # Yeni kullanıcılar
    BLOCKED = "blocked"           # Engellemiş kullanıcılar

class CircuitState(Enum):
    """
    Devre durumlarını tanımlar.
    
    Devre kesici modeli için kullanılır. Sürekli hatalar
    devre durumunu CLOSED'dan OPEN'a getirir ve belirli bir
    süre boyunca işlemleri engeller.
    """
    CLOSED = "closed"         # Devre kapalı (normal işlem)
    OPEN = "open"             # Devre açık (işlemler engelleniyor)
    HALF_OPEN = "half_open"   # Devre yarı açık (test aşaması)

class UserHandler:
    """
    Telegram bot için kullanıcı etkileşimlerini yöneten sınıf.
    
    Bu sınıf, kullanıcılara özel mesajlar gönderme, davetler yönetme,
    rate limiting ve kullanıcı komutlarını işleme gibi işlemleri yürütür.
    ServiceManager ile entegre çalışarak botun yaşam döngüsüne uyum sağlar.
    
    Attributes:
        bot: Ana bot nesnesi
        pm_delays: Rate limiting için parametre sözlüğü
        pm_state: Rate limiting için durum takibi sözlüğü
        is_running: Servisin çalışma durumu
        is_paused: Servisin duraklatılma durumu
        stop_event: Durdurma sinyali için asyncio.Event nesnesi
        stats: İstatistik verileri sözlüğü
        circuit: Devre kesici durum bilgileri
        metrics: Prometheus metrik nesneleri
    """
    
    def __init__(self, bot, stop_event=None):
        """
        UserHandler sınıfının başlatıcı metodu.

        Args:
            bot: Bağlı olduğu bot nesnesi
            stop_event: Durdurma sinyali için Event nesnesi (opsiyonel)
        """
        self.bot = bot
        
        # Durum yönetimi
        self.is_running = False
        self.is_paused = False
        self.stop_event = stop_event or asyncio.Event()
        
        # Rate limiting için parametreler - çevre değişkenlerinden veya varsayılan değerlerden
        self.pm_delays = {
            'min_delay': int(os.environ.get('PM_MIN_DELAY', '45')),       # Min bekleme süresi (saniye)
            'max_delay': int(os.environ.get('PM_MAX_DELAY', '120')),      # Max bekleme süresi (saniye)
            'burst_limit': int(os.environ.get('PM_BURST_LIMIT', '5')),    # Art arda gönderim limiti
            'burst_delay': int(os.environ.get('PM_BURST_DELAY', '300')),  # Burst limit sonrası bekleme
            'hourly_limit': int(os.environ.get('PM_HOURLY_LIMIT', '15'))  # Saatlik maksimum mesaj
        }
        
        # Rate limiting için durum takibi
        self.pm_state = {
            'burst_count': 0,
            'hourly_count': 0,
            'hour_start': datetime.now(),
            'last_pm_time': None,
            'consecutive_errors': 0
        }
        
        # İstatistikler
        self.stats = {
            "messages_sent": 0,
            "commands_processed": 0,
            "invites_sent": 0,
            "errors": 0,
            "flood_waits": 0,
            "last_activity": datetime.now(),
            "start_time": None,
            "retry_success": 0,    # Yeniden deneme başarılı sayısı
            "retry_failure": 0,    # Yeniden deneme başarısız sayısı
            "circuit_trips": 0,    # Devre kesici tetiklenme sayısı
            "segment_stats": {     # Segment bazlı istatistikler
                "high_value": 0,
                "active": 0,
                "inactive": 0,
                "new": 0,
                "blocked": 0
            }
        }
        
        # Kullanıcı segmentasyonu ayarları
        self.segment_settings = {
            UserSegment.HIGH_VALUE: {
                "invite_interval_days": 30,
                "max_invites_per_day": 2,
                "greeting_style": "personal"
            },
            UserSegment.ACTIVE: {
                "invite_interval_days": 14,
                "max_invites_per_day": 1,
                "greeting_style": "standard"
            },
            UserSegment.INACTIVE: {
                "invite_interval_days": 45,
                "max_invites_per_day": 1,
                "greeting_style": "incentive"
            },
            UserSegment.NEW: {
                "invite_interval_days": 5,
                "max_invites_per_day": 1,
                "greeting_style": "welcome"
            },
            UserSegment.BLOCKED: {
                "invite_interval_days": 90,
                "max_invites_per_day": 0,
                "greeting_style": "none"
            }
        }
        
        # Circuit breaker için durum bilgileri
        self.circuit = {
            "state": CircuitState.CLOSED,
            "failure_count": 0,
            "failure_threshold": 5,
            "recovery_timeout": 300,  # 5 dakika
            "last_failure_time": None,
            "last_test_time": None,
            "operation_counts": {
                "success": 0,
                "failure": 0
            }
        }
        
        # Metrik sistemi
        self.metrics = self._setup_metrics() if PROMETHEUS_AVAILABLE else {}
        
        logger.info("UserHandler başlatıldı")
    
    def _setup_metrics(self) -> Dict[str, Any]:
        """
        Prometheus metriklerini yapılandırır.
        
        Returns:
            Dict[str, Any]: Metrik nesnelerini içeren sözlük
        """
        if not PROMETHEUS_AVAILABLE:
            logger.warning("prometheus_client kütüphanesi bulunamadı, metrikler devre dışı.")
            return {}
            
        metrics = {}
        
        # Telegram API işlem sayaçları
        metrics["invites_total"] = prometheus_client.Counter(
            'telegram_bot_invites_total', 
            'Gönderilen toplam davet sayısı'
        )
        
        metrics["messages_total"] = prometheus_client.Counter(
            'telegram_bot_messages_total', 
            'Gönderilen toplam mesaj sayısı'
        )
        
        metrics["errors_total"] = prometheus_client.Counter(
            'telegram_bot_errors_total', 
            'Toplam hata sayısı',
            ['error_type']
        )
        
        # Rate limiting ve devre kesici metrikleri
        metrics["circuit_state"] = prometheus_client.Gauge(
            'telegram_bot_circuit_state',
            'Devre kesici durumu (0=kapalı, 1=yarı açık, 2=açık)'
        )
        
        metrics["rate_limited_total"] = prometheus_client.Counter(
            'telegram_bot_rate_limited_total',
            'Rate limiting nedeniyle bekleyen işlem sayısı'
        )
        
        # Segment dağılımı metrikleri
        metrics["segment_distribution"] = prometheus_client.Gauge(
            'telegram_bot_segment_distribution',
            'Kullanıcıların segment dağılımı',
            ['segment']
        )
        
        # İşlem süresi metrikleri
        metrics["invite_duration"] = prometheus_client.Histogram(
            'telegram_bot_invite_duration_seconds',
            'Davet işlemi süreleri',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )
        
        # Başlatma metrik değerlerini sıfırla
        for segment in UserSegment:
            metrics["segment_distribution"].labels(segment=segment.value).set(0)
            
        metrics["circuit_state"].set(0)  # Başlangıçta devre kapalı
            
        return metrics
    
    async def initialize(self) -> bool:
        """
        Servisi başlatmak için gerekli hazırlıkları yapar.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            # İstatistikleri sıfırla
            self.stats["start_time"] = datetime.now()
            
            # Yapılandırma ayarlarını yükle (eğer bot nesnesinde varsa)
            if hasattr(self.bot, 'config'):
                # Rate limiting ayarları
                if hasattr(self.bot.config, 'user_handler_config'):
                    config = self.bot.config.user_handler_config
                    self.pm_delays = {
                        'min_delay': config.get('min_delay', self.pm_delays['min_delay']),
                        'max_delay': config.get('max_delay', self.pm_delays['max_delay']),
                        'burst_limit': config.get('burst_limit', self.pm_delays['burst_limit']),
                        'burst_delay': config.get('burst_delay', self.pm_delays['burst_delay']),
                        'hourly_limit': config.get('hourly_limit', self.pm_delays['hourly_limit'])
                    }
                
                # Devre kesici ayarları
                if hasattr(self.bot.config, 'circuit_breaker_config'):
                    circuit_config = self.bot.config.circuit_breaker_config
                    self.circuit['failure_threshold'] = circuit_config.get(
                        'failure_threshold', 
                        self.circuit['failure_threshold']
                    )
                    self.circuit['recovery_timeout'] = circuit_config.get(
                        'recovery_timeout',
                        self.circuit['recovery_timeout']
                    )
            
            logger.info("UserHandler başarıyla initialize edildi")
            return True
            
        except Exception as e:
            logger.error(f"UserHandler initialize hatası: {str(e)}", exc_info=True)
            return False
    
    async def start(self) -> bool:
        """
        Kullanıcı handler servisini başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            self.is_running = True
            self.is_paused = False
            
            # Servis durum kontrolü
            if not hasattr(self.bot, 'client'):
                logger.error("Bot client nesnesi bulunamadı")
                return False
                
            # Rate limiting durumunu sıfırla
            self.pm_state = {
                'burst_count': 0,
                'hourly_count': 0,
                'hour_start': datetime.now(),
                'last_pm_time': None,
                'consecutive_errors': 0
            }
            
            # Devre kesiciyi sıfırla
            self.circuit["state"] = CircuitState.CLOSED
            self.circuit["failure_count"] = 0
            self.circuit["operation_counts"] = {"success": 0, "failure": 0}
            
            # İstatistik sıfırlama
            self.stats["start_time"] = datetime.now()
            
            # Metrik sistemi başlatma
            if self.metrics and PROMETHEUS_AVAILABLE:
                # Metrik sunucusu başlatılmış mı?
                if hasattr(self.bot, 'metrics_port') and self.bot.metrics_port:
                    try:
                        prometheus_client.start_http_server(self.bot.metrics_port)
                        logger.info(f"Prometheus metrik sunucusu port {self.bot.metrics_port}'de başlatıldı")
                    except Exception as e:
                        logger.warning(f"Metrik sunucusu başlatılamadı: {e}")
            
            logger.info("UserHandler başarıyla başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"UserHandler start hatası: {str(e)}")
            return False
    
    async def stop(self) -> None:
        """
        Kullanıcı handler servisini durdurur.
        """
        logger.info("UserHandler durduruluyor...")
        self.is_running = False
        self.stop_event.set()
        logger.info("UserHandler durduruldu")
    
    async def pause(self) -> None:
        """
        Kullanıcı handler servisini geçici olarak duraklatır.
        """
        if not self.is_paused:
            self.is_paused = True
            logger.info("UserHandler duraklatıldı")
    
    async def resume(self) -> None:
        """
        Duraklatılmış kullanıcı handler servisini devam ettirir.
        """
        if self.is_paused:
            self.is_paused = False
            logger.info("UserHandler devam ettiriliyor")
    
    async def run(self) -> None:
        """
        Ana servis döngüsü - periyodik olarak davet işlemlerini yürütür.
        
        Bu metot, servis durdurulana kadar çalışır ve belirli aralıklarla
        davet sürecini başlatır.
        """
        logger.info("UserHandler ana döngüsü başlatıldı")
        
        try:
            while not self.stop_event.is_set() and self.is_running:
                if not self.is_paused:
                    try:
                        # Devre kesici durumu kontrol et
                        if self._check_circuit():
                            # Davet işleme sürecini başlat
                            await self.process_personal_invites()
                        else:
                            logger.warning("Devre kesici açık, davet işlemi atlandı")
                            
                            # Devre kesici durumunu güncelle
                            await self._update_circuit_state()
                    except Exception as e:
                        self.stats["errors"] += 1
                        logger.error(f"UserHandler davet işleme hatası: {str(e)}")
                        
                    # Bir sonraki tur için bekle - bekleme süresi konfigüre edilebilir
                    try:
                        # 2 dakika bekle, ama durdurulabilir olmalı
                        await asyncio.wait_for(self.stop_event.wait(), timeout=120)
                    except asyncio.TimeoutError:
                        pass  # Normal timeout, devam et
                else:
                    # Duraklatılmışsa her 1 saniyede bir kontrol et
                    await asyncio.sleep(1)
        
        except asyncio.CancelledError:
            logger.info("UserHandler ana görevi iptal edildi")
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"UserHandler ana döngü hatası: {str(e)}", exc_info=True)
    
    # =========================================================================
    # YENİ: Otomatik Yeniden Deneme Dekoratörü
    # =========================================================================
    
    def retry_decorator(self, max_retries: int = 3, 
                       retry_on: Tuple[Exception, ...] = (FloodWaitError, RPCError),
                       base_delay: float = 1.0, 
                       backoff_factor: float = 2.0):
        """
        İşlemleri başarısız olduğunda otomatik olarak tekrar deneyen bir dekoratör.
        
        Bu dekoratör, belirtilen hata türlerinde işlemi belirli sayıda yeniden 
        deneyerek geçici hatalara karşı dayanıklılık sağlar.
        
        Args:
            max_retries: Maksimum yeniden deneme sayısı
            retry_on: Yakalanacak hata türleri
            base_delay: İlk yeniden deneme için bekleme süresi (saniye)
            backoff_factor: Her denemede bekleme süresinin çarpanı
            
        Returns:
            Callable: Dekoratör fonksiyonu
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exception = None
                
                # Asenkron fonksiyon kontrolü
                if not asyncio.iscoroutinefunction(func):
                    raise TypeError("retry_decorator yalnızca asenkron fonksiyonlar için kullanılabilir")
                
                for attempt in range(max_retries + 1):
                    try:
                        # İlk deneme değilse bekle
                        if attempt > 0:
                            # Her deneme için artan bekleme süresi (exponential backoff)
                            delay = base_delay * (backoff_factor ** (attempt - 1))
                            # Bekleme süresine rastgelelik ekle (jitter)
                            jitter = random.uniform(0.8, 1.2)
                            sleep_time = delay * jitter
                            
                            logger.debug(f"{func.__name__} fonksiyonu için {attempt}. deneme, {sleep_time:.2f}s bekleniyor...")
                            
                            # Kesintili bekleme
                            await self._interruptible_sleep(sleep_time)
                            
                        return await func(*args, **kwargs)
                        
                    except retry_on as e:
                        last_exception = e
                        
                        # FloodWaitError için özel işlem
                        if isinstance(e, FloodWaitError):
                            logger.info(f"FloodWaitError yakalandı, {e.seconds}s bekleniyor ({attempt+1}/{max_retries+1})...")
                            
                            # Prometheus metriği (eğer varsa)
                            if PROMETHEUS_AVAILABLE and "rate_limited_total" in self.metrics:
                                self.metrics["rate_limited_total"].inc()
                            
                            # Rate limit durumunda doğrudan Telegram'ın istediği süre kadar bekle
                            try:
                                await self._interruptible_sleep(e.seconds)
                                self.stats["flood_waits"] += 1
                                continue  # FloodWaitError sonrası mutlaka devam et
                            except asyncio.CancelledError:
                                logger.info(f"{func.__name__} fonksiyonu için bekleme iptal edildi")
                                break
                        
                        logger.warning(f"{func.__name__} fonksiyonu {attempt+1}. denemede başarısız: {e}")
                        
                        # Son deneme değilse devam et
                        if attempt < max_retries:
                            continue
                            
                        # Son deneme başarısız, istatistikleri güncelle
                        self.stats["retry_failure"] += 1
                        break
                    
                    except asyncio.CancelledError:
                        logger.info(f"{func.__name__} fonksiyonu iptal edildi")
                        raise
                    
                    except Exception as e:
                        # Burada yakalanmayan istisnalar doğrudan yükseltilir
                        logger.error(f"{func.__name__} fonksiyonunda beklenmeyen hata: {e}")
                        raise
                
                # Tüm denemeler başarısız oldu
                if last_exception:
                    # Devre kesiciyi güncelle
                    self._record_circuit_failure()
                    
                    logger.error(f"{func.__name__} fonksiyonu {max_retries+1} denemeden sonra başarısız oldu")
                    raise last_exception
                
                return None
                
            return wrapper
        
        return decorator
    
    # =========================================================================
    # YENİ: Circuit Breaker (Devre Kesici) Model
    # =========================================================================
    
    def _check_circuit(self) -> bool:
        """
        Devre kesici durumunu kontrol eder.
        
        Returns:
            bool: İşlemlere devam edilebilirse True, aksi halde False
        """
        # Devre kapalıysa (normal çalışma)
        if self.circuit["state"] == CircuitState.CLOSED:
            return True
            
        # Devre açıksa (koruma modunda)
        elif self.circuit["state"] == CircuitState.OPEN:
            # Belirli bir süre geçti mi?
            if self.circuit["last_failure_time"] is None:
                return False
                
            recovery_time = datetime.now() - self.circuit["last_failure_time"]
            if recovery_time.total_seconds() > self.circuit["recovery_timeout"]:
                # Recovery timeout geçti, yarı açık duruma geç
                self.circuit["state"] = CircuitState.HALF_OPEN
                logger.info(f"Devre kesici HALF_OPEN durumuna geçti (recovery timeout: {self.circuit['recovery_timeout']}s)")
                
                # Metrik güncelleme
                if PROMETHEUS_AVAILABLE and "circuit_state" in self.metrics:
                    self.metrics["circuit_state"].set(1)  # 1 = HALF_OPEN
                
                return True
            else:
                # Henüz recovery timeout geçmedi
                return False
                
        # Devre yarı açıksa (test modu)
        elif self.circuit["state"] == CircuitState.HALF_OPEN:
            # Sınırlı sayıda işlem geçişine izin ver
            return True
            
        return True
    
    def _record_circuit_success(self) -> None:
        """
        Başarılı bir işlemi devre kesici için kaydeder.
        """
        self.circuit["operation_counts"]["success"] += 1
        
        # Yarı açık durumdaysa ve yeterli başarılı işlem varsa, kapalı duruma geç
        if self.circuit["state"] == CircuitState.HALF_OPEN and self.circuit["operation_counts"]["success"] >= 3:
            self.circuit["state"] = CircuitState.CLOSED
            self.circuit["failure_count"] = 0
            logger.info("Devre kesici CLOSED durumuna döndü (yeterli başarılı işlem)")
            
            # Metrik güncelleme
            if PROMETHEUS_AVAILABLE and "circuit_state" in self.metrics:
                self.metrics["circuit_state"].set(0)  # 0 = CLOSED
    
    def _record_circuit_failure(self) -> None:
        """
        Başarısız bir işlemi devre kesici için kaydeder.
        """
        current_time = datetime.now()
        
        # Başarısız işlem sayacını artır
        self.circuit["failure_count"] += 1
        self.circuit["operation_counts"]["failure"] += 1
        self.circuit["last_failure_time"] = current_time
        
        # Eğer yarı açık durumdaysa, hemen açık duruma geç
        if self.circuit["state"] == CircuitState.HALF_OPEN:
            self.circuit["state"] = CircuitState.OPEN
            logger.warning("Devre kesici OPEN durumuna döndü (yarı açık durumda hata)")
            self.stats["circuit_trips"] += 1
            
            # Metrik güncelleme
            if PROMETHEUS_AVAILABLE and "circuit_state" in self.metrics:
                self.metrics["circuit_state"].set(2)  # 2 = OPEN
            
        # Eğer kapalı durumdaysa ve başarısız işlem sayısı eşiği geçtiyse açık duruma geç
        elif self.circuit["state"] == CircuitState.CLOSED and self.circuit["failure_count"] >= self.circuit["failure_threshold"]:
            self.circuit["state"] = CircuitState.OPEN
            logger.warning(f"Devre kesici OPEN durumuna geçti (başarısız işlem eşiği aşıldı: {self.circuit['failure_threshold']})")
            self.stats["circuit_trips"] += 1
            
            # Metrik güncelleme
            if PROMETHEUS_AVAILABLE and "circuit_state" in self.metrics:
                self.metrics["circuit_state"].set(2)  # 2 = OPEN
    
    async def _update_circuit_state(self) -> None:
        """
        Devre kesici durumunu periyodik olarak günceller.
        """
        current_time = datetime.now()
        
        # Açık durumdaki devrenin durumunu kontrol et
        if self.circuit["state"] == CircuitState.OPEN and self.circuit["last_failure_time"]:
            # Recovery timeout'u geçti mi?
            time_since_failure = (current_time - self.circuit["last_failure_time"]).total_seconds()
            if time_since_failure > self.circuit["recovery_timeout"]:
                self.circuit["state"] = CircuitState.HALF_OPEN
                self.circuit["operation_counts"]["success"] = 0
                self.circuit["operation_counts"]["failure"] = 0
                logger.info("Devre kesici HALF_OPEN durumuna geçti (recovery timeout)")
                
                # Metrik güncelleme
                if PROMETHEUS_AVAILABLE and "circuit_state" in self.metrics:
                    self.metrics["circuit_state"].set(1)  # 1 = HALF_OPEN
    
    # =========================================================================
    # YENİ: Kullanıcı Segmentasyon Sistemi
    # =========================================================================
    
    async def determine_user_segment(self, user_id: int) -> UserSegment:
        """
        Kullanıcının hangi segmente ait olduğunu belirler.
        
        Bu metot, kullanıcının aktivite düzeyine, yanıt oranına ve
        diğer faktörlere bakarak en uygun segmenti döndürür.
        
        Args:
            user_id: Segmenti belirlenecek kullanıcı ID
            
        Returns:
            UserSegment: Kullanıcının segmenti
        """
        try:
            # Kullanıcı verisini al
            user_data = await self._get_user_data(user_id)
            
            if not user_data:
                # Kullanıcı verisi bulunamadı, NEW olarak kabul et
                return UserSegment.NEW
            
            # Kullanıcı engellenmiş mi?
            if user_data.get('is_blocked', False):
                self.stats["segment_stats"]["blocked"] += 1
                
                # Metrik güncelleme
                if PROMETHEUS_AVAILABLE and "segment_distribution" in self.metrics:
                    self.metrics["segment_distribution"].labels(segment=UserSegment.BLOCKED.value).inc()
                    
                return UserSegment.BLOCKED
            
            # Kullanıcı yeni mi?
            join_date = user_data.get('join_date')
            if join_date:
                # Datetime türüne dönüştür (metot farklı formatlar döndürebilir)
                if isinstance(join_date, str):
                    try:
                        join_date = datetime.fromisoformat(join_date.replace('Z', '+00:00'))
                    except ValueError:
                        # ISO format değilse timestamp olabilir
                        try:
                            join_date = datetime.fromtimestamp(float(join_date))
                        except:
                            join_date = None
                
                # Son 7 gün içinde katıldıysa NEW
                if join_date and (datetime.now() - join_date).days < 7:
                    self.stats["segment_stats"]["new"] += 1
                    
                    # Metrik güncelleme
                    if PROMETHEUS_AVAILABLE and "segment_distribution" in self.metrics:
                        self.metrics["segment_distribution"].labels(segment=UserSegment.NEW.value).inc()
                        
                    return UserSegment.NEW
            
            # Kullanıcının aktiflik düzeyi
            # Son davet tarihine bakılır
            last_invited = user_data.get('last_invited')
            if not last_invited:
                # Hiç davet edilmemiş, yeni kullanıcı olarak değerlendir
                return UserSegment.NEW
            
            # Datetime türüne dönüştür
            if isinstance(last_invited, str):
                try:
                    last_invited = datetime.fromisoformat(last_invited.replace('Z', '+00:00'))
                except ValueError:
                    try:
                        last_invited = datetime.fromtimestamp(float(last_invited))
                    except:
                        last_invited = None
            
            if not last_invited:
                return UserSegment.NEW
            
            # Son davetten bu yana geçen gün
            days_since_last_invite = (datetime.now() - last_invited).days
            
            # Yanıt oranını kontrol et
            response_rate = user_data.get('response_rate', 0) or 0  # None ise 0 al
            
            # Segment belirleme kriterleri
            if response_rate >= 0.7:  # %70+ yanıt oranı
                self.stats["segment_stats"]["high_value"] += 1
                
                # Metrik güncelleme
                if PROMETHEUS_AVAILABLE and "segment_distribution" in self.metrics:
                    self.metrics["segment_distribution"].labels(segment=UserSegment.HIGH_VALUE.value).inc()
                    
                return UserSegment.HIGH_VALUE
            elif response_rate >= 0.3:  # %30-70 yanıt oranı
                self.stats["segment_stats"]["active"] += 1
                
                # Metrik güncelleme
                if PROMETHEUS_AVAILABLE and "segment_distribution" in self.metrics:
                    self.metrics["segment_distribution"].labels(segment=UserSegment.ACTIVE.value).inc()
                    
                return UserSegment.ACTIVE
            else:
                # Düşük yanıt oranı veya yeni kullanıcı
                self.stats["segment_stats"]["inactive"] += 1
                
                # Metrik güncelleme
                if PROMETHEUS_AVAILABLE and "segment_distribution" in self.metrics:
                    self.metrics["segment_distribution"].labels(segment=UserSegment.INACTIVE.value).inc()
                    
                return UserSegment.INACTIVE
            
        except Exception as e:
            logger.error(f"Segment belirleme hatası (user_id: {user_id}): {e}")
            # Varsayılan olarak INACTIVE
            return UserSegment.INACTIVE
    
    async def _get_user_data(self, user_id: int) -> Dict[str, Any]:
        """
        Kullanıcı verisini döndürür.
        
        Args:
            user_id: Verisi alınacak kullanıcı ID
            
        Returns:
            Dict[str, Any]: Kullanıcı verisi sözlüğü veya boş sözlük
        """
        try:
            # UserService üzerinden veri al
            if hasattr(self.bot, 'user_service') and hasattr(self.bot.user_service, 'get_user_data'):
                if asyncio.iscoroutinefunction(self.bot.user_service.get_user_data):
                    return await self.bot.user_service.get_user_data(user_id) or {}
                else:
                    return self.bot.user_service.get_user_data(user_id) or {}
                    
            # Farklı metot ismi olabilir
            if hasattr(self.bot, 'user_service') and hasattr(self.bot.user_service, 'get_user'):
                if asyncio.iscoroutinefunction(self.bot.user_service.get_user):
                    return await self.bot.user_service.get_user(user_id) or {}
                else:
                    return self.bot.user_service.get_user(user_id) or {}
            
            # DB üzerinden
            if hasattr(self.bot, 'db') and hasattr(self.bot.db, 'get_user'):
                if asyncio.iscoroutinefunction(self.bot.db.get_user):
                    return await self.bot.db.get_user(user_id) or {}
                else:
                    return self.bot.db.get_user(user_id) or {}
            
            return {}
            
        except Exception as e:
            logger.error(f"Kullanıcı verisi alınamadı (user_id: {user_id}): {e}")
            return {}
    
    def _create_segmented_message(self, user_id: int, username: str, segment: UserSegment) -> str:
        """
        Kullanıcı segmentine özel mesaj oluşturur.
        
        Args:
            user_id: Kullanıcı ID
            username: Kullanıcı adı
            segment: Kullanıcı segmenti
            
        Returns:
            str: Segment için özel mesaj
        """
        # Temel mesajı al
        base_message = self._create_invite_message(user_id, username)
        
        # Segmente göre özelleştir
        greeting_style = self.segment_settings[segment]["greeting_style"]
        
        if segment == UserSegment.HIGH_VALUE:
            # Değerli kullanıcı için özel mesaj
            custom_intro = f"Merhaba {username or 'değerli kullanıcı'}! Gruplarımızda aktif katılımınız için teşekkür ederiz. 🌟"
            return f"{custom_intro}\n\n{base_message}"
            
        elif segment == UserSegment.ACTIVE:
            # Aktif kullanıcı için standart mesaj
            return base_message
            
        elif segment == UserSegment.INACTIVE:
            # İnaktif kullanıcılar için teşvik edici mesaj
            custom_intro = "Merhaba! Uzun zamandır görüşemiyoruz. Sizi yeniden aramızda görmek isteriz. 💫"
            return f"{custom_intro}\n\n{base_message}\n\nGruplarımızda sizin gibi değerli üyelere ihtiyacımız var!"
            
        elif segment == UserSegment.NEW:
            # Yeni kullanıcılar için hoş geldin mesajı
            custom_intro = "Hoş geldiniz! Sizi Telegram topluluğumuza davet etmekten mutluluk duyarız. 🎉"
            return f"{custom_intro}\n\n{base_message}\n\nHer türlü sorunuzda size yardımcı olmaya hazırız."
            
        else:
            # Diğer segmentler için standart mesaj
            return base_message
    
    # =========================================================================
    # Mevcut metodların güncellenen versiyonları
    # =========================================================================
    
    async def process_command(self, event: Any, command: str, args: List[str] = None) -> None:
        """
        Kullanıcıdan gelen komutları işler.
        
        Args:
            event: Telethon mesaj olayı
            command: İşlenecek komut (/ olmadan)
            args: Komut argümanları (opsiyonel)
        """
        if not self.is_running or self.is_paused:
            return
            
        try:
            user_id = getattr(event.sender, 'id', None)
            username = getattr(event.sender, 'username', None)
            user_info = f"@{username}" if username else f"ID:{user_id}"
            
            logger.info(f"📝 Komut işleniyor: /{command} - Kullanıcı: {user_info}")
            
            # İstatistik güncelleme
            self.stats["commands_processed"] += 1
            self.stats["last_activity"] = datetime.now()
            
            # Metrik güncelleme
            if PROMETHEUS_AVAILABLE and "messages_total" in self.metrics:
                self.metrics["messages_total"].inc()
            
            # Komutlara göre işlem yap
            if command == "info":
                # Kullanıcı bilgilerini göster
                user_info_text = await self._get_user_info(user_id)
                await event.reply(user_info_text)
                
            elif command == "stats":
                # Bot istatistiklerini göster (eğer yetkisi varsa)
                if await self._check_admin_permission(user_id):
                    stats_text = await self._get_stats_text()
                    await event.reply(stats_text)
                else:
                    await event.reply("Bu komutu kullanmak için yeterli yetkiniz yok.")
                
            elif command == "help":
                # Yardım mesajını göster
                help_text = self._create_help_text()
                await event.reply(help_text)
            
            # YENİ: Segment bilgisi komutu
            elif command == "segment" and await self._check_admin_permission(user_id):
                # Yönetici için segment bilgilerini göster
                if len(args) > 0 and args[0].isdigit():
                    target_user_id = int(args[0])
                    segment = await self.determine_user_segment(target_user_id)
                    segment_info = f"Kullanıcı ID {target_user_id} için segment: {segment.value}"
                    await event.reply(segment_info)
                else:
                    await event.reply("Segment bilgisi için bir kullanıcı ID'si belirtin: /segment [user_id]")
                
            # YENİ: Devre kesici durum komutu  
            elif command == "circuit" and await self._check_admin_permission(user_id):
                # Yönetici için devre kesici bilgilerini göster
                circuit_info = (
                    f"Devre Kesici Durumu: {self.circuit['state'].value}\n"
                    f"Hata Sayacı: {self.circuit['failure_count']}/{self.circuit['failure_threshold']}\n"
                    f"Başarılı İşlem: {self.circuit['operation_counts']['success']}\n"
                    f"Başarısız İşlem: {self.circuit['operation_counts']['failure']}\n"
                    f"Son Hata Zamanı: {self.circuit['last_failure_time'].strftime('%H:%M:%S') if self.circuit['last_failure_time'] else 'Yok'}"
                )
                await event.reply(circuit_info)
                
            # YENİ: Devre kesiciyi sıfırlama komutu
            elif command == "reset_circuit" and await self._check_admin_permission(user_id):
                self.circuit["state"] = CircuitState.CLOSED
                self.circuit["failure_count"] = 0
                self.circuit["operation_counts"] = {"success": 0, "failure": 0}
                
                # Metrik güncelleme
                if PROMETHEUS_AVAILABLE and "circuit_state" in self.metrics:
                    self.metrics["circuit_state"].set(0)  # 0 = CLOSED
                    
                await event.reply("Devre kesici sıfırlandı ve kapatıldı!")
                
            else:
                # Bilinmeyen komut
                unknown_command_text = f"Bilinmeyen komut: /{command}\nKullanılabilir komutlar için /help yazınız."
                await event.reply(unknown_command_text)
        
        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"Komut işleme hatası ({command}): {str(e)}")
            
            # Metrik güncelleme
            if PROMETHEUS_AVAILABLE and "errors_total" in self.metrics:
                self.metrics["errors_total"].labels(error_type="command_error").inc()
    
    async def process_personal_invites(self) -> int:
        """
        Sistemdeki kullanıcılara özel davetler gönderir.
        
        Bu metot, veritabanından davet edilecek kullanıcıları alır,
        onlara özel mesajlar gönderir ve sonuçları izler. Rate limiting 
        ve hata yönetimi içerir.
        
        Returns:
            int: Başarıyla gönderilen davet sayısı
        """
        if not self.is_running or self.is_paused or not self._check_circuit():
            return 0
            
        sent_count = 0
        
        try:
            # Davet edilecek kullanıcıları al
            try:
                # UserService üzerinden mi alınıyor?
                if hasattr(self.bot, 'user_service') and hasattr(self.bot.user_service, 'get_users_to_invite'):
                    users_to_invite = await self.bot.user_service.get_users_to_invite(limit=5)
                # Veritabanından mı alınıyor?
                elif hasattr(self.bot.db, 'get_users_to_invite'):
                    if asyncio.iscoroutinefunction(self.bot.db.get_users_to_invite):
                        users_to_invite = await self.bot.db.get_users_to_invite(limit=5)
                    else:
                        users_to_invite = self.bot.db.get_users_to_invite(limit=5)
                else:
                    logger.error("Davet edilecek kullanıcıları alacak bir servis bulunamadı")
                    return 0
                    
            except Exception as e:
                logger.error(f"Kullanıcı listesi alma hatası: {str(e)}")
                
                # Hata metriği güncelleme
                if PROMETHEUS_AVAILABLE and "errors_total" in self.metrics:
                    self.metrics["errors_total"].labels(error_type="db_error").inc()
                    
                self._record_circuit_failure()
                await self._interruptible_sleep(30)
                return 0
                
            if not users_to_invite:
                logger.info("📪 Davet edilecek kullanıcı bulunamadı")
                return 0
                
            logger.info(f"📩 {len(users_to_invite)} kullanıcıya davet gönderiliyor...")
            
            # Her kullanıcıya davet gönder
            for user_data in users_to_invite:
                # Kapatma sinyali kontrol et
                if not self.is_running or self.is_paused or self.stop_event.is_set():
                    break
                    
                # Rate limiting ve diğer kontrolleri yap
                if self.pm_state['hourly_count'] >= self.pm_delays['hourly_limit']:
                    logger.warning("⚠️ Saatlik mesaj limiti doldu!")
                    break
                    
                # Kullanıcı bilgisini çıkar - farklı formatları destekle
                user_id, username = self._extract_user_info(user_data)
                
                if not user_id:
                    continue
                
                # Kullanıcının segmentini belirle
                segment = await self.determine_user_segment(user_id)
                
                # Segmente göre özelleştirilmiş mesaj oluştur
                invite_message = self._create_segmented_message(user_id, username, segment)
                
                # Retry dekoratör ile özel mesaj gönderme
                start_time = time.time()
                try:
                    # Yeniden deneme dekoratörü ile mesaj gönderme
                    retry_send = self.retry_decorator(
                        max_retries=2, 
                        retry_on=(FloodWaitError, RPCError)
                    )(self._send_personal_message)
                    
                    # Mesajı gönder
                    if await retry_send(user_id, invite_message):
                        # İşaret ve istatistik güncelleme
                        await self._mark_user_invited(user_id)
                        sent_count += 1
                        self.stats["invites_sent"] += 1
                        
                        # Başarılı devre kesici kaydı
                        self._record_circuit_success()
                        
                        # Metrik güncelleme
                        if PROMETHEUS_AVAILABLE and "invites_total" in self.metrics:
                            self.metrics["invites_total"].inc()
                        
                except Exception as e:
                    logger.error(f"Davet gönderme hatası ({user_id}): {e}")
                    self.stats["errors"] += 1
                    
                    # Metrik güncelleme
                    if PROMETHEUS_AVAILABLE and "errors_total" in self.metrics:
                        self.metrics["errors_total"].labels(error_type="invite_error").inc()
                
                finally:
                    # İşlem süresi hesapla
                    duration = time.time() - start_time
                    
                    # Metrik güncelleme
                    if PROMETHEUS_AVAILABLE and "invite_duration" in self.metrics:
                        self.metrics["invite_duration"].observe(duration)
                    
                # Davetler arasında bekle - bölünmüş bekleme
                await self._interruptible_sleep(random.randint(30, 60))
                
            return sent_count
                
        except asyncio.CancelledError:
            logger.info("Davet işleme görevi iptal edildi")
            raise
        except Exception as e:
            self.stats["errors"] += 1
            self._record_circuit_failure()
            
            # Metrik güncelleme
            if PROMETHEUS_AVAILABLE and "errors_total" in self.metrics:
                self.metrics["errors_total"].labels(error_type="invite_process_error").inc()
            
            # Tekrarlanan hataları filtreleme mekanizması
            if hasattr(self.bot, 'error_handler'):
                self.bot.error_handler.log_error("Davet işleme hatası", str(e))
            else:
                logger.error(f"Özel davet hatası: {str(e)}")
                
            await self._interruptible_sleep(30)
            return sent_count
    
    # =========================================================================
    # YENİ: YARDIMCI METODLAR
    # =========================================================================
    
    async def _get_stats_text(self) -> str:
        """
        Bot istatistiklerini metin olarak döndürür.
        
        Returns:
            str: İstatistik metni
        """
        # Çalışma süresi hesapla
        uptime = datetime.now() - self.stats["start_time"] if self.stats["start_time"] else timedelta(0)
        uptime_str = str(uptime).split('.')[0]  # Mikrosaniye kısmını kaldır
        
        # Segment istatistikleri
        segment_stats = "\n".join([
            f"- {segment.capitalize()}: {count}" 
            for segment, count in self.stats["segment_stats"].items()
        ])
        
        # Devre kesici durumu
        circuit_state = self.circuit["state"].value
        circuit_failures = f"{self.circuit['failure_count']}/{self.circuit['failure_threshold']}"
        
        # Diğer istatistikler
        stats_text = (
            f"📊 **Bot İstatistikleri**\n\n"
            f"**Durum:** {'Çalışıyor' if self.is_running else 'Durduruldu'} "
            f"{'(Duraklatıldı)' if self.is_paused else ''}\n"
            f"**Devre Kesici:** {circuit_state} ({circuit_failures})\n"
            f"**Çalışma süresi:** {uptime_str}\n"
            f"**Gönderilen mesajlar:** {self.stats['messages_sent']}\n"
            f"**İşlenen komutlar:** {self.stats['commands_processed']}\n"
            f"**Gönderilen davetler:** {self.stats['invites_sent']}\n"
            f"**Flood wait durumları:** {self.stats['flood_waits']}\n"
            f"**Hatalar:** {self.stats['errors']}\n"
            f"**Başarılı retry sayısı:** {self.stats['retry_success']}\n"
            f"**Devre kesici tetiklenmesi:** {self.stats['circuit_trips']}\n"
            f"**Son aktivite:** {self.stats['last_activity'].strftime('%H:%M:%S')}\n\n"
            f"**Segment Dağılımı:**\n{segment_stats}"
        )
        
        return stats_text
    
    def _create_help_text(self) -> str:
        """
        Yardım mesajını oluşturur.
        
        Returns:
            str: Yardım mesajı
        """
        help_text = (
            "📋 **Kullanılabilir Komutlar**\n\n"
            "/start - Botu başlat\n"
            "/help - Bu yardım mesajını göster\n"
            "/info - Kullanıcı bilgilerini göster\n"
            "/groups - Grup listesini göster\n"
            "/stats - Bot istatistiklerini göster (sadece adminler için)\n"
            "/segment [user_id] - Kullanıcı segment bilgisi (sadece adminler için)\n"
            "/circuit - Devre kesici durumu (sadece adminler için)\n"
            "/reset_circuit - Devre kesiciyi sıfırla (sadece adminler için)\n\n"
            
            "Ayrıca özel mesaj gönderebilir veya yukarıdaki gruplarımıza katılabilirsiniz."
        )
        
        return help_text