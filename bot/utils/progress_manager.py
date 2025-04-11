"""
# ============================================================================ #
# Dosya: progress_manager.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/utils/progress_manager.py
# İşlev: Telegram botunun ilerleme ve durum yönetimi.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class ProgressManager:
    """
    İlerleme ve durum yönetimi için yardımcı sınıf.
    
    Bu sınıf, grup mesajları, davetler ve diğer işlemler için 
    ilerleme durumunu takip etmeyi sağlar.
    """
    
    def __init__(self):
        """ProgressManager sınıfı başlatıcısı."""
        self.progress = {}
        self.stats = {
            'started_at': datetime.now(),
            'total_items': 0,
            'completed_items': 0,
            'error_count': 0,
            'success_rate': 0.0
        }
        self.last_updated = datetime.now()
    
    def start_tracking(self, task_id: str, total_items: int) -> None:
        """
        Yeni bir görev için ilerleme takibi başlat.
        
        Args:
            task_id: Görev tanımlayıcısı
            total_items: Toplam öğe sayısı
        """
        self.progress[task_id] = {
            'started_at': datetime.now(),
            'total_items': total_items,
            'completed_items': 0,
            'current_item': None,
            'error_count': 0,
            'last_updated': datetime.now(),
            'status': 'running',
            'eta': None
        }
        self.stats['total_items'] += total_items
        
    def update_progress(self, task_id: str, completed: int = 1, 
                       current_item: Any = None, has_error: bool = False) -> None:
        """
        Görev ilerlemesini güncelle.
        
        Args:
            task_id: Görev tanımlayıcısı
            completed: Tamamlanan öğe sayısı
            current_item: Şu anki işlenen öğe
            has_error: Hata oluştu mu
        """
        if task_id not in self.progress:
            logger.warning(f"Bilinmeyen görev ID: {task_id}")
            return
            
        # İlerlemeyi güncelle
        self.progress[task_id]['completed_items'] += completed
        self.progress[task_id]['current_item'] = current_item
        self.progress[task_id]['last_updated'] = datetime.now()
        
        if has_error:
            self.progress[task_id]['error_count'] += 1
            self.stats['error_count'] += 1
        
        # Genel istatistikleri güncelle
        self.stats['completed_items'] += completed
        self.last_updated = datetime.now()
        
        # Başarı oranını hesapla
        if self.stats['total_items'] > 0:
            self.stats['success_rate'] = ((self.stats['total_items'] - self.stats['error_count']) / 
                                         self.stats['total_items']) * 100
                                         
        # Tahmini tamamlanma süresini hesapla
        task = self.progress[task_id]
        if task['total_items'] > 0 and task['completed_items'] > 0:
            elapsed = (datetime.now() - task['started_at']).total_seconds()
            rate = task['completed_items'] / elapsed if elapsed > 0 else 0
            remaining = (task['total_items'] - task['completed_items']) / rate if rate > 0 else 0
            self.progress[task_id]['eta'] = datetime.now() + timedelta(seconds=remaining)
    
    def complete_task(self, task_id: str) -> None:
        """
        Görevi tamamlandı olarak işaretle.
        
        Args:
            task_id: Görev tanımlayıcısı
        """
        if task_id not in self.progress:
            logger.warning(f"Bilinmeyen görev ID: {task_id}")
            return
            
        self.progress[task_id]['status'] = 'completed'
        self.progress[task_id]['completed_items'] = self.progress[task_id]['total_items']
        self.progress[task_id]['last_updated'] = datetime.now()
    
    def get_status(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Görevin durumunu döndür.
        
        Args:
            task_id: Görev tanımlayıcısı (None ise genel durum)
            
        Returns:
            Dict: Durum bilgisi
        """
        if task_id is not None and task_id in self.progress:
            return self.progress[task_id]
        
        return {
            'tasks': len(self.progress),
            'stats': self.stats,
            'last_updated': self.last_updated
        }
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm görevlerin durumunu döndür.
        
        Returns:
            Dict: Tüm görevlerin durumu
        """
        return self.progress