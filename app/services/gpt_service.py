"""
# ============================================================================ #
# Dosya: gpt_service.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/gpt_service.py
# İşlev: OpenAI GPT entegrasyonu için Telegram bot servisi.
#
# Versiyon: v2.0.0
# ============================================================================ #
"""

import asyncio
import logging
from datetime import datetime
import json
import os
import time
from typing import Dict, List, Any, Optional, Union
from sqlalchemy import text

from app.services.base_service import BaseService
from app.db.session import get_session

logger = logging.getLogger(__name__)

class GPTRequestStatus(str):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    
    @classmethod
    def normalize(cls, value):
        """Herhangi bir formattaki durum değerini standart formata dönüştürür"""
        if value is None:
            return cls.PENDING
            
        # String ise
        if isinstance(value, str):
            upper_value = value.upper()
            if upper_value == "PENDING":
                return cls.PENDING
            elif upper_value == "PROCESSING":
                return cls.PROCESSING
            elif upper_value == "COMPLETED":
                return cls.COMPLETED
            elif upper_value == "ERROR":
                return cls.ERROR
            return cls.PENDING
            
        return cls.PENDING

class GPTService(BaseService):
    """
    GPT servis sınıfı - OpenAI API kullanarak AI tabanlı yanıtlar oluşturur
    """
    
    service_name = "gpt_service"
    default_interval = 60  # 1 dakikada bir çalıştır
    
    def __init__(self, name='gpt_service', client=None, db=None, config=None, stop_event=None, *args, **kwargs):
        """
        GPT servisini başlat
        
        Args:
            name: Servis adı
            client: OpenAI API istemcisi
            db: Veritabanı bağlantısı
            config: Servis yapılandırması
            stop_event: Servis durdurma olayı
            **kwargs: Başlatma parametreleri
        """
        super().__init__(name=name)
        self.client = client
        self.db = db
        self.config = config
        self.stop_event = stop_event
        
        # OpenAI API anahtarını yapılandırmadan al
        self.api_key = getattr(self.config, "OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        self.model = getattr(self.config, "OPENAI_MODEL", "gpt-3.5-turbo")
        self.max_tokens = getattr(self.config, "OPENAI_MAX_TOKENS", 1000)
        self.temperature = getattr(self.config, "OPENAI_TEMPERATURE", 0.7)
        
        # OpenAI API istek yapılandırması
        self.client_config = {
            "api_key": self.api_key,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        
        # İstatistik takibi
        self.stats = {
            "total_requests": 0,
            "completed_requests": 0,
            "failed_requests": 0,
            "last_update": None
        }
        
        # OpenAI API istemcisini başlat
        self.ai_client = None
        try:
            import openai
            openai.api_key = self.api_key
            self.ai_client = openai
            self.logger.info("OpenAI API istemcisi başlatıldı")
        except ImportError:
            self.logger.error("OpenAI paketleri bulunamadı. 'pip install openai' komutunu çalıştırın.")
        except Exception as e:
            self.logger.error(f"OpenAI API istemcisi başlatılamadı: {str(e)}", exc_info=True)
    
    async def _start(self) -> bool:
        """
        GPT servisini başlat
        
        Returns:
            bool: Başlatma başarılı mı
        """
        self.logger.info("GPT servisi başlatılıyor...")
        
        # API anahtarı kontrol et
        if not self.api_key:
            self.logger.error("OpenAI API anahtarı bulunamadı. Lütfen yapılandırma dosyasını kontrol edin.")
            return False
        
        # AI istemcisi kontrol et
        if not self.ai_client:
            try:
                import openai
                openai.api_key = self.api_key
                self.ai_client = openai
                self.logger.info("OpenAI API istemcisi başlatıldı")
            except ImportError:
                self.logger.error("OpenAI paketleri bulunamadı. 'pip install openai' komutunu çalıştırın.")
                return False
            except Exception as e:
                self.logger.error(f"OpenAI API istemcisi başlatılamadı: {str(e)}", exc_info=True)
                return False
        
        # İstatistikleri yükle
        await self.load_stats()
        
        self.logger.info(f"GPT servisi başlatıldı. Model: {self.model}, Max Tokens: {self.max_tokens}")
        return True
    
    async def _stop(self) -> bool:
        """
        GPT servisini durdur
        
        Returns:
            bool: Durdurma başarılı mı
        """
        self.logger.info("GPT servisi durduruluyor...")
        
        # Kapatma işlemleri - özel bir işlem gerekmiyor
        
        self.logger.info("GPT servisi durduruldu")
        return True
    
    async def _update(self) -> None:
        """Servis güncellemesi"""
        self.logger.debug("GPT servisi güncelleniyor...")
        
        # Bekleyen GPT isteklerini işle
        try:
            await self.process_pending_requests()
            
            # İstatistikleri güncelle
            await self.load_stats()
            
            self.logger.debug(f"GPT servisi güncellendi. Toplam istek: {self.stats['total_requests']}, " 
                             f"Tamamlanan: {self.stats['completed_requests']}, " 
                             f"Başarısız: {self.stats['failed_requests']}")
        except Exception as e:
            self.logger.error(f"GPT istekleri işlenirken hata: {str(e)}", exc_info=True)
    
    async def load_stats(self) -> None:
        """GPT istatistiklerini veritabanından yükle"""
        try:
            session = next(get_session())
            
            # Toplam istek sayısı
            total_query = text("SELECT COUNT(*) FROM gpt_requests")
            total_result = session.execute(total_query).scalar()
            
            # Tamamlanan istek sayısı - UPPER ile büyük/küçük harf duyarsızlığı
            completed_query = text("""
                SELECT COUNT(*) FROM gpt_requests 
                WHERE UPPER(status) = 'COMPLETED'
            """)
            completed_result = session.execute(completed_query).scalar()
            
            # Başarısız istek sayısı
            failed_query = text("""
                SELECT COUNT(*) FROM gpt_requests 
                WHERE UPPER(status) = 'ERROR'
            """)
            failed_result = session.execute(failed_query).scalar()
            
            # İstatistikleri güncelle
            self.stats['total_requests'] = total_result or 0
            self.stats['completed_requests'] = completed_result or 0
            self.stats['failed_requests'] = failed_result or 0
            self.stats['last_update'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"GPT istatistikleri yüklenirken hata: {str(e)}", exc_info=True)
    
    async def process_pending_requests(self) -> None:
        """Bekleyen GPT isteklerini işle"""
        # Veritabanı bağlantısı al
        try:
            session = next(get_session())
            
            # Bekleyen istekleri al - UPPER ile büyük/küçük harf duyarsızlığı
            query = text("""
            SELECT id, prompt, created_at 
            FROM gpt_requests
            WHERE UPPER(status) = 'PENDING'
            ORDER BY created_at ASC
            LIMIT 10
            """)
            
            rows = session.execute(query).all()
            
            if not rows:
                self.logger.debug("İşlenecek bekleyen GPT isteği bulunamadı")
                return
            
            self.logger.info(f"{len(rows)} bekleyen GPT isteği işlenecek")
            
            # Her isteği işle
            for row in rows:
                request_id = row[0]
                prompt = row[1]
                created_at = row[2]
                
                self.logger.info(f"GPT isteği işleniyor (ID: {request_id})")
                
                # İsteği işlemeye başla
                update_query = text("""
                    UPDATE gpt_requests 
                    SET status = :status, updated_at = :updated_at 
                    WHERE id = :id
                """)
                
                session.execute(update_query, {
                    "status": GPTRequestStatus.PROCESSING, 
                    "updated_at": datetime.now(), 
                    "id": request_id
                })
                session.commit()
                
                # GPT yanıtı al
                try:
                    response = await self.generate_response(prompt)
                    
                    # Yanıtı kaydet
                    success_query = text("""
                        UPDATE gpt_requests 
                        SET status = :status, response = :response, 
                            completed_at = :completed_at, updated_at = :updated_at 
                        WHERE id = :id
                    """)
                    
                    session.execute(success_query, {
                        "status": GPTRequestStatus.COMPLETED, 
                        "response": response, 
                        "completed_at": datetime.now(), 
                        "updated_at": datetime.now(), 
                        "id": request_id
                    })
                    session.commit()
                    
                    self.logger.info(f"GPT isteği tamamlandı (ID: {request_id})")
                    
                except Exception as e:
                    # Hata durumunda güncelle
                    error_query = text("""
                        UPDATE gpt_requests 
                        SET status = :status, error = :error, updated_at = :updated_at 
                        WHERE id = :id
                    """)
                    
                    session.execute(error_query, {
                        "status": GPTRequestStatus.ERROR, 
                        "error": str(e), 
                        "updated_at": datetime.now(), 
                        "id": request_id
                    })
                    session.commit()
                    
                    self.logger.error(f"GPT isteği işlenirken hata (ID: {request_id}): {str(e)}", exc_info=True)
                
                # İstekler arasında bekle (hız sınırlarını aşmamak için)
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Bekleyen GPT istekleri işlenirken hata: {str(e)}", exc_info=True)
    
    async def generate_response(self, prompt: str) -> str:
        """
        OpenAI GPT modelini kullanarak yanıt oluştur
        
        Args:
            prompt: Kullanıcı sorusu/promptu
            
        Returns:
            str: Oluşturulan yanıt
        """
        if not self.ai_client:
            raise Exception("OpenAI istemcisi başlatılmadı")
            
        if not prompt or not isinstance(prompt, str):
            raise ValueError("Geçersiz prompt: Boş veya string değil")
        
        try:
            # OpenAI API'si ile yanıt oluştur
            response = await asyncio.to_thread(
                self.ai_client.ChatCompletion.create,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            # Yanıtı çıkart
            response_text = response.choices[0].message.content.strip()
            
            return response_text
            
        except Exception as e:
            self.logger.error(f"OpenAI yanıtı oluşturulurken hata: {str(e)}", exc_info=True)
            raise
    
    async def add_request(self, prompt: str, user_id: int = None, chat_id: int = None) -> int:
        """
        Yeni bir GPT isteği ekle
        
        Args:
            prompt: Kullanıcı sorusu/promptu
            user_id: İsteği oluşturan kullanıcı ID'si (opsiyonel)
            chat_id: İsteğin yapıldığı sohbet ID'si (opsiyonel)
            
        Returns:
            int: Oluşturulan isteğin ID'si
        """
        if not prompt or not isinstance(prompt, str):
            raise ValueError("Geçersiz prompt: Boş veya string değil")
        
        try:
            session = next(get_session())
            
            # Yeni istek oluştur
            query = text("""
            INSERT INTO gpt_requests 
            (prompt, user_id, chat_id, status, created_at, updated_at) 
            VALUES (:prompt, :user_id, :chat_id, :status, :created_at, :updated_at)
            RETURNING id
            """)
            
            now = datetime.now()
            result = session.execute(query, {
                "prompt": prompt,
                "user_id": user_id,
                "chat_id": chat_id,
                "status": GPTRequestStatus.PENDING,
                "created_at": now,
                "updated_at": now
            }).scalar()
            
            session.commit()
            
            if not result:
                raise Exception("GPT isteği eklenirken hata oluştu")
                
            request_id = result
            self.logger.info(f"GPT isteği eklendi (ID: {request_id})")
            
            return request_id
                
        except Exception as e:
            self.logger.error(f"GPT isteği eklenirken hata: {str(e)}", exc_info=True)
            raise
    
    async def get_response(self, request_id: int) -> Dict[str, Any]:
        """
        Bir GPT isteğinin yanıtını al
        
        Args:
            request_id: İsteğin ID'si
            
        Returns:
            Dict[str, Any]: İstek ve yanıt bilgileri
        """
        try:
            session = next(get_session())
            
            query = text("""
            SELECT id, prompt, response, status, error, created_at, completed_at
            FROM gpt_requests
            WHERE id = :id
            """)
            
            result = session.execute(query, {"id": request_id}).first()
            
            if not result:
                return {"error": f"İstek bulunamadı (ID: {request_id})"}
                
            status = result[3]
            
            # Yanıtın durumuna göre sonuç döndür
            response_data = {
                "id": result[0],
                "prompt": result[1],
                "status": status,
                "created_at": result[5],
            }
            
            # Completed ise yanıtı ekle
            if status.upper() == GPTRequestStatus.COMPLETED:
                response_data["response"] = result[2]
                response_data["completed_at"] = result[6]
            # Error ise hatayı ekle
            elif status.upper() == GPTRequestStatus.ERROR:
                response_data["error"] = result[4]
            # Pending veya Processing ise durum bilgisi
            else:
                response_data["message"] = f"İstek henüz tamamlanmadı. Durum: {status}"
                
            return response_data
                
        except Exception as e:
            self.logger.error(f"GPT yanıtı alınırken hata: {str(e)}", exc_info=True)
            return {"error": str(e)}
            
    async def get_statistics(self) -> Dict[str, Any]:
        """Servis istatistiklerini getir"""
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "total_requests": self.stats['total_requests'],
            "completed_requests": self.stats['completed_requests'],
            "failed_requests": self.stats['failed_requests'],
            "last_update": self.stats['last_update']
        }