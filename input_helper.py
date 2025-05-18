"""
Input yardımcı aracı.

Bu modül, hem standart input'tan hem de dosyadan okuma yapabilen bir işlev sağlar.
"""
import os
import sys
import time
import logging

logger = logging.getLogger("InputHelper")

def safe_input(prompt, file_path=None, retry_count=3, retry_delay=1):
    """
    Güvenli input fonksiyonu.
    
    Bu fonksiyon önce standart girişten veri almayı dener.
    Eğer stdin kullanılamıyorsa veya EOF hatası alınırsa, dosyadan okumayı dener.
    
    Args:
        prompt (str): Kullanıcıya gösterilecek istem
        file_path (str, optional): Alternatif olarak okunacak dosya yolu
        retry_count (int): Deneme sayısı
        retry_delay (int): Denemeler arası bekleme süresi (saniye)
        
    Returns:
        str: Alınan input
    """
    # Önce dosyadan okumayı dene
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                content = f.read().strip()
                if content:
                    logger.info(f"Girdi dosyadan okundu: {file_path}")
                    # Dosyadan okunan veriyi kullandıktan sonra temizle
                    try:
                        os.remove(file_path)
                        logger.info(f"Güvenlik için dosya silindi: {file_path}")
                    except Exception as e:
                        logger.warning(f"Dosya silinemedi: {e}")
                    return content
        except Exception as e:
            logger.warning(f"Dosyadan okuma hatası: {e}")
    
    # Standart girişten okumayı dene
    for attempt in range(retry_count):
        try:
            print(prompt, end='', flush=True)
            value = sys.stdin.readline().strip()
            if value:
                return value
            
            logger.warning(f"Boş girdi alındı, deneme {attempt+1}/{retry_count}")
            time.sleep(retry_delay)
        except (EOFError, KeyboardInterrupt, ValueError) as e:
            logger.warning(f"Standart girişten okuma hatası: {e}, deneme {attempt+1}/{retry_count}")
            
            if attempt < retry_count - 1:
                time.sleep(retry_delay)
            else:
                logger.error("Tüm girdi okuma denemeleri başarısız oldu.")
                # Son çare - varsayılan bir değer dön veya hata fırlat
                if file_path:
                    logger.info(f"Son çare olarak dosya yeniden kontrol ediliyor: {file_path}")
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'r') as f:
                                content = f.read().strip()
                                if content:
                                    logger.info(f"Girdi son deneme olarak dosyadan okundu")
                                    return content
                        except Exception as e:
                            logger.error(f"Dosyadan son okuma denemesi de başarısız: {e}")
                            
                logger.error("Kullanıcı girişi alınamadı!")
                return ""
    
    # Eğer buraya kadar geldiyse, boş değer dön
    logger.error("Kullanıcı girişi alınamadı (tüm denemeler sonrasında)!")
    return ""
