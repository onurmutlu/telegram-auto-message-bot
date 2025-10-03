"""
Service şemaları

API'nin servis yönetimi için kullanılan şema sınıfları.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ServiceResponse(BaseModel):
    """
    Servis bilgilerini döndüren yanıt modeli.
    """
    name: str = Field(..., description="Servis adı")
    status: str = Field("unknown", description="Servis durumu (started, stopped, error, starting, stopping)")
    running: bool = Field(False, description="Servisin çalışıp çalışmadığı")
    healthy: bool = Field(False, description="Servisin sağlıklı olup olmadığı")
    uptime: int = Field(0, description="Çalışma süresi (saniye)")
    last_error: Optional[str] = Field(None, description="Son hata mesajı")
    depends_on: List[str] = Field([], description="Bağımlı olduğu servisler")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "activity",
                "status": "started",
                "running": True,
                "healthy": True,
                "uptime": 3600,
                "last_error": None,
                "depends_on": ["database", "redis"]
            }
        }

class ServiceStartRequest(BaseModel):
    """
    Servis başlatma isteği.
    """
    services: List[str] = Field([], description="Başlatılacak servis listesi (boşsa tüm servisler)")

    class Config:
        json_schema_extra = {
            "example": {
                "services": ["activity", "user"]
            }
        }

class ServiceStopRequest(BaseModel):
    """
    Servis durdurma isteği.
    """
    services: List[str] = Field([], description="Durdurulacak servis listesi (boşsa tüm servisler)")
    force: bool = Field(False, description="Zorla durdurma")

    class Config:
        json_schema_extra = {
            "example": {
                "services": ["activity", "user"],
                "force": False
            }
        }

class ServiceStatusResponse(BaseModel):
    """
    Servis işlem sonucu yanıtı.
    """
    status: str = Field(..., description="İşlem durumu (success, error)")
    message: str = Field(..., description="İşlem mesajı")
    details: Dict[str, Any] = Field({}, description="İşlem detayları")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Servisler başlatıldı",
                "details": {
                    "activity": "started",
                    "user": "started"
                }
            }
        } 