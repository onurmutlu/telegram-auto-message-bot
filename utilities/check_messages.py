#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Mesajların durumunu kontrol eden ve raporlayan betik.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
import dotenv

# .env dosyasından değerleri yükle
dotenv.load_dotenv()

# Loglamayı yapılandır
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('message_check.log')
    ]
)

logger = logging.getLogger(__name__)

async def main():
    try:
        logger.info("Mesaj durumu kontrol ediliyor...")
        
        # Gerekli modülleri import et
        from app.db.session import get_session
        from app.models.message import Message, MessageStatus
        from sqlalchemy import text
        
        # Veritabanı oturumu al
        session = next(get_session())
        
        # Son 24 saatteki mesajları sorgula
        recent_messages_query = text("""
            SELECT id, group_id, content, status, scheduled_for, sent_at, error, created_at
            FROM messages
            WHERE created_at > NOW() - INTERVAL '24 hours'
            ORDER BY created_at DESC
        """)
        
        recent_messages = session.execute(recent_messages_query).all()
        
        if not recent_messages:
            logger.info("Son 24 saatte mesaj bulunamadı.")
            return
            
        logger.info(f"Son 24 saatte {len(recent_messages)} mesaj bulundu.")
        
        # Duruma göre gruplama
        status_counts = {}
        for msg in recent_messages:
            status = msg[3]  # status değeri
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
            
        # Durum istatistiklerini göster
        logger.info("Mesaj durumu istatistikleri:")
        for status, count in status_counts.items():
            logger.info(f"  - {status}: {count} mesaj")
            
        # Son 10 mesajı detaylı göster
        logger.info("\nSon 10 mesaj:")
        for i, msg in enumerate(recent_messages[:10], 1):
            msg_id = msg[0]
            group_id = msg[1]
            content_preview = msg[2][:50] + "..." if len(msg[2]) > 50 else msg[2]
            status = msg[3]
            scheduled_for = msg[4]
            sent_at = msg[5]
            error = msg[6]
            created_at = msg[7]
            
            logger.info(f"{i}. Mesaj ID: {msg_id}")
            logger.info(f"   Grup: {group_id}")
            logger.info(f"   İçerik: {content_preview}")
            logger.info(f"   Durum: {status}")
            logger.info(f"   Oluşturulma: {created_at}")
            
            if scheduled_for:
                logger.info(f"   Planlanan: {scheduled_for}")
                
            if sent_at:
                logger.info(f"   Gönderilme: {sent_at}")
                
            if error:
                logger.info(f"   Hata: {error}")
                
            logger.info("")
            
        # Zamanlanmış mesajları kontrol et
        scheduled_query = text("""
            SELECT id, group_id, content, scheduled_for
            FROM messages
            WHERE (UPPER(status) = 'SCHEDULED' OR status = 'scheduled')
            ORDER BY scheduled_for
        """)
        
        scheduled_messages = session.execute(scheduled_query).all()
        
        if scheduled_messages:
            logger.info(f"\nZamanlanmış {len(scheduled_messages)} mesaj bulundu:")
            for i, msg in enumerate(scheduled_messages, 1):
                msg_id = msg[0]
                group_id = msg[1]
                content_preview = msg[2][:50] + "..." if len(msg[2]) > 50 else msg[2]
                scheduled_for = msg[3]
                
                logger.info(f"{i}. Mesaj ID: {msg_id}")
                logger.info(f"   Grup: {group_id}")
                logger.info(f"   İçerik: {content_preview}")
                logger.info(f"   Planlanan: {scheduled_for}")
                logger.info("")
        else:
            logger.info("Zamanlanmış mesaj bulunamadı.")
            
        # Hatalı mesajları kontrol et
        failed_query = text("""
            SELECT id, group_id, content, error, created_at
            FROM messages
            WHERE (UPPER(status) = 'FAILED' OR status = 'failed')
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        failed_messages = session.execute(failed_query).all()
        
        if failed_messages:
            logger.info(f"\nSon 10 başarısız mesaj:")
            for i, msg in enumerate(failed_messages, 1):
                msg_id = msg[0]
                group_id = msg[1]
                content_preview = msg[2][:50] + "..." if len(msg[2]) > 50 else msg[2]
                error = msg[3]
                created_at = msg[4]
                
                logger.info(f"{i}. Mesaj ID: {msg_id}")
                logger.info(f"   Grup: {group_id}")
                logger.info(f"   İçerik: {content_preview}")
                logger.info(f"   Hata: {error}")
                logger.info(f"   Oluşturulma: {created_at}")
                logger.info("")
        else:
            logger.info("Başarısız mesaj bulunamadı.")
            
    except Exception as e:
        logger.error(f"Mesaj durumu kontrol edilirken hata oluştu: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        pass

if __name__ == "__main__":
    asyncio.run(main()) 