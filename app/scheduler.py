#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Bot Scheduler

Zamanlanmış görevleri yönetir ve uygulama genelinde merkezi zamanlayıcı olarak çalışır.
"""

import os
import asyncio
import logging
import signal
import sys
from datetime import datetime
import json

# Modül ve paket eklemelerinden önce PYTHONPATH'i yapılandır
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.logger import setup_logging
from app.core.scheduler import scheduler
from app.db.session import init_db, get_session
from app.models import Message, MessageStatus
from sqlmodel import select

# Loglama yapılandırması
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"scheduler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

setup_logging(log_file=LOG_FILE)
logger = logging.getLogger("app.scheduler")

# Sinyal işleyicileri
stop_event = asyncio.Event()

def signal_handler(sig, frame):
    """Sinyal işleyici fonksiyonu"""
    logger.info(f"Sinyal alındı: {sig}. Zamanlayıcıyı durduruyorum...")
    stop_event.set()

# Sinyalleri kaydet
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Zamanlanmış görevler
async def check_scheduled_messages():
    """
    Zamanlanmış mesajları kontrol eder ve gönderilmesi gerekenleri işaretler.
    """
    try:
        session = next(get_session())
        now = datetime.utcnow()
        
        # Zamanlanmış ve gönderilmesi gereken mesajları al
        stmt = select(Message).where(
            Message.status == MessageStatus.SCHEDULED,
            Message.scheduled_for <= now
        )
        
        messages = session.exec(stmt).all()
        
        if messages:
            logger.info(f"{len(messages)} zamanlanmış mesaj gönderilmek üzere işaretlendi")
            
            # Mesajları API üzerinden göndermek üzere PENDING olarak işaretle
            for message in messages:
                message.status = MessageStatus.PENDING
                
            session.commit()
        
    except Exception as e:
        logger.exception(f"Zamanlanmış mesajları kontrol hatası: {str(e)}")
    finally:
        session.close()

async def perform_database_maintenance():
    """
    Veritabanı bakım işlemlerini gerçekleştirir.
    """
    try:
        logger.info("Veritabanı bakımı yapılıyor...")
        
        # Burada veritabanı bakım işlemleri yapılabilir
        # Örneğin eski mesajları temizleme, tablo istatistikleri güncelleme vb.
        
        # Bakım işlemleri tamamlandı
        logger.info("Veritabanı bakımı tamamlandı")
        
    except Exception as e:
        logger.exception(f"Veritabanı bakım hatası: {str(e)}")

async def check_session_health():
    """
    Oturum sağlığını kontrol eder ve raporlar.
    """
    try:
        # Sessions dizinindeki tüm oturumları kontrol et
        sessions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        
        session_dirs = [d for d in os.listdir(sessions_dir) if os.path.isdir(os.path.join(sessions_dir, d))]
        logger.info(f"Toplam {len(session_dirs)} oturum bulundu")
        
        for session in session_dirs:
            # Oturum dizinindeki son durumu kontrol et
            try:
                session_path = os.path.join(sessions_dir, session)
                
                # td_state.bin dosyasının varlığını kontrol et
                if os.path.exists(os.path.join(session_path, "td_state.bin")):
                    last_modified = datetime.fromtimestamp(os.path.getmtime(
                        os.path.join(session_path, "td_state.bin")
                    ))
                    
                    # Son 24 saat içinde güncellenmiş mi?
                    if (datetime.now() - last_modified).total_seconds() > 86400:  # 24 saat
                        logger.warning(f"Oturum '{session}' son 24 saattir güncellenmemiş")
                    else:
                        logger.info(f"Oturum '{session}' aktif ({(datetime.now() - last_modified).total_seconds()/3600:.1f} saat önce güncellendi)")
                else:
                    logger.warning(f"Oturum '{session}' için td_state.bin bulunamadı")
                    
            except Exception as e:
                logger.error(f"Oturum '{session}' kontrolü sırasında hata: {str(e)}")
        
    except Exception as e:
        logger.exception(f"Oturum sağlığı kontrol hatası: {str(e)}")

async def register_scheduled_jobs():
    """
    Zamanlanmış görevleri kaydeder.
    """
    try:
        # Mesaj zamanlaması kontrolü (her dakika)
        await scheduler.add_interval_job(
            func=check_scheduled_messages,
            minutes=1,
            job_id="check_scheduled_messages"
        )
        logger.info("Zamanlanmış mesaj kontrolü görevi eklendi (her dakika)")
        
        # Veritabanı bakımı (her gün gece yarısı)
        await scheduler.add_cron_job(
            func=perform_database_maintenance,
            hour=0,
            minute=0,
            job_id="database_maintenance"
        )
        logger.info("Veritabanı bakım görevi eklendi (her gün 00:00)")
        
        # Oturum sağlığı kontrolü (her saat)
        await scheduler.add_interval_job(
            func=check_session_health,
            hours=1,
            job_id="check_session_health"
        )
        logger.info("Oturum sağlığı kontrol görevi eklendi (her saat)")
        
    except Exception as e:
        logger.exception(f"Zamanlanmış görevleri kaydetme hatası: {str(e)}")

async def shutdown():
    """
    Uygulamayı güvenli bir şekilde kapatır.
    """
    logger.info("Zamanlayıcıyı durduruyorum...")
    
    # Zamanlayıcıyı durdur
    scheduler.shutdown()
    
    # Uygulama işlemine son ver
    logger.info("Zamanlayıcı durduruldu.")

async def main():
    """
    Ana uygulama fonksiyonu.
    
    Zamanlayıcıyı başlatır ve görevleri yönetir.
    """
    try:
        logger.info("Telegram Bot Zamanlayıcısı başlatılıyor...")
        
        # Veritabanını başlat
        logger.info("Veritabanı bağlantısı kuruluyor...")
        init_db()
        
        # Zamanlayıcıyı başlat
        logger.info("Zamanlayıcı başlatılıyor...")
        scheduler.start()
        
        # Zamanlanmış görevleri kaydet
        await register_scheduled_jobs()
        
        # Durdurma olayını bekle
        logger.info("Zamanlayıcı çalışıyor. Durdurmak için CTRL+C tuşlarına basın.")
        await stop_event.wait()
        
        # Uygulamayı durdur
        await shutdown()
        
    except Exception as e:
        logger.exception(f"Uygulama hatası: {str(e)}")
        # Uygulama beklenmedik şekilde dursa bile zamanlayıcıyı düzgün kapatalım
        await shutdown()

if __name__ == "__main__":
    # Uygulamayı başlat
    asyncio.run(main()) 