from typing import Optional, List
from datetime import datetime
from enum import Enum
from sqlmodel import Field, Relationship
from app.models.base import BaseModel

class MessageTemplate(BaseModel, table=True):
    """Mesaj şablonlarını temsil eden model"""
    __tablename__ = "message_templates"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str = Field(default="")
    type: str = Field(default="engagement")  # engagement, reply, dm_welcome, dm_service, dm_invite, promo
    engagement_rate: float = Field(default=0.0)
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    def __repr__(self) -> str:
        preview = self.content[:30] + "..." if len(self.content) > 30 else self.content
        return f"<MessageTemplate {self.type}: {preview}>" 