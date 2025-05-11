#!/usr/bin/env python3
"""
Telegram botunun grup mesaj ayarlarını daha agresif hale getirir.
Bu script, mesaj gönderme hızını artıracak ve bekleme sürelerini azaltacak
şekilde ayarları günceller.

Kullanım:
    python agresif_mesaj_ayarla.py
"""

import os
import sys
import re
import logging
import shutil
import asyncio

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def update_message_service():
    """MessageService sınıfındaki ayarları daha agresif hale getirir"""
    try:
        # Ana dizini belirle
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        message_service_path = os.path.join(base_dir, "bot", "services", "message_service.py")
        
        if not os.path.exists(message_service_path):
            logger.error(f"message_service.py dosyası bulunamadı: {message_service_path}")
            return False
        
        # Yedekleme yap
        backup_path = f"{message_service_path}.bak"
        shutil.copy2(message_service_path, backup_path)
        logger.info(f"Yedek oluşturuldu: {backup_path}")
        
        # Dosyayı oku
        with open(message_service_path, 'r') as f:
            content = f.read()
        
        # RateLimiter ayarlarını güncelle
        content = re.sub(
            r'initial_rate=\d+\.\d+,\s*# Saniyede \d+ istek',
            'initial_rate=5.0,  # Saniyede 5 istek',
            content
        )
        content = re.sub(
            r'period=\d+,\s*# \d+ saniyelik periyot',
            'period=5,         # 5 saniyelik periyot',
            content
        )
        content = re.sub(
            r'error_backoff=\d+\.\d+,\s*# Hata durumunda \d+\.\d+x yavaşlama',
            'error_backoff=1.05, # Hata durumunda 1.05x yavaşlama',
            content
        )
        content = re.sub(
            r'max_jitter=\d+(?:\.\d+)?\s*# Maksimum \d+(?:\.\d+)? saniyelik rastgele gecikme',
            'max_jitter=0.2     # Maksimum 0.2 saniyelik rastgele gecikme',
            content
        )
        
        # Mesaj ayarlarını güncelle
        content = re.sub(
            r"self.batch_size = self.config.get_setting\('message_batch_size', \d+\)",
            "self.batch_size = self.config.get_setting('message_batch_size', 50)",
            content
        )
        content = re.sub(
            r"self.batch_interval = self.config.get_setting\('message_batch_interval', \d+\)",
            "self.batch_interval = self.config.get_setting('message_batch_interval', 30)",
            content
        )
        content = re.sub(
            r"self.interval_multiplier = \d+\.\d+",
            "self.interval_multiplier = 0.2",
            content
        )
        content = re.sub(
            r"self.default_interval = \d+",
            "self.default_interval = 60",
            content
        )
        
        # Dosyayı güncelle
        with open(message_service_path, 'w') as f:
            f.write(content)
        
        logger.info("MessageService ayarları daha agresif hale getirildi!")
        return True
        
    except Exception as e:
        logger.error(f"MessageService güncellenirken hata: {str(e)}")
        return False

def update_announcement_service():
    """AnnouncementService sınıfındaki ayarları daha agresif hale getirir"""
    try:
        # Ana dizini belirle
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        announcement_service_path = os.path.join(base_dir, "bot", "services", "announcement_service.py")
        
        if not os.path.exists(announcement_service_path):
            logger.error(f"announcement_service.py dosyası bulunamadı: {announcement_service_path}")
            return False
        
        # Yedekleme yap
        backup_path = f"{announcement_service_path}.bak"
        shutil.copy2(announcement_service_path, backup_path)
        logger.info(f"Yedek oluşturuldu: {backup_path}")
        
        # Dosyayı oku
        with open(announcement_service_path, 'r') as f:
            content = f.read()
        
        # RateLimiter ayarlarını güncelle
        content = re.sub(
            r'initial_rate=\d+,\s*# Başlangıçta dakikada \d+ mesaj',
            'initial_rate=20,  # Başlangıçta dakikada 20 mesaj',
            content
        )
        content = re.sub(
            r'period=\d+,\s*# \d+ saniyelik periyot',
            'period=10,       # 10 saniyelik periyot',
            content
        )
        content = re.sub(
            r'error_backoff=\d+\.\d+,\s*# Hata durumunda \d+\.\d+x yavaşlama',
            'error_backoff=1.1, # Hata durumunda 1.1x yavaşlama',
            content
        )
        content = re.sub(
            r'max_jitter=\d+\.\d+\s*# Maksimum \d+\.\d+ saniyelik rastgele gecikme',
            'max_jitter=0.5   # Maksimum 0.5 saniyelik rastgele gecikme',
            content
        )
        
        # Duyuru aralığını güncelle
        content = re.sub(
            r"self.announcement_interval_minutes = self.config.get_setting\('announcement_interval_minutes', \d+\)",
            "self.announcement_interval_minutes = self.config.get_setting('announcement_interval_minutes', 10)",
            content
        )
        
        # Grup kategorilerine göre gönderim aralıklarını güncelle
        cooldown_update = """        # Grup kategorilerine göre gönderim aralıkları (saat)
        self.cooldown_hours = {
            'own_groups': 0.1,        # Kendi gruplarımızda çok sık mesaj
            'safe_groups': 0.25,      # Güvenli gruplarda sık mesaj
            'risky_groups': 0.5,      # Riskli gruplarda daha sık
            'high_traffic_groups': 0.3  # Yüksek trafikli gruplarda sık mesaj
        }"""
        
        content = re.sub(
            r"# Grup kategorilerine göre gönderim aralıkları \(saat\)\s+self\.cooldown_hours = \{[^}]+\}",
            cooldown_update,
            content
        )
        
        # Batch boyutlarını güncelle
        batch_update = """        # Grup kategorileri için batchler
        self.batch_size = {
            'own_groups': 20,           # Kendi gruplarımızın hepsine
            'safe_groups': 30,          # Güvenli gruplara toplu
            'risky_groups': 15,         # Riskli gruplara çoklu
            'high_traffic_groups': 20   # Yüksek trafikli gruplara toplu
        }"""
        
        content = re.sub(
            r"# Grup kategorileri için batchler\s+self\.batch_size = \{[^}]+\}",
            batch_update,
            content
        )
        
        # Announcement loop'u güncelle
        content = re.sub(
            r"# Bir sonraki tura kadar bekle \(Daha da kısaltıldı\)\s+interval = \(self\.announcement_interval_minutes \* 60\) / \d+",
            "# Bir sonraki tura kadar bekle (Aşırı kısaltıldı)\n                interval = (self.announcement_interval_minutes * 60) / 16",
            content
        )
        
        # Her mesaj arasındaki bekleme süresini güncelle
        content = re.sub(
            r"# Her mesaj arasında çok az bekle \(Daha da kısaltıldı\)\s+await asyncio\.sleep\(\d+\.\d+ \+ random\.random\(\) \* \d+\.\d+\)",
            "# Her mesaj arasında neredeyse hiç bekleme\n                        await asyncio.sleep(0.1 + random.random() * 0.2)",
            content
        )
        
        # Dosyayı güncelle
        with open(announcement_service_path, 'w') as f:
            f.write(content)
        
        logger.info("AnnouncementService ayarları daha agresif hale getirildi!")
        return True
        
    except Exception as e:
        logger.error(f"AnnouncementService güncellenirken hata: {str(e)}")
        return False

def update_datamining_service():
    """DataMiningService sınıfındaki veri toplama sıklığını artırır"""
    try:
        # Ana dizini belirle
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        datamining_service_path = os.path.join(base_dir, "bot", "services", "datamining_service.py")
        
        if not os.path.exists(datamining_service_path):
            logger.error(f"datamining_service.py dosyası bulunamadı: {datamining_service_path}")
            return False
        
        # Yedekleme yap
        backup_path = f"{datamining_service_path}.bak"
        shutil.copy2(datamining_service_path, backup_path)
        logger.info(f"Yedek oluşturuldu: {backup_path}")
        
        # Dosyayı oku
        with open(datamining_service_path, 'r') as f:
            content = f.read()
        
        # Veri toplama döngüsündeki aralığı güncelle
        content = re.sub(
            r"# Her \d+ dakikada bir grup ve kullanıcı verilerini topla",
            "# Her 5 dakikada bir grup ve kullanıcı verilerini topla",
            content
        )
        
        # Grup üyelerini güncelleme aralığını değiştir
        content = re.sub(
            r"# Her \d+ saatte bir grup kullanıcılarını güncelle[^\n]+\s+current_hour = datetime\.now\(\)\.hour\s+if current_hour % \d+ == 0:",
            "# Her 1 saatte bir grup kullanıcılarını güncelle\n                current_hour = datetime.now().hour\n                if current_hour % 1 == 0:",
            content
        )
        
        # While döngüsündeki bekleme süresini güncelle
        content = re.sub(
            r"# \d+ dakika bekle\s+await asyncio\.sleep\(\d+ \* 60\)",
            "# 5 dakika bekle\n                await asyncio.sleep(5 * 60)",
            content
        )
        
        # Dosyayı güncelle
        with open(datamining_service_path, 'w') as f:
            f.write(content)
        
        logger.info("DataMiningService ayarları daha agresif hale getirildi!")
        return True
        
    except Exception as e:
        logger.error(f"DataMiningService güncellenirken hata: {str(e)}")
        return False

def update_service_manager():
    """ServiceManager sınıfındaki watchdog ayarlarını daha hızlı hale getirir"""
    try:
        # Ana dizini belirle
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        service_manager_path = os.path.join(base_dir, "bot", "services", "service_manager.py")
        
        if not os.path.exists(service_manager_path):
            logger.error(f"service_manager.py dosyası bulunamadı: {service_manager_path}")
            return False
        
        # Yedekleme yap
        backup_path = f"{service_manager_path}.bak"
        shutil.copy2(service_manager_path, backup_path)
        logger.info(f"Yedek oluşturuldu: {backup_path}")
        
        # Dosyayı oku
        with open(service_manager_path, 'r') as f:
            content = f.read()
        
        # Watchdog ayarlarını güncelle
        content = re.sub(
            r"CHECK_INTERVAL = \d+\s*# \d+ saniyede bir kontrol et",
            "CHECK_INTERVAL = 5  # 5 saniyede bir kontrol et",
            content
        )
        content = re.sub(
            r"MAX_SERVICE_SILENCE = \d+\s*# \d+ dakika yanıt vermezse yeniden başlat",
            "MAX_SERVICE_SILENCE = 30  # 30 saniye yanıt vermezse yeniden başlat",
            content
        )
        content = re.sub(
            r"MAX_RESTART_ATTEMPTS = \d+\s*# Maksimum \d+ kez yeniden başlatmayı dene",
            "MAX_RESTART_ATTEMPTS = 10  # Maksimum 10 kez yeniden başlatmayı dene",
            content
        )
        
        # Servis yeniden başlatma beklemesini güncelle
        content = re.sub(
            r"# Yeniden başlatma öncesi biraz bekle \(\d+ saniye\)\s+await asyncio\.sleep\(\d+\)",
            "# Yeniden başlatma öncesi biraz bekle (1 saniye)\n                    await asyncio.sleep(1)",
            content
        )
        
        # Heartbeat güncellemesi sıklığını güncelle
        content = re.sub(
            r"# Her \d+ saniyede bir çalışan servislerin heartbeat'ini güncelle\s+await asyncio\.sleep\(\d+\)",
            "# Her 2 saniyede bir çalışan servislerin heartbeat'ini güncelle\n            await asyncio.sleep(2)",
            content
        )
        
        # Dosyayı güncelle
        with open(service_manager_path, 'w') as f:
            f.write(content)
        
        logger.info("ServiceManager ayarları daha agresif hale getirildi!")
        return True
        
    except Exception as e:
        logger.error(f"ServiceManager güncellenirken hata: {str(e)}")
        return False

def restart_bot():
    """Botu yeniden başlatır"""
    try:
        logger.info("Bot yeniden başlatılıyor...")
        
        # Önce çalışan botu durdur
        os.system("pkill -f 'python -m bot.main'")
        
        # 1 saniye bekle
        import time
        time.sleep(1)
        
        # Botu başlat
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.system(f"cd {base_dir} && python -m bot.main > /dev/null 2>&1 &")
        
        logger.info("Bot yeniden başlatıldı!")
        return True
        
    except Exception as e:
        logger.error(f"Bot yeniden başlatılırken hata: {str(e)}")
        return False

def main():
    """Ana çalışma işlevi"""
    logger.info("🚀 Telegram bot ayarları agresif hale getiriliyor...")
    
    # MessageService güncelle
    if update_message_service():
        logger.info("✅ MessageService ayarları güncellemesi başarılı")
    else:
        logger.error("❌ MessageService ayarları güncellemesi başarısız")
    
    # AnnouncementService güncelle
    if update_announcement_service():
        logger.info("✅ AnnouncementService ayarları güncellemesi başarılı")
    else:
        logger.error("❌ AnnouncementService ayarları güncellemesi başarısız")
    
    # DataMiningService güncelle
    if update_datamining_service():
        logger.info("✅ DataMiningService ayarları güncellemesi başarılı")
    else:
        logger.error("❌ DataMiningService ayarları güncellemesi başarısız")
    
    # ServiceManager güncelle
    if update_service_manager():
        logger.info("✅ ServiceManager ayarları güncellemesi başarılı")
    else:
        logger.error("❌ ServiceManager ayarları güncellemesi başarısız")
    
    # Botu yeniden başlat
    if restart_bot():
        logger.info("🎉 Tüm ayarlar güncellendi ve bot yeniden başlatıldı!")
    else:
        logger.warning("⚠️ Ayarlar güncellendi fakat bot yeniden başlatılamadı, lütfen manuel olarak yeniden başlatın")
    
    logger.info("İşlem tamamlandı! Bot artık çok daha agresif mesaj gönderecek.")

if __name__ == "__main__":
    main() 