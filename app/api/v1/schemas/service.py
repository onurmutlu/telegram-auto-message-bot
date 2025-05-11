"""
Service Schemas

Servis yönetimi için veri modellerini tanımlar.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class ServiceBase(BaseModel):
    """Servis için temel şema."""
    name: str = Field(..., description="Servis adı")
    
class ServiceResponse(ServiceBase):
    """Servis yanıt şeması."""
    status: str = Field(..., description="Servis durumu (running, stopped, error)")
    running: bool = Field(..., description="Servis çalışıyor mu?")
    healthy: bool = Field(..., description="Servis sağlıklı mı?")
    uptime: int = Field(default=0, description="Çalışma süresi (saniye)")
    last_error: Optional[str] = Field(default=None, description="Son hata mesajı")
    depends_on: List[str] = Field(default=[], description="Bağımlı olduğu servisler")
    
class ServiceStartRequest(BaseModel):
    """Servis başlatma isteği şeması."""
    services: List[str] = Field(default=[], description="Başlatılacak servis listesi (boş bırakılırsa tüm servisler)")
    
class ServiceStopRequest(BaseModel):
    """Servis durdurma isteği şeması."""
    services: List[str] = Field(default=[], description="Durdurulacak servis listesi (boş bırakılırsa tüm servisler)")
    force: bool = Field(default=False, description="Zorunlu durdurma")
    
class ServiceStatusResponse(BaseModel):
    """Servis işlem yanıt şeması."""
    status: str = Field(..., description="İşlem durumu (success, error)")
    message: str = Field(..., description="İşlem mesajı")
    details: Dict[str, Any] = Field(default={}, description="İşlem detayları") 