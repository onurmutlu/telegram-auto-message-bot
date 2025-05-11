"""
API Router

API rotalarını tanımlar.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import messages, services, groups, users, auth, settings
try:
    # Yeni endpoint'leri import etmeyi dene
    from app.api.v1.endpoints import analytics, stats, health, admin, session
except ImportError:
    # İçeri aktarma hatası olduğunda sessizce devam et
    pass

api_router = APIRouter()

# Temel rotalar
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(services.router, prefix="/services", tags=["services"])

# Auth rotaları
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Ayarlar rotaları
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])

# Yeni eklenen rotalar (varsa)
try:
    api_router.include_router(analytics.router)  # Yeni analytics endpoint'i
except NameError:
    pass

try:
    api_router.include_router(stats.router)
    api_router.include_router(health.router)
    api_router.include_router(admin.router)
    api_router.include_router(session.router)
except NameError:
    pass 