"""
TDLib Client

Telegram Database Library (TDLib) istemcisi.
TDLib, Telegram API'sini daha düşük seviyede kullanmak için resmi C++ kütüphanedir.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Awaitable, Union
from datetime import datetime

from app.core.logger import get_logger
from app.core.config import settings
from app.core.metrics import track_telegram_request, TELEGRAM_API_REQUESTS

logger = get_logger(__name__)

class TDLibClient:
    """
    TDLib ile etkileşimi yöneten istemci sınıfı.
    """
    
    def __init__(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        phone: Optional[str] = None,
        session_name: Optional[str] = None,
        files_directory: Optional[str] = None,
        database_directory: Optional[str] = None,
        use_message_database: bool = True,
        use_secret_chats: bool = False,
        system_language_code: str = "tr",
        device_model: str = "Telegram Bot",
        application_version: str = "1.0",
        system_version: str = "Bot",
        proxy_settings: Optional[Dict[str, Any]] = None,
        tdlib_verbosity: int = 2,
    ):
        """
        TDLib istemcisini başlatır.
        
        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            phone: Telefon numarası
            session_name: Oturum adı
            files_directory: Dosya dizini
            database_directory: Veritabanı dizini
            use_message_database: Mesaj veritabanı kullanılsın mı
            use_secret_chats: Gizli sohbetler kullanılsın mı
            system_language_code: Sistem dili kodu
            device_model: Cihaz modeli
            application_version: Uygulama sürümü
            system_version: Sistem sürümü
            proxy_settings: Proxy ayarları
            tdlib_verbosity: TDLib log seviyesi
        """
        # TDLib kütüphanesini yükle
        try:
            global tdjson
            from ctypes.util import find_library
            from ctypes import CDLL, c_char_p, c_double, c_int, c_void_p
            
            tdjson_path = find_library('tdjson')
            if not tdjson_path:
                raise ImportError("tdjson kütüphanesi bulunamadı")
                
            tdjson = CDLL(tdjson_path)
            
            # TDLib fonksiyonlarını yapılandır
            self._td_json_client_create = tdjson.td_json_client_create
            self._td_json_client_create.restype = c_void_p
            self._td_json_client_create.argtypes = []
            
            self._td_json_client_send = tdjson.td_json_client_send
            self._td_json_client_send.restype = None
            self._td_json_client_send.argtypes = [c_void_p, c_char_p]
            
            self._td_json_client_receive = tdjson.td_json_client_receive
            self._td_json_client_receive.restype = c_char_p
            self._td_json_client_receive.argtypes = [c_void_p, c_double]
            
            self._td_json_client_execute = tdjson.td_json_client_execute
            self._td_json_client_execute.restype = c_char_p
            self._td_json_client_execute.argtypes = [c_void_p, c_char_p]
            
            self._td_json_client_destroy = tdjson.td_json_client_destroy
            self._td_json_client_destroy.restype = None
            self._td_json_client_destroy.argtypes = [c_void_p]
            
            self._td_set_log_verbosity_level = tdjson.td_set_log_verbosity_level
            self._td_set_log_verbosity_level.restype = None
            self._td_set_log_verbosity_level.argtypes = [c_int]
            
            # TDLib log seviyesini ayarla
            self._td_set_log_verbosity_level(tdlib_verbosity)
            
            # TDLib istemcisini oluştur
            self._client = self._td_json_client_create()
            
        except Exception as e:
            logger.error(f"TDLib yüklenirken hata oluştu: {str(e)}")
            raise
            
        # Parametreleri yapılandır
        self.api_id = api_id or settings.API_ID
        self.api_hash = api_hash or settings.API_HASH.get_secret_value() if hasattr(settings.API_HASH, 'get_secret_value') else settings.API_HASH
        self.phone = phone or settings.PHONE
        self.session_name = session_name or settings.SESSION_NAME
        
        # Dizinleri yapılandır
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        sessions_dir = os.path.join(base_dir, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        
        # Oturum dizinini oluştur
        session_dir = os.path.join(sessions_dir, self.session_name)
        os.makedirs(session_dir, exist_ok=True)
        
        self.files_directory = files_directory or os.path.join(session_dir, "files")
        self.database_directory = database_directory or os.path.join(session_dir, "db")
        
        # Dizinleri oluştur
        os.makedirs(self.files_directory, exist_ok=True)
        os.makedirs(self.database_directory, exist_ok=True)
        
        # Parametreleri kaydet
        self.use_message_database = use_message_database
        self.use_secret_chats = use_secret_chats
        self.system_language_code = system_language_code
        self.device_model = device_model
        self.application_version = application_version
        self.system_version = system_version
        self.proxy_settings = proxy_settings
        
        # İç durum değişkenleri
        self._is_authorized = False
        self._is_connected = False
        self._authentication_code = None
        self._updates_queue = asyncio.Queue()
        self._update_handlers = []
        self._pending_requests = {}
        self._next_request_id = 0
        
        # TDLib istemci döngüsü
        self._recv_task = None
        
    async def connect(self) -> bool:
        """
        TDLib istemcisine bağlanır.
        
        Returns:
            bool: Bağlantı başarılıysa True
        """
        try:
            # TDLib parametrelerini ayarla
            parameters = {
                '@type': 'setTdlibParameters',
                'use_test_dc': False,
                'database_directory': self.database_directory,
                'files_directory': self.files_directory,
                'use_file_database': True,
                'use_chat_info_database': True,
                'use_message_database': self.use_message_database,
                'use_secret_chats': self.use_secret_chats,
                'api_id': self.api_id,
                'api_hash': self.api_hash,
                'system_language_code': self.system_language_code,
                'device_model': self.device_model,
                'application_version': self.application_version,
                'system_version': self.system_version,
                'enable_storage_optimizer': True
            }
            
            # Proxy ayarları
            if self.proxy_settings:
                proxy_result = await self._execute({
                    '@type': 'addProxy',
                    **self.proxy_settings
                })
                logger.info(f"Proxy ayarlandı: {proxy_result}")
            
            # TDLib parametrelerini gönder
            await self._send(parameters)
            
            # Alıcı görevi başlat
            self._recv_task = asyncio.create_task(self._receive_loop())
            
            # Yanıt bekle
            result = await self._wait_for_type('updateAuthorizationState', timeout=10.0)
            
            self._is_connected = True
            logger.info(f"TDLib bağlantısı sağlandı: {self.session_name}")
            
            # Yetkilendirme durumunu kontrol et
            if result.get('authorization_state', {}).get('@type') == 'authorizationStateReady':
                self._is_authorized = True
                logger.info(f"TDLib oturumu hazır: {self.session_name}")
            
            return self._is_connected
            
        except Exception as e:
            logger.exception(f"TDLib bağlantı hatası: {str(e)}")
            return False
            
    async def disconnect(self) -> bool:
        """
        TDLib istemcisinden bağlantıyı keser.
        
        Returns:
            bool: Bağlantı kesme başarılıysa True
        """
        try:
            # İstemciyi kapat
            if self._client:
                await self._send({'@type': 'close'})
                
                # Alıcı görevini bekle
                if self._recv_task and not self._recv_task.done():
                    try:
                        self._recv_task.cancel()
                        await self._recv_task
                    except asyncio.CancelledError:
                        pass
                        
                # İstemciyi yok et
                self._td_json_client_destroy(self._client)
                self._client = None
                
            self._is_connected = False
            self._is_authorized = False
            logger.info(f"TDLib bağlantısı kesildi: {self.session_name}")
            
            return True
        except Exception as e:
            logger.exception(f"TDLib bağlantı kesme hatası: {str(e)}")
            return False
            
    async def _send(self, data: Dict[str, Any]) -> None:
        """
        TDLib'e veri gönderir.
        
        Args:
            data: Gönderilecek veri
        """
        if not self._client:
            raise RuntimeError("TDLib istemcisi başlatılmadı")
            
        # Request ID ekle
        if '@extra' not in data:
            data['@extra'] = {'request_id': self._next_request_id}
            self._next_request_id += 1
            
        # JSON'a dönüştür
        request_json = json.dumps(data).encode('utf-8')
        
        # Gönder
        self._td_json_client_send(self._client, request_json)
        
    async def _execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        TDLib komutunu senkron olarak yürütür.
        
        Args:
            data: Yürütülecek komut
            
        Returns:
            Dict[str, Any]: Yanıt
        """
        if not self._client:
            raise RuntimeError("TDLib istemcisi başlatılmadı")
            
        # JSON'a dönüştür
        request_json = json.dumps(data).encode('utf-8')
        
        # Çalıştır
        result_json = self._td_json_client_execute(self._client, request_json)
        
        if result_json:
            return json.loads(result_json.decode('utf-8'))
        else:
            return {}
            
    async def _receive(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        TDLib'den veri alır.
        
        Args:
            timeout: Zaman aşımı
            
        Returns:
            Optional[Dict[str, Any]]: Alınan veri
        """
        if not self._client:
            raise RuntimeError("TDLib istemcisi başlatılmadı")
            
        # Al
        result_json = self._td_json_client_receive(self._client, timeout)
        
        if result_json:
            return json.loads(result_json.decode('utf-8'))
        else:
            return None
            
    async def _receive_loop(self) -> None:
        """
        TDLib'den sürekli veri alan döngü.
        """
        while self._client:
            try:
                result = await self._receive()
                
                if result:
                    # Request ID varsa bekleyen isteği kontrol et
                    extra = result.get('@extra', {})
                    request_id = extra.get('request_id')
                    
                    if request_id is not None and request_id in self._pending_requests:
                        future = self._pending_requests.pop(request_id)
                        if not future.done():
                            future.set_result(result)
                    else:
                        # Güncelleme kuyruğuna ekle
                        await self._updates_queue.put(result)
                        
                        # Güncelleme işleyicilere bildir
                        update_type = result.get('@type')
                        if update_type:
                            for handler in self._update_handlers:
                                try:
                                    await handler(result)
                                except Exception as e:
                                    logger.exception(f"Güncelleme işleyici hatası: {str(e)}")
            except Exception as e:
                logger.exception(f"TDLib alıcı döngüsü hatası: {str(e)}")
                await asyncio.sleep(1.0)  # Hata sonrası bekle
                
    @track_telegram_request("auth_phone")
    async def phone_login(self, phone: Optional[str] = None) -> bool:
        """
        Telefon numarasıyla giriş yapar.
        
        Args:
            phone: Telefon numarası
            
        Returns:
            bool: Giriş başarılıysa True
        """
        try:
            phone = phone or self.phone
            
            # Telefon numarasını gönder
            await self._send({
                '@type': 'setAuthenticationPhoneNumber',
                'phone_number': phone
            })
            
            # Doğrulama kodunu bekle
            code_result = await self._wait_for_type('authorizationStateWaitCode', timeout=60.0)
            
            if not code_result:
                logger.error(f"Doğrulama kodu beklenirken zaman aşımı: {phone}")
                return False
                
            # Doğrulama kodunu iste
            code = input(f"Lütfen {phone} numarasına gelen doğrulama kodunu girin: ")
            
            # Doğrulama kodunu gönder
            await self._send({
                '@type': 'checkAuthenticationCode',
                'code': code
            })
            
            # Yetkilendirme durumunu bekle
            auth_result = await self._wait_for_type('authorizationStateReady', timeout=60.0)
            
            if auth_result:
                self._is_authorized = True
                logger.info(f"Giriş başarılı: {phone}")
                return True
            else:
                logger.error(f"Giriş başarısız: {phone}")
                return False
                
        except Exception as e:
            logger.exception(f"Telefon girişi hatası: {str(e)}")
            return False
            
    async def _wait_for_type(self, update_type: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """
        Belirli bir güncelleme türünü bekler.
        
        Args:
            update_type: Beklenen güncelleme türü
            timeout: Zaman aşımı
            
        Returns:
            Optional[Dict[str, Any]]: Beklenen güncelleme
        """
        start_time = datetime.now()
        while (datetime.now() - start_time).total_seconds() < timeout:
            try:
                # Güncelleme kuyruğunu kontrol et
                if not self._updates_queue.empty():
                    update = await self._updates_queue.get()
                    
                    if update.get('@type') == update_type:
                        return update
                    elif update.get('authorization_state', {}).get('@type') == update_type:
                        return update
                        
                # Yeni güncelleme bekle
                result = await self._receive(timeout=0.1)
                
                if result:
                    if result.get('@type') == update_type:
                        return result
                    elif result.get('authorization_state', {}).get('@type') == update_type:
                        return result
                        
                # Kısa bekle
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.exception(f"Güncelleme beklenirken hata: {str(e)}")
                
        return None
        
    @track_telegram_request("api_request")
    async def send_request(self, method: str, **kwargs) -> Dict[str, Any]:
        """
        TDLib API'sine istek gönderir.
        
        Args:
            method: API metodu
            **kwargs: API parametreleri
            
        Returns:
            Dict[str, Any]: API yanıtı
        """
        try:
            # İsteği hazırla
            request = {
                '@type': method,
                **kwargs
            }
            
            # Request ID ayarla
            request_id = self._next_request_id
            self._next_request_id += 1
            request['@extra'] = {'request_id': request_id}
            
            # Future oluştur
            future = asyncio.Future()
            self._pending_requests[request_id] = future
            
            # İsteği gönder
            await self._send(request)
            
            # Yanıtı bekle
            result = await asyncio.wait_for(future, timeout=60.0)
            
            # Hata kontrolü
            if result.get('@type') == 'error':
                error_code = result.get('code', 0)
                error_message = result.get('message', 'Unknown error')
                logger.error(f"TDLib API hatası: {method} - {error_code} {error_message}")
                
                # Metrikleri güncelle
                method_name = method.lower()
                TELEGRAM_API_REQUESTS.labels(method=method_name, status="error").inc()
                
                # Hata durumuna göre işlem
                if error_code == 401:  # Yetkilendirme hatası
                    self._is_authorized = False
                    
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"TDLib API zaman aşımı: {method}")
            return {'@type': 'error', 'code': 408, 'message': 'Request timeout'}
        except Exception as e:
            logger.exception(f"TDLib API isteği hatası: {str(e)}")
            return {'@type': 'error', 'code': 500, 'message': str(e)}
            
    def is_authorized(self) -> bool:
        """
        İstemcinin yetkilendirilmiş olup olmadığını kontrol eder.
        
        Returns:
            bool: Yetkilendirilmişse True
        """
        return self._is_authorized
        
    def is_connected(self) -> bool:
        """
        İstemcinin bağlı olup olmadığını kontrol eder.
        
        Returns:
            bool: Bağlıysa True
        """
        return self._is_connected
        
    async def get_me(self) -> Dict[str, Any]:
        """
        Mevcut kullanıcı bilgilerini getirir.
        
        Returns:
            Dict[str, Any]: Kullanıcı bilgileri
        """
        return await self.send_request('getMe')
        
    async def add_update_handler(self, handler: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """
        Güncelleme işleyici ekler.
        
        Args:
            handler: Güncelleme işleyici fonksiyon
        """
        if handler not in self._update_handlers:
            self._update_handlers.append(handler)
            
    async def remove_update_handler(self, handler: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """
        Güncelleme işleyiciyi kaldırır.
        
        Args:
            handler: Kaldırılacak güncelleme işleyici
        """
        if handler in self._update_handlers:
            self._update_handlers.remove(handler) 