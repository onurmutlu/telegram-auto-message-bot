"""
# ============================================================================ #
# Dosya: messaging.py
# Yol: /Users/siyahkare/code/telegram-bot/app/models/messaging.py
# İşlev: Mesaj etkinliği ve DM dönüşüm takibi için model sınıfları.
#
# Versiyon: v1.0.0
# ============================================================================ #
"""

from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from pydantic import validator
from enum import Enum, auto
from uuid import uuid4

class MessageCategory(str, Enum):
    """Mesaj kategorileri"""
    ENGAGE = "engage"
    DM_INVITE = "dm_invite"
    WELCOME = "welcome"
    PROMOTION = "promotion"
    REGULAR = "regular"
    RESPONSE = "response"
    QUESTION = "question"

class MessageEffectiveness(SQLModel, table=True):
    """
    Mesaj etkinliği takibi için model.
    
    Bu tablo, gönderilen her mesajın etkinliğini ve aldığı yanıtları takip eder.
    """
    __tablename__ = "message_effectiveness"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    message_id: int = Field(index=True)
    group_id: int = Field(index=True)
    content: str
    category: str = Field(default=MessageCategory.REGULAR)
    sent_at: datetime = Field(default_factory=datetime.now)
    
    # Etkinlik metrikleri
    views: int = Field(default=0)
    reactions: int = Field(default=0)
    replies: int = Field(default=0)
    forwards: int = Field(default=0)
    
    # İlişkili DM dönüşümleri
    conversions: List["DMConversion"] = Relationship(back_populates="source_message")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now, sa_column_kwargs={"onupdate": datetime.now})

class ConversionType(str, Enum):
    """DM dönüşüm tipleri"""
    DIRECT_REPLY = "direct_reply"  # Doğrudan mesaj yanıtı olarak DM
    INVITE_CLICK = "invite_click"  # DM daveti tıklaması
    USER_INITIATED = "user_initiated"  # Kullanıcı tarafından başlatılan
    BOT_COMMAND = "bot_command"  # Bot komutu ile başlatılan

class DMConversion(SQLModel, table=True):
    """
    DM dönüşüm takibi için model.
    
    Bu tablo, grup mesajlarından özel mesaja geçişleri takip eder.
    """
    __tablename__ = "dm_conversions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    conversion_id: str = Field(default_factory=lambda: str(uuid4()), index=True)
    user_id: int = Field(index=True)
    source_message_id: Optional[int] = Field(default=None, foreign_key="message_effectiveness.id")
    group_id: int = Field(index=True)
    conversion_type: str = Field(default=ConversionType.USER_INITIATED)
    converted_at: datetime = Field(default_factory=datetime.now)
    
    # Takip metrikleri
    message_count: int = Field(default=0)  # Dönüşüm sonrası mesaj sayısı
    response_time: float = Field(default=0.0)  # İlk yanıta kadar geçen süre (saniye)
    session_duration: float = Field(default=0.0)  # Toplam oturum süresi (saniye)
    is_successful: bool = Field(default=False)  # Başarılı dönüşüm mü? (işlem tamamlandı mı)
    
    # İlişkiler
    source_message: Optional[MessageEffectiveness] = Relationship(back_populates="conversions")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now, sa_column_kwargs={"onupdate": datetime.now})

# Veri Şemaları (API için)
class MessageEffectivenessCreate(SQLModel):
    """Mesaj etkinliği oluşturma şeması"""
    message_id: int
    group_id: int
    content: str
    category: str = MessageCategory.REGULAR

class MessageEffectivenessUpdate(SQLModel):
    """Mesaj etkinliği güncelleme şeması"""
    views: Optional[int] = None
    reactions: Optional[int] = None
    replies: Optional[int] = None
    forwards: Optional[int] = None

class DMConversionCreate(SQLModel):
    """DM dönüşümü oluşturma şeması"""
    user_id: int
    source_message_id: Optional[int] = None
    group_id: int
    conversion_type: str = ConversionType.USER_INITIATED

class DMConversionUpdate(SQLModel):
    """DM dönüşümü güncelleme şeması"""
    message_count: Optional[int] = None
    response_time: Optional[float] = None
    session_duration: Optional[float] = None
    is_successful: Optional[bool] = None 