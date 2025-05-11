#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
# ============================================================================ #
# Dosya: service_starter.py
# Yol: /Users/siyahkare/code/telegram-bot/app/service_starter.py
# İşlev: Telegram bot servislerini başlatma ve yönetme
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import sys
import time
import asyncio
import logging
import signal
import traceback
from datetime import datetime, timedelta
from pathlib import Path

# Çevre değişkenlerini yükle
from dotenv import load_dotenv
load_dotenv()

# Bot dizinini ekle
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.append(parent_dir)

# Gerekli modülleri import et
try:
    from app.config import Config
    from app.service_manager import ServiceManager, ServiceStatus
    from app.utils.logger_setup import setup_logger
    from app.utils.postgres_db import setup_postgres_db
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
except ImportError as e:
    print(f"Gerekli modüller yüklenemedi: {str(e)}")
    print("Lütfen şu komutla gerekli paketleri yükleyin:")
    print("pip install -r requirements.txt")
    sys.exit(1)

# Logger ayarları
logger = setup_logger()

# Renkli konsol çıktısı için
try:
    from colorama import init, Fore, Style
    init()  # Colorama'yı başlat
    
    def colored(text, color):
        return color + text + Style.RESET_ALL
        
except ImportError:
    def colored(text, color):
        return text

class ServiceStarter:
    """
    Bot servislerini başlatma ve yönetme sınıfı
    """
    
    def __init__(self):
        """
        ServiceStarter sınıfının başlatıcısı
        """
        self.config = None
        self.client = None
        self.db = None
        self.service_manager = None
        self.shutdown_event = asyncio.Event()
        self.session_dir = os.path.join(parent_dir, "session")
        
        # Oturum dizini kontrolü
        os.makedirs(self.session_dir, exist_ok=True)
        
        # Log dizini kontrolü
        logs_dir = os.path.join(parent_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Signal handler'ları ekle
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("ServiceStarter başlatıldı")
    
    def _signal_handler(self, sig, frame):
        """Sinyal işleyici"""
        logger.info(f"Sinyal alındı: {sig}. Bot kapatılıyor...")
        self.shutdown_event.set()
    
    async def setup(self):
        """
        Bot için gerekli yapılandırmaları yükle
        """
        try:
            logger.info("Bot yapılandırması yükleniyor...")
            
            # Çevre değişkenlerinden bir yapılandırma sözlüğü oluştur
            config_dict = {
                'api_id': os.getenv('API_ID'),
                'api_hash': os.getenv('API_HASH'),
                'database_url': os.getenv('DATABASE_URL'),
                'bot_token': os.getenv('BOT_TOKEN'),
                'message_batch_size': int(os.getenv('MESSAGE_BATCH_SIZE', 10)),
                'message_batch_interval': int(os.getenv('MESSAGE_BATCH_INTERVAL', 30))
            }
            
            # Config'i oluştur
            self.config = Config(config_dict)
            logger.info("Yapılandırma yüklendi")
            
            # PostgreSQL veritabanını kur
            logger.info("PostgreSQL veritabanına bağlanılıyor...")
            self.db = setup_postgres_db()
            if not self.db or not hasattr(self.db, 'connected') or not self.db.connected:
                logger.error("PostgreSQL veritabanı bağlantısı kurulamadı. Dummy DB ile devam ediliyor.")
                from app.test_services import DatabaseMock
                self.db = DatabaseMock()
            
            # Telegram istemcisini oluştur
            logger.info("Telegram istemcisi başlatılıyor...")
            
            # Oturum dosyası yolu
            session_file = os.path.join(self.session_dir, "session_v140")
            logger.info(f"Kullanılan oturum dosyası: {session_file}")
            
            # İstemciyi oluştur
            self.client = TelegramClient(
                session_file,
                self.config.get('api_id'), 
                self.config.get('api_hash')
            )
            
            # Oturum aç
            await self.client.start()
            
            if not await self.client.is_user_authorized():
                logger.info("Kullanıcı oturumu bulunamadı. Lütfen telefon numarası ile giriş yapın.")
                phone = input("Telefon numarası (+905xxxxxxxxx): ")
                await self.client.send_code_request(phone)
                code = input("Telegram'dan aldığınız kodu girin: ")
                
                try:
                    await self.client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    password = input("İki faktörlü kimlik doğrulama şifrenizi girin: ")
                    await self.client.sign_in(password=password)
            
            # Botun bağlı olduğunu göster
            me = await self.client.get_me()
            logger.info(f"Bağlantı başarılı: {me.first_name} (@{me.username})")
            
            # ServiceManager'ı oluştur
            self.service_manager = ServiceManager(self.config, self.db, self.client)
            
            return True
            
        except Exception as e:
            logger.error(f"Bot ayarlanırken hata oluştu: {str(e)}", exc_info=True)
            return False
            
    async def register_services(self):
        """
        Bot için servisleri kaydet
        """
        try:
            if not self.service_manager:
                logger.error("ServiceManager oluşturulmamış!")
                return False
                
            logger.info("Servisler kaydediliyor...")
            
            # Servisleri doğrudan oluşturup kaydedelim (sınıf kaydı yerine)
            stop_event = self.shutdown_event
            
            # EventService'i oluştur ve kaydet
            try:
                from app.services.event_service import EventService
                event_service = EventService(
                    client=self.client,
                    config=self.config,
                    db=self.db,
                    stop_event=stop_event
                )
                self.service_manager.register_service(event_service)
                logger.info(f"EventService başarıyla kaydedildi")
            except ImportError:
                logger.error(f"EventService modülü bulunamadı")
                return False
                
            # Diğer servisleri oluştur ve kaydet - bu yaklaşım, servis bulunamadı hatalarını önler
            service_classes = [
                ("message", "app.services.message_service", "MessageService", ["event"]),
                ("group", "app.services.group_service", "GroupService", ["event"]),
                ("user", "app.services.user_service", "UserService", ["event", "group"]),
                ("error", "app.services.analytics.error_service", "ErrorService", ["event"]),
                ("reply", "app.services.messaging.reply_service", "ReplyService", ["event", "message"])
            ]
            
            for service_name, module_path, class_name, dependencies in service_classes:
                try:
                    # Dinamik olarak modülü ve sınıfı import et
                    module = __import__(module_path, fromlist=[class_name])
                    service_class = getattr(module, class_name)
                    
                    # Servisi oluştur
                    service = service_class(
                        client=self.client, 
                        config=self.config, 
                        db=self.db, 
                        stop_event=stop_event
                    )
                    
                    # Servisi kaydet
                    self.service_manager.register_service(service, dependencies=dependencies)
                    logger.info(f"{class_name} başarıyla kaydedildi")
                    
                except ImportError:
                    logger.warning(f"{module_path}.{class_name} modülü bulunamadı, bu servis atlanıyor")
                except AttributeError:
                    logger.warning(f"{class_name} sınıfı {module_path} modülünde bulunamadı, bu servis atlanıyor")
                except Exception as e:
                    logger.error(f"{class_name} servisi oluşturulurken hata: {str(e)}")
            
            # Servis bağımlılıklarını kontrol et
            await self.service_manager.dependency_check(print_graph=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Servisler kaydedilirken hata oluştu: {str(e)}", exc_info=True)
            return False
            
    async def start_services(self):
        """
        Bot servislerini başlat
        """
        try:
            if not self.service_manager:
                logger.error("ServiceManager oluşturulmamış!")
                return False
                
            logger.info("Servisler başlatılıyor...")
            
            # Servisleri başlat
            success = await self.service_manager.start_all_services()
            
            if success:
                logger.info("Tüm servisler başarıyla başlatıldı!")
                
                # Servis durumlarını göster
                statuses = self.service_manager.get_all_service_statuses()
                for service_name, status in statuses.items():
                    status_color = Fore.GREEN if status == ServiceStatus.RUNNING else Fore.RED
                    logger.info(f"Servis: {service_name}, Durum: {colored(str(status), status_color)}")
                
                return True
            else:
                logger.error("Servisler başlatılamadı!")
                return False
                
        except Exception as e:
            logger.error(f"Servisler başlatılırken hata oluştu: {str(e)}", exc_info=True)
            return False
    
    async def start_console(self):
        """
        Konsol arayüzünü başlat
        """
        try:
            print(colored("\nTelegram Bot - Servis Yöneticisi", Fore.CYAN))
            print(colored("==============================", Fore.CYAN))
            print("Kullanılabilir komutlar:")
            print(colored("  help, h, ?", Fore.YELLOW) + " - Bu yardım mesajını göster")
            print(colored("  status, s", Fore.YELLOW) + " - Servis durumlarını göster")
            print(colored("  restart <servis_adı>", Fore.YELLOW) + " - Belirtilen servisi yeniden başlat")
            print(colored("  stop <servis_adı>", Fore.YELLOW) + " - Belirtilen servisi durdur")
            print(colored("  start <servis_adı>", Fore.YELLOW) + " - Belirtilen servisi başlat")
            print(colored("  list, l", Fore.YELLOW) + " - Tüm servisleri listele")
            print(colored("  stats", Fore.YELLOW) + " - Servis istatistiklerini göster")
            print(colored("  exit, quit, q", Fore.YELLOW) + " - Botu kapat ve çık")
            
            while not self.shutdown_event.is_set():
                try:
                    # Konsol girişini non-blocking bekle
                    command = await asyncio.wait_for(
                        self._async_input("\n>>> "), 
                        timeout=0.5
                    )
                    
                    if not command:
                        continue
                    
                    # Komutu işle
                    await self._process_command(command)
                    
                except asyncio.TimeoutError:
                    # Timeout, bu normal ve beklenen
                    await asyncio.sleep(0.1)
                    continue
                except asyncio.CancelledError:
                    logger.info("Konsol arayüzü iptal edildi")
                    break
                except Exception as e:
                    logger.error(f"Komut işlenirken hata: {str(e)}", exc_info=True)
        except Exception as e:
            logger.error(f"Konsol arayüzü başlatılırken hata: {str(e)}", exc_info=True)
    
    async def _async_input(self, prompt):
        """Asenkron giriş okuma"""
        # Standart input'un asenkron versiyonu
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input(prompt))
    
    async def _process_command(self, command):
        """Komutu işle"""
        try:
            command = command.strip().lower()
            parts = command.split()
            
            if not parts:
                return
                
            cmd = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd in ["exit", "quit", "q"]:
                # Botu kapat
                print(colored("Bot kapatılıyor...", Fore.YELLOW))
                self.shutdown_event.set()
                
            elif cmd in ["help", "h", "?"]:
                # Yardım göster
                print(colored("\nKullanılabilir komutlar:", Fore.CYAN))
                print(colored("  help, h, ?", Fore.YELLOW) + " - Bu yardım mesajını göster")
                print(colored("  status, s", Fore.YELLOW) + " - Servis durumlarını göster")
                print(colored("  restart <servis_adı>", Fore.YELLOW) + " - Belirtilen servisi yeniden başlat")
                print(colored("  stop <servis_adı>", Fore.YELLOW) + " - Belirtilen servisi durdur")
                print(colored("  start <servis_adı>", Fore.YELLOW) + " - Belirtilen servisi başlat")
                print(colored("  list, l", Fore.YELLOW) + " - Tüm servisleri listele")
                print(colored("  stats", Fore.YELLOW) + " - Servis istatistiklerini göster")
                print(colored("  exit, quit, q", Fore.YELLOW) + " - Botu kapat ve çık")
                
            elif cmd in ["status", "s"]:
                # Servis durumlarını göster
                print(colored("\nServis Durumları:", Fore.CYAN))
                statuses = self.service_manager.get_all_service_statuses()
                for service_name, status in statuses.items():
                    status_color = Fore.GREEN if status == ServiceStatus.RUNNING else Fore.RED
                    print(f"  {service_name}: {colored(str(status), status_color)}")
                
            elif cmd == "restart" and args:
                # Servisi yeniden başlat
                service_name = args[0]
                print(colored(f"\n{service_name} servisi yeniden başlatılıyor...", Fore.YELLOW))
                success = await self.service_manager.restart_service(service_name)
                if success:
                    print(colored(f"{service_name} servisi başarıyla yeniden başlatıldı", Fore.GREEN))
                else:
                    print(colored(f"{service_name} servisi yeniden başlatılamadı", Fore.RED))
                
            elif cmd == "stop" and args:
                # Servisi durdur
                service_name = args[0]
                print(colored(f"\n{service_name} servisi durduruluyor...", Fore.YELLOW))
                success = await self.service_manager.stop_service(service_name)
                if success:
                    print(colored(f"{service_name} servisi başarıyla durduruldu", Fore.GREEN))
                else:
                    print(colored(f"{service_name} servisi durdurulamadı", Fore.RED))
                
            elif cmd == "start" and args:
                # Servisi başlat
                service_name = args[0]
                print(colored(f"\n{service_name} servisi başlatılıyor...", Fore.YELLOW))
                success = await self.service_manager.start_service(service_name)
                if success:
                    print(colored(f"{service_name} servisi başarıyla başlatıldı", Fore.GREEN))
                else:
                    print(colored(f"{service_name} servisi başlatılamadı", Fore.RED))
                
            elif cmd in ["list", "l"]:
                # Tüm servisleri listele
                print(colored("\nKayıtlı Servisler:", Fore.CYAN))
                services = self.service_manager.get_all_services()
                for service_name, service in services.items():
                    print(f"  {service_name}")
                    
            elif cmd == "stats":
                # Servis istatistiklerini göster
                print(colored("\nServis İstatistikleri:", Fore.CYAN))
                services = self.service_manager.get_all_services()
                for service_name, service in services.items():
                    try:
                        status = self.service_manager.get_service_status(service_name)
                        status_color = Fore.GREEN if status == ServiceStatus.RUNNING else Fore.RED
                        print(colored(f"\n{service_name} ({status}):", status_color))
                        
                        # Çalışma süresi
                        uptime = self.service_manager.get_service_uptime(service_name)
                        if uptime:
                            print(f"  Çalışma süresi: {uptime}")
                            
                        # İstatistikler
                        if hasattr(service, 'get_statistics') and callable(service.get_statistics):
                            try:
                                stats = await service.get_statistics()
                                if stats:
                                    for key, value in stats.items():
                                        print(f"  {key}: {value}")
                            except Exception as e:
                                print(colored(f"  İstatistikler alınamadı: {str(e)}", Fore.RED))
                    except Exception as e:
                        print(colored(f"  {service_name} istatistikleri alınamadı: {str(e)}", Fore.RED))
                        
            else:
                print(colored(f"\nBilinmeyen komut: {command}", Fore.RED))
                print("Yardım için 'help' yazın")
                
        except Exception as e:
            print(colored(f"\nKomut işlenirken hata: {str(e)}", Fore.RED))
    
    async def run(self):
        """
        Bot'u çalıştır
        """
        try:
            # Kurulumu yap
            if not await self.setup():
                logger.error("Bot kurulumu yapılamadı, çıkılıyor...")
                return
            
            # Servisleri kaydet
            if not await self.register_services():
                logger.error("Servisler kaydedilemedi, çıkılıyor...")
                return
            
            # Servisleri başlat
            if not await self.start_services():
                logger.error("Servisler başlatılamadı, çıkılıyor...")
                return
            
            # Konsol arayüzünü başlat
            console_task = asyncio.create_task(self.start_console())
            
            # Ana döngü
            try:
                while not self.shutdown_event.is_set():
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info("Bot kapatılıyor...")
            finally:
                # Konsol görevini iptal et
                if not console_task.done():
                    console_task.cancel()
                    try:
                        await console_task
                    except asyncio.CancelledError:
                        pass
                
                # Servisleri durdur
                logger.info("Servisler durduruluyor...")
                await self.service_manager.stop_all_services()
                
                # Telegram istemcisini kapat
                if self.client:
                    await self.client.disconnect()
                    
                logger.info("Bot başarıyla kapatıldı")
                
        except Exception as e:
            logger.error(f"Bot çalışırken hata oluştu: {str(e)}", exc_info=True)
        
def main():
    """
    Ana işlev
    """
    try:
        # Bot başlatıcıyı oluştur
        starter = ServiceStarter()
        
        # Bot'u çalıştır
        asyncio.run(starter.run())
        
    except KeyboardInterrupt:
        print("\nKullanıcı tarafından kesildi")
    except Exception as e:
        print(f"Kritik hata: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 