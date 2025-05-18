#!/usr/bin/env python3
"""
Telegram bağlantı durumunu test eder ve gerekirse yeniden bağlanır.
Bu araç:
1. Mevcut bağlantı durumunu kontrol eder
2. Telethon oturum uyumluluğunu kontrol eder
3. Gerekirse yeni oturum oluşturur
4. Bağlantıyı zorlar ve oturum açar
5. İstek üzerine .env dosyasını günceller

Kullanım:
    python reconnect_bot.py [--force-new-session] [--update-env]
"""

import os
import sys
import asyncio
import argparse
import logging
import time
import shutil
from pathlib import Path

# Ana dizinin yolunu ekleyin
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(BASE_DIR, "reconnect.log"))
    ]
)

logger = logging.getLogger(__name__)

# Ortam değişkenlerini yükleyin (eğer dotenv yüklüyse)
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    logger.warning("python-dotenv yüklü değil, .env dosyasından değişkenler yüklenemeyecek")

class TelegramReconnector:
    """Telegram bot bağlantı ve oturum yöneticisi."""
    
    def __init__(self):
        """Başlatıcı."""
        # Gerekli modülleri import et
        try:
            from app.core.config import settings
            from telethon import TelegramClient, errors
            self.settings = settings
            self.TelegramClient = TelegramClient
            self.errors = errors
        except ImportError as e:
            logger.error(f"Gerekli modüller yüklenemedi: {e}")
            sys.exit(1)
            
        # Oturum bilgileri
        self.session_name = os.getenv("SESSION_NAME", "telegram_session")
        self.api_id = os.getenv("API_ID") or self.settings.API_ID
        self.api_hash = os.getenv("API_HASH") or self.settings.API_HASH
        self.phone = os.getenv("PHONE")
        
        # API_HASH'i düzgün şekilde işle
        if hasattr(self.api_hash, 'get_secret_value'):
            self.api_hash = self.api_hash.get_secret_value()
        
        # Oturum dizini
        if hasattr(self.settings, "SESSIONS_DIR"):
            self.session_dir = self.settings.SESSIONS_DIR
        else:
            self.session_dir = os.path.join(BASE_DIR, "session")
            
        # Oturum dosyası yolu
        self.session_path = os.path.join(self.session_dir, f"{self.session_name}.session")
        
        # Client nesnesi
        self.client = None
        
        logger.info(f"TelegramReconnector başlatıldı")
        logger.info(f"Oturum: {self.session_name}")
        logger.info(f"Oturum dosyası: {self.session_path}")
        
    async def check_session_compatibility(self):
        """Oturum dosyasını kontrol et ve Telethon sürüm uyumluluğunu doğrula."""
        logger.info(f"Oturum dosyası kontrolü yapılıyor: {self.session_path}")
        
        result = {
            "exists": False,
            "corrupted": False,
            "version_mismatch": False,
            "column_count": 0
        }
        
        # Oturum dosyası var mı?
        if not os.path.exists(self.session_path):
            logger.warning("Oturum dosyası bulunamadı")
            return result
        
        result["exists"] = True
        
        # SQLite veritabanı mı?
        try:
            import sqlite3
            
            # Dosyanın başlangıcını kontrol et
            with open(self.session_path, 'rb') as f:
                header = f.read(100)
                if not header.startswith(b'SQLite'):
                    logger.warning("Dosya SQLite veritabanı değil")
                    result["corrupted"] = True
                    return result
            
            # SQLite bağlantısı kur
            conn = sqlite3.connect(self.session_path)
            cursor = conn.cursor()
            
            # Tabloları kontrol et
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            table_names = [table[0] for table in tables]
            
            logger.info(f"Tablolar: {', '.join(table_names)}")
            
            if "sessions" not in table_names:
                logger.warning("sessions tablosu bulunamadı")
                result["corrupted"] = True
                conn.close()
                return result
            
            # sessions tablosunun yapısını kontrol et
            cursor.execute("PRAGMA table_info(sessions)")
            columns = cursor.fetchall()
            
            # Sütun sayısını kontrol et
            column_count = len(columns)
            column_names = [col[1] for col in columns]
            
            logger.info(f"sessions tablosunda {column_count} sütun bulundu: {', '.join(column_names)}")
            result["column_count"] = column_count
            
            # Telethon 1.40.0 için 5 sütun olmalı
            if column_count != 5:
                logger.warning(f"Telethon sürüm uyumsuzluğu tespit edildi: {column_count} sütun (5 olması gerekiyor)")
                result["version_mismatch"] = True
            
            # Bağlantıyı kapat
            conn.close()
            
        except Exception as e:
            logger.error(f"Oturum dosyası kontrolü sırasında hata: {e}")
            result["corrupted"] = True
            
        return result
    
    async def create_new_session(self):
        """Yeni bir oturum dosyası oluştur."""
        logger.info("Yeni oturum dosyası oluşturuluyor...")
        
        # Eski oturum dosyasını yedekle
        if os.path.exists(self.session_path):
            backup_path = f"{self.session_path}.backup.{int(time.time())}"
            try:
                shutil.copy2(self.session_path, backup_path)
                logger.info(f"Eski oturum dosyası yedeklendi: {backup_path}")
                
                # Eski dosyayı sil
                os.remove(self.session_path)
                logger.info("Eski oturum dosyası silindi")
            except Exception as e:
                logger.error(f"Oturum dosyası yedeklenirken hata: {e}")
        
        # Yeni bir oturum adı oluştur
        new_session_name = f"{self.session_name}_new_{int(time.time())}"
        new_session_path = os.path.join(self.session_dir, f"{new_session_name}.session")
        
        # Oturum klasörünü oluştur
        os.makedirs(self.session_dir, exist_ok=True)
        
        # TelegramClient oluştur
        try:
            # Telethon sürüm bilgisi
            import telethon
            logger.info(f"Telethon sürümü: {telethon.__version__}")
            
            # Yeni client oluştur
            client = self.TelegramClient(
                new_session_path,
                self.api_id,
                self.api_hash
            )
            
            # Bağlantı kur
            await client.connect()
            
            if client.is_connected():
                logger.info("Yeni oturum için bağlantı başarılı")
                
                # Bağlantıyı kapat
                await client.disconnect()
                
                # Oturum bilgilerini güncelle
                self.session_name = new_session_name
                self.session_path = new_session_path
                
                return {
                    "success": True,
                    "session_name": new_session_name,
                    "session_path": new_session_path
                }
            else:
                logger.error("Yeni oturum için bağlantı kurulamadı")
                return {
                    "success": False,
                    "error": "Bağlantı kurulamadı"
                }
                
        except Exception as e:
            logger.error(f"Yeni oturum oluşturulurken hata: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def force_connect(self):
        """Telethon bağlantısını zorla ve oturum durumunu kontrol et."""
        logger.info("Bağlantı zorlanıyor...")
        
        # Önce oturum uyumluluğunu kontrol et
        session_status = await self.check_session_compatibility()
        
        # Oturum sorunu varsa düzelt
        if not session_status["exists"] or session_status["corrupted"] or session_status["version_mismatch"]:
            logger.warning("Oturum sorunu tespit edildi, yeni oturum oluşturuluyor...")
            
            if not session_status["exists"]:
                logger.warning("Oturum dosyası yok")
            elif session_status["corrupted"]:
                logger.warning("Oturum dosyası bozuk")
            elif session_status["version_mismatch"]:
                logger.warning(f"Oturum sürüm uyumsuzluğu: {session_status['column_count']} sütun (5 olması gerekiyor)")
            
            # Yeni oturum oluştur
            create_result = await self.create_new_session()
            
            if not create_result["success"]:
                logger.error(f"Yeni oturum oluşturulamadı: {create_result.get('error', 'Bilinmeyen hata')}")
                return {
                    "success": False,
                    "connected": False,
                    "authorized": False,
                    "error": f"Yeni oturum oluşturulamadı: {create_result.get('error', 'Bilinmeyen hata')}"
                }
        
        # Client oluştur
        try:
            # Health Service aracılığıyla bağlantı kur
            from app.services.monitoring.health_service import HealthService
            from app.db.session import get_session
            
            # Veritabanı bağlantısı
            db = next(get_session())
            
            # Client oluştur
            self.client = self.TelegramClient(
                self.session_path,
                self.api_id,
                self.api_hash
            )
            
            # Health Service
            health_service = HealthService(client=self.client, service_manager=None, db=db)
            await health_service.initialize()
            
            # Bağlantıyı zorla
            logger.info("Health Service aracılığıyla bağlantı zorlanıyor...")
            result = await health_service.force_connect()
            
            connected = result.get("connected", False)
            authorized = result.get("authorized", False)
            
            if connected:
                logger.info("Bağlantı başarılı!")
                
                if authorized:
                    logger.info(f"Oturum açık: {result.get('first_name', 'Bilinmiyor')} (ID: {result.get('user_id', 'Bilinmiyor')})")
                    return {
                        "success": True,
                        "connected": True,
                        "authorized": True,
                        "user_info": {
                            "id": result.get("user_id"),
                            "first_name": result.get("first_name"),
                            "username": result.get("username")
                        }
                    }
                else:
                    logger.warning("Bağlantı başarılı fakat oturum açık değil")
                    
                    # Telefon bilgisi varsa yetkilendirme yap
                    if self.phone:
                        logger.info(f"Telefon numarası ile yetkilendirme yapılıyor: {self.phone}")
                        
                        try:
                            # Doğrulama kodu gönder
                            await self.client.send_code_request(self.phone)
                            
                            # Kodu al
                            verification_code = input("Telegram'dan gelen doğrulama kodunu girin: ")
                            
                            # Giriş yap
                            try:
                                user = await self.client.sign_in(self.phone, verification_code)
                                
                                logger.info(f"Yetkilendirme başarılı: {user.first_name} (ID: {user.id})")
                                
                                return {
                                    "success": True,
                                    "connected": True,
                                    "authorized": True,
                                    "user_info": {
                                        "id": user.id,
                                        "first_name": user.first_name,
                                        "username": user.username if hasattr(user, "username") else None
                                    }
                                }
                            except self.errors.SessionPasswordNeededError:
                                # 2FA gerekli
                                logger.info("İki faktörlü kimlik doğrulama (2FA) gerekli")
                                
                                # Şifreyi al
                                password = input("Lütfen iki faktörlü kimlik doğrulama şifrenizi girin: ")
                                
                                # 2FA ile giriş yap
                                user = await self.client.sign_in(password=password)
                                
                                logger.info(f"2FA ile giriş başarılı: {user.first_name} (ID: {user.id})")
                                
                                return {
                                    "success": True,
                                    "connected": True,
                                    "authorized": True,
                                    "user_info": {
                                        "id": user.id,
                                        "first_name": user.first_name,
                                        "username": user.username if hasattr(user, "username") else None
                                    }
                                }
                        except Exception as auth_err:
                            logger.error(f"Yetkilendirme hatası: {auth_err}")
                            return {
                                "success": False,
                                "connected": True,
                                "authorized": False,
                                "error": f"Yetkilendirme hatası: {auth_err}"
                            }
                    else:
                        return {
                            "success": False,
                            "connected": True,
                            "authorized": False,
                            "error": "Telefon numarası tanımlı değil, otomatik yetkilendirme yapılamıyor"
                        }
            else:
                logger.error(f"Bağlantı kurulamadı: {result.get('error', 'Bilinmeyen hata')}")
                return {
                    "success": False,
                    "connected": False,
                    "authorized": False,
                    "error": f"Bağlantı kurulamadı: {result.get('error', 'Bilinmeyen hata')}"
                }
                
        except Exception as e:
            logger.error(f"Bağlantı zorlanırken beklenmeyen hata: {e}")
            return {
                "success": False,
                "connected": False,
                "authorized": False,
                "error": f"Beklenmeyen hata: {e}"
            }
        finally:
            # Client bağlantısını kapat
            if self.client and self.client.is_connected():
                await self.client.disconnect()
    
    async def update_env_file(self):
        """Oturum adını .env dosyasında güncelle."""
        logger.info(f".env dosyası güncelleniyor. Yeni oturum adı: {self.session_name}")
        
        try:
            # .env dosyasını oku
            env_path = os.path.join(BASE_DIR, ".env")
            
            if not os.path.exists(env_path):
                logger.warning(".env dosyası bulunamadı")
                return False
            
            with open(env_path, "r") as f:
                content = f.read()
            
            # SESSION_NAME değerini güncelle
            import re
            pattern = r"(SESSION_NAME=)([^\r\n]*)"
            replacement = f"\\1{self.session_name}"
            new_content = re.sub(pattern, replacement, content)
            
            # .env dosyasını yaz
            with open(env_path, "w") as f:
                f.write(new_content)
                
            logger.info(f".env dosyası güncellendi, yeni oturum adı: {self.session_name}")
            return True
        except Exception as e:
            logger.error(f".env dosyası güncellenirken hata: {e}")
            return False

async def main():
    """Ana fonksiyon."""
    parser = argparse.ArgumentParser(description="Telegram bot bağlantısını düzelt")
    parser.add_argument("--force-new-session", action="store_true", help="Yeni oturum oluşturmayı zorla")
    parser.add_argument("--update-env", action="store_true", help=".env dosyasını güncelle")
    args = parser.parse_args()
    
    reconnector = TelegramReconnector()
    
    try:
        # Yeni oturum zorlanmışsa veya oturum kontrolü gerekiyorsa
        if args.force_new_session:
            logger.info("Yeni oturum oluşturma zorlandı")
            session_result = await reconnector.create_new_session()
            
            if not session_result["success"]:
                logger.error(f"Yeni oturum oluşturulamadı: {session_result.get('error', 'Bilinmeyen hata')}")
                return
        
        # Bağlantıyı zorla
        result = await reconnector.force_connect()
        
        print("\n" + "="*50)
        print(" Telegram Bot Bağlantı Sonuçları ")
        print("="*50)
        
        # Sonuçları yazdır
        print(f"Başarı: {'Evet' if result['success'] else 'Hayır'}")
        print(f"Bağlantı: {'Var' if result['connected'] else 'Yok'}")
        print(f"Oturum Açık: {'Evet' if result['authorized'] else 'Hayır'}")
        
        if not result["success"]:
            print(f"Hata: {result.get('error', 'Bilinmeyen hata')}")
        elif "user_info" in result:
            print("\nKullanıcı Bilgileri:")
            for key, value in result["user_info"].items():
                print(f"  {key}: {value}")
        
        # .env güncelleme
        if args.update_env and result["success"]:
            env_updated = await reconnector.update_env_file()
            print(f"\n.env dosyası güncellendi: {'Evet' if env_updated else 'Hayır'}")
        
        print("\nİŞLEM TAMAMLANDI!")
        print("="*50)
        
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    # Windows'ta multiprocessing için gerekli
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Ana döngüyü başlat
    asyncio.run(main())
