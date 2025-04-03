"""
# ============================================================================ #
# Dosya: session_cleaner.py
# Yol: /Users/siyahkare/code/telegram-bot/utils/session_cleaner.py
# İşlev: Telegram bot bileşeni
#
# Build: 2025-04-01-00:07:55
# Versiyon: v3.4.0
# ============================================================================ #
#
# Bu modül, Telegram bot uygulamasının bileşenlerinden biridir.
# - İlgili servislere entegrasyon
# - Hata yönetimi ve loglama
# - Asenkron işlem desteği
#
# ============================================================================ #
"""
import os
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

def clean_sessions(session_path):
    """
    Bozuk oturum dosyalarını temizler ve sağlıklı bir başlangıç sağlar
    
    Args:
        session_path: Session dosyasının yolu
    
    Returns:
        bool: Temizlik başarılıysa True, değilse False
    """
    session_file = Path(session_path)
    journal_file = Path(f"{session_path}.session-journal")
    
    logger.info(f"🧹 Oturum dosyaları temizleniyor: {session_file}")
    
    # Journal dosyasını temizle
    if journal_file.exists():
        try:
            os.remove(journal_file)
            logger.debug(f"Journal dosyası silindi: {journal_file}")
        except Exception as e:
            logger.error(f"Journal dosyası silinemedi: {e}")
            return False
            
    # Session dosyasını düzelt
    if session_file.exists():
        try:
            # SQLite veritabanını onar
            conn = sqlite3.connect(session_file)
            conn.execute("VACUUM")
            conn.commit()
            conn.close()
            logger.debug(f"Session veritabanı onarıldı: {session_file}")
        except Exception as e:
            logger.error(f"Session onarılamadı: {e}")
            if "database is locked" in str(e):
                logger.warning("Veritabanı kilitli, bağlantıları temizleme deneniyor...")
                try:
                    # Eğer kilit varsa dosyayı yeniden oluştur
                    os.rename(session_file, f"{session_file}.bak")
                    logger.info(f"Bozuk session yedeklendi: {session_file}.bak")
                except Exception as e2:
                    logger.error(f"Session dosyası yeniden adlandırılamadı: {e2}")
                    return False
            else:
                return False
    
    logger.info("✅ Oturum dosyaları başarıyla temizlendi")
    return True