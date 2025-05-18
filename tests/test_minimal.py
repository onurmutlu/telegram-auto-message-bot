#!/usr/bin/env python3
import asyncio
import logging
from app.core.config import settings
from app.db.session import get_session
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def main():
    logger.info("Test başlatılıyor...")
    
    # Veritabanı bağlantısını test et
    try:
        db = next(get_session())
        result = db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            logger.info("Veritabanı bağlantısı başarılı")
        else:
            logger.error("Beklenmeyen sonuç")
        db.close()
    except Exception as e:
        logger.error(f"Veritabanı hatası: {e}")
    
    logger.info("Test tamamlandı.")

if __name__ == "__main__":
    asyncio.run(main())
