"""
# ============================================================================ #
# Dosya: gpt_helper.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/utils/gpt_helper.py
# İşlev: OpenAI GPT API ile etkileşim için yardımcı sınıf.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class GptHelper:
    """
    OpenAI GPT API ile etkileşim için basit yardımcı sınıf.
    """
    
    def __init__(self, api_key=None, model="gpt-3.5-turbo", temperature=0.7, max_tokens=150):
        """GptHelper başlatıcısı."""
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.is_available = bool(self.api_key)
        self.total_tokens = 0
        self.error_count = 0
        
    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """GPT yanıtı üretir."""
        logger.warning("generate_response çağrıldı fakat GPT API entegrasyonu devre dışı.")
        return "GPT API devre dışı."
            
    def get_status(self) -> Dict[str, Any]:
        """GptHelper durumunu döndürür."""
        return {
            "is_available": self.is_available,
            "model": self.model,
            "total_tokens": self.total_tokens,
            "error_count": self.error_count
        }