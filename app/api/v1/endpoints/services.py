"""
Services API

Servis yönetimi için API endpoint'leri.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Body, Path

from app.core.logger import get_logger
from app.services.service_wrapper import ServiceWrapper
from app.api.v1.schemas.service import (
    ServiceResponse, 
    ServiceStartRequest, 
    ServiceStopRequest,
    ServiceStatusResponse
)

router = APIRouter()
logger = get_logger(__name__)

def get_service_wrapper() -> ServiceWrapper:
    """ServiceWrapper instance'ı döndürür."""
    return ServiceWrapper()

@router.get("/", response_model=List[ServiceResponse])
async def get_services(
    service_wrapper: ServiceWrapper = Depends(get_service_wrapper)
):
    """
    Tüm servisleri listeler.
    """
    logger.info("Tüm servisler listeleniyor")
    services = await service_wrapper.list_services()
    return [
        {
            "name": name, 
            "status": status.get("status", "unknown"),
            "running": status.get("running", False),
            "healthy": status.get("healthy", False),
            "uptime": status.get("uptime", 0),
            "last_error": status.get("last_error", None),
            "depends_on": status.get("depends_on", []),
        } for name, status in services.items()
    ]

@router.get("/{service_name}", response_model=ServiceResponse)
async def get_service(
    service_name: str = Path(..., title="Servis Adı", description="Görüntülenecek servisin adı"),
    service_wrapper: ServiceWrapper = Depends(get_service_wrapper)
):
    """
    Belirli bir servisin detaylarını gösterir.
    
    - **service_name**: Servis adı
    """
    logger.info(f"Servis görüntüleniyor: {service_name}")
    status = await service_wrapper.get_service_status(service_name)
    
    if not status:
        logger.warning(f"Servis bulunamadı: {service_name}")
        raise HTTPException(status_code=404, detail=f"{service_name} servisi bulunamadı")
    
    return {
        "name": service_name, 
        "status": status.get("status", "unknown"),
        "running": status.get("running", False),
        "healthy": status.get("healthy", False),
        "uptime": status.get("uptime", 0),
        "last_error": status.get("last_error", None),
        "depends_on": status.get("depends_on", []),
    }

@router.post("/start", response_model=ServiceStatusResponse)
async def start_services(
    request: ServiceStartRequest = Body(...),
    service_wrapper: ServiceWrapper = Depends(get_service_wrapper)
):
    """
    Servisleri başlatır.
    
    - **services**: Başlatılacak servis listesi (boş bırakılırsa tüm servisler başlatılır)
    """
    service_names = request.services
    
    if not service_names:
        # Tüm servisleri başlat
        logger.info("Tüm servisler başlatılıyor")
        result = await service_wrapper.start_all()
        return {"status": "success", "message": "Tüm servisler başlatıldı", "details": result}
    else:
        # Seçili servisleri başlat
        logger.info(f"Seçili servisler başlatılıyor: {service_names}")
        result = {}
        for service_name in service_names:
            success = await service_wrapper.start_service(service_name)
            result[service_name] = "started" if success else "error"
        
        return {"status": "success", "message": "Seçili servisler başlatıldı", "details": result}

@router.post("/stop", response_model=ServiceStatusResponse)
async def stop_services(
    request: ServiceStopRequest = Body(...),
    service_wrapper: ServiceWrapper = Depends(get_service_wrapper)
):
    """
    Servisleri durdurur.
    
    - **services**: Durdurulacak servis listesi (boş bırakılırsa tüm servisler durdurulur)
    - **force**: Zorunlu durdurma
    """
    service_names = request.services
    force = request.force
    
    if not service_names:
        # Tüm servisleri durdur
        logger.info(f"Tüm servisler durduruluyor (force={force})")
        result = await service_wrapper.stop_all(force=force)
        return {"status": "success", "message": "Tüm servisler durduruldu", "details": result}
    else:
        # Seçili servisleri durdur
        logger.info(f"Seçili servisler durduruluyor: {service_names} (force={force})")
        result = {}
        for service_name in service_names:
            success = await service_wrapper.stop_service(service_name, force=force)
            result[service_name] = "stopped" if success else "error"
        
        return {"status": "success", "message": "Seçili servisler durduruldu", "details": result}

@router.post("/restart/{service_name}", response_model=ServiceStatusResponse)
async def restart_service(
    service_name: str = Path(..., title="Servis Adı", description="Yeniden başlatılacak servisin adı"),
    service_wrapper: ServiceWrapper = Depends(get_service_wrapper)
):
    """
    Bir servisi yeniden başlatır.
    
    - **service_name**: Yeniden başlatılacak servis adı
    """
    logger.info(f"Servis yeniden başlatılıyor: {service_name}")
    
    success = await service_wrapper.restart_service(service_name)
    
    if not success:
        logger.error(f"Servis yeniden başlatılamadı: {service_name}")
        raise HTTPException(status_code=500, detail=f"{service_name} servisi yeniden başlatılamadı")
    
    return {
        "status": "success", 
        "message": f"{service_name} servisi yeniden başlatıldı",
        "details": {service_name: "restarted"}
    }

@router.get("/health", response_model=Dict[str, Any])
async def get_services_health(
    service_wrapper: ServiceWrapper = Depends(get_service_wrapper)
):
    """
    Tüm servislerin sağlık durumunu döndürür.
    """
    logger.info("Servis sağlık durumları kontrol ediliyor")
    
    health_status = await service_wrapper.check_health()
    
    return {
        "status": "success",
        "all_healthy": all(status.get("healthy", False) for status in health_status.values()),
        "services": health_status
    } 