#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Bot API

FastAPI tabanlı web API ve yönetim paneli.
"""

import os
import asyncio
import logging
import signal
import sys
from datetime import datetime
import uvicorn
from contextlib import asynccontextmanager

# Modül ve paket eklemelerinden önce PYTHONPATH'i yapılandır
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
from fastapi.websockets import WebSocket
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.config import settings
from app.core.logger import setup_logging, get_logger
from app.db.session import init_db
from app.api.v1.api import api_router
from app.api.middlewares import LoggingMiddleware, PrometheusMiddleware

# Loglama yapılandırması
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

setup_logging(log_file=LOG_FILE, json_format=True)
logger = get_logger("app.api")

# Sinyal işleyicileri
stop_event = asyncio.Event()

def signal_handler(sig, frame):
    """Sinyal işleyici fonksiyonu"""
    logger.info(f"Sinyal alındı: {sig}. API'yi durduruyorum...")
    stop_event.set()

# Sinyalleri kaydet
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Uygulama başlatma ve kapatma
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Uygulama başlatma işlemleri
    logger.info("API başlatılıyor...")
    
    # Veritabanını başlat
    logger.info("Veritabanı bağlantısı kuruluyor...")
    init_db()
    
    # WebSocket bağlantılarını takip etmek için
    app.state.active_connections = []
    
    yield
    
    # Uygulama kapatma işlemleri
    logger.info("API durduruluyor...")
    
    # WebSocket bağlantılarını kapat
    for connection in app.state.active_connections:
        await connection.close()
        
    logger.info("API durduruldu.")

# FastAPI uygulaması
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Telegram Bot Yönetim API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# CORS yapılandırması
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware'ler
app.add_middleware(LoggingMiddleware)
app.add_middleware(PrometheusMiddleware)

# API rotaları
app.include_router(api_router, prefix=settings.API_V1_STR)

# Statik dosyalar
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Temel rotalar
@app.get("/")
async def root():
    """Ana sayfa."""
    return {"message": "Telegram Bot API"}

@app.get("/api/health")
async def health_check():
    """Sağlık kontrolü için endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus metrikleri için endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# WebSocket log akışı
@app.websocket("/api/logs")
async def websocket_logs(websocket: WebSocket):
    """
    WebSocket üzerinden log akışı.
    
    Client'lar bu endpoint'e bağlanarak canlı log akışı alabilir.
    """
    await websocket.accept()
    app.state.active_connections.append(websocket)
    
    try:
        # İstemciye mevcut durumu gönder
        await websocket.send_json({
            "type": "info",
            "message": "Log akışına bağlandınız",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # İstemci bağlı kaldığı sürece bekle
        while True:
            data = await websocket.receive_text()
            # Ping-pong kontrolü
            if data == "ping":
                await websocket.send_text("pong")
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"WebSocket hatası: {str(e)}")
    finally:
        if websocket in app.state.active_connections:
            app.state.active_connections.remove(websocket)

def start():
    """API sunucusunu başlatır."""
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )

if __name__ == "__main__":
    # API'yi başlat
    start() 