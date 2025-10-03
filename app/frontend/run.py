#!/usr/bin/env python3
"""
Telegram Bot Dashboard
-----------------
Bot durumunu izlemek için basit bir web arayüzü
"""
import os
import sys
import logging
import asyncio
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
import uvicorn

# Loglama
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("dashboard")

# FastAPI uygulaması
app = FastAPI(
    title="Telegram Bot Dashboard",
    description="Bot durumunu izlemek için web arayüzü",
    version="1.0.0"
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statik dosyalar ve şablonlar
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)

templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
os.makedirs(templates_dir, exist_ok=True)

# Default sayfa HTML'i
default_html = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Bot Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .status {
            background-color: #f9f9f9;
            border-left: 5px solid #3498db;
            padding: 15px;
            margin: 20px 0;
        }
        .service {
            margin-bottom: 10px;
            padding: 10px;
            background-color: #f5f5f5;
            border-radius: 5px;
        }
        .running {
            color: green;
            font-weight: bold;
        }
        .stopped {
            color: red;
            font-weight: bold;
        }
        .actions {
            margin-top: 30px;
            padding: 15px;
            background-color: #ecf0f1;
            border-radius: 5px;
        }
        button {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
        }
        button:hover {
            background-color: #2980b9;
        }
    </style>
</head>
<body>
    <h1>Telegram Bot Dashboard</h1>
    
    <div class="status">
        <h2>Bot Durumu</h2>
        <p><strong>Durum:</strong> <span class="running">Çalışıyor</span></p>
        <p><strong>Çalışma Süresi:</strong> <span id="uptime">12 saat, 45 dakika</span></p>
        <p><strong>Son Güncelleme:</strong> <span id="last-update">21.05.2025 21:20</span></p>
    </div>
    
    <h2>Servisler</h2>
    <div class="service">
        <h3>Mesajlaşma Servisi</h3>
        <p><strong>Durum:</strong> <span class="running">Çalışıyor</span></p>
        <p><strong>Mesaj Sayısı:</strong> 120</p>
    </div>
    
    <div class="service">
        <h3>Analiz Servisi</h3>
        <p><strong>Durum:</strong> <span class="running">Çalışıyor</span></p>
        <p><strong>İzlenen Grup Sayısı:</strong> 15</p>
    </div>
    
    <div class="service">
        <h3>İzleme Servisi</h3>
        <p><strong>Durum:</strong> <span class="running">Çalışıyor</span></p>
        <p><strong>Son Kontrol:</strong> 21.05.2025 21:15</p>
    </div>
    
    <div class="actions">
        <h2>İşlemler</h2>
        <button onclick="alert('Servisler yeniden başlatılıyor...')">Servisleri Yeniden Başlat</button>
        <button onclick="alert('Loglar görüntüleniyor...')">Logları Görüntüle</button>
        <button onclick="alert('Ayarlar açılıyor...')">Ayarları Düzenle</button>
    </div>

    <script>
        // Gerçek zamanlı güncelleme için buraya JavaScript eklenebilir
        document.getElementById('last-update').textContent = new Date().toLocaleString('tr-TR');
    </script>
</body>
</html>
"""

# Default şablon oluştur
with open(os.path.join(templates_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(default_html)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Ana sayfa"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def status():
    """Bot durumunu döndür"""
    return {
        "status": "running",
        "uptime": "12 saat, 45 dakika",
        "last_update": "21.05.2025 21:20",
        "services": {
            "messaging": {"status": "running", "message_count": 120},
            "analytics": {"status": "running", "group_count": 15},
            "monitoring": {"status": "running", "last_check": "21.05.2025 21:15"}
        }
    }

@app.get("/api/logs")
async def logs():
    """Son logları döndür"""
    return {
        "logs": [
            {"time": "21.05.2025 21:20:10", "level": "INFO", "message": "Mesaj gönderildi: Merhaba arkadaşlar!"},
            {"time": "21.05.2025 21:15:05", "level": "INFO", "message": "Yeni grup bulundu: Telegram Türkiye"},
            {"time": "21.05.2025 21:10:12", "level": "WARNING", "message": "Grup mesajı gönderilemedi: Geçersiz ID"}
        ]
    }

if __name__ == "__main__":
    uvicorn.run("run:app", host="0.0.0.0", port=8000, reload=True) 