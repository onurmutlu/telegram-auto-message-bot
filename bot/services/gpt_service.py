"""
# ============================================================================ #
# Dosya: gpt_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/gpt_service.py
# İşlev: OpenAI GPT entegrasyonu için Telegram bot servisi.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
from bot.services.base_service import BaseService
from datetime import datetime
import aiohttp
import os

logger = logging.getLogger(__name__)

class GptService(BaseService):
    """Basit OpenAI GPT entegrasyonu."""
    
    def __init__(self, client, config, db, stop_event):
        """GptService başlatıcısı."""
        super().__init__("gpt", client, config, db, stop_event)
        # Önce config'den almayı dene, yoksa doğrudan env değişkeninden al
        self.api_key = os.getenv('OPENAI_API_KEY')
        
        # Config nesnesinden ayarları doğru şekilde al
        if hasattr(config, 'get_setting'):
            self.model = config.get_setting('GPT_MODEL', 'gpt-3.5-turbo')
            self.max_tokens = config.get_setting('GPT_MAX_TOKENS', 1000)
            self.temperature = config.get_setting('GPT_TEMPERATURE', 0.7)
        else:
            # Varsayılan değerler
            self.model = os.getenv('GPT_MODEL', 'gpt-3.5-turbo')
            self.max_tokens = int(os.getenv('GPT_MAX_TOKENS', '1000'))
            self.temperature = float(os.getenv('GPT_TEMPERATURE', '0.7'))
        
        self.conversations = {}
        self.last_update = datetime.now()
        logger.info("GPT servisi başlatıldı")
    
    async def initialize(self):
        """Servisi başlangıç durumuna getirir"""
        try:
            # running değişkenini başlat
            self.running = False
            
            if not self.api_key:
                logger.error("GPT API anahtarı bulunamadı")
                return False
                
            logger.info("GPT servisi başlangıç durumuna getirildi")
            return True
            
        except Exception as e:
            logger.error(f"GPT servisi başlangıç durumuna getirilirken hata: {str(e)}")
            return False
        
    async def run(self):
        """Servisin ana çalışma döngüsü."""
        logger.info("GPT servisi çalışıyor (pasif mod)")
        while self.running:
            if self.stop_event.is_set():
                break
            await asyncio.sleep(60)
    
    async def get_status(self):
        """Servisin mevcut durumunu döndürür."""
        status = await super().get_status()
        status.update({
            "service_type": "gpt",
            "name": "GPT Servisi",
            "active": self.running,
            "api_available": bool(self.api_key),
            "status": "Aktif" if self.running and self.api_key else "API Key yok - GPT devre dışı" if not self.api_key else "Devre dışı"
        })
        return status

    async def start(self):
        """Servisi başlatır"""
        try:
            if self.running:
                logger.warning("GPT servisi zaten çalışıyor")
                return True
                
            if not self.api_key:
                logger.error("GPT API anahtarı bulunamadı")
                return False
                
            self.running = True
            logger.info("GPT servisi başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"GPT servisi başlatılırken hata: {str(e)}")
            self.running = False
            return False
            
    async def stop(self):
        """Servisi durdurur"""
        try:
            if not self.running:
                logger.warning("GPT servisi zaten durdurulmuş")
                return True
                
            self.running = False
            self.conversations.clear()
            
            logger.info("GPT servisi durduruldu")
            return True
            
        except Exception as e:
            logger.error(f"GPT servisi durdurulurken hata: {str(e)}")
            return False
            
    async def generate_response(self, prompt, conversation_id=None):
        """GPT modelini kullanarak yanıt oluşturur"""
        try:
            if not self.running:
                logger.error("GPT servisi çalışmıyor")
                return None
                
            if conversation_id:
                if conversation_id not in self.conversations:
                    self.conversations[conversation_id] = []
                self.conversations[conversation_id].append({"role": "user", "content": prompt})
                
                messages = self.conversations[conversation_id]
            else:
                messages = [{"role": "user", "content": prompt}]
                
            response = await self._call_gpt_api(messages)
            
            if conversation_id and response:
                self.conversations[conversation_id].append({"role": "assistant", "content": response})
                
            return response
            
        except Exception as e:
            logger.error(f"GPT yanıtı oluşturulurken hata: {str(e)}")
            return None
            
    async def _call_gpt_api(self, messages):
        """GPT API'sini çağırır"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content']
                    else:
                        error = await response.text()
                        logger.error(f"GPT API hatası: {error}")
                        return None
                        
        except Exception as e:
            logger.error(f"GPT API çağrısı sırasında hata: {str(e)}")
            return None
            
    async def clear_conversation(self, conversation_id):
        """Belirli bir konuşmayı temizler"""
        try:
            if conversation_id in self.conversations:
                del self.conversations[conversation_id]
                logger.debug(f"Konuşma temizlendi: {conversation_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Konuşma temizlenirken hata: {str(e)}")
            return False
            
    async def clear_all_conversations(self):
        """Tüm konuşmaları temizler"""
        try:
            self.conversations.clear()
            logger.debug("Tüm konuşmalar temizlendi")
            return True
            
        except Exception as e:
            logger.error(f"Konuşmalar temizlenirken hata: {str(e)}")
            return False