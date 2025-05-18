"""
API Router

API rotalarını tanımlar.
"""

from fastapi import APIRouter

# from app.api.v1.endpoints import messages, services, groups, users, auth, settings
from app.api.v1.endpoints import messages, services, auth # Temporarily remove groups, users, and settings
try:
    # Yeni endpoint'leri import etmeyi dene
    # from app.api.v1.endpoints import analytics, stats, health, admin, session
    from app.api.v1.endpoints import analytics, health, admin # Temporarily remove stats and session if not critical
except ImportError:
    # İçeri aktarma hatası olduğunda sessizce devam et
    pass

api_router = APIRouter()

# Temel rotalar
# api_router.include_router(users.router, prefix="/users", tags=["users"]) # Temporarily commented out
# api_router.include_router(groups.router, prefix="/groups", tags=["groups"]) # Temporarily commented out
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(services.router, prefix="/services", tags=["services"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# api_router.include_router(settings.router, prefix="/settings", tags=["settings"]) # settings.py yok, router eklemesini kaldır

# Yeni rotaları eklemeyi dene (opsiyonel)
if 'analytics' in globals():
    api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
# if 'stats' in globals(): # Temporarily commented out
#     api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
if 'health' in globals():
    api_router.include_router(health.router, prefix="/health", tags=["health"])
if 'admin' in globals():
    api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
# if 'session' in globals(): # Temporarily commented out
#     api_router.include_router(session.router, prefix="/session", tags=["session"])