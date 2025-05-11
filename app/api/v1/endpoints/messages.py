"""
Message API

Mesaj işlemleri için API endpoint'leri.
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.logger import get_logger
from app.db import models
from app.api.v1.schemas.message import (
    MessageCreate, 
    MessageUpdate, 
    MessageResponse, 
    MessageScheduleResponse
)

router = APIRouter()
logger = get_logger(__name__)

@router.get("/", response_model=List[MessageResponse])
async def get_messages(
    skip: int = 0,
    limit: int = 100,
    group_id: Optional[int] = None,
    is_scheduled: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Mesajları listeler.
    
    - **skip**: Atlama değeri
    - **limit**: Limit değeri
    - **group_id**: Grup ID'sine göre filtrele
    - **is_scheduled**: Zamanlanmış mesajları filtrele
    """
    logger.info(f"Mesajlar listeleniyor: skip={skip}, limit={limit}, group_id={group_id}")
    
    query = db.query(models.MessageTracking)
    
    # Filtreleme
    if group_id:
        query = query.filter(models.MessageTracking.group_id == group_id)
    if is_scheduled is not None:
        query = query.filter(models.MessageTracking.is_scheduled == is_scheduled)
    
    # Sıralama ve sayfalama
    messages = query.order_by(models.MessageTracking.created_at.desc()).offset(skip).limit(limit).all()
    
    return messages

@router.post("/", response_model=MessageResponse)
async def create_message(
    message: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Yeni bir mesaj oluşturur.
    
    - **message**: Mesaj verileri
    """
    logger.info(f"Yeni mesaj oluşturuluyor: group_id={message.group_id}")
    
    db_message = models.MessageTracking(
        group_id=message.group_id,
        content=message.content,
        content_type=message.content_type,
        is_scheduled=message.scheduled_time is not None,
        scheduled_time=message.scheduled_time
    )
    
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    logger.info(f"Mesaj oluşturuldu: id={db_message.id}")
    
    return db_message

@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: int = Path(..., title="Mesaj ID", description="Görüntülenecek mesajın ID'si"),
    db: Session = Depends(get_db)
):
    """
    Belirli bir mesajı görüntüler.
    
    - **message_id**: Mesaj ID
    """
    message = db.query(models.MessageTracking).filter(models.MessageTracking.id == message_id).first()
    
    if not message:
        logger.warning(f"Mesaj bulunamadı: id={message_id}")
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı")
    
    return message

@router.put("/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: int = Path(..., title="Mesaj ID", description="Güncellenecek mesajın ID'si"),
    message_update: MessageUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Bir mesajı günceller.
    
    - **message_id**: Mesaj ID
    - **message_update**: Güncellenecek alanlar
    """
    db_message = db.query(models.MessageTracking).filter(models.MessageTracking.id == message_id).first()
    
    if not db_message:
        logger.warning(f"Güncellenecek mesaj bulunamadı: id={message_id}")
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı")
    
    update_data = message_update.dict(exclude_unset=True)
    
    # Zamanlanmış mesaj kontrolü
    if "scheduled_time" in update_data:
        db_message.is_scheduled = update_data["scheduled_time"] is not None
    
    # Alanları güncelle
    for key, value in update_data.items():
        setattr(db_message, key, value)
    
    db_message.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_message)
    
    logger.info(f"Mesaj güncellendi: id={message_id}")
    
    return db_message

@router.delete("/{message_id}", response_model=dict)
async def delete_message(
    message_id: int = Path(..., title="Mesaj ID", description="Silinecek mesajın ID'si"),
    db: Session = Depends(get_db)
):
    """
    Bir mesajı siler.
    
    - **message_id**: Mesaj ID
    """
    db_message = db.query(models.MessageTracking).filter(models.MessageTracking.id == message_id).first()
    
    if not db_message:
        logger.warning(f"Silinecek mesaj bulunamadı: id={message_id}")
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı")
    
    db.delete(db_message)
    db.commit()
    
    logger.info(f"Mesaj silindi: id={message_id}")
    
    return {"message": "Mesaj başarıyla silindi", "id": message_id}

@router.post("/schedule", response_model=MessageScheduleResponse)
async def schedule_message(
    message: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    Bir mesajı zamanlayarak gönderir.
    
    - **message**: Mesaj verileri (scheduled_time alanı dolu olmalı)
    """
    if not message.scheduled_time:
        logger.error("Zamanlanmış mesaj için scheduled_time alanı gerekli")
        raise HTTPException(status_code=400, detail="Zamanlanmış mesaj için scheduled_time alanı gerekli")
    
    # Mesajı oluştur
    db_message = models.MessageTracking(
        group_id=message.group_id,
        content=message.content,
        content_type=message.content_type,
        is_scheduled=True,
        scheduled_time=message.scheduled_time,
        status="pending"
    )
    
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    logger.info(f"Mesaj zamanlandı: id={db_message.id}, scheduled_time={message.scheduled_time}")
    
    # Scheduler'a ekle (Burada gerçek scheduler servisine gönderim yapılacak)
    # from app.services.scheduler_service import add_scheduled_message
    # await add_scheduled_message(db_message.id)
    
    return {
        "id": db_message.id,
        "scheduled_time": db_message.scheduled_time,
        "status": "scheduled",
        "message": "Mesaj başarıyla zamanlandı"
    }

@router.post("/send/{message_id}", response_model=dict)
async def send_message_now(
    message_id: int = Path(..., title="Mesaj ID", description="Gönderilecek mesajın ID'si"),
    db: Session = Depends(get_db)
):
    """
    Bir mesajı hemen gönderir.
    
    - **message_id**: Gönderilecek mesajın ID'si
    """
    db_message = db.query(models.MessageTracking).filter(models.MessageTracking.id == message_id).first()
    
    if not db_message:
        logger.warning(f"Gönderilecek mesaj bulunamadı: id={message_id}")
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı")
    
    # Gönderim işlemini yap (Burada gerçek gönderim servisine istek yapılacak)
    # from app.services.message_service import send_message
    # success = await send_message(db_message)
    success = True  # Şimdilik başarılı kabul edelim
    
    if success:
        db_message.sent_at = datetime.utcnow()
        db_message.status = "sent"
        db_message.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Mesaj gönderildi: id={message_id}")
        
        return {"message": "Mesaj başarıyla gönderildi", "id": message_id}
    else:
        logger.error(f"Mesaj gönderme hatası: id={message_id}")
        raise HTTPException(status_code=500, detail="Mesaj gönderilirken bir hata oluştu") 