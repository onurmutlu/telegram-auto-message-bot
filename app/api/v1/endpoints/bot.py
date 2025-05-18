"""
# ============================================================================ #
# Dosya: bot.py
# Yol: /Users/siyahkare/code/telegram-bot/app/api/v1/endpoints/bot.py
# İşlev: Bot durumu ve servis yönetimi için API endpointleri.
#
# Versiyon: v1.0.0
# ============================================================================ #
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import json
import os

from app.db.session import get_session
from app.services.service_manager import ServiceManager
from app.core.security import get_current_active_user
from app.models.user import User

router = APIRouter()

# Global bot_instance referansı - main.py'deki TelegramBot nesnesine erişmek için
bot_instance = None

def get_bot_instance():
    global bot_instance
    if bot_instance is None:
        # İhtiyaç duyulduğunda botu yükle
        from app.main import TelegramBot
        bot_instance = TelegramBot()
    return bot_instance

async def load_bot_instance_async():
    """Bot örneğini asenkron olarak yükle."""
    try:
        # Bot örneğini al
        bot = get_bot_instance()
        
        # Başlatılmamışsa başlat
        if not hasattr(bot, 'services') or not bot.services:
            await bot.initialize()
        
        return bot
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bot yüklenirken hata: {str(e)}")

@router.get("/status")
async def get_bot_status(db: AsyncSession = Depends(get_session)):
    """
    Bot durumunu getir.
    """
    try:
        # Bot örneğini al
        bot = await load_bot_instance_async()
        
        # Health servisini al
        health_service = bot.services.get("health")
        if health_service:
            status = await health_service.get_detailed_status()
            
            # CPU kullanımı yüksekse uyarı ekle
            if status['current']['system'].get('cpu_usage', 0) > 80:
                status['warnings'] = status.get('warnings', [])
                status['warnings'].append("Yüksek CPU kullanımı")
            
            return status
        else:
            # Health servis yoksa manuel durum oluştur
            return {
                "status": "running" if bot.running else "stopped",
                "services": {name: {"running": service.running if hasattr(service, "running") else False} 
                            for name, service in bot.services.items()},
                "message": "Health servisi yüklü değil, sınırlı durum bilgisi sunuluyor",
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bot durumu alınırken hata: {str(e)}")

@router.post("/start", dependencies=[Depends(get_current_active_user)])
async def start_bot(background_tasks: BackgroundTasks):
    """
    Botu başlat (yönetici erişimi gerektirir).
    """
    try:
        # Bot örneğini al
        bot = await load_bot_instance_async()
        
        # Bot zaten çalışıyorsa bildir
        if bot.running:
            return {"status": "success", "message": "Bot zaten çalışıyor"}
        
        # Botu arka planda başlat
        async def start_bot_async():
            try:
                await bot.start()
            except Exception as e:
                print(f"Bot başlatılırken hata: {str(e)}")
                
        background_tasks.add_task(start_bot_async)
        
        return {"status": "success", "message": "Bot başlatılıyor"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bot başlatılırken hata: {str(e)}")

@router.post("/stop", dependencies=[Depends(get_current_active_user)])
async def stop_bot():
    """
    Botu durdur (yönetici erişimi gerektirir).
    """
    try:
        # Bot örneğini al
        bot = await load_bot_instance_async()
        
        # Bot zaten durmuşsa bildir
        if not bot.running:
            return {"status": "success", "message": "Bot zaten durmuş durumda"}
        
        # Botu durdur
        bot.shutdown_event.set()
        
        return {"status": "success", "message": "Bot durdurma sinyali gönderildi"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bot durdurulurken hata: {str(e)}")

@router.get("/services")
async def get_services():
    """
    Servis listesini al.
    """
    try:
        # Bot örneğini al
        bot = await load_bot_instance_async()
        
        # Servisleri topla
        services_list = []
        for name, service in bot.services.items():
            service_info = {
                "name": name,
                "running": getattr(service, "running", False),
                "initialized": getattr(service, "initialized", False),
            }
            
            # Ek servis bilgisi varsa ekle
            if hasattr(service, "get_status") and callable(service.get_status):
                try:
                    service_status = await service.get_status()
                    service_info.update(service_status)
                except:
                    pass
                    
            services_list.append(service_info)
        
        return {"services": services_list}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Servis listesi alınırken hata: {str(e)}")

@router.post("/services/{service_name}/restart", dependencies=[Depends(get_current_active_user)])
async def restart_service(service_name: str):
    """
    Belirli bir servisi yeniden başlat (yönetici erişimi gerektirir).
    """
    try:
        # Bot örneğini al
        bot = await load_bot_instance_async()
        
        # Servisi kontrol et
        if service_name not in bot.services:
            raise HTTPException(status_code=404, detail=f"Servis bulunamadı: {service_name}")
        
        # Servisi yeniden başlat
        service = bot.services[service_name]
        
        # Servis restart metoduna sahipse
        if hasattr(service, "restart") and callable(service.restart):
            restart_success = await service.restart()
            if restart_success:
                return {"status": "success", "message": f"{service_name} servisi yeniden başlatıldı"}
            else:
                raise HTTPException(status_code=500, detail=f"Servis yeniden başlatılamadı: {service_name}")
        else:
            # Manuel olarak durdur ve başlat
            if hasattr(service, "stop") and callable(service.stop):
                await service.stop()
                
            if hasattr(service, "start") and callable(service.start):
                start_success = await service.start()
                if start_success:
                    return {"status": "success", "message": f"{service_name} servisi yeniden başlatıldı"}
                else:
                    raise HTTPException(status_code=500, detail=f"Servis yeniden başlatılamadı: {service_name}")
            
            raise HTTPException(status_code=400, detail=f"Servis yeniden başlatma metoduna sahip değil: {service_name}")
            
    except HTTPException:
        raise  # Mevcut HTTPException'ları yeniden fırlat
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Servis yeniden başlatılırken hata: {str(e)}")

@router.get("/logs")
async def get_logs(limit: int = 100, current_user: User = Depends(get_current_active_user)):
    """
    Son log kayıtlarını getir (yönetici erişimi gerektirir).
    """
    try:
        log_file = os.path.join('logs', 'bot.log')
        
        if not os.path.exists(log_file):
            return {"logs": []}
        
        logs = []
        with open(log_file, 'r') as f:
            lines = f.readlines()
            logs = lines[-limit:] if lines else []
        
        return {"logs": logs}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Log kayıtları alınırken hata: {str(e)}")

@router.post("/refresh-templates", dependencies=[Depends(get_current_active_user)])
async def refresh_templates():
    """
    Mesaj şablonlarını yeniden yükle (yönetici erişimi gerektirir).
    """
    try:
        # Bot örneğini al
        bot = await load_bot_instance_async()
        
        # Mesaj şablonlarını yeniden yükle
        for name, service in bot.services.items():
            if hasattr(service, "_load_message_templates") and callable(service._load_message_templates):
                await service._load_message_templates()
                
        # Şablonları veritabanına yükle
        from app.scripts.load_templates import load_templates
        await load_templates()
        
        return {"status": "success", "message": "Mesaj şablonları yeniden yüklendi"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Şablonlar yeniden yüklenirken hata: {str(e)}")

@router.get("/system-info")
async def get_system_info(current_user: User = Depends(get_current_active_user)):
    """
    Sistem bilgilerini getir (yönetici erişimi gerektirir).
    """
    try:
        import psutil
        
        # CPU kullanımı
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # RAM kullanımı
        memory = psutil.virtual_memory()
        
        # Disk kullanımı
        disk = psutil.disk_usage('/')
        
        # İşletim sistemi bilgisi
        uname = os.uname() if hasattr(os, 'uname') else {'sysname': 'Unknown', 'release': 'Unknown'}
        
        # Çalışma süresi
        uptime = psutil.boot_time()
        
        # Toplanan bilgileri döndür
        return {
            "cpu": {
                "percent": cpu_percent,
                "cores": psutil.cpu_count()
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
            },
            "disk": {
                "total": disk.total,
                "free": disk.free,
                "percent": disk.percent
            },
            "system": {
                "os": getattr(uname, 'sysname', 'Unknown'),
                "release": getattr(uname, 'release', 'Unknown'),
                "uptime": uptime
            }
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sistem bilgileri alınırken hata: {str(e)}")

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_session)):
    """
    Bot istatistiklerini getir.
    """
    try:
        # Veritabanından istatistikleri al
        # Grup sayıları
        groups_query = """
            SELECT 
                COUNT(*) as total_groups,
                SUM(CASE WHEN is_active = true THEN 1 ELSE 0 END) as active_groups,
                SUM(CASE WHEN is_banned = true THEN 1 ELSE 0 END) as banned_groups,
                SUM(member_count) as total_members
            FROM groups
        """
        groups_result = await db.execute(groups_query)
        groups_stats = groups_result.fetchone()
        
        # Mesaj sayıları
        messages_query = """
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT group_id) as groups_with_messages,
                MAX(created_at) as last_message_time
            FROM messages
        """
        messages_result = await db.execute(messages_query)
        messages_stats = messages_result.fetchone()
        
        # Son 24 saat içindeki mesajlar
        recent_messages_query = """
            SELECT 
                COUNT(*) as messages_last_24h
            FROM messages
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """
        recent_messages_result = await db.execute(recent_messages_query)
        recent_messages_stats = recent_messages_result.fetchone()
        
        # Verileri birleştir
        stats = {
            "groups": dict(groups_stats),
            "messages": dict(messages_stats),
            "recent_activity": dict(recent_messages_stats)
        }
        
        return stats
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"İstatistikler alınırken hata: {str(e)}")

@router.post("/backup", dependencies=[Depends(get_current_active_user)])
async def create_backup(background_tasks: BackgroundTasks):
    """
    Veritabanı yedeği oluştur (yönetici erişimi gerektirir).
    """
    try:
        # Arka planda yedekleme işlemi başlat
        async def backup_database():
            try:
                import subprocess
                import time
                
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                backup_file = f"runtime/database/backups/postgres_telegram_bot_{timestamp}.sql"
                
                # pg_dump komutunu çalıştır
                cmd = [
                    "pg_dump",
                    f"--host={os.getenv('DB_HOST', 'localhost')}",
                    f"--port={os.getenv('DB_PORT', '5432')}",
                    f"--username={os.getenv('DB_USER', 'postgres')}",
                    f"--dbname={os.getenv('DB_NAME', 'telegram_bot')}",
                    f"--file={backup_file}",
                    "--format=plain",
                ]
                
                # PGPASSWORD çevre değişkeni ile şifreyi ayarla
                env = os.environ.copy()
                env["PGPASSWORD"] = os.getenv('DB_PASSWORD', 'postgres')
                
                # Komutu çalıştır
                result = subprocess.run(cmd, env=env, check=True)
                
                if result.returncode == 0:
                    # Backup dosyasını sıkıştır
                    subprocess.run(["gzip", backup_file], check=True)
                    print(f"Veritabanı yedeği oluşturuldu: {backup_file}.gz")
                else:
                    print(f"Veritabanı yedeği oluşturulurken hata: {result.stderr}")
                
            except Exception as e:
                print(f"Yedekleme hatası: {str(e)}")
        
        background_tasks.add_task(backup_database)
        
        return {"status": "success", "message": "Veritabanı yedekleme işlemi başlatıldı"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Yedekleme başlatılırken hata: {str(e)}") 