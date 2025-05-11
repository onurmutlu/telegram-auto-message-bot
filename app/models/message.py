from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from enum import Enum
from sqlmodel import Field, Relationship
from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.group import Group
    from app.models.user import User

class MessageStatus(str, Enum):
    """Mesaj durumları"""
    # Büyük harfli versiyonlar (SQLModel standartları)
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SCHEDULED = "SCHEDULED"
    # Küçük harfli versiyonlar (DB'de mevcut eski değerler)
    pending = "pending"  
    sent = "sent"
    failed = "failed"
    scheduled = "scheduled"
    
    @classmethod
    def normalize(cls, value):
        """Herhangi bir formattaki durum değerini standart formata dönüştürür"""
        if value is None:
            return cls.PENDING
        
        # String ise
        if isinstance(value, str):
            # Uppercase yapıp enum değerini bul
            try:
                upper_value = value.upper()
                if upper_value == "PENDING":
                    return cls.PENDING
                elif upper_value == "SENT":
                    return cls.SENT
                elif upper_value == "FAILED":
                    return cls.FAILED
                elif upper_value == "SCHEDULED":
                    return cls.SCHEDULED
                # Eşleşme bulunamazsa varsayılan
                return cls.PENDING
            except (KeyError, AttributeError):
                # Eşleşme bulunamazsa varsayılan
                return cls.PENDING
        
        # Zaten enum ise
        if isinstance(value, cls):
            return value
            
        # Varsayılan değer
        return cls.PENDING

class MessageType(str, Enum):
    """Mesaj tipleri"""
    # Büyük harfli versiyonlar (SQLModel standartları)
    TEXT = "TEXT"
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
    STICKER = "STICKER"
    POLL = "POLL"
    # Küçük harfli versiyonlar (DB'de mevcut eski değerler)
    text = "text"
    photo = "photo"
    video = "video"
    document = "document"
    sticker = "sticker"
    poll = "poll"
    
    @classmethod
    def normalize(cls, value):
        """Herhangi bir formattaki tip değerini standart formata dönüştürür"""
        if value is None:
            return cls.TEXT
        
        # String ise
        if isinstance(value, str):
            # Uppercase yapıp enum değerini bul
            try:
                upper_value = value.upper()
                if upper_value == "TEXT":
                    return cls.TEXT
                elif upper_value == "PHOTO":
                    return cls.PHOTO
                elif upper_value == "VIDEO":
                    return cls.VIDEO
                elif upper_value == "DOCUMENT":
                    return cls.DOCUMENT
                elif upper_value == "STICKER":
                    return cls.STICKER
                elif upper_value == "POLL":
                    return cls.POLL
                # Eşleşme bulunamazsa varsayılan
                return cls.TEXT
            except (KeyError, AttributeError):
                # Eşleşme bulunamazsa varsayılan
                return cls.TEXT
        
        # Zaten enum ise
        if isinstance(value, cls):
            return value
            
        # Varsayılan değer
        return cls.TEXT
    
class Message(BaseModel, table=True):
    """Telegram mesajlarını temsil eden model"""
    __tablename__ = "messages"
    
    # Veritabanında var olan alanlar
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: Optional[int] = Field(default=None, index=True, foreign_key="groups.group_id")
    content: str = Field(default="")
    sent_at: Optional[datetime] = None
    status: Optional[str] = Field(default=MessageStatus.PENDING.value)
    error: Optional[str] = None
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    scheduled_for: Optional[datetime] = None
    message_type: Optional[str] = Field(default=MessageType.TEXT.value)
    media_path: Optional[str] = Field(default=None)
    media_id: Optional[str] = Field(default=None)
    reply_to_message_id: Optional[int] = Field(default=None)
    user_id: Optional[int] = Field(default=None)
    
    # İlişkiler
    group: Optional["Group"] = Relationship(back_populates="messages", sa_relationship_kwargs={"lazy": "selectin"})
    
    def __repr__(self) -> str:
        preview = self.content[:30] + "..." if len(self.content) > 30 else self.content
        return f"<Message {self.message_type or 'text'}: {preview}>" 