"""
Message Schemas

Mesaj ile ilgili veri modellerini tanımlar.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class MessageBase(BaseModel):
    """Mesaj için temel şema."""
    content: str = Field(..., description="Mesaj içeriği")
    content_type: str = Field(default="text", description="Mesaj içerik tipi (text, image, video vb.)")
    group_id: int = Field(..., description="Mesajın gönderileceği grup ID'si")
    
class MessageCreate(MessageBase):
    """Yeni mesaj oluşturma şeması."""
    scheduled_time: Optional[datetime] = Field(default=None, description="Mesajın zamanlanacağı tarih/saat")
    user_id: Optional[int] = Field(default=None, description="Mesajı gönderen kullanıcı ID'si")
    reply_to_message_id: Optional[int] = Field(default=None, description="Yanıt verilen mesaj ID'si")
    is_outgoing: bool = Field(default=True, description="Giden mesaj mı?")
    
class MessageUpdate(BaseModel):
    """Mesaj güncelleme şeması."""
    content: Optional[str] = Field(default=None, description="Mesaj içeriği")
    content_type: Optional[str] = Field(default=None, description="Mesaj içerik tipi")
    scheduled_time: Optional[datetime] = Field(default=None, description="Mesajın zamanlanacağı tarih/saat")
    status: Optional[str] = Field(default=None, description="Mesaj durumu")
    
class MessageResponse(MessageBase):
    """Mesaj yanıt şeması."""
    id: int = Field(..., description="Mesaj ID'si")
    message_id: Optional[int] = Field(default=None, description="Telegram mesaj ID'si")
    user_id: Optional[int] = Field(default=None, description="Kullanıcı ID'si")
    sent_at: Optional[datetime] = Field(default=None, description="Gönderilme tarihi")
    is_outgoing: bool = Field(default=True, description="Giden mesaj mı?")
    is_reply: bool = Field(default=False, description="Yanıt mesajı mı?")
    reply_to_message_id: Optional[int] = Field(default=None, description="Yanıt verilen mesaj ID'si")
    is_scheduled: bool = Field(default=False, description="Zamanlanmış mesaj mı?")
    scheduled_time: Optional[datetime] = Field(default=None, description="Zamanlanmış tarih/saat")
    status: Optional[str] = Field(default=None, description="Mesaj durumu")
    forwards: Optional[int] = Field(default=0, description="İletilme sayısı")
    views: Optional[int] = Field(default=0, description="Görüntülenme sayısı")
    created_at: datetime = Field(..., description="Oluşturulma tarihi")
    updated_at: Optional[datetime] = Field(default=None, description="Güncellenme tarihi")
    
    class Config:
        """Pydantic yapılandırması."""
        from_attributes = True
        
class MessageScheduleResponse(BaseModel):
    """Mesaj zamanlama yanıt şeması."""
    id: int = Field(..., description="Mesaj ID'si")
    scheduled_time: datetime = Field(..., description="Zamanlanmış tarih/saat")
    status: str = Field(..., description="Mesaj durumu")
    message: str = Field(..., description="Bilgi mesajı")