"""
API middlewares.

API için middleware bileşenleri.
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logger import get_logger
from app.core.metrics import TELEGRAM_API_REQUESTS, TELEGRAM_API_LATENCY

logger = get_logger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    HTTP istek ve yanıtları loglayan middleware.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        path = request.url.path
        method = request.method
        
        # İsteği logla
        logger.info(
            f"İstek alındı: {method} {path}",
            method=method,
            path=path,
            query_params=dict(request.query_params),
            client=request.client.host if request.client else None
        )
        
        try:
            # İsteği işle
            response = await call_next(request)
            
            # Yanıtı logla
            process_time = time.time() - start_time
            status_code = response.status_code
            
            log_method = logger.info if status_code < 400 else logger.error
            log_method(
                f"Yanıt gönderildi: {method} {path} {status_code} ({process_time:.4f}s)",
                method=method,
                path=path,
                status_code=status_code,
                process_time=f"{process_time:.4f}s"
            )
            
            return response
        except Exception as e:
            # Hataları logla
            process_time = time.time() - start_time
            logger.exception(
                f"İstek işleme hatası: {method} {path} - {str(e)}",
                method=method,
                path=path,
                error=str(e),
                process_time=f"{process_time:.4f}s"
            )
            raise

class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    HTTP isteklerini Prometheus metriklerine çeviren middleware.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        path = request.url.path
        method = request.method
        
        try:
            # İsteği işle
            response = await call_next(request)
            
            # Metrikleri güncelle
            status = response.status_code
            endpoint = _get_endpoint(request)
            
            TELEGRAM_API_REQUESTS.labels(
                method=f"{method}_{endpoint}",
                status="success" if status < 400 else "error"
            ).inc()
            
            TELEGRAM_API_LATENCY.labels(
                method=f"{method}_{endpoint}"
            ).observe(time.time() - start_time)
            
            return response
        except Exception as e:
            # Hata durumunda metrikleri güncelle
            endpoint = _get_endpoint(request)
            
            TELEGRAM_API_REQUESTS.labels(
                method=f"{method}_{endpoint}",
                status="error"
            ).inc()
            
            raise

def _get_endpoint(request: Request) -> str:
    """
    İstek URL'sinden endpoint adını çıkarır.
    
    Args:
        request: HTTP isteği
        
    Returns:
        str: Endpoint adı
    """
    path = request.url.path
    
    # /api/v1/users/{id} -> users
    parts = path.strip("/").split("/")
    
    if len(parts) >= 3 and parts[0] == "api" and parts[1].startswith("v"):
        return parts[2]
    elif len(parts) >= 1:
        return parts[0]
    else:
        return "root" 