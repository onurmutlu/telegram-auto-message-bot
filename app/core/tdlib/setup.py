"""
TDLib Kurulum Yardımcısı

TDLib kütüphanesinin kurulumu ve yapılandırılması için yardımcı fonksiyonlar.
"""

import os
import sys
import subprocess
import platform
import logging
from typing import Optional, Dict, Any, List, Tuple

from app.core.logger import get_logger

logger = get_logger(__name__)

def setup_tdlib(
    install_dir: Optional[str] = None,
    build_dir: Optional[str] = None,
    source_dir: Optional[str] = None,
    verbosity: int = 2,
    force_rebuild: bool = False
) -> bool:
    """
    TDLib kütüphanesini kurar ve yapılandırır.
    
    Args:
        install_dir: Kurulum dizini
        build_dir: Derleme dizini
        source_dir: Kaynak kod dizini
        verbosity: Log seviyesi
        force_rebuild: Yeniden derlemeye zorla
        
    Returns:
        bool: Kurulum başarılıysa True
    """
    try:
        logger.info("TDLib kurulumu başlatılıyor...")
        
        # Platformu kontrol et
        system = platform.system().lower()
        if system not in ["linux", "darwin", "windows"]:
            logger.error(f"Desteklenmeyen platform: {system}")
            return False
            
        # Dizinleri yapılandır
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        if not install_dir:
            install_dir = os.path.join(base_dir, "tdlib")
        
        if not build_dir:
            build_dir = os.path.join(install_dir, "build")
            
        if not source_dir:
            source_dir = os.path.join(install_dir, "td")
            
        os.makedirs(install_dir, exist_ok=True)
        
        # TDLib zaten var mı kontrol et
        tdlib_path = _find_tdlib()
        if tdlib_path and not force_rebuild:
            logger.info(f"TDLib zaten kurulu: {tdlib_path}")
            return True
        
        # TDLib kaynağını indir
        if not os.path.exists(source_dir) or force_rebuild:
            if not _clone_tdlib(source_dir, force_rebuild):
                return False
                
        # TDLib'i derle
        if not _build_tdlib(source_dir, build_dir, install_dir, system):
            return False
            
        # Kurulumu doğrula
        tdlib_path = _find_tdlib()
        if tdlib_path:
            logger.info(f"TDLib başarıyla kuruldu: {tdlib_path}")
            return True
        else:
            logger.error("TDLib kurulumu doğrulanamadı")
            return False
            
    except Exception as e:
        logger.exception(f"TDLib kurulum hatası: {str(e)}")
        return False
        
def _find_tdlib() -> Optional[str]:
    """
    Sistemde TDLib kütüphanesini arar.
    
    Returns:
        Optional[str]: TDLib kütüphanesi yolu
    """
    try:
        from ctypes.util import find_library
        
        # Platformu kontrol et
        system = platform.system().lower()
        
        # Platforma göre kütüphane adını belirle
        if system == "linux":
            lib_names = ["libtdjson.so", "libtdjson.so.1.8.3"]
        elif system == "darwin":
            lib_names = ["libtdjson.dylib", "tdjson", "libtdjson.1.8.3.dylib"]
        elif system == "windows":
            lib_names = ["tdjson.dll", "tdjson64.dll", "tdjson32.dll"]
        else:
            lib_names = ["tdjson"]
            
        # Kütüphaneyi ara
        for name in lib_names:
            lib_path = find_library(name)
            if lib_path:
                return lib_path
                
        # Yüklü kütüphane bulunamadı
        return None
        
    except Exception as e:
        logger.exception(f"TDLib arama hatası: {str(e)}")
        return None
        
def _clone_tdlib(source_dir: str, force_rebuild: bool) -> bool:
    """
    TDLib kaynak kodunu Git üzerinden indirir.
    
    Args:
        source_dir: İndirme dizini
        force_rebuild: Mevcut kodu sil ve yeniden indir
        
    Returns:
        bool: İndirme başarılıysa True
    """
    try:
        logger.info(f"TDLib kaynağı indiriliyor: {source_dir}")
        
        # Dizin zaten varsa ve yeniden indirilmeyecekse
        if os.path.exists(source_dir) and not force_rebuild:
            logger.info(f"TDLib kaynağı zaten var: {source_dir}")
            return True
            
        # Mevcut dizini sil
        if os.path.exists(source_dir) and force_rebuild:
            import shutil
            logger.info(f"Mevcut TDLib kaynağı siliniyor: {source_dir}")
            shutil.rmtree(source_dir)
            
        # Git komutunu çalıştır
        git_cmd = ["git", "clone", "https://github.com/tdlib/td.git", source_dir]
        process = subprocess.run(git_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if process.returncode != 0:
            logger.error(f"Git klonlama hatası: {process.stderr.decode('utf-8')}")
            return False
            
        logger.info(f"TDLib kaynağı başarıyla indirildi: {source_dir}")
        return True
        
    except Exception as e:
        logger.exception(f"TDLib indirme hatası: {str(e)}")
        return False
        
def _build_tdlib(source_dir: str, build_dir: str, install_dir: str, system: str) -> bool:
    """
    TDLib kütüphanesini derler.
    
    Args:
        source_dir: Kaynak kod dizini
        build_dir: Derleme dizini
        install_dir: Kurulum dizini
        system: Platform adı
        
    Returns:
        bool: Derleme başarılıysa True
    """
    try:
        logger.info(f"TDLib derleniyor: {build_dir}")
        
        # Derleme dizini oluştur
        os.makedirs(build_dir, exist_ok=True)
        
        # Önceki derleme dizinindeki dosyaları temizle
        for item in os.listdir(build_dir):
            item_path = os.path.join(build_dir, item)
            if os.path.isfile(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                import shutil
                shutil.rmtree(item_path)
                
        # Platforma göre derleme komutları
        if system == "linux" or system == "darwin":
            # Linux ve macOS için derleme
            build_commands = [
                ["cmake", "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_INSTALL_PREFIX:PATH={install_dir}", ".."],
                ["cmake", "--build", ".", "--target", "install", "-j", str(os.cpu_count() or 1)]
            ]
        elif system == "windows":
            # Windows için derleme
            build_commands = [
                ["cmake", "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_INSTALL_PREFIX:PATH={install_dir}", ".."],
                ["cmake", "--build", ".", "--config", "Release", "--target", "install", "-j", str(os.cpu_count() or 1)]
            ]
        else:
            logger.error(f"Desteklenmeyen platform: {system}")
            return False
            
        # Derleme dizinine geç
        original_dir = os.getcwd()
        os.chdir(build_dir)
        
        try:
            # Derleme komutlarını çalıştır
            for cmd in build_commands:
                logger.info(f"Çalıştırılıyor: {' '.join(cmd)}")
                process = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                if process.returncode != 0:
                    logger.error(f"Derleme hatası: {process.stderr.decode('utf-8')}")
                    return False
                    
            logger.info(f"TDLib başarıyla derlendi: {install_dir}")
            return True
            
        finally:
            # Orijinal dizine geri dön
            os.chdir(original_dir)
            
    except Exception as e:
        logger.exception(f"TDLib derleme hatası: {str(e)}")
        return False
        
def check_tdlib_version() -> Optional[str]:
    """
    Kurulu TDLib sürümünü kontrol eder.
    
    Returns:
        Optional[str]: TDLib sürümü
    """
    try:
        # TDLib sürümünü getiren işlem
        from ctypes.util import find_library
        from ctypes import CDLL, c_char_p, c_double, c_int, c_void_p
        
        # TDLib kütüphanesini bul
        tdjson_path = _find_tdlib()
        if not tdjson_path:
            logger.error("TDLib kütüphanesi bulunamadı")
            return None
            
        # Kütüphaneyi yükle
        tdjson = CDLL(tdjson_path)
        
        # Sürüm fonksiyonunu yapılandır
        td_json_client_create = tdjson.td_json_client_create
        td_json_client_create.restype = c_void_p
        td_json_client_create.argtypes = []
        
        td_json_client_execute = tdjson.td_json_client_execute
        td_json_client_execute.restype = c_char_p
        td_json_client_execute.argtypes = [c_void_p, c_char_p]
        
        td_json_client_destroy = tdjson.td_json_client_destroy
        td_json_client_destroy.restype = None
        td_json_client_destroy.argtypes = [c_void_p]
        
        # İstemci oluştur
        client = td_json_client_create()
        
        # Sürüm komutunu gönder
        import json
        request = json.dumps({"@type": "getOption", "name": "version"}).encode('utf-8')
        result_json = td_json_client_execute(client, request)
        
        # İstemciyi temizle
        td_json_client_destroy(client)
        
        # Yanıtı işle
        if result_json:
            result = json.loads(result_json.decode('utf-8'))
            version = result.get('value', {}).get('value', 'Unknown')
            return version
            
        return None
        
    except Exception as e:
        logger.exception(f"TDLib sürüm kontrolü hatası: {str(e)}")
        return None 