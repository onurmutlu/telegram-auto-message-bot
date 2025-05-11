"""
# ============================================================================ #
# Dosya: analytics.py
# Yol: /Users/siyahkare/code/telegram-bot/app/api/v1/endpoints/analytics.py
# İşlev: Telegram bot analitik API endpoint'leri.
#
# Versiyon: v1.0.0
# ============================================================================ #
"""

from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.db.session import get_session
from app.services.analytics.message_analytics_service import MessageAnalyticsService
from app.models.messaging import MessageCategory

# Router oluştur
router = APIRouter(prefix="/analytics", tags=["analytics"])

# Servis örneği - lazy loading
_message_analytics_service = None

async def get_message_analytics_service() -> MessageAnalyticsService:
    """MessageAnalyticsService örneğini döndürür"""
    global _message_analytics_service
    if _message_analytics_service is None:
        _message_analytics_service = MessageAnalyticsService()
        await _message_analytics_service._start()
    return _message_analytics_service

@router.get("/message/top", response_model=List[Dict[str, Any]])
async def get_top_performing_messages(
    days: int = Query(7, ge=1, le=90, description="Kaç günlük mesajları getireceği"),
    category: Optional[str] = Query(None, description="Mesaj kategorisi (engage, dm_invite, welcome, vb.)"),
    service: MessageAnalyticsService = Depends(get_message_analytics_service)
):
    """
    En iyi performans gösteren mesajları getirir.
    
    Args:
        days: Kaç günlük mesajları getireceği
        category: Mesaj kategorisi (None ise tüm kategoriler)
    
    Returns:
        List[Dict[str, Any]]: En iyi performans gösteren mesajlar
    """
    return await service.get_top_performing_messages(days=days, category=category)

@router.get("/message/category-performance", response_model=Dict[str, Any])
async def get_message_category_performance(
    service: MessageAnalyticsService = Depends(get_message_analytics_service)
):
    """
    Mesaj kategorilerine göre performans raporunu getirir.
    
    Returns:
        Dict[str, Any]: Mesaj kategorisi performans raporu
    """
    return await service.get_category_performance()

@router.get("/dm/conversions", response_model=Dict[str, Any])
async def get_dm_conversion_metrics(
    service: MessageAnalyticsService = Depends(get_message_analytics_service)
):
    """
    DM dönüşüm metriklerini getirir.
    
    Returns:
        Dict[str, Any]: DM dönüşüm metrikleri
    """
    return await service.get_conversion_metrics()

@router.get("/status", response_model=Dict[str, Any])
async def get_service_status(
    service: MessageAnalyticsService = Depends(get_message_analytics_service)
):
    """
    Analitik servisi durumunu getirir.
    
    Returns:
        Dict[str, Any]: Servis durumu
    """
    return await service.get_status()

@router.get("/reports/daily/{date}", response_model=Dict[str, Any])
async def get_daily_report(
    date: str,
    session: Session = Depends(get_session),
    service: MessageAnalyticsService = Depends(get_message_analytics_service)
):
    """
    Belirli bir tarihe ait günlük raporu getirir.
    
    Args:
        date: Rapor tarihi (YYYY-MM-DD formatında)
    
    Returns:
        Dict[str, Any]: Günlük rapor
    """
    try:
        from sqlalchemy import text
        import json
        
        # Raporu veritabanından al
        query = text("""
            SELECT content
            FROM analytics_reports
            WHERE report_date = :date AND report_type = 'message_daily'
        """)
        
        result = session.execute(query, {"date": date}).first()
        
        if not result:
            raise HTTPException(status_code=404, detail=f"{date} tarihine ait rapor bulunamadı")
            
        report_content = result[0]
        
        # JSON olarak parse et
        try:
            report = json.loads(report_content)
            return report
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Rapor parse edilirken hata: {str(e)}")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rapor getirilirken hata: {str(e)}")

@router.get("/message/categories", response_model=List[str])
async def get_message_categories():
    """
    Kullanılabilir mesaj kategorilerini getirir.
    
    Returns:
        List[str]: Mesaj kategorileri
    """
    return [category.value for category in MessageCategory] 