"""
# ============================================================================ #
# Dosya: group.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/models/group.py
# İşlev: Telegram gruplarının model sınıfı.
#
# Amaç: Bu modül, Telegram gruplarının verilerini temsil eden model sınıfını 
# içerir. GroupService ve GroupHandler tarafından veritabanı ile uygulama 
# arasında veri transfer nesnesi olarak kullanılır. Grup durumunu, aktivitesini ve
# istatistiklerini takip etmek için gerekli özellikleri sağlar.
#
# Temel Özellikler:
# - Grup kimliği, adı, katılım tarihi gibi temel bilgilerin saklanması
# - Mesaj ve üye sayısı istatistikleri
# - Grubun aktiflik durumu ve hata takibi
# - Dictionary ve diğer formatlar arasında kolay dönüşüm
# - Tarih bazlı grup durumu izleme
#
# Build: 2025-04-08-23:55:00
# Versiyon: v3.5.0
# ============================================================================ #
#
# Değişiklik Geçmişi:
# v3.5.0 (2025-04-08) - Kapsamlı tip belirtimleri eklendi
#                      - __str__ ve __repr__ metodları eklendi
#                      - Aktivite durumu özelliği ve yardımcı metodlar eklendi
#                      - Tarih bazlı durum kontrolü için metodlar eklendi
#                      - Daha kapsamlı dokümantasyon ve örnek kullanım eklendi
# v3.4.0 (2025-04-01) - JSON dönüşüm destekleri eklendi
# v3.3.0 (2025-03-15) - İlk sürüm
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, List


class Group:
    """
    Telegram gruplarının bilgilerini temsil eden model sınıfı.
    
    Bu sınıf grup bilgilerini depolar, veritabanı ile uygulama arasında veri
    transferi sağlar ve grup durumunu izlemek için çeşitli yardımcı metodlar sunar.
    
    Attributes:
        group_id (int): Grubun benzersiz Telegram ID'si
        name (Optional[str]): Grubun adı
        join_date (Optional[datetime]): Bota gruba katılma tarihi
        last_message (Optional[datetime]): Son mesaj gönderme tarihi
        message_count (int): Gruba gönderilen toplam mesaj sayısı
        member_count (int): Gruptaki üye sayısı
        error_count (int): Grup ile ilgili toplam hata sayısı
        last_error (Optional[str]): Son alınan hata mesajı
        is_active (bool): Grubun aktif olup olmadığı
        retry_after (Optional[datetime]): Tekrar deneme zamanı (hata durumunda)
        activity_level (str): Grubun aktivite seviyesi ('high', 'medium', 'low')
    """
    
    def __init__(self, 
                 group_id: int, 
                 name: Optional[str] = None,
                 join_date: Optional[datetime] = None, 
                 last_message: Optional[datetime] = None,
                 message_count: int = 0, 
                 member_count: int = 0, 
                 error_count: int = 0, 
                 last_error: Optional[str] = None,
                 is_active: bool = True, 
                 retry_after: Optional[datetime] = None,
                 activity_level: str = 'medium'):
        """
        Grup modelinin başlatıcı metodu.
        
        Args:
            group_id: Grubun benzersiz Telegram ID'si
            name: Grubun adı
            join_date: Botun gruba katılma tarihi
            last_message: Son mesaj gönderme tarihi
            message_count: Gruba gönderilen toplam mesaj sayısı
            member_count: Gruptaki üye sayısı
            error_count: Grup ile ilgili toplam hata sayısı
            last_error: Son alınan hata mesajı
            is_active: Grubun aktif olup olmadığı
            retry_after: Tekrar deneme zamanı (hata durumunda)
            activity_level: Grubun aktivite seviyesi ('high', 'medium', 'low')
        """
        self.group_id = group_id
        self.name = name
        self.join_date = join_date
        self.last_message = last_message
        self.message_count = message_count or 0
        self.member_count = member_count or 0 
        self.error_count = error_count or 0
        self.last_error = last_error
        self.is_active = is_active if is_active is not None else True
        self.retry_after = retry_after
        self.activity_level = activity_level
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional['Group']:
        """
        Dictionary verilerinden Group nesnesi oluşturur.
        
        Args:
            data: Group nesnesini oluşturmak için gereken veriler sözlüğü
            
        Returns:
            Group: Oluşturulan Group nesnesi veya None (eğer data None ise)
            
        Example:
            ```python
            group_data = {
                'group_id': 12345678,
                'name': 'Test Grubu',
                'message_count': 10
            }
            group = Group.from_dict(group_data)
            ```
        """
        if not data:
            return None
        return cls(
            group_id=data.get('group_id'),
            name=data.get('name'),
            join_date=data.get('join_date'),
            last_message=data.get('last_message'),
            message_count=data.get('message_count', 0),
            member_count=data.get('member_count', 0),
            error_count=data.get('error_count', 0),
            last_error=data.get('last_error'),
            is_active=data.get('is_active', True),
            retry_after=data.get('retry_after'),
            activity_level=data.get('activity_level', 'medium')
        )
    
    @classmethod
    def from_entity(cls, entity: Any) -> 'Group':
        """
        Telethon Entity nesnesinden Group nesnesi oluşturur.
        
        Args:
            entity: Telethon kütüphanesinden gelen Chat/Channel entity
            
        Returns:
            Group: Oluşturulan Group nesnesi
        """
        group_id = getattr(entity, 'id', 0)
        name = getattr(entity, 'title', f'Grup {group_id}')
        member_count = getattr(entity, 'participants_count', 0)
        
        return cls(
            group_id=group_id,
            name=name,
            join_date=datetime.now(),
            member_count=member_count,
            is_active=True
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Group nesnesini sözlük formatına dönüştürür.
        
        Returns:
            Dict[str, Any]: Grup bilgilerini içeren sözlük
            
        Example:
            ```python
            group = Group(12345678, name="Test Grubu")
            group_dict = group.to_dict()
            ```
        """
        return {
            'group_id': self.group_id,
            'name': self.name,
            'join_date': self.join_date,
            'last_message': self.last_message,
            'message_count': self.message_count,
            'member_count': self.member_count,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'is_active': self.is_active,
            'retry_after': self.retry_after,
            'activity_level': self.activity_level
        }
        
    def to_json_compatible(self) -> Dict[str, Any]:
        """
        JSON serileştirmeye uygun bir sözlük döndürür.
        
        Returns:
            Dict[str, Any]: JSON uyumlu sözlük
        """
        result = self.to_dict()
        
        # Datetime nesnelerini string'e dönüştür
        if self.join_date:
            result['join_date'] = self.join_date.isoformat()
        if self.last_message:
            result['last_message'] = self.last_message.isoformat()
        if self.retry_after:
            result['retry_after'] = self.retry_after.isoformat()
            
        return result
    
    def increment_message_count(self, count: int = 1) -> None:
        """
        Mesaj sayacını artırır ve son mesaj zamanını günceller.
        
        Args:
            count: Artırılacak miktar (varsayılan: 1)
        """
        self.message_count += count
        self.last_message = datetime.now()
    
    def increment_error_count(self, error_message: Optional[str] = None) -> None:
        """
        Hata sayacını artırır ve son hata mesajını günceller.
        
        Args:
            error_message: Kaydedilecek hata mesajı
        """
        self.error_count += 1
        if error_message:
            self.last_error = error_message
    
    def set_inactive(self, hours: int = 24, error_message: Optional[str] = None) -> None:
        """
        Grubu belirtilen süre için devre dışı bırakır.
        
        Args:
            hours: Devre dışı kalacağı saat
            error_message: Devre dışı bırakma nedeni
        """
        self.is_active = False
        self.retry_after = datetime.now() + timedelta(hours=hours)
        
        if error_message:
            self.last_error = error_message
            self.error_count += 1
    
    def set_active(self) -> None:
        """
        Grubu tekrar aktif hale getirir.
        """
        self.is_active = True
        self.retry_after = None
        self.error_count = 0
    
    def should_retry(self) -> bool:
        """
        Grubun tekrar deneme zamanının gelip gelmediğini kontrol eder.
        
        Returns:
            bool: Tekrar deneme zamanı geldiyse True
        """
        if self.is_active:
            return True
            
        if not self.retry_after:
            return True
            
        return datetime.now() >= self.retry_after
    
    def update_activity_level(self, level: str = None) -> None:
        """
        Grubun aktivite seviyesini günceller.
        
        Args:
            level: Aktivite seviyesi ('high', 'medium', 'low')
        """
        if level in ('high', 'medium', 'low'):
            self.activity_level = level
    
    def calculate_message_interval(self) -> int:
        """
        Aktivite seviyesine göre mesaj gönderme aralığını hesaplar.
        
        Returns:
            int: Saniye cinsinden mesaj aralığı
        """
        if self.activity_level == 'high':
            return 60 * 15  # 15 dakika
        elif self.activity_level == 'medium':
            return 60 * 30  # 30 dakika
        else:
            return 60 * 60  # 1 saat
    
    def was_messaged_recently(self, minutes: int = 60) -> bool:
        """
        Gruba yakın zamanda mesaj gönderilip gönderilmediğini kontrol eder.
        
        Args:
            minutes: Kontrol edilecek dakika aralığı
            
        Returns:
            bool: Belirtilen süre içinde mesaj gönderildiyse True
        """
        if not self.last_message:
            return False
            
        threshold = datetime.now() - timedelta(minutes=minutes)
        return self.last_message >= threshold
    
    def __str__(self) -> str:
        """
        Grubun okunabilir bir string temsilini döndürür.
        
        Returns:
            str: Grup bilgisi
        """
        active_status = "Aktif" if self.is_active else f"Devre dışı (yeniden: {self.retry_after})"
        return f"Grup '{self.name}' (ID: {self.group_id}) - {active_status}"
    
    def __repr__(self) -> str:
        """
        Grubun teknik bir string temsilini döndürür.
        
        Returns:
            str: Grup teknik temsili
        """
        return f"Group(id={self.group_id}, name='{self.name}', active={self.is_active}, msgs={self.message_count})"
    
    def __eq__(self, other) -> bool:
        """
        İki grup nesnesinin eşit olup olmadığını kontrol eder.
        
        Args:
            other: Karşılaştırılacak diğer nesne
            
        Returns:
            bool: Grup ID'leri aynıysa True
        """
        if not isinstance(other, Group):
            return False
        return self.group_id == other.group_id