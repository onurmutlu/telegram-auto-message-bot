"""
Geriye dönük uyumluluk için base.py.
Bu dosya sadece BaseService'i dışa aktarmak için kullanılır.
"""

from app.services.base_service import BaseService, ConfigAdapter

__all__ = ["BaseService", "ConfigAdapter"] 