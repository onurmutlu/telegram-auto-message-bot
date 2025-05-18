#!/usr/bin/env python3
"""
Telegram bağlantı sorunlarını düzelten kapsamlı bir araç.
Bu araç:
1. Telegram API bağlantısını test eder
2. Telegram API kimlik bilgilerini doğrular
3. Oturum dosyalarını kontrol eder ve gerekirse temiz bir oturum oluşturur
4. Bağlantıyı zorlar ve Health Service metodlarını kullanır
5. Sorunları tespit eder ve raporlar
"""

import os
import sys
import time
import asyncio
import logging
from pathlib import Path
import json

# Ana dizini ekle
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Ortam değişkenlerini yükle, mevcut değerleri değiştirmeden
from dotenv import load_dotenv
load_dotenv(override=True)

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(BASE_DIR, "connection_fix.log"))
    ]
)

logger = logging.getLogger(__name__)

# Gerekli modülleri import et
try:
    from telethon import TelegramClient, errors
    from app.core.config import settings, safe_getenv_int
    from app.services.monitoring.health_service import HealthService
except ImportError as e:
    logger.error(f"Gerekli modüller yüklenemedi: {e}")
    logger.error("Lütfen 'pip install -r requirements.txt' komutunu çalıştırın")
    sys.exit(1)

class TelegramConnectionFixer:
    """Telegram bağlantı sorunlarını tespit eden ve düzelten sınıf."""
    
    def __init__(self):
        """Başlatıcı."""
        self.client = None
        self.health_service = None
        self.original_session_name = os.getenv("SESSION_NAME", "telegram_session")
        self.api_id = os.getenv("API_ID", None)
        self.api_hash = os.getenv("API_HASH", None)
        
        # Oturum yolu
        if hasattr(settings, "SESSIONS_DIR"):
            self.session_dir = settings.SESSIONS_DIR
        else:
            self.session_dir = os.path.join(BASE_DIR, "session")
        
        # Varsayılan oturum yolu
        self.session_path = os.path.join(self.session_dir, f"{self.original_session_name}.session")
        
        logger.info(f"TelegramConnectionFixer başlatıldı")
        logger.info(f"Kullanılan oturum: {self.original_session_name}")
        logger.info(f"Oturum dosyası: {self.session_path}")
        logger.info(f"API ID: {self.api_id}")
        # Güvenlik için sadece ilk 4 ve son 4 karakteri göster
        api_hash_safe = f"{self.api_hash[:4]}...{self.api_hash[-4:]}" if self.api_hash and len(self.api_hash) > 8 else "Tanımsız"
        logger.info(f"API HASH: {api_hash_safe}")
    
    async def fix_connection(self, force_new_session=False):
        """Ana düzeltme işlemini yürüt."""
        logger.info(f"Bağlantı düzeltme işlemi başlıyor...")
        
        # Sorun tespit sonuçları
        issues = {
            "session_file_missing": False,
            "session_file_corrupted": False,
            "api_id_invalid": False,
            "api_hash_invalid": False,
            "connection_error": False,
            "auth_error": False
        }
        
        # 1. API kimlik bilgilerini kontrol et
        if not self.api_id or not self.api_hash:
            logger.error("API kimlik bilgileri bulunamadı")
            issues["api_id_invalid"] = not self.api_id
            issues["api_hash_invalid"] = not self.api_hash
            return {
                "success": False,
                "message": "API kimlik bilgileri bulunamadı, lütfen .env dosyasını kontrol edin",
                "issues": issues
            }
        
        # 2. Oturum dosyasını kontrol et
        session_status = self._check_session_file()
        issues["session_file_missing"] = not session_status["exists"]
        issues["session_file_corrupted"] = session_status.get("corrupted", False)
        
        # Eğer dosya yoksa veya bozuksa veya force_new_session=True ise yeni oturum oluştur
        if force_new_session or issues["session_file_missing"] or issues["session_file_corrupted"]:
            logger.info("Yeni oturum dosyası oluşturuluyor...")
            new_session_name = f"{self.original_session_name}_new_{int(time.time())}"
            session_created = await self._create_new_session(new_session_name)
            
            if session_created:
                logger.info(f"Yeni oturum dosyası başarıyla oluşturuldu: {new_session_name}")
                self.original_session_name = new_session_name
                # Oturum yolunu güncelle
                self.session_path = os.path.join(self.session_dir, f"{self.original_session_name}.session")
            else:
                logger.error("Yeni oturum dosyası oluşturulamadı")
                return {
                    "success": False,
                    "message": "Yeni oturum dosyası oluşturulamadı",
                    "issues": issues
                }
        
        # 3. Bağlantı işlemini dene
        connection_result = await self._try_connection()
        
        # Bağlantı sonucunu değerlendir
        if not connection_result["success"]:
            issues["connection_error"] = True
            issues["api_id_invalid"] = connection_result.get("api_id_invalid", False)
            issues["api_hash_invalid"] = connection_result.get("api_hash_invalid", False)
            
            # Health Service ile düzeltmeyi dene
            if self.client:
                health_result = await self._try_health_service_recovery()
                if health_result["success"]:
                    logger.info("Health Service ile bağlantı başarıyla düzeltildi")
                    issues["connection_error"] = False
                    return {
                        "success": True,
                        "message": "Health Service ile bağlantı başarıyla düzeltildi",
                        "issues": issues,
                        "client": self.client
                    }
                else:
                    logger.error("Health Service ile bağlantı düzeltilemedi")
            
            return {
                "success": False,
                "message": connection_result["message"],
                "issues": issues
            }
        
        # 4. Yetkilendirme durumunu kontrol et
        auth_result = await self._check_authorization()
        issues["auth_error"] = not auth_result["authorized"]
        
        if not auth_result["authorized"]:
            logger.warning("Kullanıcı yetkilendirilmemiş, yeniden yetkilendirme gerekli")
            auth_result = await self._authorize_user()
            issues["auth_error"] = not auth_result["success"]
            
            if not auth_result["success"]:
                logger.error("Kullanıcı yetkilendirilemedi")
                return {
                    "success": False,
                    "message": "Kullanıcı yetkilendirilemedi, lütfen manuel olarak yetkilendirin",
                    "issues": issues
                }
        
        # 5. Son durum kontrolü 
        final_check = await self._final_connection_check()
        
        if final_check["success"]:
            logger.info("Bağlantı başarıyla düzeltildi")
            return {
                "success": True,
                "message": "Bağlantı başarıyla düzeltildi",
                "issues": issues,
                "client": self.client
            }
        else:
            logger.error("Bağlantı düzeltilemedi: " + final_check["message"])
            return {
                "success": False,
                "message": final_check["message"],
                "issues": issues
            }
    
    def _check_session_file(self):
        """Oturum dosyasını kontrol et."""
        result = {"exists": False, "corrupted": False}
        
        # Oturum klasörünü oluştur
        os.makedirs(self.session_dir, exist_ok=True)
        
        # Dosya var mı kontrol et
        if os.path.exists(self.session_path):
            result["exists"] = True
            
            # Dosya boyutunu kontrol et
            file_size = os.path.getsize(self.session_path)
            if file_size < 100:  # Minimum boyut kontrolü
                result["corrupted"] = True
                logger.warning(f"Oturum dosyası çok küçük: {file_size} bayt, muhtemelen bozuk")
            
            # İlk 100 baytı oku ve beklenilen SQLite magic number'ı içeriyor mu kontrol et
            try:
                with open(self.session_path, 'rb') as f:
                    header = f.read(100)
                    # SQLite magic number: 53 51 4c 69 74 65 ("SQLite" in ASCII)
                    if not header.startswith(b'SQLite'):
                        result["corrupted"] = True
                        logger.warning("Oturum dosyası SQLite veritabanı değil, muhtemelen bozuk")
            except Exception as e:
                result["corrupted"] = True
                logger.warning(f"Oturum dosyası okuma hatası: {e}")
        else:
            logger.warning(f"Oturum dosyası bulunamadı: {self.session_path}")
        
        return result
    
    async def _create_new_session(self, session_name):
        """Yeni bir oturum dosyası oluştur."""
        try:
            # Oturum klasörünü oluştur
            os.makedirs(self.session_dir, exist_ok=True)
            
            # Oturum dosyası yolu
            session_path = os.path.join(self.session_dir, f"{session_name}.session")
            
            # Telethon, connect() çağrıldığında otomatik olarak oturum dosyası oluşturur
            # TelegramClient oluştur
            client = TelegramClient(
                session_path, 
                int(self.api_id), 
                self.api_hash,
                device_model="Connection Fixer",
                system_version="1.0",
                app_version="1.0"
            )
            
            # Bağlan
            await client.connect()
            
            # Bağlantıyı kapat
            if client.is_connected():
                await client.disconnect()
                logger.info(f"Oturum dosyası başarıyla oluşturuldu: {session_path}")
                return True
            else:
                logger.error("Oturum dosyası oluşturulurken bağlantı kurulamadı")
                return False
            
        except Exception as e:
            logger.error(f"Oturum dosyası oluşturulurken hata: {e}")
            return False
    
    async def _try_connection(self):
        """Temel bağlantı işlemini dene."""
        try:
            # TelegramClient oluştur
            logger.info(f"TelegramClient oluşturuluyor: {self.original_session_name}")
            
            self.client = TelegramClient(
                self.session_path, 
                int(self.api_id), 
                self.api_hash,
                device_model="Connection Fixer",
                system_version="1.0",
                app_version="1.0",
                connection_retries=10
            )
            
            # Bağlan
            logger.info("Bağlanılıyor...")
            await self.client.connect()
            
            # Bağlantı durumunu kontrol et
            if self.client.is_connected():
                logger.info("Bağlantı başarılı!")
                return {
                    "success": True,
                    "message": "Bağlantı başarılı"
                }
            else:
                logger.error("Bağlantı başarısız")
                return {
                    "success": False,
                    "message": "Bağlantı başarısız"
                }
                
        except errors.ApiIdInvalidError:
            logger.error("API ID/HASH geçersiz")
            return {
                "success": False,
                "message": "API ID/HASH geçersiz",
                "api_id_invalid": True,
                "api_hash_invalid": True
            }
        except Exception as e:
            logger.error(f"Bağlantı sırasında hata: {str(e)}")
            return {
                "success": False,
                "message": f"Bağlantı sırasında hata: {str(e)}"
            }
    
    async def _try_health_service_recovery(self):
        """Health Service ile bağlantıyı düzeltmeyi dene."""
        try:
            if not self.client:
                logger.error("Client nesnesi oluşturulmamış")
                return {
                    "success": False,
                    "message": "Client nesnesi oluşturulmamış"
                }
            
            # Health Service oluştur
            logger.info("Health Service ile düzeltme deneniyor...")
            from app.db.session import get_session
            db = next(get_session())
            
            # ServiceManager parametresi için bot nesnesi gerekiyor, ama sadece
            # force_connect metodunu kullanacağımız için None olarak geçiyoruz
            self.health_service = HealthService(client=self.client, service_manager=None, db=db)
            
            # Health Service initialize
            await self.health_service.initialize()
            
            # Force connect çağır
            logger.info("Health Service force_connect çağrılıyor...")
            conn_result = await self.health_service.force_connect()
            
            if conn_result.get("connected", False):
                logger.info("Health servisi ile bağlantı başarıyla kuruldu!")
                logger.info(f"Kullanıcı bilgileri: {conn_result.get('first_name', 'Bilinmiyor')} ID: {conn_result.get('user_id', 'Bilinmiyor')}")
                return {
                    "success": True,
                    "message": "Health servisi ile bağlantı başarıyla kuruldu",
                    "user_info": conn_result
                }
            else:
                logger.error(f"Health servisi ile bağlantı kurulamadı: {conn_result.get('error', 'Bilinmeyen hata')}")
                return {
                    "success": False,
                    "message": f"Health servisi ile bağlantı kurulamadı: {conn_result.get('error', 'Bilinmeyen hata')}"
                }
                
        except Exception as e:
            logger.error(f"Health Service düzeltme girişimi sırasında hata: {str(e)}")
            return {
                "success": False,
                "message": f"Health Service düzeltme girişimi sırasında hata: {str(e)}"
            }
    
    async def _check_authorization(self):
        """Yetkilendirme durumunu kontrol et."""
        try:
            if not self.client:
                logger.error("Client nesnesi oluşturulmamış")
                return {
                    "authorized": False,
                    "message": "Client nesnesi oluşturulmamış"
                }
            
            if not self.client.is_connected():
                logger.warning("Client bağlı değil, yeniden bağlanılıyor...")
                await self.client.connect()
                
                if not self.client.is_connected():
                    logger.error("Yeniden bağlantı başarısız")
                    return {
                        "authorized": False,
                        "message": "Yeniden bağlantı başarısız"
                    }
            
            # Yetkilendirme durumunu kontrol et
            is_authorized = await self.client.is_user_authorized()
            
            if is_authorized:
                logger.info("Kullanıcı oturumu açık")
                return {
                    "authorized": True,
                    "message": "Kullanıcı oturumu açık"
                }
            else:
                logger.warning("Kullanıcı oturumu açık değil")
                return {
                    "authorized": False,
                    "message": "Kullanıcı oturumu açık değil"
                }
                
        except Exception as e:
            logger.error(f"Yetkilendirme kontrolü sırasında hata: {str(e)}")
            return {
                "authorized": False,
                "message": f"Yetkilendirme kontrolü sırasında hata: {str(e)}"
            }
    
    async def _authorize_user(self):
        """Kullanıcıyı yetkilendir."""
        try:
            if not self.client:
                logger.error("Client nesnesi oluşturulmamış")
                return {
                    "success": False,
                    "message": "Client nesnesi oluşturulmamış"
                }
            
            if not self.client.is_connected():
                logger.warning("Client bağlı değil, yeniden bağlanılıyor...")
                await self.client.connect()
                
                if not self.client.is_connected():
                    logger.error("Yeniden bağlantı başarısız")
                    return {
                        "success": False,
                        "message": "Yeniden bağlantı başarısız"
                    }
            
            # Telefon numarasını al
            phone = os.getenv("PHONE", None)
            if not phone:
                logger.error("Telefon numarası tanımlanmamış, manuel yetkilendirme gerekli")
                return {
                    "success": False,
                    "message": "Telefon numarası tanımlanmamış, manuel yetkilendirme gerekli"
                }
            
            logger.info(f"Telefon numarası: {phone}")
            
            try:
                # Doğrulama kodu gönder
                logger.info(f"Doğrulama kodu gönderiliyor: {phone}")
                await self.client.send_code_request(phone)
                
                # Kodu al
                verification_code = input("Telegram'dan gelen doğrulama kodunu girin: ")
                
                # Giriş yap
                logger.info("Doğrulama kodu ile giriş yapılıyor...")
                user = await self.client.sign_in(phone, verification_code)
                
                logger.info(f"Giriş başarılı: {user.first_name} (ID: {user.id})")
                return {
                    "success": True,
                    "message": f"Giriş başarılı: {user.first_name} (ID: {user.id})"
                }
                
            except errors.SessionPasswordNeededError:
                # 2FA aktif
                logger.info("İki faktörlü kimlik doğrulama (2FA) gerekli")
                
                # Şifreyi al
                password = input("Lütfen iki faktörlü kimlik doğrulama şifrenizi girin: ")
                
                # 2FA ile giriş yap
                user = await self.client.sign_in(password=password)
                
                logger.info(f"2FA ile giriş başarılı: {user.first_name} (ID: {user.id})")
                return {
                    "success": True,
                    "message": f"2FA ile giriş başarılı: {user.first_name} (ID: {user.id})"
                }
                
            except errors.PhoneCodeInvalidError:
                logger.error("Geçersiz doğrulama kodu")
                return {
                    "success": False,
                    "message": "Geçersiz doğrulama kodu"
                }
                
            except Exception as e:
                logger.error(f"Yetkilendirme sırasında hata: {str(e)}")
                return {
                    "success": False,
                    "message": f"Yetkilendirme sırasında hata: {str(e)}"
                }
                
        except Exception as e:
            logger.error(f"Yetkilendirme işlemi sırasında beklenmeyen hata: {str(e)}")
            return {
                "success": False,
                "message": f"Yetkilendirme işlemi sırasında beklenmeyen hata: {str(e)}"
            }
    
    async def _final_connection_check(self):
        """Son bağlantı kontrolünü yap."""
        try:
            if not self.client:
                logger.error("Client nesnesi oluşturulmamış")
                return {
                    "success": False,
                    "message": "Client nesnesi oluşturulmamış"
                }
            
            if not self.client.is_connected():
                logger.warning("Client bağlı değil, yeniden bağlanılıyor...")
                await self.client.connect()
                
                if not self.client.is_connected():
                    logger.error("Yeniden bağlantı başarısız")
                    return {
                        "success": False,
                        "message": "Yeniden bağlantı başarısız"
                    }
            
            # Yetkilendirme durumunu kontrol et
            is_authorized = await self.client.is_user_authorized()
            
            if not is_authorized:
                logger.error("Kullanıcı oturumu açık değil")
                return {
                    "success": False,
                    "message": "Kullanıcı oturumu açık değil"
                }
            
            # get_me ile ping testi
            try:
                me = await self.client.get_me()
                if me:
                    logger.info(f"Ping testi başarılı: {me.first_name} (ID: {me.id})")
                    return {
                        "success": True,
                        "message": "Ping testi başarılı",
                        "user_info": {
                            "id": me.id,
                            "first_name": me.first_name,
                            "username": me.username if hasattr(me, "username") else None
                        }
                    }
                else:
                    logger.error("Ping testi başarısız: get_me() None döndürdü")
                    return {
                        "success": False,
                        "message": "Ping testi başarısız: get_me() None döndürdü"
                    }
            except Exception as e:
                logger.error(f"Ping testi sırasında hata: {str(e)}")
                return {
                    "success": False,
                    "message": f"Ping testi sırasında hata: {str(e)}"
                }
                
        except Exception as e:
            logger.error(f"Son bağlantı kontrolü sırasında hata: {str(e)}")
            return {
                "success": False,
                "message": f"Son bağlantı kontrolü sırasında hata: {str(e)}"
            }

    async def update_env_file(self, new_session_name=None):
        """Oturum adını .env dosyasında güncelle."""
        if not new_session_name:
            new_session_name = self.original_session_name
            
        try:
            # .env dosyasını oku
            env_path = os.path.join(BASE_DIR, ".env")
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    content = f.read()
                
                # SESSION_NAME değerini güncelle
                import re
                pattern = r"(SESSION_NAME=)([^\r\n]*)"
                replacement = f"\\1{new_session_name}"
                new_content = re.sub(pattern, replacement, content)
                
                # .env dosyasını yaz
                with open(env_path, "w") as f:
                    f.write(new_content)
                    
                logger.info(f".env dosyası güncellendi, yeni oturum adı: {new_session_name}")
                return True
            else:
                logger.warning(".env dosyası bulunamadı")
                return False
        except Exception as e:
            logger.error(f".env dosyası güncellenirken hata: {str(e)}")
            return False
    
    async def cleanup(self):
        """Bağlantıyı temizle."""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            logger.info("Bağlantı kapatıldı")

async def main():
    """Ana fonksiyon."""
    parser = argparse.ArgumentParser(description="Telegram bağlantı sorunlarını düzelt")
    parser.add_argument("--new-session", action="store_true", help="Yeni oturum oluştur")
    parser.add_argument("--env-update", action="store_true", help=".env dosyasını güncelle")
    args = parser.parse_args()
    
    fixer = TelegramConnectionFixer()
    try:
        result = await fixer.fix_connection(force_new_session=args.new_session)
        
        print("\n" + "="*50)
        print(" Telegram Bağlantı Düzeltici Sonuçları ")
        print("="*50)
        
        # Sonucu JSON formatında ekrana yazdır
        print(f"Başarı: {'Evet' if result['success'] else 'Hayır'}")
        print(f"Mesaj: {result['message']}")
        print("\nTespit Edilen Sorunlar:")
        for issue, status in result["issues"].items():
            print(f"  {issue}: {'Evet' if status else 'Hayır'}")
        
        # Eğer yeni oturum oluşturulmuşsa ve --env-update parametresi verilmişse .env dosyasını güncelle
        if args.env_update and result["success"] and fixer.original_session_name:
            await fixer.update_env_file(fixer.original_session_name)
            print(f"\n.env dosyası güncellendi, yeni oturum adı: {fixer.original_session_name}")
            
        print("\nİŞLEM TAMAMLANDI!")
        print("="*50)
        
        if not result["success"]:
            sys.exit(1)
    except Exception as e:
        logger.error(f"Bağlantı düzeltici sırasında beklenmeyen hata: {str(e)}")
        sys.exit(1)
    finally:
        await fixer.cleanup()

if __name__ == "__main__":
    import argparse
    asyncio.run(main())
