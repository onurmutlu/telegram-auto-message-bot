"""Çalışma zamanı monitör sınıfı"""
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class RuntimeMonitor:
    """Bot çalışma zamanı bilgilerini izleyen sınıf"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.processed_messages = 0
        self.sent_messages = 0
        self.errors = 0
        self.last_activity = datetime.now()
        self.last_periodic_log = datetime.now()
    
    def get_uptime(self):
        """Çalışma süresini döndürür"""
        uptime = datetime.now() - self.start_time
        hours, remainder = divmod(uptime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours)}:{int(minutes):02}:{int(seconds):02}"
    
    def get_stats_dict(self):
        """İstatistikleri sözlük olarak döndürür"""
        return {
            "uptime": self.get_uptime(),
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "processed_messages": self.processed_messages,
            "sent_messages": self.sent_messages,
            "errors": self.errors,
            "idle_time": (datetime.now() - self.last_activity).total_seconds()
        }
    
    def record_message_sent(self):
        """Gönderilmiş mesajı kaydeder"""
        self.sent_messages += 1
        self.last_activity = datetime.now()
        
    def record_message_processed(self):
        """İşlenmiş mesajı kaydeder"""
        self.processed_messages += 1
        self.last_activity = datetime.now()
        
    def record_error(self):
        """Hata kaydeder"""
        self.errors += 1
        self.last_activity = datetime.now()
        
    def get_formatted_report(self):
        """Formatlı istatistik raporu döndürür"""
        stats = self.get_stats_dict()
        return f"""Çalışma Süresi: {stats['uptime']}
Başlangıç: {stats['start_time']}
İşlenen Mesaj: {stats['processed_messages']}
Gönderilen Mesaj: {stats['sent_messages']}
Hata Sayısı: {stats['errors']}
Son Aktivite: {self.last_activity.strftime('%H:%M:%S')}
"""
    
    def log_periodic_stats(self, interval_minutes=60):
        """Belirli aralıklarla istatistikleri loglar"""
        current_time = datetime.now()
        if (current_time - self.last_periodic_log).total_seconds() >= interval_minutes * 60:
            logger.info(f"Periyodik İstatistikler: {self.get_formatted_report()}")
            self.last_periodic_log = current_time
            return True
        return False