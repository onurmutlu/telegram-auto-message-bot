"""
# ============================================================================ #
# Dosya: exceptions.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/error_handling/exceptions.py
# İşlev: Özel hata sınıfları tanımlamaları.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

from typing import Dict, Any, Optional, List


class ServiceError(Exception):
    """
    Temel servis hatası sınıfı.
    
    Tüm servis hatalarının türediği temel sınıf. Servis hatalarını
    kategorilere ayırmak ve yapılandırılmış şekilde işlemek için
    kullanılır.
    """
    
    def __init__(
        self, 
        message: str, 
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retriable: bool = True,
        severity: int = 1,
        error_code: Optional[str] = None
    ):
        """
        ServiceError başlatıcısı.
        
        Args:
            message: Hata mesajı
            service_name: Hatayı fırlatan servis
            details: Hata detayları (JSON serileştirilebilir)
            retriable: Hatanın yeniden denenebilir olup olmadığı
            severity: Hata ciddiyeti (1: düşük, 2: orta, 3: yüksek)
            error_code: Hata kodu
        """
        self.service_name = service_name
        self.details = details or {}
        self.retriable = retriable
        self.severity = severity
        self.error_code = error_code
        self.occurred_at = None  # Hata yöneticisi tarafından doldurulacak
        
        # Mesajı ayarla
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Hata bilgilerini dict olarak döndürür."""
        return {
            "message": str(self),
            "service_name": self.service_name,
            "details": self.details,
            "retriable": self.retriable,
            "severity": self.severity,
            "error_code": self.error_code,
            "occurred_at": self.occurred_at,
            "error_type": self.__class__.__name__
        }


class DependencyError(ServiceError):
    """
    Bağımlılık hatası.
    
    Bir servisin bağımlı olduğu başka bir servis veya kaynağa
    erişememesi durumunda fırlatılır.
    """
    
    def __init__(
        self, 
        message: str, 
        dependency_name: str,
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retriable: bool = True,
        severity: int = 2
    ):
        """
        DependencyError başlatıcısı.
        
        Args:
            message: Hata mesajı
            dependency_name: Bağımlı olunan servis/kaynak adı
            service_name: Hatayı fırlatan servis
            details: Hata detayları
            retriable: Hatanın yeniden denenebilir olup olmadığı
            severity: Hata ciddiyeti (1: düşük, 2: orta, 3: yüksek)
        """
        self.dependency_name = dependency_name
        
        # Details'e dependency_name ekle
        if details is None:
            details = {}
        details["dependency_name"] = dependency_name
        
        # Üst sınıf başlatıcısını çağır
        super().__init__(
            message=message,
            service_name=service_name,
            details=details,
            retriable=retriable,
            severity=severity,
            error_code=f"DEPENDENCY_ERROR"
        )


class ResourceError(ServiceError):
    """
    Kaynak hatası.
    
    Veritabanı, dosya sistemi, ağ gibi dış kaynaklara
    erişimle ilgili hataları temsil eder.
    """
    
    def __init__(
        self, 
        message: str, 
        resource_type: str,
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retriable: bool = True,
        severity: int = 2
    ):
        """
        ResourceError başlatıcısı.
        
        Args:
            message: Hata mesajı
            resource_type: Kaynak türü (database, file, network, etc.)
            service_name: Hatayı fırlatan servis
            details: Hata detayları
            retriable: Hatanın yeniden denenebilir olup olmadığı
            severity: Hata ciddiyeti (1: düşük, 2: orta, 3: yüksek)
        """
        self.resource_type = resource_type
        
        # Details'e resource_type ekle
        if details is None:
            details = {}
        details["resource_type"] = resource_type
        
        # Üst sınıf başlatıcısını çağır
        super().__init__(
            message=message,
            service_name=service_name,
            details=details,
            retriable=retriable,
            severity=severity,
            error_code=f"RESOURCE_ERROR"
        )


class ConfigurationError(ServiceError):
    """
    Yapılandırma hatası.
    
    Servis yapılandırmasıyla ilgili hataları temsil eder.
    """
    
    def __init__(
        self, 
        message: str, 
        parameter: Optional[str] = None,
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retriable: bool = False,  # Çoğu yapılandırma hatası yeniden denemeyle çözülmez
        severity: int = 2
    ):
        """
        ConfigurationError başlatıcısı.
        
        Args:
            message: Hata mesajı
            parameter: Sorunlu parametre adı
            service_name: Hatayı fırlatan servis
            details: Hata detayları
            retriable: Hatanın yeniden denenebilir olup olmadığı
            severity: Hata ciddiyeti (1: düşük, 2: orta, 3: yüksek)
        """
        self.parameter = parameter
        
        # Details'e parameter ekle
        if details is None:
            details = {}
        if parameter:
            details["parameter"] = parameter
        
        # Üst sınıf başlatıcısını çağır
        super().__init__(
            message=message,
            service_name=service_name,
            details=details,
            retriable=retriable,
            severity=severity,
            error_code=f"CONFIG_ERROR"
        )


class BusinessLogicError(ServiceError):
    """
    İş mantığı hatası.
    
    Servisin iş mantığı kurallarının ihlal edilmesi 
    durumunda fırlatılır.
    """
    
    def __init__(
        self, 
        message: str, 
        rule: Optional[str] = None,
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retriable: bool = False,  # İş mantığı hataları genelde yeniden denemeyle çözülmez
        severity: int = 1
    ):
        """
        BusinessLogicError başlatıcısı.
        
        Args:
            message: Hata mesajı
            rule: İhlal edilen kural adı
            service_name: Hatayı fırlatan servis
            details: Hata detayları
            retriable: Hatanın yeniden denenebilir olup olmadığı
            severity: Hata ciddiyeti (1: düşük, 2: orta, 3: yüksek)
        """
        self.rule = rule
        
        # Details'e rule ekle
        if details is None:
            details = {}
        if rule:
            details["rule"] = rule
        
        # Üst sınıf başlatıcısını çağır
        super().__init__(
            message=message,
            service_name=service_name,
            details=details,
            retriable=retriable,
            severity=severity,
            error_code=f"BUSINESS_ERROR"
        )


class ThrottlingError(ServiceError):
    """
    Rate limit veya throttling hatası.
    
    API rate limit, kaynak kısıtlaması gibi durumlar için.
    """
    
    def __init__(
        self, 
        message: str, 
        retry_after: Optional[float] = None,
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retriable: bool = True,  # Rate limit hataları genelde yeniden denemeyle çözülür
        severity: int = 1
    ):
        """
        ThrottlingError başlatıcısı.
        
        Args:
            message: Hata mesajı
            retry_after: Tavsiye edilen yeniden deneme süresi (saniye)
            service_name: Hatayı fırlatan servis
            details: Hata detayları
            retriable: Hatanın yeniden denenebilir olup olmadığı
            severity: Hata ciddiyeti (1: düşük, 2: orta, 3: yüksek)
        """
        self.retry_after = retry_after
        
        # Details'e retry_after ekle
        if details is None:
            details = {}
        if retry_after is not None:
            details["retry_after"] = retry_after
        
        # Üst sınıf başlatıcısını çağır
        super().__init__(
            message=message,
            service_name=service_name,
            details=details,
            retriable=retriable,
            severity=severity,
            error_code=f"THROTTLING_ERROR"
        )


class ValidationError(ServiceError):
    """
    Doğrulama hatası.
    
    Giriş verileri, parametreler veya durum doğrulaması 
    hatalarını temsil eder.
    """
    
    def __init__(
        self, 
        message: str, 
        field: Optional[str] = None,
        validation_errors: Optional[List[Dict[str, Any]]] = None,
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        retriable: bool = False,  # Doğrulama hataları genelde yeniden denemeyle çözülmez
        severity: int = 1
    ):
        """
        ValidationError başlatıcısı.
        
        Args:
            message: Hata mesajı
            field: Sorunlu alan adı
            validation_errors: Çoklu doğrulama hatası durumunda detaylı liste
            service_name: Hatayı fırlatan servis
            details: Hata detayları
            retriable: Hatanın yeniden denenebilir olup olmadığı
            severity: Hata ciddiyeti (1: düşük, 2: orta, 3: yüksek)
        """
        self.field = field
        self.validation_errors = validation_errors or []
        
        # Details'e validasyon bilgilerini ekle
        if details is None:
            details = {}
        if field:
            details["field"] = field
        if validation_errors:
            details["validation_errors"] = validation_errors
        
        # Üst sınıf başlatıcısını çağır
        super().__init__(
            message=message,
            service_name=service_name,
            details=details,
            retriable=retriable,
            severity=severity,
            error_code=f"VALIDATION_ERROR"
        ) 