import asyncio
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("bot_status")

async def check_bot_status():
    logger.info("Bot durumu kontrol ediliyor...")
    
    try:
        # Telegram client bağlantısı kontrolü
        from app.core.unified.client import get_client
        client = await get_client()
        
        if client:
            me = await client.get_me()
            logger.info(f"Telegram bağlantısı: ✅ BAŞARILI ({me.first_name} @{me.username})")
        else:
            logger.error("Telegram bağlantısı: ❌ BAŞARISIZ")
            return
            
        # Servis Yöneticisi kontrolü
        from app.services.service_manager import ServiceManager
        sm = ServiceManager(client=client)
        await sm.load_all_services()
        
        # Tüm servislerin durumunu al
        status = await sm.get_all_service_status()
        
        logger.info("\n--- SERVİS DURUMLARI ---")
        for name, info in status.items():
            status_text = "✅ ÇALIŞIYOR" if info.get("running", False) else "❌ DURDU"
            logger.info(f"{name}: {status_text}")
            
        # Etkinlik servisi kontrolü
        from app.services.event_service import EventService
        es = EventService(client=client)
        await es.initialize()
        
        handlers = await es.get_event_handlers()
        logger.info(f"\n--- ETKİNLİK İŞLEYİCİLERİ ({len(handlers)}) ---")
        event_types = {}
        for h in handlers:
            event_type = h.get("event_type")
            if event_type not in event_types:
                event_types[event_type] = 0
            event_types[event_type] += 1
            
        for event_type, count in event_types.items():
            logger.info(f"{event_type}: {count} işleyici")
            
        # Grupları kontrol et
        from app.models.group import Group
        from app.db.session import get_session
        session = next(get_session())
        
        groups_query = "SELECT COUNT(*) FROM groups WHERE is_active = TRUE"
        group_count = session.execute(groups_query).scalar()
        
        logger.info(f"\n--- GRUPLAR ({group_count}) ---")
        
        # Aktif kampanyaları kontrol et
        from app.services.messaging.promo_service import PromoService
        ps = PromoService(client=client)
        await ps.initialize()
        await ps.load_campaigns()
        
        active_campaigns = [c for c in getattr(ps, 'campaigns', []) if c.get('status') == 'active']
        
        logger.info(f"\n--- AKTİF KAMPANYALAR ({len(active_campaigns)}) ---")
        for camp in active_campaigns:
            logger.info(f"{camp.get('name')} (ID: {camp.get('id')}, Hedef: {camp.get('target_count')}, Şu anki: {camp.get('current_count')})")
    
        # DM servisini kontrol et
        from app.services.messaging.dm_service import DirectMessageService
        dm = DirectMessageService(client=client)
        await dm.initialize()
        
        # Botun çalışma süresini kontrol et
        from os.path import getmtime
        import time
        try:
            with open('.bot_initialized', 'r') as f:
                start_time = f.read().strip()
                if not start_time:
                    start_time = str(getmtime('.bot_initialized'))
                
                start_dt = datetime.fromtimestamp(float(start_time))
                uptime = datetime.now() - start_dt
                days, seconds = uptime.days, uptime.seconds
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                seconds = seconds % 60
                
                logger.info(f"\n--- BOT ÇALIŞMA SÜRESİ ---")
                logger.info(f"Başlangıç: {start_dt}")
                logger.info(f"Çalışma süresi: {days} gün, {hours} saat, {minutes} dakika, {seconds} saniye")
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Bot başlangıç zamanı belirlenemedi: {e}")
    
    except Exception as e:
        logger.error(f"Bot durumu kontrolünde hata: {str(e)}", exc_info=True)
    finally:
        logger.info("Bot durumu kontrolü tamamlandı")

if __name__ == "__main__":
    asyncio.run(check_bot_status()) 